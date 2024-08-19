"""This module contains pytest test cases for the `probe` function in the netcfgbu package."""

import asyncio
from unittest.mock import Mock

import pytest  # noqa
from asynctest import CoroutineMock  # noqa

from netcfgbu import probe
from netcfgbu.consts import DEFAULT_PROBE_TIMEOUT


def setup_mock_asyncio(monkeypatch, side_effect=None):
    """Helper function to setup mock for asyncio library.

    This function mocks the asyncio library and optionally sets a side effect
    for the `wait_for` method.

    Args:
        monkeypatch: Pytest's monkeypatch fixture to modify behavior.
        side_effect: Optional; A function to be used as the side effect of the wait_for mock.

    Returns:
        Mock: The mock object for asyncio.
    """
    mock_asyncio = Mock()
    mock_asyncio.TimeoutError = asyncio.TimeoutError
    mock_wait_for = CoroutineMock() if side_effect is None else Mock()

    if side_effect:
        mock_wait_for.side_effect = side_effect

    mock_asyncio.wait_for = mock_wait_for
    monkeypatch.setattr(probe, "asyncio", mock_asyncio)

    return mock_asyncio


@pytest.mark.asyncio
async def test_probe_pass(monkeypatch):
    """Test that the probe function returns True on successful completion.

    This test mocks the asyncio library to simulate a successful probe and
    verifies that the probe function returns True.

    Args:
        monkeypatch: Pytest's monkeypatch fixture to modify behavior.
    """
    setup_mock_asyncio(monkeypatch)

    ok = await probe.probe(host="1.2.3.4", timeout=DEFAULT_PROBE_TIMEOUT)
    assert ok is True


@pytest.mark.asyncio
async def test_probe_pass_timeout(monkeypatch):
    """Test that the probe function returns False on a timeout.

    This test mocks the asyncio library to simulate a timeout error during
    the probe and verifies that the probe function returns False.

    Args:
        monkeypatch: Pytest's monkeypatch fixture to modify behavior.
    """
    def raises_timeout(coro, timeout):  # noqa
        raise asyncio.TimeoutError

    setup_mock_asyncio(monkeypatch, side_effect=raises_timeout)

    ok = await probe.probe(host="1.2.3.4", timeout=DEFAULT_PROBE_TIMEOUT)
    assert ok is False


@pytest.mark.asyncio
async def test_probe_pass_raises_timeout(monkeypatch):
    """Test that the probe function raises an exception on a timeout when specified.

    This test mocks the asyncio library to simulate a timeout error during
    the probe and verifies that the probe function raises an asyncio.TimeoutError
    when `raise_exc=True` is passed.

    Args:
        monkeypatch: Pytest's monkeypatch fixture to modify behavior.
    """
    def raises_timeout(coro, timeout):  # noqa
        raise asyncio.TimeoutError

    setup_mock_asyncio(monkeypatch, side_effect=raises_timeout)

    with pytest.raises(asyncio.TimeoutError):
        await probe.probe(host="1.2.3.4", timeout=DEFAULT_PROBE_TIMEOUT, raise_exc=True)
