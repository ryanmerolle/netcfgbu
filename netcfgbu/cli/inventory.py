"""This module handles inventory management for network devices.

This provides CLI commands for listing & building network device inventories.
It interacts with the inventory system to document info about available devices
& their operating systems, as well as to build inventory files from config.
"""

from textwrap import indent

import click
from tabulate import tabulate

from netcfgbu.config_model import AppConfig
from netcfgbu.inventory import build

from .report import LN_SEP, SPACES_4
from .root import (
    WithConfigCommand,
    WithInventoryCommand,
    cli,
    get_spec_nameorfirst,
    opt_config_file,
    opts_inventory,
)

# -----------------------------------------------------------------------------
#                                Inventory Commands
# -----------------------------------------------------------------------------


@cli.group(name="inventory")
def cli_inventory() -> None:
    """Group of commands for managing device inventory.

    This command group provides various subcommands that allow users to view,
    build, and manage the network device inventory.
    """
    pass  # pragma: no cover


@cli_inventory.command("list", cls=WithInventoryCommand)
@opt_config_file
@opts_inventory
@click.option("--brief", "-b", is_flag=True)
@click.pass_context
def cli_inventory_list(ctx: click.Context, **cli_opts):
    """List network devices in the inventory.

    This command displays a summary of devices in the inventory, grouped by
    operating system, & optionally shows detailed information for each device.

    Args:
        ctx: Click context object containing inventory records and other shared data.
        **cli_opts: Command line options including:
            brief: If True, only shows the summary & not detailed device information.
    """
    inventory_recs = ctx.obj["inventory_recs"]
    inventory_tabular_data = []
    os_name_counter = {}
    for rec in inventory_recs:
        os_name = rec.get("os_name")
        if os_name:
            os_name_counter[os_name] = os_name_counter.get(os_name, 0) + 1

    inventory_tabular_data = sorted(os_name_counter.items())
    inventory_tabular_data.append(("-" * 7, "-" * 5))
    inventory_tabular_data.append(("TOTAL", len(inventory_recs)))

    os_name_table = indent(
        tabulate(
            headers=["os_name", "count"],
            tabular_data=inventory_tabular_data,
            tablefmt="pretty",
        ),
        SPACES_4,
    )

    print(LN_SEP)
    print("SUMMARY:")
    print(os_name_table)

    if cli_opts["brief"] is True:
        return  # pragma: no cover

    field_names = inventory_recs[0].keys()

    print(
        tabulate(
            headers=field_names,
            tabular_data=[rec.values() for rec in inventory_recs],
            tablefmt="pretty",
        )
    )

    print(LN_SEP)


@cli_inventory.command("build", cls=WithConfigCommand)
@opt_config_file
@click.option("--name", "-n", help="inventory name as defined in config file")
@click.option("--brief", is_flag=True)
@click.pass_context
def cli_inventory_build(ctx: click.Context, **cli_opts) -> None:
    """Build the inventory file from configuration.

    Creates an inventory file based on definitions in the netcfgbu configuration file.
    If multiple inventory definitions exist, a specific inventory can be selected using
    the --name option.

    Args:
        ctx: Click context object containing application configuration.
        **cli_opts: Command line options including:
            name: Name of the inventory section defined in the config file.
            brief: Flag for brief output format.

    Raises:
        RuntimeError: If the specified inventory is not defined in the configuration file
                     or if no configuration file is provided.
    """
    app_cfg: AppConfig = ctx.obj["app_cfg"]

    if not (spec := get_spec_nameorfirst(app_cfg.inventory, cli_opts["name"])):
        cfg_opt = ctx.params["config"]
        inv_name = cli_opts["name"]
        inv_name = f"'{inv_name}'" if inv_name else ""
        err_msg = (
            f"Inventory section {inv_name} not defined in configuration file: {cfg_opt.name}"
            if cfg_opt
            else "Configuration file required for use with build subcommand"
        )
        raise RuntimeError(err_msg)

    build(spec)
