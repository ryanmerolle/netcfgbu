"""Root command handler for the CLI.

This module provides the foundation for the command-line interface,
including custom Click commands, CLI options and common utilities.
"""

from pathlib import Path
from typing import Annotated, Optional

import typer

from netcfgbu import config as _config
from netcfgbu import inventory as _inventory
from netcfgbu import jumphosts

cli = typer.Typer(
    context_settings={"help_option_names": ["-h", "--help"]},
    add_completion=False,
)


def version_callback(value: bool):
    """Show application version and exit."""
    if value:
        from importlib import metadata

        print(f"netcfgbu version: {metadata.version('netcfgbu')}")
        raise typer.Exit()


@cli.callback()
def common(
    ctx: typer.Context,
    version: Annotated[
        Optional[bool],
        typer.Option(
            "--version",
            callback=version_callback,
            is_eager=True,
            help="Show application version and exit.",
        ),
    ] = None,
):
    """Network Configuration Backup Utility."""
    ctx.obj = {}


class WithConfigCommand(typer.core.TyperCommand):
    """Custom Typer command that loads the configuration file before invoking the command.

    This class extends the Typer Command class to automatically load the application
    configuration file before executing the command function.
    """

    def invoke(self, ctx: typer.Context) -> None:
        """Invokes the command after loading the configuration file.

        Args:
            ctx: Typer context object containing command parameters and state.

        Raises:
            typer.Exit: If there is an error loading the configuration file.
        """
        try:
            config_file_path = ctx.params.get("config") or Path("netcfgbu.toml")
            if not config_file_path.exists() and ctx.params.get(
                "config"
            ):  # only raise if user specified a file
                raise FileNotFoundError(f"Config file not found: {config_file_path}")

            # Ensure ctx.obj is initialized
            if ctx.obj is None:
                ctx.obj = {}
            ctx.obj["app_cfg"] = _config.load(
                fileio=config_file_path if config_file_path.exists() else None
            )
            super().invoke(ctx)

        except Exception as exc:
            print(f"Error: {exc}")  # Provide more user-friendly error
            raise typer.Exit(code=1) from exc


class WithInventoryCommand(typer.core.TyperCommand):  # noqa: D101
    """Custom Typer command that preloads configuration and inventory.

    This class extends Typer Command to automatically load both configuration and inventory
    data before executing the command. It also handles SSH debugging setup and jumphost
    configuration when specified.
    """

    def invoke(self, ctx: typer.Context) -> None:
        """Invokes the command after loading the configuration and inventory.

        This method loads the application configuration and inventory data before invoking
        the command function. It also sets up SSH debugging if enabled and initializes
        any configured jumphosts.

        Args:
            ctx: Typer context object containing command parameters and state.

        Raises:
            typer.Exit: If no inventory matches the specified limits or other errors.
        """
        try:
            # Ensure config is loaded first (potentially by WithConfigCommand if chained)
            if "app_cfg" not in ctx.obj:
                config_file_path = ctx.params.get("config") or Path("netcfgbu.toml")
                if not config_file_path.exists() and ctx.params.get(
                    "config"
                ):  # only raise if user specified a file
                    raise FileNotFoundError(f"Config file not found: {config_file_path}")
                ctx.obj["app_cfg"] = _config.load(
                    fileio=config_file_path if config_file_path.exists() else None
                )

            app_cfg = ctx.obj["app_cfg"]

            if debug_ssh_lvl := ctx.params.get("debug_ssh"):  # pragma: no cover
                import logging

                from asyncssh import logging as assh_lgr

                assh_lgr.set_log_level(logging.DEBUG)
                assh_lgr.set_debug_level(debug_ssh_lvl)

            inventory_path_param = ctx.params.get("inventory")
            if inventory_path_param:
                app_cfg.defaults.inventory = Path(inventory_path_param)

            # Ensure inventory path exists if specified by user
            if inventory_path_param and not app_cfg.defaults.inventory.exists():
                raise FileNotFoundError(f"Inventory file not found: {app_cfg.defaults.inventory}")

            inv = ctx.obj["inventory_recs"] = _inventory.load(
                app_cfg=app_cfg,
                limits=ctx.params.get("limit") or [],  # Ensure it's a list
                excludes=ctx.params.get("exclude") or [],  # Ensure it's a list
            )

            if not inv:
                inventory_source = app_cfg.defaults.inventory or "default inventory"
                limit_msg = f" with limits {ctx.params['limit']}" if ctx.params.get("limit") else ""
                exclude_msg = (
                    f" with excludes {ctx.params['exclude']}" if ctx.params.get("exclude") else ""
                )
                raise RuntimeError(
                    f"No inventory matching{limit_msg}{exclude_msg} in: {inventory_source}"
                )

            if app_cfg.jumphost:
                jumphosts.init_jumphosts(jumphost_specs=app_cfg.jumphost, inventory=inv)

            super().invoke(ctx)

        except Exception as exc:
            print(f"Error: {exc}")  # Provide more user-friendly error
            raise typer.Exit(code=1) from exc


def get_spec_nameorfirst(spec_list, spec_name: Optional[str] = None):  # noqa: D103
    """Returns the first matching spec by name or the first spec in the list."""
    if not spec_list:
        return None
    if not spec_name:
        return spec_list[0]
    return next((spec for spec in spec_list if getattr(spec, "name", "") == spec_name), None)


# Removed check_for_default as Typer handles file existence with Path and Optional.
# Options will be defined directly in command signatures using Annotated.
# Removed opts_inventory decorator for the same reason.
# Removed opt_batch, opt_timeout, opt_debug_ssh as they will be Typer.Option in specific commands.
