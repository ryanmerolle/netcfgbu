"""Tests for the linters module in the netcfgbu package.

This module contains tests for various linter functionalities in the
netcfgbu package. It uses pytest for testing.

Functions:
    test_linter_detection: Test the detection of linters.
    test_linter_execution: Test the execution of linters.
    test_linter_output_parsing: Test the parsing of linter output.
"""

from pathlib import Path

from netcfgbu import config_model, linter


def test_linters_pass_content(files_dir):
    """Test linter with content from a file.

    Verifies that the `lint_content` function properly extracts the desired content
    between the start and end markers.

    Args:
        files_dir: Directory containing the test files.
    """
    good_content = files_dir.joinpath("test-content-config.txt").read_text()
    lint_spec = config_model.LinterSpec(
        config_starts_after="!Time:", config_ends_at="! end-test-marker"
    )

    lint_content = (
        """\
!Command: show running-config
!Time: Sat Jun 27 17:54:17 2020
"""
        + good_content
        + """
! end-test-marker"""
    )

    result = linter.lint_content(lint_spec=lint_spec, config_content=lint_content)
    assert result == good_content


def test_liners_pass_file(files_dir, tmpdir):
    """Test linter with a file.

    Verifies that the `lint_file` function properly processes a file and
    extracts the desired content between the start and end markers.

    Args:
        files_dir: Directory containing the test files.
        tmpdir: Temporary directory for storing intermediate files.
    """
    exp_content = files_dir.joinpath("test-content-config.txt").read_text()
    lint_spec = config_model.LinterSpec(
        config_starts_after="!Time:", config_ends_at="! end-test-marker"
    )

    tmp_file = Path(tmpdir.join("content"))
    tmp_file.write_text(
        """\
!Command: show running-config
!Time: Sat Jun 27 17:54:17 2020
"""
        + exp_content
        + """
! end-test-marker"""
    )

    linter.lint_file(tmp_file, lint_spec=lint_spec)
    linted_content = tmp_file.read_text()
    assert linted_content == exp_content


def test_liners_pass_nochange(files_dir, tmpdir, log_vcr, monkeypatch):
    """Test linter with no changes in content.

    Verifies that the `lint_file` function properly detects that no changes
    are needed in the content and logs the appropriate message.

    Args:
        files_dir: Directory containing the test files.
        tmpdir: Temporary directory for storing intermediate files.
        log_vcr: Logger for capturing log output.
        monkeypatch: Fixture for modifying behavior of imports.
    """
    exp_content = files_dir.joinpath("test-content-config.txt").read_text()
    lint_spec = config_model.LinterSpec(
        config_starts_after="!Time:", config_ends_at="! end-test-marker"
    )

    tmp_file = Path(tmpdir.join("content"))
    tmp_file.write_text(exp_content)

    monkeypatch.setattr(linter, "log", log_vcr)

    changed = linter.lint_file(tmp_file, lint_spec=lint_spec)

    assert changed is False
    linted_content = tmp_file.read_text()
    assert linted_content == exp_content
    last_log = log_vcr.handlers[0].records[-1].msg
    assert "LINT no change on" in last_log
