import asyncio
import socket

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


def exec_probe(inventory_recs, timeout=None) -> None:
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

    async def proces_check() -> None:
        nonlocal done

        async for task in as_completed(tasks):
            done += 1
            coro = task.get_coro()
            rec = tasks[coro]
            done_msg = f"DONE ({done}/{total}): {rec['host']} "

            try:
                probe_ok = task.result()
                report.task_results[probe_ok].append((rec, probe_ok))
                log.info(done_msg + ("PASS" if probe_ok else "FAIL"))

            except socket.gaierror as exc:
                await handle_exception(
                    exc, "NameResolutionError", rec, done_msg, report
                )
            except asyncio.TimeoutError as exc:
                await handle_exception(exc, "TimeoutError", rec, done_msg, report)
            except OSError as exc:
                if exc.errno == 113:
                    await handle_exception(exc, "NoRouteToHost", rec, done_msg, report)
                else:
                    await handle_exception(exc, "OSError", rec, done_msg, report)
            except Exception as exc:
                exception_name = type(exc).__name__
                subclass_names = [cls.__name__ for cls in type(exc).__bases__]
                await handle_exception(
                    exc, f"{exception_name}.{subclass_names}", rec, done_msg, report
                )

    report.start_timing()
    loop.run_until_complete(proces_check())
    report.stop_timing()
    stop_aiologging()
    report.print_report(reports_type="probe")


@cli.command(name="probe", cls=WithInventoryCommand)
@opt_config_file
@opts_inventory
@opt_timeout
@click.pass_context
def cli_check(ctx, **cli_opts) -> None:
    """
    Probe device for SSH reachablility.

    The probe check determines if the device is reachable and the SSH port
    is available to receive connections.
    """
    exec_probe(ctx.obj["inventory_recs"], timeout=cli_opts["timeout"])
