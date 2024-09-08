"""Tests for the connectors module in the netcfgbu package.

This module contains tests for various connector classes and functions in the
netcfgbu package. It uses pytest for testing.

Functions:
    test_connectors_pass: Test the default connector class retrieval.
    test_connectors_pass_named: Test named connector class retrieval.
    test_connectors_fail_named: Test connector class retrieval with an invalid name.
"""

import pytest  # noqa

from netcfgbu import connectors


def test_connectors_pass():
    """Test the default connector class retrieval.

    Verifies that the `get_connector_class` function returns the `BasicSSHConnector`
    class when no name is provided.
    """
    conn_cls = connectors.get_connector_class()
    assert conn_cls == connectors.BasicSSHConnector


def test_connectors_pass_named():
    """Test named connector class retrieval.

    Verifies that the `get_connector_class` function returns the correct class
    when a specific connector class name is provided.
    """
    name = "netcfgbu.connectors.ssh.LoginPromptUserPass"
    conn_cls = connectors.get_connector_class(name)
    from netcfgbu.connectors.ssh import LoginPromptUserPass

    assert conn_cls == LoginPromptUserPass


def test_connectors_fail_named(tmpdir):
    """Test connector class retrieval with an invalid name.

    Verifies that the `get_connector_class` function raises a `ModuleNotFoundError`
    when an invalid connector class name is provided.
    """
    with pytest.raises(ModuleNotFoundError):
        connectors.get_connector_class(str(tmpdir))
