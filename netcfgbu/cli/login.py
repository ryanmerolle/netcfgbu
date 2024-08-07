import asyncio
import asyncssh
import socket

import click

from netcfgbu.logger import get_logger, stop_aiologging
from netcfgbu.aiofut import as_completed
from netcfgbu.os_specs import make_host_connector
from netcfgbu.connectors import set_max_startups


from .root import (
    cli,
    WithInventoryCommand,
    opt_config_file,
    opts_inventory,
    opt_batch,
    opt_debug_ssh,
    opt_timeout,
)

from .report import Report
from netcfgbu import jumphosts
from netcfgbu.config_model import AppConfig
from netcfgbu.consts import DEFAULT_LOGIN_TIMEOUT


def exec_test_login(app_cfg: AppConfig, inventory_recs, cli_opts):
    timeout = cli_opts["timeout"] or DEFAULT_LOGIN_TIMEOUT

    login_tasks = {
        make_host_connector(rec, app_cfg).test_login(timeout=timeout): rec
        for rec in inventory_recs
    }

    if (batch_n := cli_opts["batch"]) is not None:
        set_max_startups(batch_n)

    total = len(login_tasks)

    report = Report()
    done = 0
    log = get_logger()

    async def process_batch():
        nonlocal done

        if app_cfg.jumphost:
            await jumphosts.connect_jumphosts()

        async for task in as_completed(login_tasks):
            done += 1
            coro = task.get_coro()
            rec = login_tasks[coro]
            done_msg = f"DONE ({done}/{total}): {rec['host']} "
            failure_msg = f"FAILURE: {rec['host']} - "

            try:
                if login_user := task.result():
                    log.info(done_msg + f"with user {login_user}")
                    report.task_results[True].append(rec)
                else:
                    reason = "all credentials failed"
                    log.warning(done_msg + reason)
                    report.task_results[False].append((rec, reason))

            except asyncssh.ConnectionLost as exc:
                report.task_results[False].append((rec, "ConnectionLost"))
                log.error(failure_msg + f"ConnectionLost - {str(exc)}")
            except socket.gaierror as exc:
                report.task_results[False].append((rec, "NameResolutionError"))
                log.error(failure_msg + f"NameResolutionError - {str(exc)}")
            except asyncio.TimeoutError as exc:
                report.task_results[False].append((rec, "TimeoutError"))
                log.error(failure_msg + f"TimeoutError - {str(exc)}")
            except OSError as exc:
                if exc.errno == 113:
                    report.task_results[False].append((rec, "NoRouteToHost"))
                    log.error(failure_msg + f"NoRouteToHost - {str(exc)}")
                else:
                    report.task_results[False].append((rec, "OSError"))
                    log.error(failure_msg + f"OSError - {str(exc)}")

    loop = asyncio.get_event_loop()
    report.start_timing()
    loop.run_until_complete(process_batch())
    report.stop_timing()
    stop_aiologging()
    report.print_report()


@cli.command(name="login", cls=WithInventoryCommand)
@opt_config_file
@opts_inventory
@opt_timeout
@opt_batch
@opt_debug_ssh
@click.pass_context
def cli_login(ctx, **cli_opts):
    """
    Verify SSH login to devices.
    """

    exec_test_login(ctx.obj["app_cfg"], ctx.obj["inventory_recs"], cli_opts)
