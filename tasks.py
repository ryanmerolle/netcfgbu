#!/usr/bin/env python
#
# For use with the invoke tool, see: http://www.pyinvoke.org/
#
# References
# ----------
#
# Black:
# Flake8: https://flake8.pycqa.org/en/latest/user/configuration.html


from invoke import task


@task
def precheck(ctx):
    """Run pre-checks on the project."""
    # ctx.run("black .")
    # ctx.run("flake8 .")
    ctx.run("poetry ruff check . --fix")
    ctx.run("poetry ruff format .")
    ctx.run("poetry pre-commit run -a")
    ctx.run("poetry run interrogate -c pyproject.toml --exclude=build --exclude tests", pty=True)


@task
def clean(ctx):
    """Clean up the project."""
    ctx.run("rm -rf netcfgbu.egg-info")
    ctx.run("rm -rf .pytest_cache .pytest_tmpdir .coverage .ruff_cache tests/__pycache__ netcfgbu/__pycache__")
    ctx.run("rm -rf netcfgbu/cli/__pycache__ netcfgbu/connectors/__pycache__ netcfgbu/vcs/__pycache__ tests/files/plugins/__pycache__")
    ctx.run("rm -rf htmlcov")


@task
def install(ctx):
    """Install the package locally."""
    ctx.run("pip install . --force")
