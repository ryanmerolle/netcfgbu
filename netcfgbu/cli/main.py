from .backup import cli_backup  # noqa
from .example import cli_example  # noqa
from .inventory import cli_inventory  # noqa
from .login import cli_login  # noqa
from .probe import cli_check  # noqa
from .root import cli
from .vcs import cli_vcs  # noqa


def run():
    cli(obj={})
