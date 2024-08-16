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
    """
    Executes the backup command on the provided inventory records.

    Args:
        inventory_recs: List of inventory records to back up.
        app_cfg: Application configuration object.
    """

    def task_creator(rec: dict, app_cfg: AppConfig):
        """
        Creates a backup task for the given inventory record.

        Args:
            rec: A dictionary representing an inventory record.
            app_cfg: Application configuration object.

        Returns:
            A backup task configured with the host connector.
        """
        return make_host_connector(rec, app_cfg).backup_config()

    def success_callback(rec, result):
        """
        Callback function executed on a successful backup.

        Args:
            rec: A dictionary representing an inventory record.
            result: The result of the backup task.
        """
        Plugin.run_backup_success(rec, result)

    def failure_callback(rec, exc):
        """
        Callback function executed on a failed backup.

        Args:
            rec: A dictionary representing an inventory record.
            exc: The exception raised during the backup task.
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
    """
    Backup network configurations.
    """
    load_plugins(ctx.obj["app_cfg"].defaults.plugins_dir)
    exec_backup(inventory_recs=ctx.obj["inventory_recs"], app_cfg=ctx.obj["app_cfg"])
