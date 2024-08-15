import asyncio

import click

from netcfgbu.aiofut import as_completed
from netcfgbu.cli.common import handle_exception
from netcfgbu.consts import DEFAULT_PROBE_TIMEOUT
from netcfgbu.logger import get_logger, stop_aiologging
from netcfgbu.probe import probe

from .report import Report
from .root import (
    WithInventoryCommand,
    cli,
    opt_config_file,
    opt_timeout,
    opts_inventory,
)

CLI_COMMAND = "probe"


def exec_probe(inventory_recs: list, timeout=None) -> None:
    timeout = timeout or DEFAULT_PROBE_TIMEOUT

    log = get_logger()

    inv_n = len(inventory_recs)
    log.info(f"Checking SSH reachability on {inv_n} devices ...")

    loop = asyncio.get_event_loop()

    tasks = {
        probe(
            rec.get("ipaddr") or rec.get("host"), timeout=timeout, raise_exc=True
        ): rec
        for rec in inventory_recs
    }

    total = len(tasks)
    done = 0
    report = Report()

    async def process_check() -> None:
        nonlocal done

        async for task in as_completed(tasks):
            done += 1
            coro = task.get_coro()
            rec = tasks[coro]
            done_msg = f"DONE ({done}/{total}): {rec['host']}"

            try:
                if result := task.result():
                    report.task_results[result].append((rec, result))
                    log.info(done_msg + " - PASS")
                else:
                    reason = f"{CLI_COMMAND} failed"
                    await handle_exception(
                        Exception(reason), reason, rec, done_msg, report
                    )

            except Exception as exc:
                await handle_exception(exc, rec, done_msg, report)

    report.start_timing()
    loop.run_until_complete(process_check())
    report.stop_timing()
    stop_aiologging()
    report.print_report(reports_type=CLI_COMMAND)


@cli.command(name=CLI_COMMAND, cls=WithInventoryCommand)
@opt_config_file
@opts_inventory
@opt_timeout
@click.pass_context
def cli_check(ctx, **cli_opts) -> None:
    """
    Probe device for SSH reachablility.
    """
    exec_probe(ctx.obj["inventory_recs"], timeout=cli_opts["timeout"])
