#!/usr/bin/env python3.9
"""Retrieve device inventory from Netbox and email or save it as a CSV file.

This script fetches the device inventory from a Netbox system using API credentials
and outputs the data as a CSV file. It supports filtering by site, region, and role,
with configurable environment variables for Netbox settings.

  NETBOX_ADDR: the URL to the NetBox server
      "https://my-netbox-server"

  NETBOX_TOKEN: the NetBox login token
      "e0759aa0d6b4146-from-netbox-f744c4489adfec48f"

The following Environment variables are OPTIONAL:

  NETBOX_INVENTORY_OPTIONS
      Same as the options provided by "--help"
"""

import argparse
import csv
import os
import sys
from collections.abc import Iterator
from functools import lru_cache
from typing import Optional

import requests  # noqa
from urllib3 import disable_warnings  # noqa

CSV_FIELD_NAMES = ["host", "ipaddr", "os_name", "role", "site", "region"]


def rec_to_csv(rec: dict) -> list:
    """Convert a NetBox device record to a list suitable for CSV output.

    Args:
        rec: A dictionary representing a device record from NetBox.

    Returns:
        list: A list of device attributes in the order of CSV_FIELD_NAMES.
    """
    hostname = rec["name"]
    ipaddr = rec["primary_ip"]["address"].split("/")[0]
    platform = rec["platform"]
    os_name = platform["slug"] if platform else "N/A"
    role = rec["device_role"]["slug"]
    site = rec["site"]["slug"]
    region = get_site(site)["region"]["slug"]

    return [hostname, ipaddr, os_name, role, site, region]


def cli() -> argparse.Namespace:
    """Create and parse command-line interface (CLI) options.

    Returns:
        argparse.Namespace: Parsed command-line options.
    """
    options_parser = argparse.ArgumentParser()
    options_parser.add_argument("--site", action="store", help="limit devices to site")
    options_parser.add_argument("--region", action="store", help="limit devices to region")
    options_parser.add_argument("--role", action="append", help="limit devices with role(s)")
    options_parser.add_argument(
        "--exclude-role", action="append", help="exclude devices with role(s)"
    )
    options_parser.add_argument(
        "--exclude-tag", action="append", help="exclude devices with tag(s)"
    )
    options_parser.add_argument(
        "--output",
        type=argparse.FileType("w+"),
        default=sys.stdout,
        help="save inventory to filename",
    )

    nb_env_opts = os.environ.get("NETBOX_INVENTORY_OPTIONS")
    opt_arg = nb_env_opts.split(";") if nb_env_opts else None
    return options_parser.parse_args(opt_arg)


class NetBoxSession(requests.Session):
    """A session for interacting with the NetBox API.

    Attributes:
        url: The base URL of the NetBox instance.
        token: The API token for authentication.
    """

    def __init__(self, url: str, token: str):
        """Initialize the NetBoxSession.

        Args:
            url: The base URL of the NetBox instance.
            token: The API token for authentication.
        """
        super(NetBoxSession, self).__init__()
        self.url = url
        self.headers["authorization"] = f"Token {token}"
        self.verify = False

    def prepare_request(self, request: requests.Request) -> requests.PreparedRequest:
        """Prepare the request by appending the base URL to the request URL.

        Args:
            request: The request object to prepare.

        Returns:
            requests.PreparedRequest: The prepared request object.
        """
        request.url = self.url + request.url
        return super(NetBoxSession, self).prepare_request(request)


NETBOX_SESSION: Optional[NetBoxSession] = None


@lru_cache
def get_site(site_slug: str) -> dict:
    """Retrieve details of a site from NetBox using its slug.

    Args:
        site_slug: The slug of the site.

    Returns:
        dict: The site details as a dictionary.
    """
    res = NETBOX_SESSION.get("/api/dcim/sites/", params={"slug": site_slug})
    res.raise_for_status()
    return res.json()["results"][0]


def create_csv_file(inventory_records: Iterator[dict], cli_opts: argparse.Namespace) -> None:
    """Create a CSV file from inventory records.

    Args:
        inventory_records: An iterator of device records.
        cli_opts: Parsed command-line options, including the output file.
    """
    csv_wr = csv.writer(cli_opts.output)
    csv_wr.writerow(CSV_FIELD_NAMES)

    for rec in inventory_records:
        csv_wr.writerow(rec_to_csv(rec))


def fetch_inventory(cli_opts: argparse.Namespace) -> Iterator[dict]:
    """Fetch the inventory of devices from NetBox based on the provided CLI options.

    Args:
        cli_opts: Parsed command-line options.

    Returns:
        Iterator[dict]: An iterator of filtered device records.
    """
    global NETBOX_SESSION

    try:
        nb_url = os.environ["NETBOX_ADDR"]
        nb_token = os.environ["NETBOX_TOKEN"]
    except KeyError as exc:
        sys.exit(f"ERROR: missing environment variable: {exc.args[0]}")

    NETBOX_SESSION = NetBoxSession(url=nb_url, token=nb_token)

    # Perform a GET on the API URL to obtain the Netbox version
    res = NETBOX_SESSION.get("/api")
    api_ver = tuple(map(int, res.headers["API-Version"].split(".")))
    params = {
        "limit": 0,
        "status": 1,
        "has_primary_ip": "true",
        "exclude": "config_context",
    }

    if api_ver > (2, 6):
        params["status"] = "active"

    if cli_opts.site:
        params["site"] = cli_opts.site

    if cli_opts.region:
        params["region"] = cli_opts.region

    res = NETBOX_SESSION.get("/api/dcim/devices/", params=params)
    if not res.ok:
        sys.exit("FAIL: get inventory: " + res.text)

    body = res.json()
    device_list = body["results"]

    return apply_filters(device_list, cli_opts)


def apply_filters(device_list: list[dict], cli_opts: argparse.Namespace) -> Iterator[dict]:
    """Apply user-provided filters to the device list.

    Args:
        device_list: The list of devices to filter.
        cli_opts: Parsed command-line options.

    Returns:
        Iterator[dict]: The filtered list of devices.
    """
    filter_functions = []

    if cli_opts.role:

        def filter_role(dev_dict: dict) -> bool:
            """Filter to include devices that match the specified roles.

            Args:
                dev_dict (dict): The device record to filter.

            Returns:
                bool: True if the device's role matches the specified roles, False otherwise.
            """
            return dev_dict["device_role"]["slug"] in cli_opts.role

        filter_functions.append(filter_role)

    if cli_opts.exclude_role:

        def filter_ex_role(dev_dict: dict) -> bool:
            """Filter to exclude devices that match the specified roles.

            Args:
                dev_dict (dict): The device record to filter.

            Returns:
                bool: True if the device's role does not match the excluded roles, False otherwise.
            """
            return dev_dict["device_role"]["slug"] not in cli_opts.exclude_role

        filter_functions.append(filter_ex_role)

    if cli_opts.exclude_tag:
        ex_tag_set = set(cli_opts.exclude_tag)

        def filter_ex_tag(dev_dict: dict) -> bool:
            """Filter to exclude devices that have the specified tags.

            Args:
                dev_dict (dict): The device record to filter.

            Returns:
                bool: True if the device does not have any of the excluded tags, False otherwise.
            """
            return not set(dev_dict["tags"]) & ex_tag_set

        filter_functions.append(filter_ex_tag)

    for dev_dict in device_list:
        if all(fn(dev_dict) for fn in filter_functions):
            yield dev_dict


def build_inventory() -> None:
    """Build the inventory by fetching device records and creating a CSV file.

    This function handles CLI parsing, inventory fetching, and CSV file creation.
    """
    cli_opts = cli()
    inventory = fetch_inventory(cli_opts)
    create_csv_file(inventory, cli_opts)


if __name__ == "__main__":
    disable_warnings()
    build_inventory()
