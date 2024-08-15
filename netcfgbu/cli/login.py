import asyncio
import socket

import asyncssh
import click

from netcfgbu import jumphosts
from netcfgbu.aiofut import as_completed
from netcfgbu.config_model import AppConfig
from netcfgbu.connectors import set_max_startups
from netcfgbu.consts import DEFAULT_LOGIN_TIMEOUT
from netcfgbu.logger import get_logger, stop_aiologging
from netcfgbu.os_specs import make_host_connector

from .report import Report
from .root import (
    WithInventoryCommand,
    cli,
    opt_batch,
    opt_config_file,
    opt_debug_ssh,
    opt_timeout,
    opts_inventory,
)


def exec_test_login(app_cfg: AppConfig, inventory_recs, cli_opts):
    timeout = cli_opts["timeout"] or DEFAULT_LOGIN_TIMEOUT

    log = get_logger()

    login_tasks = {
        make_host_connector(rec, app_cfg).test_login(timeout=timeout): rec
        for rec in inventory_recs
    }

    if (batch_n := cli_opts["batch"]) is not None:
        set_max_startups(batch_n)

    total = len(login_tasks)

    report = Report()
    done = 0

    async def handle_exception(exc, reason, rec, done_msg):
        reason_detail = f"{reason} - {str(exc)}"
        log.warning(done_msg + reason_detail)
        report.task_results[False].append((rec, reason))

    async def process_batch():
        nonlocal done

        if app_cfg.jumphost:
            await jumphosts.connect_jumphosts()

        async for task in as_completed(login_tasks):
            done += 1
            coro = task.get_coro()
            rec = login_tasks[coro]
            done_msg = f"DONE ({done}/{total}): {rec['host']} "

            try:
                if login_user := task.result():
                    log.info(done_msg + f"with user {login_user}")
                    rec["login_user"] = login_user
                    rec["attempts"] = rec.get(
                        "attempts", 1
                    )  # Capture the number of attempts if available
                    report.task_results[True].append(rec)
                else:
                    reason = "all credentials failed"
                    log.warning(done_msg + reason)
                    rec["login_user"] = reason
                    rec["attempts"] = rec.get(
                        "attempts", 1
                    )  # Capture the number of attempts if available
                    report.task_results[False].append((rec, reason))

            except asyncssh.PermissionDenied as exc:
                await handle_exception(exc, "All credentials failed", rec, done_msg)
            except asyncssh.ConnectionLost as exc:
                await handle_exception(exc, "ConnectionLost", rec, done_msg)
            except asyncssh.HostKeyNotVerifiable as exc:
                await handle_exception(exc, "HostKeyNotVerifiable", rec, done_msg)
            except socket.gaierror as exc:
                await handle_exception(exc, "NameResolutionError", rec, done_msg)
            except (asyncio.TimeoutError, asyncssh.TimeoutError) as exc:
                await handle_exception(exc, "TimeoutError", rec, done_msg)
            except OSError as exc:
                if exc.errno == 113:
                    await handle_exception(exc, "NoRouteToHost", rec, done_msg)
                else:
                    await handle_exception(exc, "OSError", rec, done_msg)
            except Exception as exc:
                exception_name = type(exc).__name__
                subclass_names = [cls.__name__ for cls in type(exc).__bases__]
                await handle_exception(
                    exc, f"{exception_name}.{subclass_names}", rec, done_msg
                )

    loop = asyncio.get_event_loop()
    report.start_timing()
    loop.run_until_complete(process_batch())
    report.stop_timing()
    stop_aiologging()
    report.print_report(reports_type="login")


@cli.command(name="login", cls=WithInventoryCommand)
@opt_config_file
@opts_inventory
@opt_debug_ssh
@opt_batch
@opt_timeout
@click.pass_context
def cli_login(ctx, **cli_opts):
    """
    Verify SSH login to devices.
    """
    exec_test_login(ctx.obj["app_cfg"], ctx.obj["inventory_recs"], cli_opts)
