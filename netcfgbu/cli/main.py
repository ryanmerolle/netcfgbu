from .backup import cli_backup  # noqa # pylint: disable=W0611
from .example import cli_example  # noqa # pylint: disable=W0611
from .inventory import cli_inventory  # noqa # pylint: disable=W0611
from .login import cli_login  # noqa # pylint: disable=W0611
from .probe import cli_check  # noqa # pylint: disable=W0611
from .root import cli
from .vcs import cli_vcs  # noqa # pylint: disable=W0611


def run() -> None:
    """Entry point for the CLI application.

    This function initializes and runs the command-line interface (CLI)
    with an empty context object.
    """
    cli(obj={})
