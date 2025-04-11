"""Root command handler for the CLI.

This module provides the foundation for the command-line interface,
including custom Click commands, CLI options and common utilities.
"""

from functools import reduce
from importlib import metadata
from pathlib import Path

import click
from first import first

import netcfgbu
from netcfgbu import config as _config
from netcfgbu import inventory as _inventory
from netcfgbu import jumphosts

VERSION = metadata.version(netcfgbu.__package__)


# -----------------------------------------------------------------------------
#
#                           CLI Custom Click Commands
#
# -----------------------------------------------------------------------------


class WithConfigCommand(click.Command):
    """Custom Click command that loads the configuration file before invoking the command.

    This class extends the Click Command class to automatically load the application
    configuration file before executing the command function.
    """

    def invoke(self, ctx):
        """Invokes the command after loading the configuration file.

        Args:
            ctx: Click context object containing command parameters and state.

        Raises:
            Exception: If there is an error loading the configuration file.
        """
        try:
            ctx.obj["app_cfg"] = _config.load(fileio=ctx.params["config"])
            super().invoke(ctx)

        except Exception as exc:
            ctx.fail(str(exc))


class WithInventoryCommand(click.Command):
    """Custom Click command that preloads configuration and inventory.

    This class extends Click Command to automatically load both configuration and inventory
    data before executing the command. It also handles SSH debugging setup and jumphost
    configuration when specified.
    """

    def invoke(self, ctx):
        """Invokes the command after loading the configuration and inventory.

        This method loads the application configuration and inventory data before invoking
        the command function. It also sets up SSH debugging if enabled and initializes
        any configured jumphosts.

        Args:
            ctx: Click context object containing command parameters and state.

        Raises:
            RuntimeError: If no inventory matches the specified limits.
            Exception: If there is an error during configuration or inventory loading.
        """
        try:
            app_cfg = ctx.obj["app_cfg"] = _config.load(fileio=ctx.params["config"])

            if debug_ssh_lvl := ctx.params.get("debug_ssh"):  # pragma: no cover
                import logging

                from asyncssh import logging as assh_lgr

                assh_lgr.set_log_level(logging.DEBUG)
                assh_lgr.set_debug_level(debug_ssh_lvl)

            if ctx.params["inventory"]:
                ctx.obj["app_cfg"].defaults.inventory = ctx.params["inventory"]

            inv = ctx.obj["inventory_recs"] = _inventory.load(
                app_cfg=app_cfg,
                limits=ctx.params["limit"],
                excludes=ctx.params["exclude"],
            )

            if not inv:
                raise RuntimeError(f"No inventory matching limits in: {app_cfg.defaults.inventory}")

            # if there is jump host configuraiton then prepare for later use.
            if app_cfg.jumphost:
                jumphosts.init_jumphosts(jumphost_specs=app_cfg.jumphost, inventory=inv)

            super().invoke(ctx)

        except Exception as exc:
            ctx.fail(str(exc))


# -----------------------------------------------------------------------------
#
#                                CLI Options
#
# -----------------------------------------------------------------------------


def get_spec_nameorfirst(spec_list, spec_name=None):
    """Returns the first matching spec by name or the first spec in the list.

    This function searches through a list of specification objects to find one that matches
    the provided name. If no name is specified, it returns the first item in the list.

    Args:
        spec_list: List of specification objects to search through.
        spec_name: Optional name of the specification to find.

    Returns:
        The first matching specification object or None if the list is empty.
    """
    if not spec_list:
        return None

    if not spec_name:
        return first(spec_list)

    return first(spec for spec in spec_list if getattr(spec, "name", "") == spec_name)


def check_for_default(ctx: click.Context, opt, value):
    """Checks if the value is provided or if a default configuration file exists.

    This function is used as a callback for Click options to determine if a default
    configuration file should be used when no explicit value is provided.

    Args:
        ctx: Click context object containing command state.
        opt: The Click option that triggered this callback.
        value: The value provided for the option, if any.

    Returns:
        The provided value or None if no value is provided and no default file exists.
    """
    if value or Path("netcfgbu.toml").exists():
        return value

    return None


opt_config_file = click.option(
    "-C",
    "--config",
    envvar="NETCFGBU_CONFIG",
    type=click.File(),
    callback=check_for_default,
    # required=True,
    # default="netcfgbu.toml",
)

# -----------------------------------------------------------------------------
# Inventory Options
# -----------------------------------------------------------------------------

opt_inventory = click.option(
    "--inventory", "-i", help="Inventory file-name", envvar="NETCFGBU_INVENTORY"
)

opt_limits = click.option(
    "--limit",
    "-l",
    "--include",
    multiple=True,
    help="limit/include in inventory",
)

opt_excludes = click.option(
    "--exclude",
    "-e",
    multiple=True,
    help="exclude from inventory",
)


def opts_inventory(in_fn_deco):
    """Decorator that applies inventory-related options to a command.

    This decorator function combines multiple inventory-related Click options
    (inventory, limits, and excludes) and applies them to a command function.

    Args:
        in_fn_deco: The command function to decorate.

    Returns:
        The decorated command function with inventory options applied.
    """
    return reduce(lambda _d, fn: fn(_d), [opt_inventory, opt_limits, opt_excludes], in_fn_deco)


opt_batch = click.option(
    "--batch",
    "-b",
    type=click.IntRange(1, 500),
    help="inventory record processing batch size",
)

opt_timeout = click.option("--timeout", "-t", help="timeout(s)", type=click.IntRange(0, 5 * 60))

opt_debug_ssh = click.option("--debug-ssh", help="enable SSH debugging", type=click.IntRange(1, 3))


@click.group()
@click.version_option(version=VERSION)
def cli() -> None:
    """The main entry point for the CLI application.

    This function defines the root command group for the application's
    command-line interface. All subcommands are attached to this group.
    """
    pass  # pragma: no cover
