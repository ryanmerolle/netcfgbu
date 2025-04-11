"""Commands for the netcfgbu CLI to generate example files.

This module contains commands for generating example files that help users
get started with netcfgbu.
"""

import importlib.resources
import shutil
from pathlib import Path

import click

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
        SystemExit: If any example files already exist in the current directory.
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
        print(
            "ERROR: No files were copied. ",
            f"The following file(s) already exist in the current directory: {existing_files_names}",
        )
        raise SystemExit(1)

    # If no existing files were found, proceed to copy
    for file_path in examples_path.iterdir():
        if file_path.is_file():
            with (
                importlib.resources.as_file(file_path) as source_file,
                open(Path.cwd() / file_path.name, "wb") as dest_file,
            ):
                shutil.copyfileobj(source_file.open("rb"), dest_file)
                print(f"Copied {file_path.name} to the current directory.")


@cli.command(name="example")
@click.pass_context
def cli_example(ctx: click.Context) -> None:
    """Generate example inventory & configuration files.

    Creates sample inventory and configuration files in the current directory
    that can be edited and used for setting up netcfgbu.

    Args:
        ctx: Click context object that holds state for the command.

    Returns:
        None
    """
    copy_example_files()
