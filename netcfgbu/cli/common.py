import asyncio
import socket

import asyncssh

from netcfgbu import jumphosts
from netcfgbu.aiofut import as_completed
from netcfgbu.cli.report import Report
from netcfgbu.connectors import set_max_startups
from netcfgbu.logger import get_logger, stop_aiologging
from netcfgbu.plugins import Plugin

log = get_logger()


async def handle_exception(exc, rec, done_msg, report) -> None:
    exception_map = {
        asyncssh.PermissionDenied: "All credentials failed",
        asyncssh.ConnectionLost: "ConnectionLost",
        asyncssh.HostKeyNotVerifiable: "HostKeyNotVerifiable",
        socket.gaierror: "NameResolutionError",
        asyncio.TimeoutError: "TimeoutError",
        asyncssh.TimeoutError: "TimeoutError",
        OSError: "NoRouteToHost" if exc.errno == 113 else "OSError",
    }

    reason = exception_map.get(type(exc), type(exc).__name__)

    reason_detail = f"{reason} - {str(exc)}"
    log.error(done_msg + " - " + reason_detail)
    report.task_results[False].append((rec, reason))


async def process_tasks(
    tasks, app_cfg, report, cli_command, success_callback=None, failure_callback=None
):
    done = 0
    total = len(tasks)

    if app_cfg is not None and app_cfg.jumphost:
        await jumphosts.connect_jumphosts()

    async for task in as_completed(tasks):
        done += 1
        coro = task.get_coro()
        rec = tasks[coro]
        done_msg = f"DONE ({done}/{total}): {rec['host']}"

        if cli_command == "login":
            await process_login_task(task, report, done_msg, rec, failure_callback)
        else:
            await process_generic_task(
                task,
                report,
                cli_command,
                done_msg,
                rec,
                success_callback,
                failure_callback,
            )


async def process_login_task(task, report, done_msg, rec, failure_callback):
    try:
        if login_user := task.result():
            rec["login_user"] = login_user
            rec["attempts"] = rec.get("attempts", 1)
            report.task_results[True].append(rec)
            log.info(done_msg + f" - {login_user=}")
        else:
            reason = "all credentials failed"
            rec["login_user"] = reason
            rec["attempts"] = rec.get("attempts", 1)
            report.task_results[False].append((rec, reason))
            log.error(done_msg + reason)
    except Exception as exc:
        await handle_exception(exc, rec, done_msg, report)
        if failure_callback:
            failure_callback(rec, exc)


async def process_generic_task(
    task, report, cli_command, done_msg, rec, success_callback, failure_callback
):
    try:
        result = task.result()
        if result:
            report.task_results[True].append((rec, result))
            log.info(done_msg + " - PASS")
            if success_callback:
                success_callback(rec, result)
        else:
            reason = f"{cli_command} failed"
            await handle_exception(Exception(reason), rec, done_msg, report)
            if failure_callback:
                failure_callback(rec, Exception(reason))
    except Exception as exc:
        await handle_exception(exc, rec, done_msg, report)
        if failure_callback:
            failure_callback(rec, exc)


def execute_command(
    inventory_recs,
    app_cfg,
    cli_command,
    task_creator,
    cli_opts={},
    success_callback=None,
    failure_callback=None,
):
    device_count = len(inventory_recs)
    log.info(f"{cli_command.capitalize()} {device_count} devices ...")

    loop = asyncio.get_event_loop()

    tasks = {task_creator(rec, app_cfg): rec for rec in inventory_recs}

    if cli_command == "login" and cli_opts.get("batch"):
        set_max_startups(cli_opts.get("batch"))

    report = Report()
    report.start_timing()
    loop.run_until_complete(
        process_tasks(
            tasks, app_cfg, report, cli_command, success_callback, failure_callback
        )
    )
    report.stop_timing()
    stop_aiologging()
    report.print_report(reports_type=cli_command)
    if cli_command == "backup":
        Plugin.run_report(report)
