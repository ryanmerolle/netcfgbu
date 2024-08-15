import asyncio
import socket

import asyncssh
import click

from netcfgbu import jumphosts
from netcfgbu.aiofut import as_completed
from netcfgbu.cli.common import handle_exception
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

CLI_COMMAND = "login"


def exec_test_login(inventory_recs: list, app_cfg: AppConfig, cli_opts) -> None:
    timeout = cli_opts["timeout"] or DEFAULT_LOGIN_TIMEOUT

    log = get_logger()

    inv_n = len(inventory_recs)
    log.info(f"Checking logins on {inv_n} devices ...")

    loop = asyncio.get_event_loop()

    tasks = {
        make_host_connector(rec, app_cfg).test_login(timeout=timeout): rec
        for rec in inventory_recs
    }

    if (batch_n := cli_opts["batch"]) is not None:
        set_max_startups(batch_n)

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
                if login_user := task.result():
                    rec["login_user"] = login_user
                    rec["attempts"] = rec.get("attempts", 1)  # Capture attempts
                    report.task_results[True].append(rec)
                    log.info(done_msg + f" - {login_user=}")
                else:
                    reason = "all credentials failed"
                    rec["login_user"] = reason
                    rec["attempts"] = rec.get("attempts", 1)  # Capture attempts
                    report.task_results[False].append((rec, reason))
                    log.error(done_msg + reason)

            except Exception as exc:
                await handle_exception(exc, rec, done_msg, report)

    report.start_timing()
    loop.run_until_complete(process_batch())
    report.stop_timing()
    stop_aiologging()
    report.print_report(reports_type=CLI_COMMAND)


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
