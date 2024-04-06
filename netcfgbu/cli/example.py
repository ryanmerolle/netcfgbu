import click
import shutil
from pathlib import Path
import pkg_resources


from .root import (
    cli,
)


def copy_example_files():
    """
    Copy all files from the 'netcfgbu/examples/' directory within the package
    to the current working directory.
    """
    package_name = "netcfgbu"
    examples_dir_name = "examples"
    examples_path = Path(
        pkg_resources.resource_filename(package_name, examples_dir_name)
    )

    # Check if the examples directory exists
    if not examples_path.exists():
        print(f"The directory {examples_path} does not exist.")
        return

    # Iterate over all files in the examples directory and copy them to the current working directory
    for file_path in examples_path.iterdir():
        if file_path.is_file():  # Make sure to copy files only
            shutil.copy(file_path, Path.cwd())
            print(f"Copied {file_path.name} to the current directory.")


@cli.command(name="example")
@click.pass_context
def cli_example(ctx, **cli_opts):
    """
    Generate example inventory & configuration files.

    These files can be edited and used for setting up netcfgbu.
    """
    copy_example_files()
