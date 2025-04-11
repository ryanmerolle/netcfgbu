"""This module provides functionality for backing up network configurations.

This module contains functions & CLI commands for executing backup operations on
network devices. It handles the coordination of backup tasks, success/failure
handling, and integration with plugins.

Note:
    This module serves as the implementation for the 'backup' CLI command.
"""

import click

from netcfgbu.cli.common import execute_command
from netcfgbu.config_model import AppConfig
from netcfgbu.os_specs import make_host_connector
from netcfgbu.plugins import Plugin, load_plugins

from .root import (
    WithInventoryCommand,
    cli,
    opt_batch,
    opt_config_file,
    opt_debug_ssh,
    opts_inventory,
)

CLI_COMMAND = "backup"


def exec_backup(inventory_recs: list, app_cfg: AppConfig) -> None:
    """Executes the backup command on the provided inventory records.

    This function orchestrates the backup process by creating tasks for each
    inventory record and handling the results through callbacks.

    Args:
        inventory_recs (list): List of inventory records to back up.
        app_cfg (AppConfig): Application configuration object.

    Returns:
        None
    """

    def task_creator(rec: dict, app_cfg: AppConfig):
        """Creates a backup task for the given inventory record.

        Args:
            rec (dict): A dictionary representing an inventory record.
            app_cfg (AppConfig): Application configuration object.

        Returns:
            object: A backup task configured with the host connector.
        """
        return make_host_connector(rec, app_cfg).backup_config()

    def success_callback(rec, result):
        """Callback function executed on a successful backup.

        Args:
            rec (dict): A dictionary representing an inventory record.
            result (object): The result of the backup task.

        Returns:
            None
        """
        Plugin.run_backup_success(rec, result)

    def failure_callback(rec, exc):
        """Callback function executed on a failed backup.

        Args:
            rec (dict): A dictionary representing an inventory record.
            exc (Exception): The exception raised during the backup task.

        Returns:
            None
        """
        Plugin.run_backup_failed(rec, exc)

    execute_command(
        inventory_recs,
        app_cfg,
        CLI_COMMAND,
        task_creator,
        success_callback,
        failure_callback,
    )


@cli.command(name=CLI_COMMAND, cls=WithInventoryCommand)
@opt_config_file
@opts_inventory
@opt_debug_ssh
@opt_batch
@click.pass_context
def cli_backup(ctx: click.Context, **_cli_opts) -> None:
    """Backup network configurations.

    This command initiates the backup process for network device configurations
    based on the provided inventory and configuration.

    Args:
        ctx (click.Context): The Click context object containing application state.
        **_cli_opts: Additional CLI options passed to the command.

    Returns:
        None
    """
    load_plugins(ctx.obj["app_cfg"].defaults.plugins_dir)
    exec_backup(inventory_recs=ctx.obj["inventory_recs"], app_cfg=ctx.obj["app_cfg"])
