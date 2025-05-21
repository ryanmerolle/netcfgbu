"""This module provides version control system (VCS) integration for network configurations.

The module implements CLI commands for managing network device configurations in a
version control system, specifically Git. It allows users to prepare, save, and check
the status of configuration backups in a Git repository.
"""

from pathlib import Path
from typing import Annotated, Optional

import typer

from netcfgbu import config as _config
from netcfgbu.config_model import AppConfig, GitSpec
from netcfgbu.logger import stop_aiologging
from netcfgbu.plugins import load_plugins
from netcfgbu.vcs import git

from .root import cli, get_spec_nameorfirst

# Create a new Typer app for the 'vcs' subcommand
vcs_cli = typer.Typer(name="vcs", help="Version Control System subcommands.")
cli.add_typer(vcs_cli)


def get_vcs_spec_from_config(
    app_cfg: AppConfig, vcs_name: Optional[str], config_path: Path
) -> GitSpec:
    """Helper to load VCS spec from config or raise error."""
    if not app_cfg.git:
        raise typer.BadParameter(f"No VCS (git) configurations found in {config_path}")

    spec = get_spec_nameorfirst(app_cfg.git, vcs_name)
    if not spec:
        name_msg = f" named '{vcs_name}'" if vcs_name else ""
        raise typer.BadParameter(f"VCS configuration{name_msg} not found in {config_path}")
    return spec


# Instead of a custom VCSCommand class, we'll use callbacks or direct logic
# in each command function to load config and vcs_spec.
# A common function can be used for this setup part.


def vcs_command_callback(ctx: typer.Context, config_path_obj: Optional[Path], name: Optional[str]):
    """Callback to load app_cfg and vcs_spec into context.

    This replaces the invoke method of the old VCSCommand class.
    """
    if ctx.resilient_parsing:
        return  # Do not run callback during completion

    try:
        # Ensure ctx.obj is initialized if coming from a direct command call not via root
        if not hasattr(ctx, "obj") or ctx.obj is None:
            ctx.obj = {}

        # If app_cfg is already loaded (e.g. by a global callback or previous command), use it.
        # Otherwise, load it.
        if "app_cfg" not in ctx.obj or not ctx.obj["app_cfg"]:
            effective_config_path = config_path_obj or Path("netcfgbu.toml")
            if (
                not effective_config_path.exists() and config_path_obj
            ):  # only error if user specified a non-existent file
                raise typer.BadParameter(
                    f"Configuration file not found: {effective_config_path}", param_hint="--config"
                )
            ctx.obj["app_cfg"] = _config.load(
                fileio=effective_config_path if effective_config_path.exists() else None
            )

        app_cfg = ctx.obj["app_cfg"]

        if not app_cfg:  # Should not happen if load is correct
            raise typer.Exit("Failed to load application configuration.", code=1)

        vcs_spec = get_vcs_spec_from_config(app_cfg, name, config_path_obj or Path("netcfgbu.toml"))
        ctx.obj["vcs_spec"] = vcs_spec
    except Exception as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(code=1) from e


common_vcs_options = [
    typer.Option(
        None,
        "-C",
        "--config",
        envvar="NETCFGBU_CONFIG",
        help="Configuration file path.",
        exists=False,  # Allow default creation logic
        resolve_path=True,
        show_default=False,  # Handled by our logic or default file name
    ),
    typer.Option(None, "--name", help="VCS name as defined in config file."),
]


@vcs_cli.command(name="prepare", help="Prepare your system with the VCS repo.")
def cli_vcs_prepare(
    ctx: typer.Context,
    config: Annotated[Optional[Path], common_vcs_options[0]] = None,
    name: Annotated[Optional[str], common_vcs_options[1]] = None,
) -> None:
    """Prepare your system with the VCS repo.

    This command sets up your `configs_dir` as the VCS repository.
    """
    vcs_command_callback(ctx, config, name)  # Load app_cfg and vcs_spec
    app_cfg = ctx.obj["app_cfg"]
    vcs_spec = ctx.obj["vcs_spec"]

    try:
        git.vcs_prepare(spec=vcs_spec, repo_dir=app_cfg.defaults.configs_dir)
        typer.echo(
            f"VCS repository prepared at {app_cfg.defaults.configs_dir} using '{vcs_spec.name}' config."
        )
    except Exception as e:
        typer.echo(f"Error preparing VCS: {e}", err=True)
        raise typer.Exit(code=1) from e
    finally:
        stop_aiologging()


@vcs_cli.command(name="save", help="Save changes into VCS repository.")
def cli_vcs_save(
    ctx: typer.Context,
    config: Annotated[Optional[Path], common_vcs_options[0]] = None,
    name: Annotated[Optional[str], common_vcs_options[1]] = None,
    add_tag: Annotated[bool, typer.Option(help="If set, create a git tag.")] = False,
    message: Annotated[Optional[str], typer.Option(help="Set commit message / tag name.")] = None,
) -> None:
    """Save changes into VCS repository."""
    vcs_command_callback(ctx, config, name)  # Load app_cfg and vcs_spec
    app_cfg = ctx.obj["app_cfg"]
    vcs_spec = ctx.obj["vcs_spec"]

    try:
        load_plugins(app_cfg.defaults.plugins_dir)
        git.vcs_save(
            vcs_spec,
            repo_dir=app_cfg.defaults.configs_dir,
            add_tag=add_tag,
            message=message,
        )
        typer.echo(
            f"Changes saved to VCS repository at {app_cfg.defaults.configs_dir} using '{vcs_spec.name}' config."
        )
        if add_tag:
            tag_name = message or typer.prompt(
                "Enter tag name (leave empty for default timestamp tag):",
                default="",
                show_default=False,
            )
            # Actual tagging logic is within git.vcs_save, this is just for echo
            typer.echo(f"Tag '{tag_name if tag_name else '<timestamp>'}' added.")
    except Exception as e:
        typer.echo(f"Error saving to VCS: {e}", err=True)
        raise typer.Exit(code=1) from e
    finally:
        stop_aiologging()


@vcs_cli.command(name="status", help="Show VCS repository status.")
def cli_vcs_status(
    ctx: typer.Context,
    config: Annotated[Optional[Path], common_vcs_options[0]] = None,
    name: Annotated[Optional[str], common_vcs_options[1]] = None,
) -> None:
    """Show VCS repository status."""
    vcs_command_callback(ctx, config, name)  # Load app_cfg and vcs_spec
    app_cfg = ctx.obj["app_cfg"]
    vcs_spec = ctx.obj["vcs_spec"]

    try:
        output = git.vcs_status(spec=vcs_spec, repo_dir=app_cfg.defaults.configs_dir)
        typer.echo(output)
    except Exception as e:
        typer.echo(f"Error getting VCS status: {e}", err=True)
        raise typer.Exit(code=1) from e
    finally:
        stop_aiologging()
