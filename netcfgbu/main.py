#!/usr/bin/env python

from netcfgbu.cli import main as main_cli


def main() -> None:
    """
    The main entry point of the application.

    This function runs the CLI interface by calling the `run` method from the `main_cli` module.
    """
    main_cli.run()
