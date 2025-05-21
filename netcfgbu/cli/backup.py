"""This module provides functionality for backing up network configurations.

This module contains functions & CLI commands for executing backup operations on
network devices. It handles the coordination of backup tasks, success/failure
handling, and integration with plugins.

Note:
    This module serves as the implementation for the 'backup' CLI command.
"""

from pathlib import Path
from typing import Annotated, Optional

import typer

from netcfgbu.cli.common import execute_command
from netcfgbu.config_model import AppConfig
from netcfgbu.os_specs import make_host_connector
from netcfgbu.plugins import Plugin, load_plugins

from .root import WithInventoryCommand, cli

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


@cli.command(name=CLI_COMMAND, cls=WithInventoryCommand, help="Backup network configurations.")
def cli_backup(
    ctx: typer.Context,
    config: Annotated[
        Optional[Path],
        typer.Option(
            "-C",
            "--config",
            envvar="NETCFGBU_CONFIG",
            help="Configuration file path.",
            exists=False,  # Allow specifying non-existent for default creation
            resolve_path=True,
        ),
    ] = None,
    inventory: Annotated[
        Optional[Path],
        typer.Option(
            "--inventory",
            "-i",
            help="Inventory file-name.",
            envvar="NETCFGBU_INVENTORY",
            exists=True,
            resolve_path=True,
        ),
    ] = None,
    limit: Annotated[
        Optional[list[str]],
        typer.Option(
            "--limit",
            "-l",
            "--include",
            help="Limit/include in inventory (can be used multiple times).",
        ),
    ] = None,
    exclude: Annotated[
        Optional[list[str]],
        typer.Option(
            "--exclude",
            "-e",
            help="Exclude from inventory (can be used multiple times).",
        ),
    ] = None,
    debug_ssh: Annotated[
        Optional[int],
        typer.Option(
            "--debug-ssh",
            help="Enable SSH debugging (level 1-3).",
            min=1,
            max=3,
        ),
    ] = None,
    batch: Annotated[
        Optional[int],
        typer.Option(
            "--batch",
            "-b",
            help="Inventory record processing batch size.",
            min=1,
            max=500,
        ),
    ] = None,
) -> None:
    """Backup network configurations.

    This command initiates the backup process for network device configurations
    based on the provided inventory and configuration.
    """
    # Config and inventory loading is handled by WithInventoryCommand
    app_cfg = ctx.obj["app_cfg"]
    inventory_recs = ctx.obj["inventory_recs"]

    load_plugins(app_cfg.defaults.plugins_dir)
    exec_backup(inventory_recs=inventory_recs, app_cfg=app_cfg)
