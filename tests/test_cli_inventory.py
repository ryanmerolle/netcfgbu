"""Test suite for the CLI inventory commands in the netcfgbu module.

This module contains tests for various CLI commands related to inventory management.
It uses pytest fixtures and the CliRunner from the Click library to simulate
command-line invocations and validate the behavior of the CLI.
"""

from pathlib import Path
from unittest.mock import Mock

import pytest
from click.testing import CliRunner

from netcfgbu.cli import inventory


@pytest.fixture(autouse=True)
def _always(netcfgbu_envars: pytest.FixtureRequest) -> None:
    """Fixture that applies the netcfgbu_envars fixture automatically to all tests."""
    pass


@pytest.fixture()
def mock_build(monkeypatch: pytest.MonkeyPatch) -> Mock:
    """Fixture that mocks the build function in the inventory module.

    Args:
        monkeypatch (pytest.MonkeyPatch): Pytest's monkeypatch fixture for modifying attributes.

    Returns:
        Mock: The mocked build function.
    """
    mock = Mock()
    monkeypatch.setattr(inventory, "build", mock)
    return mock


def test_cli_inventory_fail_noinventoryfile() -> None:
    """Test CLI inventory command when no inventory file is present.

    This test verifies that the CLI command fails with an appropriate error message
    when the inventory file is missing.
    """
    runner = CliRunner()

    with runner.isolated_filesystem():
        res = runner.invoke(inventory.cli_inventory_list, obj={})

    assert res.exit_code != 0
    assert "Inventory file does not exist" in res.output


def test_cli_inventory_pass(files_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Test CLI inventory command with a valid inventory file.

    This test verifies that the CLI command succeeds when a valid inventory file is provided.

    Args:
        files_dir (Path): The directory containing the test files.
        monkeypatch (pytest.MonkeyPatch): Pytest's monkeypatch fixture to modify environment variables.
    """
    test_cfg = files_dir.joinpath("test-inventory-script-donothing.toml")
    test_inv = files_dir.joinpath("test-small-inventory.csv")

    monkeypatch.setenv("NETCFGBU_INVENTORY", str(test_inv))
    monkeypatch.setenv("SCRIPT_DIR", str(files_dir))
    monkeypatch.setenv("NETCFGBU_CONFIG", str(test_cfg))

    runner = CliRunner()
    res = runner.invoke(inventory.cli_inventory_list, obj={})
    assert res.exit_code == 0


def test_cli_inventory_fail_limits_zero(files_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Test CLI inventory command with a filter that excludes all inventory.

    This test verifies that the CLI command fails with an appropriate error message
    when the provided filter excludes all inventory items.

    Args:
        files_dir (Path): The directory containing the test files.
        monkeypatch (pytest.MonkeyPatch): Pytest's monkeypatch fixture to modify environment variables.
    """
    test_inv = files_dir.joinpath("test-small-inventory.csv")
    monkeypatch.setenv("NETCFGBU_INVENTORY", str(test_inv))

    runner = CliRunner()
    res = runner.invoke(inventory.cli_inventory_list, obj={}, args=["--exclude", "os_name=.*"])

    assert res.exit_code != 0
    assert "No inventory matching limits" in res.output


def test_cli_inventory_fail_limits_invalid(files_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Test CLI inventory command with an invalid filter expression.

    This test verifies that the CLI command fails with an appropriate error message
    when the provided filter expression is invalid.

    Args:
        files_dir (Path): The directory containing the test files.
        monkeypatch (pytest.MonkeyPatch): Pytest's monkeypatch fixture to modify environment variables.
    """
    test_inv = files_dir.joinpath("test-small-inventory.csv")
    monkeypatch.setenv("NETCFGBU_INVENTORY", str(test_inv))

    runner = CliRunner()
    res = runner.invoke(inventory.cli_inventory_list, obj={}, args=["--limit", "foo=bar"])

    assert res.exit_code != 0
    assert "Invalid filter expression" in res.output


def test_cli_inventory_fail_build() -> None:
    """Test CLI build command when no configuration file is provided.

    This test verifies that the CLI build command fails with an appropriate error message
    when no configuration file is provided.
    """
    runner = CliRunner()
    res = runner.invoke(inventory.cli_inventory_build, obj={})
    assert res.exit_code != 0
    assert "Configuration file required for use with build subcommand" in res.output


def test_cli_inventory_pass_build(files_dir: Path, mock_build: Mock, monkeypatch: pytest.MonkeyPatch) -> None:
    """Test CLI build command with a valid configuration file.

    This test verifies that the CLI build command succeeds when a valid configuration
    file is provided and that the build function is called.

    Args:
        files_dir (Path): The directory containing the test files.
        mock_build (Mock): The mocked build function.
        monkeypatch (pytest.MonkeyPatch): Pytest's monkeypatch fixture to modify environment variables.
    """
    test_cfg = files_dir.joinpath("test-inventory-script-donothing.toml")

    monkeypatch.setenv("SCRIPT_DIR", str(files_dir))
    monkeypatch.setenv("NETCFGBU_CONFIG", str(test_cfg))

    runner = CliRunner()
    res = runner.invoke(inventory.cli_inventory_build, obj={})

    assert res.exit_code == 0
    assert mock_build.called is True
    inv_spec = mock_build.mock_calls[0].args[0]
    assert inv_spec.script.endswith("do-nothing.sh")


def run_cli_inventory_build_test(
    files_dir: Path, monkeypatch: pytest.MonkeyPatch, args: list[str]
):
    """Helper function to run the CLI inventory build test with the given parameters.

    Args:
        files_dir (Path): The directory containing test files.
        monkeypatch (pytest.MonkeyPatch): Pytest's monkeypatch fixture.
        args (List[str]): The arguments to pass to the CLI command.

    Returns:
        click.testing.Result: The result of the CLI invocation.
    """
    test_cfg = files_dir.joinpath("test-inventory-script-donothing.toml")

    monkeypatch.setenv("SCRIPT_DIR", str(files_dir))
    monkeypatch.setenv("NETCFGBU_CONFIG", str(test_cfg))

    runner = CliRunner()
    return runner.invoke(inventory.cli_inventory_build, obj={}, args=args)


def test_cli_inventory_pass_build_name(files_dir: Path, mock_build: Mock, monkeypatch: pytest.MonkeyPatch) -> None:
    """Test CLI build command with a specific inventory name.

    Args:
        files_dir (Path): The directory containing test files.
        mock_build (Mock): The mocked build function.
        monkeypatch (pytest.MonkeyPatch): Pytest's monkeypatch fixture to modify environment variables.
    """
    res = run_cli_inventory_build_test(files_dir, monkeypatch, args=["--name=dummy"])
    assert res.exit_code == 0
    assert mock_build.called is True
    inv_spec = mock_build.mock_calls[0].args[0]
    assert inv_spec.name == "dummy"


def test_cli_inventory_fail_build_badname(files_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Test CLI build command with an invalid inventory name.

    Args:
        files_dir (Path): The directory containing test files.
        monkeypatch (pytest.MonkeyPatch): Pytest's monkeypatch fixture to modify environment variables.
    """
    res = run_cli_inventory_build_test(files_dir, monkeypatch, args=["--name=noexists"])
    assert res.exit_code != 0
    assert "Inventory section 'noexists' not defined in configuration file" in res.output
