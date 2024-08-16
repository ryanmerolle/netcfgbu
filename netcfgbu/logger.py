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


_G_QUELGR_LISTENER: logging.handlers.QueueListener


class LocalQueueHandler(logging.handlers.QueueHandler):
    """
    A custom logging handler that enqueues log records to be processed in a separate thread.

    This handler is designed to handle task cancellations and queue overflow errors gracefully.
    """

    def emit(self, record: logging.LogRecord) -> None:
        """
        Emit a log record by enqueuing it.

        Args:
            record: The log record to be enqueued.

        Raises:
            asyncio.CancelledError: If the task was cancelled.
            asyncio.QueueFull: If the queue is full.
        """
        # Removed the call to self.prepare(), handle task cancellation
        try:
            self.enqueue(record)

        except asyncio.CancelledError:  # pylint: disable=W0706
            raise

        except asyncio.QueueFull:
            self.handleError(record)


def setup_logging_queue(logger_names: Set[str]) -> None:
    """
    Set up a logging queue to move log handling to a separate thread.

    This function replaces all configured handlers with a LocalQueueHandler
    and starts a logging.QueueListener that holds the original handlers.

    Args:
        logger_names: A set of logger names to configure with queue-based logging.
    """
    global _G_QUELGR_LISTENER
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

    _G_QUELGR_LISTENER = logging.handlers.QueueListener(
        queue, *handlers, respect_handler_level=True
    )
    _G_QUELGR_LISTENER.start()


def setup_logging(app_cfg: dict) -> None:
    """
    Set up logging configuration based on the provided application configuration.

    This function reads the logging configuration from the application config
    and applies it using `dictConfig`. It also sets up queue-based logging.

    Args:
        app_cfg: The application configuration containing logging settings.
    """
    log_cfg = app_cfg.get("logging") or {}
    log_cfg["version"] = 1

    try:
        dictConfig(log_cfg)
    except ValueError as exc:
        print(f"Error in logging configuration: {exc}", file=sys.stderr)
        sys.exit(1)

    try:
        setup_logging_queue(log_cfg.get("loggers") or [])
    except Exception as exc:
        print(f"Error setting up logging queue: {exc}", file=sys.stderr)
        sys.exit(1)


def stop_aiologging() -> None:
    """
    Stop the asynchronous logging queue listener and flush stdout.

    This function stops the logging.QueueListener and flushes the standard output.
    """
    _G_QUELGR_LISTENER.stop()  # noqa
    sys.stdout.flush()


def get_logger() -> logging.Logger:
    """
    Get a logger instance for the current package.

    Returns:
        logging.Logger: The logger instance for the current package.
    """
    return getLogger(__package__)
