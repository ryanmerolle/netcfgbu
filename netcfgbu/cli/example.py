"""This module provides example commands for the CLI."""

import importlib.resources
import shutil
from pathlib import Path

import click

from .root import cli


def copy_example_files() -> None:
    """Check if any example file already exists in the current working directory.
    If so, print an error message and do not copy any files.
    Otherwise, copy all files from the 'src/examples/' directory within the package.
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

    These files can be edited and used for setting up netcfgbu.
    """
    copy_example_files()
