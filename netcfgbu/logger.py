"""

References
----------

Logging in asyncio applications
   https://bit.ly/36WWgrf
"""

import asyncio
import logging
import logging.handlers
import sys
from logging import getLogger
from logging.config import dictConfig
from queue import SimpleQueue as Queue
from typing import Set

__all__ = ["setup_logging", "get_logger", "stop_aiologging"]


_g_quelgr_listener: logging.handlers.QueueListener


class LocalQueueHandler(logging.handlers.QueueHandler):
    def emit(self, record: logging.LogRecord) -> None:
        # Removed the call to self.prepare(), handle task cancellation
        try:
            self.enqueue(record)

        except asyncio.CancelledError:
            raise

        except asyncio.QueueFull:
            self.handleError(record)


def setup_logging_queue(logger_names) -> None:
    """
    Move log handlers to a separate thread.

    Replace all configured handlers with a LocalQueueHandler, and start a
    logging.QueueListener holding the original handlers.
    """
    global _g_quelgr_listener
    queue = Queue()
    handlers: Set[logging.Handler] = set()
    que_handler = LocalQueueHandler(queue)

    for lname in logger_names:
        log = logging.getLogger(lname)
        log.addHandler(que_handler)
        for handler in log.handlers[:]:
            if handler is not que_handler:
                log.removeHandler(handler)
                handlers.add(handler)

    _g_quelgr_listener = logging.handlers.QueueListener(
        queue, *handlers, respect_handler_level=True
    )
    _g_quelgr_listener.start()


def setup_logging(app_cfg) -> None:
    log_cfg = app_cfg.get("logging") or {}
    log_cfg["version"] = 1

    try:
        dictConfig(log_cfg)
    except ValueError as e:
        print(f"Error in logging configuration: {e}", file=sys.stderr)
        sys.exit(1)

    try:
        setup_logging_queue(log_cfg.get("loggers") or [])
    except Exception as e:
        print(f"Error setting up logging queue: {e}", file=sys.stderr)
        sys.exit(1)


def stop_aiologging() -> None:
    _g_quelgr_listener.stop()  # noqa
    sys.stdout.flush()


def get_logger():
    return getLogger(__package__)
