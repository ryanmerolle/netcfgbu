"""This module generates reports based on network configuration data."""

import asyncio
import csv
from collections import defaultdict
from datetime import datetime
from errno import errorcode
from time import monotonic
from typing import Any, Union

from tabulate import tabulate

LN_SEP = "\n# " + "-" * 78 + "\n"
SPACES_4 = " " * 4


def err_reason(exc) -> str:
    """Returns a string representation of the error reason based on the exception type.

    Args:
        exc: The exception to handle.

    Returns:
        A string describing the error.
    """
    return {
        str: lambda: exc,
        asyncio.TimeoutError: lambda: f"TIMEOUT{str(exc.args or '')}",
        OSError: lambda: errorcode[exc.errno],
    }.get(exc.__class__, lambda: f"{exc.__class__.__name__}: {str(exc)}")()


class Report:
    """A class to handle reporting of task results, including timing, saving reports to files,
    and printing summaries.
    """

    TIME_FORMAT = "%Y-%b-%d %I:%M:%S %p"

    def __init__(self) -> None:
        """Initializes a new instance of the Report class."""
        self.start_ts: Union[None, datetime] = None
        self.start_tm: float = 0.0
        self.stop_ts: Union[None, datetime] = None
        self.stop_tm: float = 0.0
        self.task_results: dict[bool, list[dict[str, Any]]] = defaultdict(list)

    def start_timing(self) -> None:
        """Starts the timing for the report."""
        self.start_ts = datetime.now()
        self.start_tm = monotonic()

    def stop_timing(self) -> None:
        """Stops the timing for the report."""
        self.stop_ts = datetime.now()
        self.stop_tm = monotonic()

    @property
    def start_time(self) -> str:
        """Returns the formatted start time of the report.

        Raises:
            ValueError: If the start time has not been set.

        Returns:
            str: The start time as a formatted string.
        """
        if self.start_ts is None:
            raise ValueError("start_ts is not set")
        return self.start_ts.strftime(self.TIME_FORMAT)

    @property
    def stop_time(self) -> str:
        """Returns the formatted stop time of the report.

        Raises:
            ValueError: If the stop time has not been set.

        Returns:
            str: The stop time as a formatted string.
        """
        if self.stop_ts is None:
            raise ValueError("stop_ts is not set")
        return self.stop_ts.strftime(self.TIME_FORMAT)

    @property
    def duration(self) -> float:
        """Returns the duration between the start and stop times.

        Returns:
            float: The duration in seconds.
        """
        return self.stop_tm - self.start_tm

    def save_report(
        self,
        filename: str,
        headers: list[str],
        data: list[list[Any]],
        summary_headers: Union[None, list[str]] = None,
        summary_data: Union[None, dict[str, dict[str, int]]] = None,
    ) -> None:
        """Saves the report data to a CSV file and prints a summary if provided.

        Args:
            filename: The name of the CSV file to save the report to.
            headers: The headers for the CSV file.
            data: The data to save in the CSV file.
            summary_headers: The headers for the summary table (optional).
            summary_data: The data for the summary table (optional).
        """
        data.sort(key=lambda x: x[0])  # Sorting by the first column (usually 'host')

        with open(filename, "w+", encoding="utf-8") as ofile:
            wr_csv = csv.writer(ofile)
            wr_csv.writerow(headers)
            wr_csv.writerows(data)

        if summary_headers and summary_data:
            base_filename = filename.rsplit(".", 1)[0]  # Ensure this is a string
            print(f"\n\n{base_filename.upper()} SUMMARY")
            summary_tabular_data: list[list[Any]] = []
            total_count = 0
            for key1, key2_data in summary_data.items():
                for key2, count in key2_data.items():
                    summary_tabular_data.append([key1, key2, count])
                    total_count += count

            summary_tabular_data.sort(key=lambda x: (x[0], x[1]))  # Sort by key1, then key2
            summary_tabular_data.append(["-" * 7, "-" * 10, "-" * 5])  # Separator line
            summary_tabular_data.append(["TOTAL", "", total_count])

            print(tabulate(summary_tabular_data, headers=summary_headers, tablefmt="pretty"))

    def save_login_report(self) -> None:
        """Generates and saves the login report as a CSV file, including a summary of login
        attempts.
        """
        headers = ["host", "os_name", "num_of_attempts", "login_used"]
        login_tabular_data: list[list[Any]] = []
        summary_data: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))

        for rec in self.task_results[True]:
            host = rec["host"]
            os_name = rec["os_name"]
            attempts = rec.get("attempts", 1)  # Default to 1 if not specified
            login_used = rec["login_user"]

            login_tabular_data.append([host, os_name, attempts, login_used])
            summary_data[os_name][login_used] += attempts

        self.save_report(
            "login.csv",
            headers,
            login_tabular_data,
            ["os_name", "login_used", "count"],
            summary_data,
        )

    def save_failure_report(self) -> None:
        """Generates & saves the failure report as a CSV file, including a summary of
        failure reasons.
        """
        headers = ["host", "os_name", "reason"]
        failure_tabular_data: list[list[Any]] = [
            [rec["host"], rec["os_name"], err_reason(exc)] for rec, exc in self.task_results[False]
        ]

        summary_data: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
        for _, os_name, reason in failure_tabular_data:
            summary_data[os_name][reason] += 1

        self.save_report(
            "failures.csv",
            headers,
            failure_tabular_data,
            ["os_name", "reason", "count"],
            summary_data,
        )

    def print_report(self, reports_type: str) -> None:
        """Prints a summary report of the task results and saves the appropriate reports to files.

        Args:
            reports_type: The type of report to generate ("login" or other types).
        """
        if not self.stop_tm:
            self.stop_timing()  # pragma: no cover

        fail_n = len(self.task_results[False])
        ok_n = len(self.task_results[True])
        total_n = ok_n + fail_n

        print(LN_SEP)
        print(
            f"SUMMARY: TOTAL={total_n}, OK={ok_n}, FAIL={fail_n}\n"
            f"         START={self.start_time}, STOP={self.stop_time}\n"
            f"         DURATION={self.duration:.3f}s"
        )

        if reports_type == "login":
            self.save_login_report()

        self.save_failure_report()
