"""Commands for the netcfgbu CLI to generate example files.

This module contains commands for generating example files that help users
get started with netcfgbu.
"""

import importlib.resources
import shutil
from pathlib import Path

import typer

from .root import cli


def copy_example_files() -> None:
    """Copy example files from the package to the current directory.

    This function copies all example files from the package's examples directory
    to the user's current working directory. If any of the example files already
    exist in the current directory, no files will be copied and the function
    will exit with an error.

    Returns:
        None

    Raises:
        typer.Exit: If any example files already exist in the current directory.
    """
    package_name = "netcfgbu"
    examples_dir_name = "examples"

    # Use importlib.resources.files to access the directory
    examples_path = importlib.resources.files(package_name) / examples_dir_name

    # Preliminary check for existing files
    existing_files = [
        file_path for file_path in examples_path.iterdir() if (Path.cwd() / file_path.name).exists()
    ]
    if existing_files:
        existing_files_names = ", ".join(file_path.name for file_path in existing_files)
        error_msg = (
            "ERROR: No files were copied. The following file(s) already exist "
            f"in the current directory: {existing_files_names}"
        )
        typer.echo(error_msg, err=True)
        raise typer.Exit(code=1)

    # If no existing files were found, proceed to copy
    for file_path in examples_path.iterdir():
        if file_path.is_file():
            # Ensure destination directory exists (it's cwd, so it does, but good practice)
            # and then copy.
            dest_path = Path.cwd() / file_path.name
            try:
                with (
                    importlib.resources.as_file(file_path) as source_path_obj,
                    source_path_obj.open("rb") as sf,
                    open(dest_path, "wb") as df,
                ):
                    shutil.copyfileobj(sf, df)
                typer.echo(f"Copied {file_path.name} to the current directory.")
            except Exception as e:
                typer.echo(f"Error copying {file_path.name}: {e}", err=True)
                # Decide if one error should stop all, or continue.
                # For now, let's raise and stop.
                raise typer.Exit(code=1) from e


@cli.command(name="example", help="Generate example inventory & configuration files.")
def cli_example() -> None:
    """Generate example inventory & configuration files.

    Creates sample inventory and configuration files in the current directory
    that can be edited and used for setting up netcfgbu.
    """
    copy_example_files()
