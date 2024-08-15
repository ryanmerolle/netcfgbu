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


def exec_test_login(inventory_recs: list, app_cfg, cli_opts) -> None:
    timeout = cli_opts["timeout"] or DEFAULT_LOGIN_TIMEOUT

    def task_creator(rec: dict, app_cfg: AppConfig):
        return make_host_connector(rec, app_cfg).test_login(timeout=timeout)

    execute_command(
        inventory_recs, app_cfg, CLI_COMMAND, task_creator, cli_opts=cli_opts
    )


@cli.command(name=CLI_COMMAND, cls=WithInventoryCommand)
@opt_config_file
@opts_inventory
@opt_debug_ssh
@opt_batch
@opt_timeout
@click.pass_context
def cli_login(ctx, **cli_opts) -> None:
    """
    Verify SSH login to devices.
    """
    exec_test_login(ctx.obj["inventory_recs"], ctx.obj["app_cfg"], cli_opts)
