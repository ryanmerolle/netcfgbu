"""This module serves as the root command handler for the CLI."""

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
    """Custom Click command that loads the configuration file before invoking the command."""

    def invoke(self, ctx):
        """Invokes the command after loading the configuration file.

        Args:
            ctx: Click context object.

        Raises:
            Exception: If there is an error loading the configuration.
        """
        try:
            ctx.obj["app_cfg"] = _config.load(fileio=ctx.params["config"])
            super().invoke(ctx)

        except Exception as exc:
            ctx.fail(str(exc))


class WithInventoryCommand(click.Command):
    """Custom Click command that preloads configuration and inventory.

    This function loads the necessary configuration & inventory before invoking the specified
    command. It also initializes SSH debugging & jumphost setup if these options are configured.
    """

    def invoke(self, ctx):
        """Invokes the command after loading the configuration and inventory.

        Args:
            ctx: Click context object.

        Raises:
            Exception: If there is an error loading the configuration, inventory,
            or initializing jumphosts.
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

    Args:
        spec_list: List of specs to search.
        spec_name: Name of the spec to find (optional).

    Returns:
        The matching spec or the first spec if no name is specified.
    """
    if not spec_list:
        return None

    if not spec_name:
        return first(spec_list)

    return first(spec for spec in spec_list if getattr(spec, "name", "") == spec_name)


def check_for_default(ctx: click.Context, opt, value):
    """Checks if the value is provided or if a default configuration file exists.

    Args:
        ctx: Click context object.
        opt: Option being checked.
        value: Value of the option.

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
    """The main entry point for the CLI application."""
    pass  # pragma: no cover
