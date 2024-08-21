"""This module provides probing functionality to check the status of network devices."""

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
        inventory_recs: List of inventory records to probe.
        timeout: Optional timeout value for the probe command. Defaults to DEFAULT_PROBE_TIMEOUT.
    """
    timeout = timeout or DEFAULT_PROBE_TIMEOUT

    def task_creator(rec: dict, app_cfg: AppConfig):
        """Creates a probe task for the given inventory record.

        Args:
            rec: A dictionary representing an inventory record.
            app_cfg: Application configuration object.

        Returns:
            A probe task configured with the IP address or hostname from the inventory record.
        """
        return probe(rec.get("ipaddr") or rec.get("host"), timeout=timeout, raise_exc=True)

    execute_command(inventory_recs, None, CLI_COMMAND, task_creator)


@cli.command(name=CLI_COMMAND, cls=WithInventoryCommand)
@opt_config_file
@opts_inventory
@opt_timeout
@click.pass_context
def cli_check(ctx: click.Context, **cli_opts) -> None:
    """Probe device for SSH reachablility."""
    exec_probe(ctx.obj["inventory_recs"], timeout=cli_opts["timeout"])
