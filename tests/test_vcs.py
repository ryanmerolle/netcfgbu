"""This file contains the pytest test cases for the vcs.git module."""

from pathlib import Path
from typing import Optional
from unittest.mock import Mock

import pytest  # noqa

from netcfgbu import config_model
from netcfgbu.vcs import git


def get_expected_commands(key_file: Optional[str] = None) -> list[str]:
    """Returns a list of expected git commands.

    If a keyfile is provided, includes the 'git remote add origin' command.
    Otherwise, excludes it from the list.

    Args:
        keyfile (Optional[str]): A string representing the keyfile. Defaults to None.

    Returns:
        List[str]: A list of git commands.
    """
    commands = [
        "git init",
        "git remote add origin git@dummy.git",
        "git config --local user.email dummy-user",
        "git config --local user.name dummy-user",
        "git config --local push.default matching",
    ]

    if key_file:
        commands.append(f"git config --local core.sshCommand 'ssh -i {key_file} -o StrictHostKeyChecking=no'")

    commands.append("git pull origin main")

    return commands


@pytest.fixture()
def mock_pexpect(monkeypatch):
    """Fixture to mock the pexpect module in the vcs.git module for testing.

    Args:
        monkeypatch: Pytest's monkeypatch fixture for modifying attributes.

    Returns:
        Mock: The mocked pexpect module.
    """
    mock_pexpect = Mock()
    mock_run = Mock()

    # we don't really care about the pexpect.run return value
    mock_run.return_value = ("", 0)
    mock_pexpect.run = mock_run
    monkeypatch.setattr(git, "pexpect", mock_pexpect)
    return mock_pexpect


def test_vcs_pass_prepare_token(mock_pexpect, tmpdir, monkeypatch):
    """Test the vcs_prepare function with a token-based Git configuration.

    This test verifies that the vcs_prepare function correctly initializes the
    Git repository and configures the user and remote origin when using a token-based
    authentication method.
    """
    monkeypatch.setenv("USER", "dummy-user")
    git_cfg = config_model.GitSpec(repo="git@dummy.git", token="dummy-token")
    repo_dir = tmpdir.join("repo")

    git.vcs_prepare(spec=git_cfg, repo_dir=Path(repo_dir))

    mock_run = mock_pexpect.run
    assert mock_run.called
    calls = mock_run.mock_calls

    expected_commands = get_expected_commands()

    assert len(calls) == len(expected_commands)
    for cmd_i, cmd in enumerate(expected_commands):
        assert calls[cmd_i].kwargs["command"] == cmd


def run_vcs_prepare_test(
    mock_pexpect: Mock,
    tmpdir: Path,
    monkeypatch: pytest.MonkeyPatch,
    deploy_key: Optional[str] = None,
    deploy_passphrase: Optional[str] = None
):
    """Helper function to run the vcs_prepare test with the given parameters.

    Args:
        mock_pexpect (Mock): The mocked pexpect module.
        tmpdir (Path): Temporary directory for test files.
        monkeypatch (pytest.MonkeyPatch): Pytest's monkeypatch fixture.
        deploy_key (Optional[str]): The deploy key for the Git configuration.
        deploy_passphrase (Optional[str]): The deploy key passphrase for the Git configuration.
    """
    monkeypatch.setenv("USER", "dummy-user")

    key_file = None
    if deploy_key:
        key_file = tmpdir.join("dummy-keyfile")
        key_file.ensure()
        key_file = str(key_file)

    git_cfg = config_model.GitSpec(
        repo="git@dummy.git",
        deploy_key=key_file if deploy_key else None,
        deploy_passphrase=deploy_passphrase,
    )

    repo_dir = tmpdir.join("repo")
    git.vcs_prepare(spec=git_cfg, repo_dir=Path(repo_dir))

    mock_run = mock_pexpect.run
    assert mock_run.called
    calls = mock_run.mock_calls

    expected_commands = get_expected_commands(key_file)

    assert len(calls) == len(expected_commands)
    for cmd_i, cmd in enumerate(expected_commands):
        assert calls[cmd_i].kwargs["command"] == cmd


def test_vcs_pass_prepare_deploykey(mock_pexpect, tmpdir, monkeypatch):
    """Test the vcs_prepare function with a deploy key-based Git configuration."""
    run_vcs_prepare_test(mock_pexpect, tmpdir, monkeypatch, deploy_key="dummy-keyfile")


def test_vcs_pass_prepare_deploykey_passphrase(mock_pexpect, tmpdir, monkeypatch):
    """Test the vcs_prepare function with a deploy key and passphrase-based Git configuration."""
    run_vcs_prepare_test(
        mock_pexpect, tmpdir, monkeypatch, deploy_key="dummy-keyfile", deploy_passphrase="dummy-key-passphrase"
    )


def test_vcs_pass_save(mock_pexpect, tmpdir, monkeypatch):
    """Test the vcs_save function with a token-based Git configuration.

    This test verifies that the vcs_save function correctly commits and pushes
    changes to the Git repository when using a token-based authentication method.
    """
    monkeypatch.setenv("USER", "dummy-user")

    git_cfg = config_model.GitSpec(repo="git@dummy.git", token="dummy-token")

    repo_dir = tmpdir.join("repo")

    mock_timestamp = Mock()
    mock_timestamp.return_value = "dummy-timestamp"
    monkeypatch.setattr(git, "generate_commit_message", mock_timestamp)

    git.vcs_save(gh_cfg=git_cfg, repo_dir=Path(repo_dir))

    mock_run = mock_pexpect.run
    assert mock_run.called
    calls = mock_run.mock_calls

    expected_commands = [
        "git status",
        "git add -A",
        "git commit -m 'dummy-timestamp'",
        "git push",
        # TODO - build tests for tags vs no tags
        # "git tag -a 'dummy-timestamp' -m 'dummy-timestamp'",
        # "git push --tags",
    ]

    assert len(calls) == len(expected_commands)
    for cmd_i, cmd in enumerate(expected_commands):
        assert calls[cmd_i].kwargs["command"] == cmd


def test_vcs_pass_save_nochange(monkeypatch, tmpdir, mock_pexpect):
    """Test the vcs_save function with no changes in the repository.

    This test verifies that the vcs_save function correctly skips the commit
    and push steps when there are no changes in the Git repository.
    """
    monkeypatch.setenv("USER", "dummy-user")

    git_cfg = config_model.GitSpec(repo="git@dummy.git", token="dummy-token")

    repo_dir = tmpdir.join("repo")

    mock_pexpect.run.return_value = ("nothing to commit", 0)
    git.vcs_save(gh_cfg=git_cfg, repo_dir=Path(repo_dir))

    mock_run = mock_pexpect.run
    assert mock_run.called
    calls = mock_run.mock_calls

    expected_commands = ["git status"]

    assert len(calls) == len(expected_commands)
    for cmd_i, cmd in enumerate(expected_commands):
        assert calls[cmd_i].kwargs["command"] == cmd


def test_vcs_pass_status(monkeypatch, tmpdir, mock_pexpect):
    """Test the vcs_status function with a token-based Git configuration.

    This test verifies that the vcs_status function correctly returns the status
    of the Git repository when using a token-based authentication method.
    """
    monkeypatch.setenv("USER", "dummy-user")
    git_cfg = config_model.GitSpec(repo="git@dummy.git", token="dummy-token")
    repo_dir = tmpdir.join("repo")

    mock_pexpect.run.return_value = ("nothing to commit", 0)
    result = git.vcs_status(spec=git_cfg, repo_dir=Path(repo_dir))
    assert result == "nothing to commit"


def test_vcs_pass_run_auth(monkeypatch, tmpdir, mock_pexpect):
    """Test the git_runner function w/ a token-based Git configuration & successful authentication.

    This test verifies that the git_runner function correctly runs Git commands
    with authentication when using a token-based authentication method.
    """
    monkeypatch.setenv("USER", "dummy-user")
    git_cfg = config_model.GitSpec(repo="git@dummy.git", token="dummy-token")
    repo_dir = Path(tmpdir.join("repo"))

    git_rnr = git.git_runner(git_cfg, repo_dir)
    mock_run = Mock()
    git_rnr.run = mock_run

    mock_pexpect.run.return_value = ("yipiee!", 0)
    git_rnr.git_clone()

    calls = mock_run.mock_calls
    expected_commands = [
        f"clone git@dummy.git {repo_dir}",
        "config --local user.email dummy-user",
        "config --local user.name dummy-user",
        "config --local push.default matching",
    ]

    assert len(calls) == len(expected_commands)
    for cmd_i, cmd in enumerate(expected_commands):
        assert calls[cmd_i].args[0] == cmd


def test_vcs_fail_run_auth(monkeypatch, tmpdir, mock_pexpect):
    """Test the git_runner function with a token-based Git configuration and failed authentication.

    This test verifies that the git_runner function correctly raises a RuntimeError
    when Git commands fail due to authentication issues while using a token-based
    authentication method.
    """
    monkeypatch.setenv("USER", "dummy-user")
    git_cfg = config_model.GitSpec(repo="git@dummy.git", token="dummy-token")
    repo_dir = Path(tmpdir.join("repo"))

    git_rnr = git.git_runner(git_cfg, repo_dir)

    mock_pexpect.run.return_value = ("fake-failure", 1)
    with pytest.raises(RuntimeError) as excinfo:
        git_rnr.git_clone()

    errmsg = excinfo.value.args[0]
    assert errmsg == "fake-failure"


def test_vcs_pass_git_config(monkeypatch, tmpdir, mock_pexpect):
    """Test the git_config function with a token-based Git configuration.

    This test verifies that the git_config function correctly configures the
    Git repository settings (such as user email, name, and push behavior) when
    using a token-based authentication method.
    """
    monkeypatch.setenv("USER", "dummy-user")
    git_cfg = config_model.GitSpec(repo="https://github@dummy.git", token="dummy-token")
    repo_dir = Path(tmpdir.join("repo"))
    repo_dir.mkdir()

    git_rnr = git.git_runner(git_cfg, repo_dir)

    assert git_rnr.repo_url == "https://dummy-user@github@dummy.git"
    assert git_rnr.is_dir_empty is True

    git_rnr.git_config()

    expected_commands = [
        "git config --local user.email dummy-user",
        "git config --local user.name dummy-user",
        "git config --local push.default matching",
    ]

    calls = mock_pexpect.run.mock_calls

    assert len(calls) == len(expected_commands)
    for cmd_i, cmd in enumerate(expected_commands):
        assert calls[cmd_i].kwargs["command"] == cmd


def test_vcs_fail_run_noauth(monkeypatch, tmpdir, mock_pexpect):
    """Test the run function with a non-authenticated Git configuration & failed command execution.

    This test verifies that the run function correctly raises a RuntimeError
    when Git commands fail due to non-authentication issues while using a
    non-authenticated Git configuration.
    """
    monkeypatch.setenv("USER", "dummy-user")
    git_cfg = config_model.GitSpec(repo="https://github@dummy.git", token="dummy-token")
    repo_dir = Path(tmpdir.join("repo"))

    git_rnr = git.git_runner(git_cfg, repo_dir)

    mock_pexpect.run.return_value = ("fake-failure", 1)
    with pytest.raises(RuntimeError) as excinfo:
        git_rnr.run("status")

    errmsg = excinfo.value.args[0]
    assert errmsg == "git status failed: fake-failure"
