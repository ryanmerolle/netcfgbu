"""This module handles inventory management for network devices.

This provides CLI commands for listing & building network device inventories.
It interacts with the inventory system to document info about available devices
& their operating systems, as well as to build inventory files from config.
"""

from pathlib import Path
from textwrap import indent
from typing import Annotated, Optional

import typer
from tabulate import tabulate

from netcfgbu.config_model import AppConfig
from netcfgbu.inventory import build as build_inventory_file

from .report import LN_SEP, SPACES_4
from .root import (
    WithConfigCommand,
    WithInventoryCommand,
    cli,
    get_spec_nameorfirst,
)

# Create a new Typer app for the 'inventory' subcommand
inventory_cli = typer.Typer(
    name="inventory", help="Group of commands for managing device inventory."
)
cli.add_typer(inventory_cli)

# -----------------------------------------------------------------------------
#                                Inventory Commands
# -----------------------------------------------------------------------------


@inventory_cli.command(
    "list", cls=WithInventoryCommand, help="List network devices in the inventory."
)
def cli_inventory_list(
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
    brief: Annotated[
        bool, typer.Option("--brief", "-b", help="Show brief output (summary only).")
    ] = False,
):
    """List network devices in the inventory.

    This command displays a summary of devices in the inventory, grouped by
    operating system, & optionally shows detailed information for each device.
    """
    inventory_recs = ctx.obj["inventory_recs"]
    inventory_tabular_data = []
    os_name_counter = {}
    for rec in inventory_recs:
        os_name = rec.get("os_name")
        if os_name:
            os_name_counter[os_name] = os_name_counter.get(os_name, 0) + 1

    inventory_tabular_data = sorted(os_name_counter.items())
    inventory_tabular_data.append(("-" * 7, "-" * 5))
    inventory_tabular_data.append(("TOTAL", len(inventory_recs)))

    os_name_table = indent(
        tabulate(
            headers=["os_name", "count"],
            tabular_data=inventory_tabular_data,
            tablefmt="pretty",
        ),
        SPACES_4,
    )

    typer.echo(LN_SEP)
    typer.echo("SUMMARY:")
    typer.echo(os_name_table)

    if brief:
        return

    if not inventory_recs:  # handle case where inventory is empty after filtering
        typer.echo("No devices found in inventory matching criteria.")
        typer.echo(LN_SEP)
        return

    field_names = inventory_recs[0].keys()

    typer.echo(
        tabulate(
            headers=field_names,
            tabular_data=[rec.values() for rec in inventory_recs],
            tablefmt="pretty",
        )
    )

    typer.echo(LN_SEP)


@inventory_cli.command(
    "build", cls=WithConfigCommand, help="Build the inventory file from configuration."
)
def cli_inventory_build(
    ctx: typer.Context,
    config: Annotated[
        Path,
        typer.Option(
            "-C",
            "--config",
            envvar="NETCFGBU_CONFIG",
            help="Configuration file path (required for build).",
            exists=True,  # Must exist for build
            dir_okay=False,
            readable=True,
            resolve_path=True,
        ),
    ],  # Default config is handled by WithConfigCommand if not provided by user
    name: Annotated[
        Optional[str],
        typer.Option(
            "--name",
            "-n",
            help="Inventory name as defined in config file (uses first if not specified).",
        ),
    ] = None,
    # brief is not used by this command but kept for consistency if it were a shared option group
    # brief: Annotated[bool, typer.Option("--brief", help="Brief output (not applicable to build).")] = False,
) -> None:
    """Build the inventory file from configuration.

    Creates an inventory file based on definitions in the netcfgbu configuration file.
    If multiple inventory definitions exist, a specific inventory can be selected using
    the --name option.
    """
    app_cfg: AppConfig = ctx.obj["app_cfg"]

    if not app_cfg.inventory:
        raise typer.BadParameter(f"No inventory sections defined in configuration file: {config}")

    spec = get_spec_nameorfirst(app_cfg.inventory, name)

    if not spec:
        inv_name_msg = f"'{name}' " if name else ""
        raise typer.BadParameter(
            f"Inventory section {inv_name_msg}not defined in configuration file: {config}"
        )

    try:
        build_inventory_file(spec)
        typer.echo(
            f"Inventory file '{spec.file}' built successfully from config section '{spec.name}'."
        )
    except Exception as e:
        typer.echo(f"Error building inventory: {e}", err=True)
        raise typer.Exit(code=1) from e
