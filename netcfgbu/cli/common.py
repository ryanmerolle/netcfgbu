from netcfgbu.logger import get_logger


async def handle_exception(exc, reason, rec, done_msg, report) -> None:
    log = get_logger()
    reason_detail = f"{reason} - {str(exc)}"
    log.error(done_msg + reason_detail)
    report.task_results[False].append((rec, reason))
