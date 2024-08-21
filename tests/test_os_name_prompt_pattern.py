"""Tests for the OS name prompt pattern module in the netcfgbu package.

This module contains tests for various OS name prompt pattern functionalities in the
netcfgbu package. It uses pytest for testing.
"""

import re

from netcfgbu import os_specs
from netcfgbu.config import load
from netcfgbu.connectors import BasicSSHConnector


def test_config_os_name_prompt_pattern(netcfgbu_envars, request):  # noqa
    """Tests that a user-defined prompt pattern in [os_name.$name] is correctly applied."""
    rec = {"host": "dummy", "os_name": "cumulus"}
    abs_filepath = request.fspath.dirname + "/files/test-config-os-name-prompt-pattern.toml"
    app_cfg = load(filepath=abs_filepath)
    conn = os_specs.make_host_connector(rec, app_cfg)

    # this value is copied from the configuration toml file.  If you
    # change the test data file then you'd have to change this expected pattern.
    expected_pattern = r"[a-z0-9.\-@:~]{10,65}\s*[#$]"

    # the conenctor code adds a capture group for processing reasons.
    expected_pattern = r"^\r?(" + expected_pattern + r")\s*$"
    expected_re = re.compile(expected_pattern.encode("utf-8"))

    # going to perform a PROMPT pattern match against a sample value.
    test_prompt_value = "cumulus@leaf01:mgmt-vrf:~$"

    assert isinstance(conn, BasicSSHConnector)
    assert expected_re.pattern == conn.prompt_pattern.pattern
    assert expected_re.match(test_prompt_value.encode("utf-8"))
