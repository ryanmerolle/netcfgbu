"""Tests for the plugins module in the netcfgbu package.

This module contains tests for various plugin functionalities in the
netcfgbu package. It uses pytest for testing.

Functions:
    test_plugin_loading: Test the loading of plugins.
    test_plugin_execution: Test the execution of plugins.
    test_plugin_validation: Test the validation of plugins.
"""

import pytest

from netcfgbu.config import load
from netcfgbu.plugins import Plugin, _registered_plugins, load_plugins


@pytest.fixture()
def pytest_load_plugins(request, monkeypatch, netcfgbu_envars):
    """Fixture to set up and load plugins for testing.

    This fixture sets the `NETCFGBU_PLUGINSDIR` environment variable to point to
    the test plugins directory and loads the plugins.

    Args:
        request: Pytest request object providing access to the test module.
        monkeypatch: Pytest fixture for safely modifying environment and attributes.
        netcfgbu_envars: Fixture to set up necessary environment variables.
    """
    plugins_dir = f"{request.fspath.dirname}/files/plugins"
    monkeypatch.setenv("NETCFGBU_PLUGINSDIR", str(plugins_dir))
    app_cfg = load()

    load_plugins(app_cfg.defaults.plugins_dir)


def test_loading_plugins(pytest_load_plugins):
    """Test that plugins are correctly loaded.

    Verifies that the plugin loaded is a subclass of the `Plugin` class.
    """
    assert issubclass(_registered_plugins["hooks"][0], Plugin)


def test_plugin_backup_success(pytest_load_plugins):
    """Test the `backup_success` method of a loaded plugin.

    Ensures that the `backup_success` method correctly returns the provided
    record and result.

    Args:
        pytest_load_plugins: Fixture to load plugins for testing.
    """
    rec = {"host": "switch1", "os_name": "junos"}
    res = True

    result = _registered_plugins["hooks"][0].backup_success(rec, res)

    assert result[0] == rec
    assert result[1] == res


def test_plugin_backup_failed(pytest_load_plugins):
    """Test the `backup_failed` method of a loaded plugin.

    Ensures that the `backup_failed` method correctly returns the provided
    record and result.

    Args:
        pytest_load_plugins: Fixture to load plugins for testing.
    """
    rec = {"host": "switch1", "os_name": "junos"}
    res = False

    result = _registered_plugins["hooks"][0].backup_failed(rec, res)

    assert result[0] == rec
    assert result[1] == res
