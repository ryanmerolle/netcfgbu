import asyncio
import socket

import asyncssh

from netcfgbu.logger import get_logger


async def handle_exception(exc, rec, done_msg, report) -> None:
    exception_map = {
        asyncssh.PermissionDenied: "All credentials failed",
        asyncssh.ConnectionLost: "ConnectionLost",
        asyncssh.HostKeyNotVerifiable: "HostKeyNotVerifiable",
        socket.gaierror: "NameResolutionError",
        asyncio.TimeoutError: "TimeoutError",
        asyncssh.TimeoutError: "TimeoutError",
        OSError: "NoRouteToHost" if exc.errno == 113 else "OSError",
    }

    reason = exception_map.get(type(exc), type(exc).__name__)

    log = get_logger()
    reason_detail = f"{reason} - {str(exc)}"
    log.error(done_msg + " - " + reason_detail)
    report.task_results[False].append((rec, reason))
