# pytest configuration file

import logging
from pathlib import Path

import pytest


@pytest.fixture()
def fake_inventory_file(tmpdir):
    yield str(tmpdir.join("inventory.csv"))


@pytest.fixture()
def netcfgbu_envars(monkeypatch):
    monkeypatch.setenv("NETCFGBU_DEFAULT_USERNAME", "dummy-username")
    monkeypatch.setenv("NETCFGBU_DEFAULT_PASSWORD", "dummy-password")
    monkeypatch.setenv("NETCFGBU_INVENTORY", "/tmp/inventory.csv")
    monkeypatch.setenv("NETCFGBU_CONFIGSDIR", "/tmp/configs")
    monkeypatch.setenv("NETCFGBU_PLUGINSDIR", "/tmp/plugins")


class RecordsCollector(logging.Handler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.records = []

    def emit(self, record):
        self.records.append(record)


@pytest.fixture()
def log_vcr() -> logging.Logger:
    log = logging.getLogger()
    log.setLevel(logging.DEBUG)
    log_vcr = RecordsCollector()
    log.handlers[0] = log_vcr
    return log


@pytest.fixture(scope="module")
def files_dir(request) -> Path:
    return Path(request.module.__file__).parent / "files"
