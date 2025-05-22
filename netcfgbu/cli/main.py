"""Main module for the netcfgbu CLI application.

This module serves as the entry point for the netcfgbu command-line interface.
It imports all CLI command modules and provides the main run function to
start the application.
"""

from .backup import cli_backup  # noqa # pylint: disable=W0611
from .example import cli_example  # noqa # pylint: disable=W0611
from . import inventory  # noqa # pylint: disable=W0611
from .login import cli_login  # noqa # pylint: disable=W0611
from .probe import cli_check  # noqa # pylint: disable=W0611
from .root import cli  # This will be the Typer app
from . import vcs  # noqa # pylint: disable=W0611


def run() -> None:
    """Entry point for the CLI application.

    This function initializes and runs the command-line interface (CLI).

    Returns:
        None: This function doesn't return anything.
    """
    cli()
