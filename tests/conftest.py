# pytest configuration file

import logging
from pathlib import Path

import pytest


@pytest.fixture()
def fake_inventory_file(tmpdir: pytest.TempPathFactory):
    """Create a temporary fake inventory file for testing.

    Args:
    ----
        tmpdir (pytest.TempPathFactory): Temporary directory factory provided by pytest.

    Yields:
    ------
        str: The path to the fake inventory file.

    """
    yield str(tmpdir.join("inventory.csv"))


@pytest.fixture()
def netcfgbu_envars(monkeypatch: pytest.MonkeyPatch) -> None:
    """Set environment variables for netcfgbu configuration.

    Args:
    ----
        monkeypatch (pytest.MonkeyPatch): pytest's monkeypatch fixture for modifying environment
        variables.

    """
    monkeypatch.setenv("NETCFGBU_DEFAULT_USERNAME", "dummy-username")
    monkeypatch.setenv("NETCFGBU_DEFAULT_PASSWORD", "dummy-password")
    monkeypatch.setenv("NETCFGBU_INVENTORY", "/tmp/inventory.csv")
    monkeypatch.setenv("NETCFGBU_CONFIGSDIR", "/tmp/configs")
    monkeypatch.setenv("NETCFGBU_PLUGINSDIR", "/tmp/plugins")


class RecordsCollector(logging.Handler):
    """Custom logging handler to collect log records."""

    def __init__(self, *args, **kwargs) -> None:
        """Initialize the RecordsCollector with optional arguments."""
        super().__init__(*args, **kwargs)
        self.records = []

    def emit(self, record: logging.LogRecord) -> None:
        """Store a log record in the records list.

        Args:
        ----
            record (logging.LogRecord): The log record to store.

        """
        self.records.append(record)


@pytest.fixture()
def log_vcr() -> logging.Logger:
    """Create and configure a logger for capturing log records.

    Returns:
    -------
        logging.Logger: The configured logger with RecordsCollector as its handler.

    """
    log = logging.getLogger()
    log.setLevel(logging.DEBUG)
    log_vcr = RecordsCollector()
    log.handlers[0] = log_vcr
    return log


@pytest.fixture(scope="module")
def files_dir(request: pytest.FixtureRequest) -> Path:
    """Provide the directory containing the test files.

    Args:
    ----
        request (pytest.FixtureRequest): The pytest request object.

    Returns:
    -------
        Path: The path to the 'files' directory in the test module.

    """
    return Path(request.module.__file__).parent / "files"
