#!/usr/bin/env python
"""Common tasks for developemnt of this project.

For use with the invoke tool, see: http://www.pyinvoke.org/
"""

import io
import os
import shutil

from invoke import exceptions, task

DIRS_TO_CLEAN = [
    ".mypy_cache",
    ".pytest_cache",
    ".pytest_tmpdir",
    ".ruff_cache",
    ".tox",
    "htmlcov",
    "netcfgbu.egg-info",
    "netcfgbu/__pycache__",
    "netcfgbu/cli/__pycache__",
    "netcfgbu/connectors/__pycache__",
    "netcfgbu/vcs/__pycache__",
    "tests/__pycache__",
    "tests/files/plugins/__pycache__",

]
FILES_TO_CLEAN = [
    ".coverage",
]


def write_to_file(output: str, filename: str = "lint.tmp") -> None:
    """Write output to a specified file.

    Args:
        output (str): The content to write to the file.
        filename (str, optional): The name of the file to write to. Defaults to "lint.tmp".
    """
    with open(filename, "w", encoding="utf-8") as file:
        file.write(output)

@task
def update(ctx, help="Update project.") -> None:
    """Update project.

    Args:
        ctx (invoke.Context): The context instance (passed automatically by Invoke).
    """
    # ctx.run("poetry run ruff check . --fix")
    # ctx.run("poetry run ruff format .")
    ctx.run("poetry run pre-commit autoupdate")
    ctx.run("poetry update")


@task
def precheck(ctx, help="Run pre-checks on the project.") -> None:
    """Run pre-checks on the project.

    Args:
        ctx (invoke.Context): The context instance (passed automatically by Invoke).
    """
    # ctx.run("poetry run ruff check . --fix")
    # ctx.run("poetry run ruff format .")
    ctx.run("poetry run pre-commit run -a")
    ctx.run(
        "poetry run interrogate -c pyproject.toml --exclude=build --exclude tests",
        pty=True,
    )


@task
def clean(ctx, help="Clean up the project of cache & temp files.") -> None:
    """Clean up the project by removing specified directories & files.

    Args:
        ctx (invoke.Context): The context instance (passed automatically by Invoke).
    """
    for folder in DIRS_TO_CLEAN:
        try:
            if os.path.exists(folder):
                shutil.rmtree(folder)
                print(f"Deleted folder: {folder}")
            else:
                print(f"Folder not found: {folder}")
        except Exception as exc:
            print(f"Error deleting {folder}: {exc}")
    for file in FILES_TO_CLEAN:
        try:
            os.remove(file)
        except Exception as exc:
            print(f"Error deleting {file}: {exc}")


@task
def install(ctx, help="Install the package locally.") -> None:
    """Install the package locally.

    Args:
        ctx (invoke.Context): The context instance (passed automatically by Invoke).
    """
    try:
        ctx.run("pip install . --force")
    except exceptions.UnexpectedExit as exc:
        print(f"Installation failed: {exc}")
        raise


def write_result(output: io.StringIO, result: str) -> None:
    """Write the result of a linter check to the output buffer.

    Args:
        output (io.StringIO): The buffer to write the result to.
        result (str): The result string to write.
    """
    if result:
        output.write(result + "\n")
    else:
        output.write("No issues found.\n\n")

    output.write("-" * 120 + "\n")
