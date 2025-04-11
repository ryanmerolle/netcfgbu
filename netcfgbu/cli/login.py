"""CLI command module for testing SSH logins to devices.

This module provides functionality to verify SSH login capabilities to network
devices defined in the inventory.

Functionality:
    exec_test_login: Executes SSH login tests on provided inventory records.
    cli_login: CLI command for verifying SSH login to devices.
"""

import click

from netcfgbu.cli.common import execute_command
from netcfgbu.config_model import AppConfig
from netcfgbu.consts import DEFAULT_LOGIN_TIMEOUT
from netcfgbu.os_specs import make_host_connector  # Import added here

from .root import (
    WithInventoryCommand,
    cli,
    opt_batch,
    opt_config_file,
    opt_debug_ssh,
    opt_timeout,
    opts_inventory,
)

CLI_COMMAND = "login"


def exec_test_login(inventory_recs: list, app_cfg: AppConfig, cli_opts: dict) -> None:
    """Perform login tests on inventory records using application configuration & CLI options.

    This function executes SSH login tests for each provided inventory record using
    the configuration and options specified.

    Args:
        inventory_recs: List of inventory records to test.
        app_cfg: Application configuration object.
        cli_opts: Dictionary containing command-line options.

    Returns:
        None
    """
    timeout = cli_opts["timeout"] or DEFAULT_LOGIN_TIMEOUT

    def task_creator(rec: dict, app_cfg: AppConfig):
        """Create a task to test SSH login for a given inventory record.

        This function creates and returns a task that tests SSH login capabilities
        for the specified inventory record.

        Args:
            rec: A dictionary representing an inventory record.
            app_cfg: The application configuration object.

        Returns:
            bool: The result of the login test (True for success, False for failure).
        """
        return make_host_connector(rec, app_cfg).test_login(timeout=timeout)

    execute_command(inventory_recs, app_cfg, CLI_COMMAND, task_creator, cli_opts=cli_opts)


@cli.command(name=CLI_COMMAND, cls=WithInventoryCommand)
@opt_config_file
@opts_inventory
@opt_debug_ssh
@opt_batch
@opt_timeout
@click.pass_context
def cli_login(ctx: click.Context, **cli_opts) -> None:
    """Verify SSH login to devices.

    This command tests SSH connectivity to network devices defined in the inventory.
    It verifies that login credentials are correct and the devices are reachable.

    Args:
        ctx: Click context object containing inventory records and application config.
        **cli_opts: Additional command-line options passed to the command.

    Returns:
        None
    """
    exec_test_login(ctx.obj["inventory_recs"], ctx.obj["app_cfg"], cli_opts)
