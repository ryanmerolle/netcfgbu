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
    def task_creator(rec: dict, app_cfg: AppConfig):
        return make_host_connector(rec, app_cfg).backup_config()

    def success_callback(rec, result):
        Plugin.run_backup_success(rec, result)

    def failure_callback(rec, exc):
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
