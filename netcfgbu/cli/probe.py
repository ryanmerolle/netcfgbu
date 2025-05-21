"""Provides probing functionality to check the status of network devices.

This module contains functions and CLI commands that allow users to test connectivity
to network devices using SSH probes.
"""

from pathlib import Path
from typing import Annotated, Optional

import typer

from netcfgbu.cli.common import execute_command
from netcfgbu.config_model import (
    AppConfig,
)  # AppConfig may not be needed if not used by task_creator
from netcfgbu.consts import DEFAULT_PROBE_TIMEOUT
from netcfgbu.probe import probe as run_probe  # Renamed to avoid conflict

from .root import WithInventoryCommand, cli

CLI_COMMAND = "probe"  # This is also the command name for Typer


def exec_probe(inventory_recs: list, timeout_val: int) -> None:
    """Executes the probe command on the provided inventory records.

    Args:
        inventory_recs (list): List of inventory records to probe.
        timeout_val (int): Timeout value for the probe command in seconds.

    Returns:
        None
    """
    # timeout_val is now directly passed, no default fallback needed here as CLI defines it.

    def task_creator(rec: dict, app_cfg: Optional[AppConfig]):  # app_cfg might be None
        """Creates a probe task for the given inventory record.

        Args:
            rec (dict): A dictionary representing an inventory record.
            app_cfg (Optional[AppConfig]): Application configuration object (may be None).

        Returns:
            callable: A probe task configured with the IP address or hostname
                from the inventory record.
        """
        # Probing typically doesn't need the full app_cfg, just the target and timeout.
        # If app_cfg were needed, its presence should be ensured or handled.
        return run_probe(rec.get("ipaddr") or rec.get("host"), timeout=timeout_val, raise_exc=True)

    # Pass app_cfg=None to execute_command for probe, as task_creator may not need it
    # and WithInventoryCommand (if used as cls) might not always populate app_cfg
    # if --config is not given and not default found.
    # However, WithInventoryCommand *does* load app_cfg.
    # For probe, it's safer if task_creator and exec_probe are designed
    # not to strictly depend on app_cfg if the command's purpose doesn't require it.
    # Here, execute_command is called with app_cfg=ctx.obj.get("app_cfg") from the CLI command.
    execute_command(
        inventory_recs=inventory_recs,
        app_cfg=None,  # Explicitly None as probe itself doesn't use app_cfg directly
        cmd_name=CLI_COMMAND,
        task_creator=task_creator,
    )


@cli.command(name=CLI_COMMAND, cls=WithInventoryCommand, help="Probe devices for SSH reachability.")
def cli_check(  # Renamed from cli_check to cli_probe to match command name "probe" for clarity
    ctx: typer.Context,
    config: Annotated[
        Optional[Path],
        typer.Option(
            "-C",
            "--config",
            envvar="NETCFGBU_CONFIG",
            help="Configuration file path.",
            exists=False,
            resolve_path=True,
        ),
    ] = None,
    inventory: Annotated[
        Optional[Path],
        typer.Option(
            "--inventory",
            "-i",
            help="Inventory file-name.",
            envvar="NETCFGBU_INVENTORY",
            exists=True,
            resolve_path=True,
        ),
    ] = None,
    limit: Annotated[
        Optional[list[str]],
        typer.Option(
            "--limit",
            "-l",
            "--include",
            help="Limit/include in inventory (can be used multiple times).",
        ),
    ] = None,
    exclude: Annotated[
        Optional[list[str]],
        typer.Option(
            "--exclude",
            "-e",
            help="Exclude from inventory (can be used multiple times).",
        ),
    ] = None,
    # debug_ssh is not typically used for a simple probe, but kept if other commands in group use it
    debug_ssh: Annotated[
        Optional[int],
        typer.Option(
            "--debug-ssh",
            help="Enable SSH debugging (level 1-3, not typically used for probe).",
            min=1,
            max=3,
        ),
    ] = None,
    batch: Annotated[
        Optional[int],
        typer.Option(  # Batch may not be relevant for probe if not using execute_command's batching
            "--batch",
            "-b",
            help="Inventory record processing batch size (affects concurrent probes).",
            min=1,
            max=500,
        ),
    ] = None,
    timeout: Annotated[
        int,
        typer.Option(
            "--timeout",
            "-t",
            help="Timeout (seconds) for each SSH probe.",
            min=0,
            max=300,
        ),
    ] = DEFAULT_PROBE_TIMEOUT,
) -> None:
    """Probe devices for SSH reachability.

    Executes an SSH connection test against each device in the inventory to verify
    connectivity. Reports success or failure for each device.
    """
    inventory_recs = ctx.obj["inventory_recs"]
    app_cfg = ctx.obj.get("app_cfg")  # Get app_cfg, could be None if config not loaded

    if batch is not None and app_cfg:
        app_cfg.defaults.batch_size = batch
    # debug_ssh is available if needed by underlying mechanisms, but probe itself is simple

    # The exec_probe function's task_creator does not use app_cfg.
    # If execute_command requires app_cfg (e.g. for batching), it's passed.
    # If WithInventoryCommand is used, app_cfg is loaded.
    # For probe, we pass the app_cfg from context to execute_command,
    # which then passes it to task_creator. We made task_creator accept Optional[AppConfig].
    actual_app_cfg_for_exec_command = app_cfg
    if CLI_COMMAND == "probe":  # For probe, app_cfg isn't strictly needed by task_creator
        pass  # We still pass it to execute_command for batching consistency

    def task_creator_for_probe(rec: dict, cfg: Optional[AppConfig]):
        return run_probe(rec.get("ipaddr") or rec.get("host"), timeout=timeout, raise_exc=True)

    execute_command(
        inventory_recs=inventory_recs,
        app_cfg=actual_app_cfg_for_exec_command,  # Pass for batching, though task_creator_for_probe won't use cfg
        cmd_name=CLI_COMMAND,
        task_creator=task_creator_for_probe,
    )
