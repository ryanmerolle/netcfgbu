"""Tests for the CLI VCS commands in the netcfgbu module.

This module contains tests for various CLI commands related to version control
system (VCS) functionality. It uses pytest for testing.

Functions:
    test_cli_vcs_fail_missingconfig_file: Test the case where the VCS configuration file is missing.
    test_cli_vcs_fail_missingconfig_section: Test the case where the VCS configuration section is missing.
"""

from operator import itemgetter
from pathlib import Path
from unittest.mock import Mock

import pytest
from click.testing import CliRunner

from netcfgbu.cli import vcs


@pytest.fixture(scope="module")
def files_dir(request):
    """Fixture to provide the path to the 'files' directory for test data.

    Args:
        request: The pytest request object.

    Returns:
        Path: The path to the 'files' directory.
    """
    return Path(request.module.__file__).parent.joinpath("files")


@pytest.fixture(scope="module")
def config_file(files_dir):
    """Fixture to provide the path to the test VCS configuration file.

    Args:
        files_dir: The path to the 'files' directory.

    Returns:
        Path: The path to the VCS configuration file.
    """
    return files_dir.joinpath("test-vcs.toml")


@pytest.fixture(autouse=True)
def _vcs_each_test(monkeypatch, netcfgbu_envars):
    """Fixture that sets up the environment and monkeypatches logging for each test."""
    # need to monkeypatch the logging to avoid a conflict with the Click test
    # runner also trying to stdout.
    monkeypatch.setenv("GIT_TOKEN", "dummy-token")
    monkeypatch.setattr(vcs, "stop_aiologging", Mock())


@pytest.fixture()
def mock_git(monkeypatch):
    """Fixture to mock the git module in the VCS module for testing.

    Args:
        monkeypatch: Pytest's monkeypatch fixture for modifying attributes.

    Returns:
        Mock: The mocked git module.
    """
    monkeypatch.setattr(vcs, "git", Mock(spec=vcs.git))
    return vcs.git


def test_cli_vcs_fail_missingconfig_file():
    """Test the CLI VCS status command with a missing configuration file.

    This test verifies that the CLI command fails with an appropriate error message
    when no configuration file is provided.
    """
    runner = CliRunner()

    # isolate the file system so it doesn't accidentally pick up the sample
    # "netcfgbu.toml" in the project directory.

    with runner.isolated_filesystem():
        res = runner.invoke(vcs.cli_vcs_status, obj={})

    assert res.exit_code != 0
    assert "No configuration file provided" in res.output


def test_cli_vcs_fail_missingconfig_section(files_dir, monkeypatch):
    """Test the CLI VCS status command with a missing VCS config section.

    This test verifies that the CLI command fails with an appropriate error message
    when the VCS config section is not found in the configuration file.
    """
    # select a test inventory file that does not contain any VCS configuration
    cfg_file = files_dir.joinpath("test-config-logging.toml")

    runner = CliRunner()

    # isolate the file system so it doesn't accidentally pick up the sample
    # "netcfgbu.toml" in the project directory.

    with runner.isolated_filesystem():
        res = runner.invoke(vcs.cli_vcs_status, obj={}, args=["-C", str(cfg_file)])

    assert res.exit_code != 0
    assert "No vcs config section found" in res.output


def test_cli_vcs_pass_status(mock_git: Mock, config_file, monkeypatch):
    """Test the CLI VCS status command with a valid configuration file.

    This test verifies that the CLI command succeeds when a valid configuration
    file is provided and that the vcs_status function is called with the correct arguments.
    """
    runner = CliRunner()
    res = runner.invoke(vcs.cli_vcs_status, obj={}, args=["-C", str(config_file)])

    assert res.exit_code == 0
    assert mock_git.vcs_status.called
    kwargs = mock_git.vcs_status.mock_calls[0].kwargs
    git_spec = kwargs["spec"]
    assert git_spec.repo == "git@dummy.git"
    assert git_spec.token.get_secret_value() == "dummy-token"


def test_cli_vcs_pass_prepare(mock_git: Mock, config_file, monkeypatch):
    """Test the CLI VCS prepare command with a valid configuration file.

    This test verifies that the CLI command succeeds when a valid configuration
    file is provided and that the vcs_prepare function is called with the correct arguments.
    """
    monkeypatch.setenv("NETCFGBU_CONFIGSDIR", "/tmp/configs")

    runner = CliRunner()
    res = runner.invoke(vcs.cli_vcs_prepare, obj={}, args=["-C", str(config_file)])

    assert res.exit_code == 0
    assert mock_git.vcs_prepare.called
    kwargs = mock_git.vcs_prepare.mock_calls[0].kwargs
    git_spec, repo_dir = kwargs["spec"], kwargs["repo_dir"]
    assert git_spec.repo == "git@dummy.git"
    assert str(repo_dir) == "/tmp/configs"


def test_cli_vcs_pass_save_tag_notgiven(mock_git: Mock, config_file, monkeypatch):
    """Test the CLI VCS save command without a tag.

    This test verifies that the CLI command succeeds when no tag is provided
    and that the vcs_save function is called with the correct arguments.
    """
    monkeypatch.setenv("NETCFGBU_CONFIGSDIR", "/tmp/configs")
    runner = CliRunner()
    res = runner.invoke(vcs.cli_vcs_save, obj={}, args=["-C", str(config_file)])
    assert res.exit_code == 0
    assert mock_git.vcs_save.called
    repo_dir, message = itemgetter("repo_dir", "message")(mock_git.vcs_save.mock_calls[0].kwargs)
    assert str(repo_dir) == "/tmp/configs"
    assert message is None
