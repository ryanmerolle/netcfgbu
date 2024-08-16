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
def inventory(request):
    test_dir = Path(request.module.__file__).parent
    inv_fp = test_dir / "files/test-small-inventory.csv"
    return list(CommentedCsvReader(inv_fp.open()))


@pytest.fixture()
def mock_asyncssh_connect(monkeypatch):
    monkeypatch.setattr(jumphosts, "asyncssh", Mock())

    jumphosts.asyncssh.Error = asyncssh.Error
    jumphosts.asyncssh.connect = CoroutineMock()
    return jumphosts.asyncssh.connect


def test_jumphosts_pass_noused(inventory):
    # without an include or exclude, this jump host will not be used
    # TODO: consider this an error in config-model validation?

    jh_spec = config_model.JumphostSpec(proxy="1.2.3.4")

    jumphosts.init_jumphosts(jumphost_specs=[jh_spec], inventory=inventory)
    assert len(jumphosts.JumpHost.available) == 0


def test_jumphosts_pass_incused(inventory):
    # include on EOS devices to be used in the jump host, this will result in
    # the jump host being required by 4 of the devices in the inventory

    jh_spec = config_model.JumphostSpec(proxy="1.2.3.4", include=["os_name=eos"])

    jumphosts.init_jumphosts(jumphost_specs=[jh_spec], inventory=inventory)
    assert len(jumphosts.JumpHost.available) == 1

    jh_use_count = Counter(
        getattr(jumphosts.get_jumphost(rec), "name", None) for rec in inventory
    )

    assert jh_use_count["1.2.3.4"] == 2


def test_jumphosts_pass_exlused(inventory):
    # exclude EOS devices to be used in the jump host, this will result in the
    # jump host being required

    jh_spec = config_model.JumphostSpec(proxy="1.2.3.4", exclude=["os_name=eos"])

    jumphosts.init_jumphosts(jumphost_specs=[jh_spec], inventory=inventory)
    assert len(jumphosts.JumpHost.available) == 1

    jh_use_count = Counter(
        getattr(jumphosts.get_jumphost(rec), "name", None) for rec in inventory
    )

    assert jh_use_count["1.2.3.4"] == 4


def test_jumphosts_pass_exlallused(inventory):
    # exclude all OS names will result in no jump hosts required

    jh_spec = config_model.JumphostSpec(proxy="1.2.3.4", exclude=["os_name=.*"])

    jumphosts.init_jumphosts(jumphost_specs=[jh_spec], inventory=inventory)
    assert len(jumphosts.JumpHost.available) == 0


@pytest.mark.asyncio
async def test_jumphosts_fail_connect(
    netcfgbu_envars, log_vcr, inventory, mock_asyncssh_connect, monkeypatch
):
    monkeypatch.setattr(jumphosts, "get_logger", Mock(return_value=log_vcr))

    jh_spec = config_model.JumphostSpec(
        proxy="dummy-user@1.2.3.4:8022", exclude=["os_name=eos"]
    )

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

    # Manually format the log messages before comparison
    expected_timeout_log = "JUMPHOST: connect to dummy-user@1.2.3.4:8022 failed: TimeoutError"
    expected_error_log = "JUMPHOST: connect to dummy-user@1.2.3.4:8022 failed: nooooope"

    assert log_recs[-2].getMessage() == expected_timeout_log
    assert log_recs[-1].getMessage() == expected_error_log
