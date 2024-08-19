"""This module contains pytest test cases for the `probe` function in the netcfgbu package."""

import asyncio
from unittest.mock import Mock

import pytest  # noqa
from asynctest import CoroutineMock  # noqa

from netcfgbu import probe
from netcfgbu.consts import DEFAULT_PROBE_TIMEOUT


@pytest.mark.asyncio
async def test_probe_pass(monkeypatch):
    """Test that the probe function returns True on successful completion.

    This test mocks the asyncio library to simulate a successful probe and
    verifies that the probe function returns True.

    Args:
        monkeypatch: Pytest's monkeypatch fixture to modify behavior.
    """
    mock_asyncio = Mock()
    mock_asyncio.TimeoutError = asyncio.TimeoutError
    mock_wait_for = CoroutineMock()

    mock_asyncio.wait_for = mock_wait_for
    monkeypatch.setattr(probe, "asyncio", mock_asyncio)

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
    mock_asyncio = Mock()
    mock_asyncio.TimeoutError = asyncio.TimeoutError
    mock_wait_for = Mock()

    mock_asyncio.wait_for = mock_wait_for

    def raises_timeout(coro, timeout):  # noqa
        """Simulate a timeout error for the given coroutine.

        This function is used as a side effect in the mock to raise an
        asyncio.TimeoutError, simulating a timeout scenario during the execution
        of a coroutine.

        Args:
            coro: The coroutine being executed (not used in the function).
            timeout: The timeout value (not used in the function).

        Raises:
            asyncio.TimeoutError: Always raises this exception to simulate a timeout.
        """
        raise asyncio.TimeoutError

    mock_wait_for.side_effect = raises_timeout
    monkeypatch.setattr(probe, "asyncio", mock_asyncio)

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
    mock_asyncio = Mock()
    mock_asyncio.TimeoutError = asyncio.TimeoutError
    mock_wait_for = Mock()

    mock_asyncio.wait_for = mock_wait_for

    def raises_timeout(coro, timeout):  # noqa
        """Simulate a timeout error for the given coroutine.

        This function is used as a side effect in the mock to raise an
        asyncio.TimeoutError, simulating a timeout scenario during the execution
        of a coroutine.

        Args:
            coro: The coroutine being executed (not used in the function).
            timeout: The timeout value (not used in the function).

        Raises:
            asyncio.TimeoutError: Always raises this exception to simulate a timeout.
        """
        raise asyncio.TimeoutError

    mock_wait_for.side_effect = raises_timeout
    monkeypatch.setattr(probe, "asyncio", mock_asyncio)

    with pytest.raises(asyncio.TimeoutError):
        await probe.probe(host="1.2.3.4", timeout=DEFAULT_PROBE_TIMEOUT, raise_exc=True)
