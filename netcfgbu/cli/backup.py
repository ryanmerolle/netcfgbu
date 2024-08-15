import asyncio
import socket

import asyncssh
import click

from netcfgbu import jumphosts
from netcfgbu.aiofut import as_completed
from netcfgbu.cli.common import handle_exception
from netcfgbu.config_model import AppConfig
from netcfgbu.logger import get_logger, stop_aiologging
from netcfgbu.os_specs import make_host_connector
from netcfgbu.plugins import Plugin, load_plugins

from .report import Report
from .root import (
    WithInventoryCommand,
    cli,
    opt_batch,
    opt_config_file,
    opt_debug_ssh,
    opts_inventory,
)

CLI_COMMAND = "backup"


def exec_backup(app_cfg: AppConfig, inventory_recs) -> None:
    log = get_logger()

    inv_n = len(inventory_recs)
    log.info(f"Backing up {inv_n} devices ...")

    tasks = {
        make_host_connector(rec, app_cfg).backup_config(): rec for rec in inventory_recs
    }

    total = len(tasks)
    done = 0
    report = Report()

    async def process_batch() -> None:
        nonlocal done

        if app_cfg.jumphost:
            await jumphosts.connect_jumphosts()

        async for task in as_completed(tasks):
            done += 1
            coro = task.get_coro()
            rec = tasks[coro]
            done_msg = f"DONE ({done}/{total}): {rec['host']}"

            try:
                if result := task.result():
                    report.task_results[True].append((rec, result))
                    log.info(done_msg + " - PASS")
                    Plugin.run_backup_success(rec, result)
                else:
                    reason = f"{CLI_COMMAND} failed"
                    await handle_exception(
                        Exception(reason), reason, rec, done_msg, report
                    )

            except asyncssh.PermissionDenied as exc:
                await handle_exception(
                    exc, "All credentials failed", rec, done_msg, report
                )
                Plugin.run_backup_failed(rec, exc)
            except asyncssh.ConnectionLost as exc:
                await handle_exception(exc, "ConnectionLost", rec, done_msg, report)
                Plugin.run_backup_failed(rec, exc)
            except asyncssh.HostKeyNotVerifiable as exc:
                await handle_exception(
                    exc, "HostKeyNotVerifiable", rec, done_msg, report
                )
                Plugin.run_backup_failed(rec, exc)
            except socket.gaierror as exc:
                await handle_exception(
                    exc, "NameResolutionError", rec, done_msg, report
                )
                Plugin.run_backup_failed(rec, exc)
            except (asyncio.TimeoutError, asyncssh.TimeoutError) as exc:
                await handle_exception(exc, "TimeoutError", rec, done_msg, report)
                Plugin.run_backup_failed(rec, exc)
            except OSError as exc:
                if exc.errno == 113:
                    await handle_exception(exc, "NoRouteToHost", rec, done_msg, report)
                    Plugin.run_backup_failed(rec, exc)
                else:
                    await handle_exception(exc, "OSError", rec, done_msg, report)
                    Plugin.run_backup_failed(rec, exc)
            except Exception as exc:
                exception_name = type(exc).__name__
                await handle_exception(
                    exc, exception_name, rec, done_msg, report
                )
                Plugin.run_backup_failed(rec, exc)

    loop = asyncio.get_event_loop()
    report.start_timing()
    loop.run_until_complete(process_batch())
    report.stop_timing()
    stop_aiologging()
    report.print_report(reports_type=CLI_COMMAND)
    Plugin.run_report(report)


@cli.command(name=CLI_COMMAND, cls=WithInventoryCommand)
@opt_config_file
@opts_inventory
@opt_debug_ssh
@opt_batch
@click.pass_context
def cli_backup(ctx, **_cli_opts) -> None:
    """
    Backup network configurations.
    """
    load_plugins(ctx.obj["app_cfg"].defaults.plugins_dir)
    exec_backup(app_cfg=ctx.obj["app_cfg"], inventory_recs=ctx.obj["inventory_recs"])
