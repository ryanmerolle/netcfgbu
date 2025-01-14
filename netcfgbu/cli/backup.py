import asyncio

import click

from netcfgbu.os_specs import make_host_connector
from netcfgbu.logger import get_logger, stop_aiologging
from netcfgbu.aiofut import as_completed
from netcfgbu import jumphosts
from netcfgbu.plugins import Plugin, load_plugins

from .root import (
    cli,
    WithInventoryCommand,
    opt_config_file,
    opts_inventory,
    opt_batch,
    opt_debug_ssh,
)

from .report import Report


def exec_backup(app_cfg, inventory_recs):
    backup_tasks = dict()

    log = get_logger()

    backup_tasks = {
        make_host_connector(rec, app_cfg).backup_config(): rec for rec in inventory_recs
    }

    total = len(backup_tasks)
    report = Report()
    done = 0

    async def process_batch():
        nonlocal done

        if app_cfg.jumphost:
            await jumphosts.connect_jumphosts()

        async for task in as_completed(backup_tasks):
            done += 1
            coro = task.get_coro()
            rec = backup_tasks[coro]
            msg = f"DONE ({done}/{total}): {rec['host']} "

            try:
                res = task.result()
                ok = res is True
                report.task_results[ok].append((rec, res))
                Plugin.run_backup_success(rec, res)

            except (asyncio.TimeoutError, OSError) as exc:
                ok = False
                report.task_results[False].append((rec, exc))
                Plugin.run_backup_failed(rec, exc)

            except Exception as exc:
                ok = False
                log.error(msg + f"FAILURE: {str(exc)}")
                report.task_results[False].append((rec, exc))
                Plugin.run_backup_failed(rec, exc)

            log.info(msg + ("PASS" if ok else "FALSE"))

    loop = asyncio.get_event_loop()
    report.start_timing()
    loop.run_until_complete(process_batch())
    report.stop_timing()
    stop_aiologging()
    report.print_report()
    Plugin.run_report(report)


@cli.command(name="backup", cls=WithInventoryCommand)
@opt_config_file
@opts_inventory
@opt_debug_ssh
@opt_batch
@click.pass_context
def cli_backup(ctx, **_cli_opts):
    """
    Backup network configurations.
    """
    load_plugins(ctx.obj["app_cfg"].defaults.plugins_dir)
    exec_backup(app_cfg=ctx.obj["app_cfg"], inventory_recs=ctx.obj["inventory_recs"])
