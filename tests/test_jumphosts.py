"""Tests for the jumphosts module in the netcfgbu package.

This module contains tests for various jumphost functionalities in the
netcfgbu package. It uses pytest for testing.

Functions:
    test_jumphost_connection: Test the connection to a jumphost.
    test_jumphost_authentication: Test the authentication process for a jumphost.
    test_jumphost_command_execution: Test command execution through a jumphost.
"""

import asyncio
from collections import Counter
from pathlib import Path
from unittest.mock import Mock

import asyncssh
import pytest  # noqa
from asynctest import CoroutineMock  # noqa

from netcfgbu import config_model, jumphosts
from netcfgbu.filetypes import CommentedCsvReader


@pytest.fixture(scope="module", autouse=True)
def inventory(request: pytest.FixtureRequest):
    """Fixture to load the inventory data from a CSV file.

    This fixture loads the device inventory from the specified CSV file and
    returns it as a list of dictionaries, each representing a device record.

    Args:
        request (pytest.FixtureRequest): Pytest request object to access the module-level file path.

    Returns:
        list: A list of dictionaries representing the device inventory records.
    """
    test_dir = Path(request.module.__file__).parent
    inv_fp = test_dir / "files/test-small-inventory.csv"
    return list(CommentedCsvReader(inv_fp.open()))


@pytest.fixture()
def mock_asyncssh_connect(monkeypatch: pytest.MonkeyPatch):
    """Fixture to mock the asyncssh.connect method for testing.

    This fixture replaces the asyncssh.connect method with a CoroutineMock
    to simulate SSH connections during tests.

    Args:
        monkeypatch (pytest.MonkeyPatch): Pytest's monkeypatch fixture to modify behavior.

    Returns:
        CoroutineMock: The mocked asyncssh.connect method.
    """
    monkeypatch.setattr(jumphosts, "asyncssh", Mock())
    jumphosts.asyncssh.Error = asyncssh.Error
    jumphosts.asyncssh.connect = CoroutineMock()
    return jumphosts.asyncssh.connect


def test_jumphosts_pass_noused(inventory: list):
    """Test the initialization of a jump host when not used.

    This test verifies that a jump host is not added to the available list
    if no include or exclude filters are specified.

    Args:
        inventory (list): The device inventory loaded from the fixture.
    """
    jh_spec = config_model.JumphostSpec(proxy="1.2.3.4")
    jumphosts.init_jumphosts(jumphost_specs=[jh_spec], inventory=inventory)
    assert len(jumphosts.JumpHost.available) == 0


def common_jumphosts_pass_used(inventory: list, jh_spec: config_model.JumphostSpec):
    """Common test for the initialization of a jump host when used.

    This test verifies that a jump host is correctly assigned to devices
    when no filters are specified.

    Args:
        inventory (list): The device inventory loaded from the fixture.
        jh_spec (config_model.JumphostSpec): The jump host specification to use for initialization.

    Returns:
        collections.Counter: A counter object showing the usage of the jump host across devices.
    """
    jumphosts.init_jumphosts(jumphost_specs=[jh_spec], inventory=inventory)
    assert len(jumphosts.JumpHost.available) == 1
    return Counter(getattr(jumphosts.get_jumphost(rec), "name", None) for rec in inventory)


def test_jumphosts_pass_incused(inventory: list):
    """Test the initialization of a jump host with an include filter.

    This test verifies that a jump host is correctly assigned to devices
    when the include filter is specified for EOS devices.

    Args:
        inventory (list): The device inventory loaded from the fixture.
    """
    jh_spec = config_model.JumphostSpec(proxy="1.2.3.4", include=["os_name=eos"])
    jh_use_count = common_jumphosts_pass_used(inventory, jh_spec)
    assert jh_use_count["1.2.3.4"] == 2


def test_jumphosts_pass_exlused(inventory: list):
    """Test the initialization of a jump host with an exclude filter.

    This test verifies that a jump host is correctly assigned to devices
    when the exclude filter is specified for EOS devices.

    Args:
        inventory (list): The device inventory loaded from the fixture.
    """
    jh_spec = config_model.JumphostSpec(proxy="1.2.3.4", exclude=["os_name=eos"])
    jh_use_count = common_jumphosts_pass_used(inventory, jh_spec)
    assert jh_use_count["1.2.3.4"] == 4


def test_jumphosts_pass_exlallused(inventory: list):
    """Test the exclusion of all OS types from jump host usage.

    This test verifies that no jump hosts are required when all OS types
    are excluded from being assigned to a jump host.

    Args:
        inventory (list): The device inventory loaded from the fixture.
    """
    jh_spec = config_model.JumphostSpec(proxy="1.2.3.4", exclude=["os_name=.*"])
    jumphosts.init_jumphosts(jumphost_specs=[jh_spec], inventory=inventory)
    assert len(jumphosts.JumpHost.available) == 0


@pytest.mark.asyncio
async def test_jumphosts_fail_connect(
    netcfgbu_envars: pytest.FixtureRequest,
    log_vcr: pytest.FixtureRequest,
    inventory: list,
    mock_asyncssh_connect: CoroutineMock,
    monkeypatch: pytest.MonkeyPatch
):
    """Test the failure of SSH connection attempts to a jump host.

    This test verifies that appropriate error handling occurs when SSH connections
    to a jump host fail due to timeouts or other errors.

    Args:
        netcfgbu_envars (pytest.FixtureRequest): Pytest fixture for setting environment variables.
        log_vcr (pytest.FixtureRequest): Pytest fixture for capturing log records.
        inventory (list): The device inventory loaded from the fixture.
        mock_asyncssh_connect (CoroutineMock): The mocked asyncssh.connect method.
        monkeypatch (pytest.MonkeyPatch): Pytest's monkeypatch fixture to modify behavior.
    """
    monkeypatch.setattr(jumphosts, "get_logger", Mock(return_value=log_vcr))
    jh_spec = config_model.JumphostSpec(proxy="dummy-user@1.2.3.4:8022", exclude=["os_name=eos"])
    jumphosts.init_jumphosts(jumphost_specs=[jh_spec], inventory=inventory)

    mock_asyncssh_connect.side_effect = asyncio.TimeoutError()
    ok = await jumphosts.connect_jumphosts()
    assert ok is False

    mock_asyncssh_connect.side_effect = asyncssh.Error(code=10, reason="nooooope")
    ok = await jumphosts.connect_jumphosts()
    assert ok is False

    jh: jumphosts.JumpHost = jumphosts.JumpHost.available[0]
    with pytest.raises(RuntimeError) as excinfo:
        _ = jh.tunnel

    errmsg = excinfo.value.args[0]
    assert "not connected" in errmsg

    log_recs = log_vcr.handlers[0].records
    expected_timeout_log = "JUMPHOST: connect to dummy-user@1.2.3.4:8022 failed: TimeoutError"
    expected_error_log = "JUMPHOST: connect to dummy-user@1.2.3.4:8022 failed: nooooope"
    assert log_recs[-2].getMessage() == expected_timeout_log
    assert log_recs[-1].getMessage() == expected_error_log
