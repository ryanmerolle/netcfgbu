#!/usr/bin/env python
#
# For use with the invoke tool, see: http://www.pyinvoke.org/
#
# References
# ----------
#
# Black:
# Flake8: https://flake8.pycqa.org/en/latest/user/configuration.html


import os
import shutil

from invoke import exceptions, task

DIRS_TO_CLEAN = [
    ".mypy_cache",
    ".pytest_cache",
    ".pytest_tmpdir",
    ".ruff_cache",
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


@task
def precheck(ctx):
    """Run pre-checks on the project."""
    # ctx.run("black .")
    # ctx.run("flake8 .")
    ctx.run("poetry run ruff check . --select I --fix")
    ctx.run("poetry run ruff format .")
    ctx.run("poetry run pre-commit run -a")
    ctx.run(
        "poetry run interrogate -c pyproject.toml --exclude=build --exclude tests",
        pty=True,
    )


@task
def clean(ctx):
    """Clean up the project."""
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
def install(ctx):
    """Install the package locally."""
    try:
        ctx.run("pip install . --force")
    except exceptions.UnexpectedExit as e:
        print(f"Installation failed: {e}")
        raise
