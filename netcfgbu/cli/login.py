"""This module contains the CLI command for testing SSH logins to devices.

The following functionality is provided:

* exec_test_login: Executes SSH login tests on provided inventory records.
* cli_login: CLI command for verifying SSH login to devices.
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
    """This function performs login tests on the provided inventory records using
    the specified application configuration and command-line options.

    Args:
        inventory_recs (list): List of inventory records to test.
        app_cfg (AppConfig): Application configuration object.
        cli_opts (dict): Command-line options dictionary.

    Returns:
        None

    """
    timeout = cli_opts["timeout"] or DEFAULT_LOGIN_TIMEOUT

    def task_creator(rec: dict, app_cfg: AppConfig):
        """Create a task to test SSH login for a given inventory record.

        Args:
            rec (dict): A dictionary representing an inventory record.
            app_cfg (AppConfig): The application configuration object.

        Returns:
            bool: The result of the login test.
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
    """Verify SSH login to devices."""
    exec_test_login(ctx.obj["inventory_recs"], ctx.obj["app_cfg"], cli_opts)
