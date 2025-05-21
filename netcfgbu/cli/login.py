"""CLI command module for testing SSH logins to devices.

This module provides functionality to verify SSH login capabilities to network
devices defined in the inventory.

Functionality:
    exec_test_login: Executes SSH login tests on provided inventory records.
    cli_login: CLI command for verifying SSH login to devices.
"""

from pathlib import Path
from typing import Annotated, Optional

import typer

from netcfgbu.cli.common import execute_command
from netcfgbu.config_model import AppConfig
from netcfgbu.consts import DEFAULT_LOGIN_TIMEOUT
from netcfgbu.os_specs import make_host_connector

from .root import WithInventoryCommand, cli

CLI_COMMAND = "login"


def exec_test_login(
    inventory_recs: list,
    app_cfg: AppConfig,
    timeout_val: int,
    batch_val: Optional[int],  # Added batch to pass through, though execute_command handles it
) -> None:
    """Perform login tests on inventory records using application configuration & CLI options.

    This function executes SSH login tests for each provided inventory record using
    the configuration and options specified.

    Args:
        inventory_recs: List of inventory records to test.
        app_cfg: Application configuration object.
        timeout_val: SSH login timeout value.
        batch_val: Batch processing size (passed to execute_command).

    Returns:
        None
    """
    # timeout is now directly passed
    # batch is handled by execute_command via app_cfg or its own defaults if not overridden

    def task_creator(rec: dict, app_cfg: AppConfig):
        """Create a task to test SSH login for a given inventory record.

        This function creates and returns a task that tests SSH login capabilities
        for the specified inventory record.

        Args:
            rec: A dictionary representing an inventory record.
            app_cfg: The application configuration object.

        Returns:
            bool: The result of the login test (True for success, False for failure).
        """
        return make_host_connector(rec, app_cfg).test_login(timeout=timeout_val)

    # Pass batch to execute_command if it needs to override app_cfg.defaults.batch_size
    # However, execute_command currently uses app_cfg.defaults.batch_size.
    # If individual commands need to override this, execute_command or how batch is passed needs adjustment.
    # For now, assuming batch from CLI options updates app_cfg or is directly used if execute_command is modified.
    # The `cli_opts` dict is no longer passed directly. Specific values are.
    execute_command(
        inventory_recs=inventory_recs,
        app_cfg=app_cfg,
        cmd_name=CLI_COMMAND,
        task_creator=task_creator,
        # success/failure callbacks can be added if specific login actions are needed
    )


@cli.command(name=CLI_COMMAND, cls=WithInventoryCommand, help="Verify SSH login to devices.")
def cli_login(
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
    debug_ssh: Annotated[
        Optional[int],
        typer.Option(
            "--debug-ssh",
            help="Enable SSH debugging (level 1-3).",
            min=1,
            max=3,
        ),
    ] = None,
    batch: Annotated[
        Optional[int],
        typer.Option(
            "--batch",
            "-b",
            help="Inventory record processing batch size.",
            min=1,
            max=500,
        ),
    ] = None,
    timeout: Annotated[
        int,
        typer.Option(
            "--timeout",
            "-t",
            help="Timeout (seconds) for SSH login.",
            min=0,
            max=300,  # 5 minutes
        ),
    ] = DEFAULT_LOGIN_TIMEOUT,
) -> None:
    """Verify SSH login to devices.

    This command tests SSH connectivity to network devices defined in the inventory.
    It verifies that login credentials are correct and the devices are reachable.
    """
    app_cfg = ctx.obj["app_cfg"]
    inventory_recs = ctx.obj["inventory_recs"]

    # If batch is provided via CLI, it should ideally override config.
    # The WithInventoryCommand currently loads config, this might need adjustment
    # if CLI options should always take precedence over loaded config for such params.
    # For now, assume app_cfg might have batch size, and CLI `batch` param could override it.
    if batch is not None:
        app_cfg.defaults.batch_size = batch
    if debug_ssh is not None:  # Already handled by WithInventoryCommand if param is "debug_ssh"
        pass  # but good to be explicit if param name differed

    exec_test_login(
        inventory_recs=inventory_recs,
        app_cfg=app_cfg,
        timeout_val=timeout,
        batch_val=batch,  # Pass batch value, even if exec_test_login doesn't use it directly
        # execute_command will use app_cfg.defaults.batch_size
    )
