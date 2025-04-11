"""Provides probing functionality to check the status of network devices.

This module contains functions and CLI commands that allow users to test connectivity
to network devices using SSH probes.
"""

import click

from netcfgbu.cli.common import execute_command
from netcfgbu.config_model import AppConfig
from netcfgbu.consts import DEFAULT_PROBE_TIMEOUT
from netcfgbu.probe import probe

from .root import WithInventoryCommand, cli, opt_config_file, opt_timeout, opts_inventory

CLI_COMMAND = "probe"


def exec_probe(inventory_recs: list, timeout=None) -> None:
    """Executes the probe command on the provided inventory records.

    Args:
        inventory_recs (list): List of inventory records to probe.
        timeout (int, optional): Timeout value for the probe command in seconds.
            Defaults to DEFAULT_PROBE_TIMEOUT.

    Returns:
        None
    """
    timeout = timeout or DEFAULT_PROBE_TIMEOUT

    def task_creator(rec: dict, app_cfg: AppConfig):
        """Creates a probe task for the given inventory record.

        Args:
            rec (dict): A dictionary representing an inventory record.
            app_cfg (AppConfig): Application configuration object.

        Returns:
            callable: A probe task configured with the IP address or hostname
                from the inventory record.
        """
        return probe(rec.get("ipaddr") or rec.get("host"), timeout=timeout, raise_exc=True)

    execute_command(inventory_recs, None, CLI_COMMAND, task_creator)


@cli.command(name=CLI_COMMAND, cls=WithInventoryCommand)
@opt_config_file
@opts_inventory
@opt_timeout
@click.pass_context
def cli_check(ctx: click.Context, **cli_opts) -> None:
    """Probe devices for SSH reachability.

    Executes an SSH connection test against each device in the inventory to verify
    connectivity. Reports success or failure for each device.

    Args:
        ctx (click.Context): Click context object containing inventory records.
        **cli_opts: Command line options including timeout.

    Returns:
        None
    """
    exec_probe(ctx.obj["inventory_recs"], timeout=cli_opts["timeout"])
