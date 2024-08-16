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
    """
    Handles exceptions during task execution and logs the error.

    Args:
        exc: The exception that occurred.
        rec: The inventory record associated with the task.
        done_msg: The message indicating task completion status.
        report: The Report object to store task results.
    """
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
    """
    Processes tasks in the provided task list, handling both login and generic tasks.

    Args:
        tasks: A list of tasks to process.
        app_cfg: The application configuration object.
        report: The Report object to store task results.
        cli_command: The CLI command being executed.
        success_callback: Optional callback for successful tasks.
        failure_callback: Optional callback for failed tasks.
    """
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
    """
    Processes a login task, handling the results and exceptions.

    Args:
        task: The task to process.
        report: The Report object to store task results.
        done_msg: The message indicating task completion status.
        rec: The inventory record associated with the task.
        failure_callback: Optional callback for failed tasks.
    """
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
            log.error("%s%s", done_msg, reason)
    except Exception as exc:
        await handle_exception(exc, rec, done_msg, report)
        if failure_callback:
            failure_callback(rec, exc)


async def process_generic_task(
    task, report, cli_command, done_msg, rec, success_callback, failure_callback
):
    """
    Processes a generic task, handling the results and exceptions.

    Args:
        task: The task to process.
        report: The Report object to store task results.
        cli_command: The CLI command being executed.
        done_msg: The message indicating task completion status.
        rec: The inventory record associated with the task.
        success_callback: Optional callback for successful tasks.
        failure_callback: Optional callback for failed tasks.
    """
    try:
        result = task.result()
        if result:
            report.task_results[True].append((rec, result))
            log.info("%s - PASS", done_msg)
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
    cli_opts=None,
    success_callback=None,
    failure_callback=None,
):
    """
    Executes the specified CLI command on the provided inventory records.

    Args:
        inventory_recs: List of inventory records to process.
        app_cfg: The application configuration object.
        cli_command: The CLI command to execute.
        task_creator: Function to create tasks for each inventory record.
        cli_opts: Optional CLI options.
        success_callback: Optional callback for successful tasks.
        failure_callback: Optional callback for failed tasks.
    """
    device_count = len(inventory_recs)
    log.info("%s %d devices ...", cli_command.capitalize(), device_count)

    loop = asyncio.get_event_loop()

    tasks = {task_creator(rec, app_cfg): rec for rec in inventory_recs}
    if not cli_opts:
        cli_opts = {}

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
