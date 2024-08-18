"""This module provides an asynchronous generator that mimics the behavior of
concurrent.futures.as_completed, allowing retrieval of originating coroutines.
"""

import asyncio
from asyncio import Task
from collections.abc import AsyncIterable, Coroutine, Iterable
from typing import Optional

__all__ = ["as_completed"]


async def as_completed(
    aws: Iterable[Coroutine], timeout: Optional[int] = None
) -> AsyncIterable[Task]:
    """This async generator is used to "mimic" the behavior of the
    concurrent.futures.as_completed functionality. Usage of this as_completed
    generator is slightly different from the builtin asyncio version; see
    example below.

    The builtin asyncio.as_completed yields futures such that the originating
    coroutine can not be retrieved. In order to obtain the originating
    coroutine, these must be wrapped in futures as explained in this Stack
    Overflow: https://bit.ly/2AsPtJE.

    Parameters
    ----------
    aws:
        An iterable of coroutines that will be wrapped into futures and
        executed through the asyncio on_completed builtin.

    timeout: int
        (same as asyncio.as_completed):
        If provided, an asyncio.TimeoutError will be raised if all of the
        coroutines have not completed within the timeout value.

    Yields:
    ------
    asyncio.Task

    Examples:
    --------
        # create a dictionary of key=coroutine, value=dict, where the value will
        # be used later when the coroutine completes

        tasks = {
            probe(rec.get('ipaddr') or rec.get('host')): rec
            for rec in inventory
        }

        async for probe_task in as_completed(tasks):
            try:
                # obtain the originating coroutine so we can use it as an index
                # into the tasks dictionary and obtain the associated inventory
                # record

                task_coro = probe_task.get_coro()
                rec = tasks[task_coro]

                # now obtain the coroutine return value using the `result`
                # method.

                probe_ok = 'OK' if probe_task.result() else 'FAIL'
                report[probe_ok].append(rec)

            except OSError as exc:
                probe_ok = 'ERROR'
                report['ERROR'].append((rec, exc))

            print(f"{rec['host']}: {probe_ok}")
    """
    loop = asyncio.get_running_loop()

    def wrap_coro(coro):
        """Wrap a coroutine into a future and create a wrapper future.

        This function wraps the provided coroutine in a future, and then
        creates a separate wrapper future. The wrapper future's result
        is set once the original future completes, allowing the outer
        future to be used in the asyncio.as_completed loop.

        Args:
            coro (Coroutine): The coroutine to wrap.

        Returns:
            asyncio.Future: A wrapper future that will be set when the original
            coroutine completes.
        """
        fut = asyncio.ensure_future(coro)
        wrapper = loop.create_future()
        fut.add_done_callback(wrapper.set_result)
        return wrapper

    for next_completed in asyncio.as_completed([wrap_coro(coro) for coro in aws], timeout=timeout):
        # next_completed is a Future object that represents the next coroutine that completes.
        # We yield the result of the completed task after awaiting it.
        yield await next_completed
