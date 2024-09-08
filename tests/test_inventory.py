import pytest  # noqa
from first import first

from netcfgbu import config, inventory


def test_inventory_pass(request, monkeypatch, netcfgbu_envars) -> None:
    """Tests loading a properly formatted small inventory file.

    Validates both loading all records and loading a filtered subset.
    """
    inventory_fpath = f"{request.fspath.dirname}/files/test-small-inventory.csv"
    monkeypatch.setenv("NETCFGBU_INVENTORY", inventory_fpath)
    app_cfg = config.load()

    # all records
    inv_recs = inventory.load(app_cfg)
    assert len(inv_recs) == 6

    # filter records
    inv_recs = inventory.load(app_cfg, limits=["os_name=eos"], excludes=["host=switch1"])
    assert len(inv_recs) == 1
    assert inv_recs[0]["host"] == "switch2"


def test_inventory_fail_nofilegiven(tmpdir, netcfgbu_envars) -> None:
    """Tests failure when the configuration specifies an inventory file that does not exist."""
    app_cfg = config.load()

    with pytest.raises(FileNotFoundError) as excinfo:
        inventory.load(app_cfg)

    errmsg = excinfo.value.args[0]
    assert "Inventory file does not exist" in errmsg


def test_inventory_pass_build(request, monkeypatch, netcfgbu_envars) -> None:
    """Tests a successful inventory build where the script exists and runs without error."""
    files_dir = request.fspath.dirname + "/files"
    monkeypatch.setenv("SCRIPT_DIR", files_dir)
    config_fpath = files_dir + "/test-inventory-script-donothing.toml"
    app_cfg = config.load(filepath=config_fpath)
    inv_def = app_cfg.inventory[0]
    rc = inventory.build(inv_def)
    assert rc == 0


def test_inventory_fail_build_exitnozero(request, monkeypatch, netcfgbu_envars) -> None:
    """Tests failure when an inventory build script exists but exits with a non-zero return code."""
    files_dir = request.fspath.dirname + "/files"
    monkeypatch.setenv("SCRIPT_DIR", files_dir)
    config_fpath = files_dir + "/test-inventory-script-fails.toml"

    app_cfg = config.load(filepath=config_fpath)
    inv_def = app_cfg.inventory[0]
    rc = inventory.build(inv_def)

    assert rc != 0


def test_inventory_fail_build_noscript(request, netcfgbu_envars) -> None:
    """Tests failure when the configuration lacks a required inventory build script.

    Ensures the script is missing and raises the appropriate error.
    """
    config_fpath = f"{request.fspath.dirname}/files/test-inventory-noscript.toml"
    with pytest.raises(RuntimeError) as excinfo:
        config.load(filepath=config_fpath)

    exc_errmsgs = excinfo.value.args[0].splitlines()
    found = first([line for line in exc_errmsgs if "inventory.0.script" in line])
    assert found
    assert "Field required" in found
