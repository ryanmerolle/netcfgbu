"""Tests for the CLI probe commands in the netcfgbu module.

This module contains tests for various CLI commands related to the probe functionality.
It uses pytest fixtures, asynctest for mocking asynchronous functions, and
the CliRunner from the Click library to simulate command-line invocations.

Functions:
    test_cli_probe_pass: Test the CLI probe command with valid input.
    test_cli_probe_pass_exec: Test the CLI probe command with a successful probe execution.
    test_cli_probe_fail_exec: Test the CLI probe command with a failed probe execution.
"""

import asyncio
from unittest.mock import Mock

import pytest
from asynctest import CoroutineMock
from click.testing import CliRunner

from netcfgbu.cli import probe


@pytest.fixture(autouse=True)
def _always(netcfgbu_envars, files_dir, monkeypatch):
    """Fixture that sets up environment variables required for the tests."""
    test_inv = files_dir.joinpath("test-small-inventory.csv")
    monkeypatch.setenv("NETCFGBU_INVENTORY", str(test_inv))


def test_cli_probe_pass(monkeypatch):
    """Test the CLI probe command with valid input.

    This test verifies that the CLI probe command succeeds with valid input
    and that the exec_probe function is called with the correct arguments.
    """
    mock_exec_probe = Mock()
    monkeypatch.setattr(probe, "exec_probe", mock_exec_probe)

    runner = CliRunner()
    res = runner.invoke(probe.cli_check, obj={"inventory_recs": [{} for _ in range(6)]})

    assert res.exit_code == 0
    assert mock_exec_probe.called
    call_args = mock_exec_probe.mock_calls[0].args
    inv_rec = call_args[0]
    assert len(inv_rec) == 6


def test_cli_probe_pass_exec(monkeypatch, log_vcr):
    """Test the CLI probe command with a successful probe execution.

    This test verifies that the CLI probe command succeeds and logs "PASS"
    for each inventory record when the probe function executes successfully.
    """
    mock_probe = CoroutineMock()
    monkeypatch.setattr(probe, "probe", mock_probe)

    runner = CliRunner()
    res = runner.invoke(probe.cli_check, obj={"inventory_recs": [{} for _ in range(6)]})
    assert res.exit_code == 0
    logs = log_vcr.handlers[0].records[1:]
    assert all("PASS" in log.msg for log in logs)


def test_cli_probe_fail_exec(monkeypatch, log_vcr):
    """Test the CLI probe command with a failed probe execution.

    This test verifies that the CLI probe command completes and logs "TimeoutError"
    for each inventory record when the probe function raises an exception.
    """
    # Mock the probe function to raise an asyncio.TimeoutError
    mock_probe = CoroutineMock()
    mock_probe.side_effect = asyncio.TimeoutError
    monkeypatch.setattr(probe, "probe", mock_probe)

    runner = CliRunner()
    res = runner.invoke(probe.cli_check, obj={"inventory_recs": [{} for _ in range(6)]})
    assert res.exit_code == 0
    logs = log_vcr.handlers[0].records[1:]
    assert all("TimeoutError" in log.msg for log in logs)
