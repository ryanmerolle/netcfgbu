"""Tests for the configuration handling in the netcfgbu package.

This module contains tests for various configuration scenarios in the netcfgbu
package. It uses pytest for testing.

Functions:
    test_config_credentials_fail_emptyvar: Test the case where a required credential environment variable is empty.
    test_config_credentials_fail_missingvar: Test the case where a required credential environment variable is missing.
    test_config_credentials_pass_usesvar: Test the case where credentials are correctly used from environment variables.
    test_config_fail_asfilepath: Test the case where the configuration file path is invalid.
    test_config_git_fail_badrepo: Test the case where the Git repository is invalid.
    test_config_git_pass: Test the case where the Git repository is valid.
    test_config_inventory_fail_noscript: Test the case where the inventory script is missing.
    test_config_inventory_fail_script_noexec: Test the case where the inventory script is not executable.
    test_config_inventory_pass: Test the case where the inventory script is valid.
"""

import os
from io import StringIO
from pathlib import Path

import pytest
import toml
from first import first
from pydantic import ValidationError

from netcfgbu import config_model
from netcfgbu.config import load


def test_config_onlyenvars_pass(monkeypatch, netcfgbu_envars):
    """Execute a test where there is no configuration file.
    In this case, the NETCFGBU_<fieldname> environment variables must exist.
    """
    app_cfg = load()

    assert app_cfg.defaults.inventory == os.getenv("NETCFGBU_INVENTORY")
    assert app_cfg.defaults.credentials.username == os.getenv("NETCFGBU_DEFAULT_USERNAME")
    assert app_cfg.defaults.credentials.password.get_secret_value() == os.getenv(
        "NETCFGBU_DEFAULT_PASSWORD"
    )


def test_config_onlyenvars_fail_missing(monkeypatch):
    """Execute a test where there is no configuration file.
    Omit the default environment variables and ensure that an exception is raised as expected.
    """
    monkeypatch.delenv("NETCFGBU_INVENTORY", raising=False)
    monkeypatch.delenv("NETCFGBU_DEFAULT_USERNAME", raising=False)
    monkeypatch.delenv("NETCFGBU_DEFAULT_PASSWORD", raising=False)

    with pytest.raises(RuntimeError) as excinfo:
        load()

    exc_errmsg = excinfo.value.args[0]
    expected_envars = [
        "defaults.NETCFGBU_INVENTORY",
        "defaults.credentials.NETCFGBU_DEFAULT_USERNAME",
        "defaults.credentials.NETCFGBU_DEFAULT_PASSWORD",
    ]
    for expected in expected_envars:
        assert expected in exc_errmsg


def test_config_onlyenvars_fail_bad_noinventory(monkeypatch):
    """Test the case where NETCFGBU_INVENTORY is set but empty, &
    it generates an exception message.
    """
    monkeypatch.setenv("NETCFGBU_INVENTORY", "")

    with pytest.raises(RuntimeError) as excinfo:
        load()

    exc_errmsgs = excinfo.value.args[0].splitlines()
    found = first([line for line in exc_errmsgs if "defaults.NETCFGBU_INVENTORY" in line])
    assert found
    assert "inventory empty value not allowed" in found


def test_config_credentials_fail_missingvar(request, monkeypatch, fake_inventory_file):
    """Test the case where the [[credentials]] section uses an environment variable,
    and that environment variable is missing.
    """
    fileio = open(f"{request.fspath.dirname}/files/test-credentials.toml")

    monkeypatch.delenv("ENABLE_PASSWORD", raising=False)

    with pytest.raises(EnvironmentError, match="Environment variable 'ENABLE_PASSWORD' missing."):
        load(fileio=fileio)


def test_config_credentials_fail_emptyvar(request, monkeypatch, netcfgbu_envars):
    """Test the case where the [[credentials]] section uses an environment variable,
    and that environment variable exists but is set to an empty string.
    """
    fileio = open(f"{request.fspath.dirname}/files/test-credentials.toml")
    monkeypatch.setenv("ENABLE_PASSWORD", "")

    with pytest.raises(EnvironmentError, match="Environment variable 'ENABLE_PASSWORD' empty."):
        load(fileio=fileio)


def test_config_credentials_pass_usesvar(request, monkeypatch, netcfgbu_envars):
    """Test the case where the [[credentials]] section uses an environment variable,
    and that environment variable is set to a non-empty value.
    """
    fileio = open(f"{request.fspath.dirname}/files/test-credentials.toml")
    monkeypatch.setenv("ENABLE_PASSWORD", "foobaz")
    app_cfg = load(fileio=fileio)
    assert app_cfg.credentials[0].password.get_secret_value() == "foobaz"


def test_config_git_pass(request, netcfgbu_envars, monkeypatch):
    """Test the case where a [[git]] section is properly configured."""
    files_dir = Path(request.fspath.dirname).joinpath("files")
    monkeypatch.setenv("GIT_TOKEN", "fake-token")
    monkeypatch.setenv("GITKEY_PASSWORD", "fake-password")
    monkeypatch.setenv("GITKEY_DIR", str(files_dir.absolute()))
    fileio = files_dir.joinpath("test-gitspec.toml").open()
    app_cfg = load(fileio=fileio)

    assert app_cfg.git[0].token.get_secret_value() == "fake-token"
    assert app_cfg.git[2].deploy_passphrase.get_secret_value() == "fake-password"


def test_config_git_fail_badrepo(request, netcfgbu_envars):
    """Test the case where a [[git]] section has an improper GIT URL."""
    fileio = open(f"{request.fspath.dirname}/files/test-gitspec-badrepo.toml")
    with pytest.raises(RuntimeError) as excinfo:
        load(fileio=fileio)

    exc_errmsgs = excinfo.value.args[0].splitlines()
    found = first([line for line in exc_errmsgs if "git.0.repo" in line])
    assert found
    assert "Bad repo URL" in found


def test_config_inventory_pass(request, monkeypatch, netcfgbu_envars):
    """Test the case where an [[inventory]] section is properly configured."""
    files_dir = request.fspath.dirname + "/files"
    monkeypatch.setenv("SCRIPT_DIR", files_dir)
    fileio = open(f"{files_dir}/test-inventory.toml")
    load(fileio=fileio)


def test_config_inventory_fail_noscript(request, netcfgbu_envars):
    """Test the case where an [[inventory]] section defines a script, but the
    script does not exist.
    """
    fileio = open(f"{request.fspath.dirname}/files/test-inventory-fail.toml")
    with pytest.raises(RuntimeError) as excinfo:
        load(fileio=fileio)

    exc_errmsgs = excinfo.value.args[0].splitlines()
    found = first([line for line in exc_errmsgs if "inventory.0.script" in line])
    assert found
    assert "File not found:" in found


def test_config_inventory_fail_script_noexec(netcfgbu_envars, tmpdir):
    """Test the case where an [[inventory]] section defines a script, the script
    file exists, but the script file is not executable.
    """
    fake_script = tmpdir.join("dummy-script.sh")
    fake_script.ensure()

    config_data = {"inventory": [{"name": "foo", "script": str(fake_script)}]}

    strio = StringIO()
    strio.name = "fake-file"
    toml.dump(config_data, strio)
    strio.seek(0)

    with pytest.raises(RuntimeError) as excinfo:
        load(fileio=strio)

    exc_errmsgs = excinfo.value.args[0].splitlines()
    found = first([line for line in exc_errmsgs if "inventory.0.script" in line])
    assert found
    assert "is not executable" in found


def test_config_linter_pass(netcfgbu_envars, request):
    """Test the case where an [os_name] section defines a linter, and that
    linter exists; no errors expected.
    """
    fileio = open(f"{request.fspath.dirname}/files/test-linter.toml")
    app_cfg = load(fileio=fileio)

    assert app_cfg.os_name["ios"]
    assert app_cfg.os_name["ios"].linter == "ios"
    assert app_cfg.linters["ios"]


def test_config_linter_fail(netcfgbu_envars, request):
    """Test the case where an [os_name] section defines a linter, but that
    linter is not defined in the configuration.
    """
    fileio = open(f"{request.fspath.dirname}/files/test-linter-fail.toml")

    with pytest.raises(RuntimeError) as excinfo:
        load(fileio=fileio)

    exc_errmsgs = excinfo.value.args[0].splitlines()
    found = first([line for line in exc_errmsgs if "os_name" in line])
    assert 'OS spec "ios" using undefined linter "ios"' in found


def test_config_pass_noexistdir(tmpdir, netcfgbu_envars, monkeypatch):
    """Test use-case where the provided configs-dir directory does not
    exist in the configuration; but as a result the configs-dir is
    created.
    """
    dirpath = tmpdir.join("dummy-dir")
    monkeypatch.setenv("NETCFGBU_CONFIGSDIR", str(dirpath))
    app_cfg = load()

    configs_dir: Path = app_cfg.defaults.configs_dir
    assert configs_dir == dirpath
    assert configs_dir.exists()


def test_plugins_pass_noexistdir(tmpdir, netcfgbu_envars, monkeypatch):
    """Test use-case where the provided configs-dir directory does not
    exist in the configuration; but as a result, the configs-dir is created.
    """
    dirpath = tmpdir.join("dummy-dir")
    monkeypatch.setenv("NETCFGBU_PLUGINSDIR", str(dirpath))
    app_cfg = load()

    plugins_dir: Path = app_cfg.defaults.plugins_dir
    assert plugins_dir == dirpath
    assert plugins_dir.exists()


def test_config_pass_asfilepath(request):
    """Test use-case where the config is provided as a filepath, and the file exists."""
    abs_filepath = f"{request.fspath.dirname}/files/test-just-defaults.toml"
    load(filepath=abs_filepath)


def test_config_fail_asfilepath(tmpdir):
    """Test use-case where the config is provided as a filepath, and the file
    does not exist.
    """
    noexist_filepath = str(tmpdir.join("noexist"))

    with pytest.raises(FileNotFoundError) as excinfo:
        load(filepath=noexist_filepath)

    assert excinfo.value.filename == noexist_filepath


def test_config_jumphost_name(netcfgbu_envars, request):
    """Test the case where jumphost name is correctly set from the config."""
    abs_filepath = request.fspath.dirname + "/files/test-config-jumphosts.toml"
    app_cfg = load(filepath=abs_filepath)
    jh = app_cfg.jumphost[0]
    assert jh.name == jh.proxy

    jh = app_cfg.jumphost[1]
    assert jh.name != jh.proxy


def test_vcs_fail_config(tmpdir):
    """Test validation errors in GitSpec configuration."""
    fake_key = tmpdir.join("fake-key")
    fake_key.ensure()
    fake_key = str(fake_key)

    with pytest.raises(ValidationError) as excinfo:
        config_model.GitSpec(repo="git@dummy.git", password="fooer", deploy_passphrase="foobaz")

    errs = excinfo.value.errors()
    assert "deploy_key required when using deploy_passphrase" in errs[0]["msg"]

    with pytest.raises(ValidationError) as excinfo:
        config_model.GitSpec(repo="git@dummy.git")

    errs = excinfo.value.errors()
    assert "Missing one of required auth method fields" in errs[0]["msg"]

    with pytest.raises(ValidationError) as excinfo:
        config_model.GitSpec(repo="git@dummy.git", token="token", deploy_key=fake_key)

    errs = excinfo.value.errors()
    assert "Only one of" in errs[0]["msg"]
