import asyncio
import csv
from collections import defaultdict
from datetime import datetime
from errno import errorcode
from time import monotonic
from typing import Any, Dict, List, Union

from tabulate import tabulate

LN_SEP = "\n# " + "-" * 78 + "\n"
SPACES_4 = " " * 4


def err_reason(exc) -> str:
    return {
        str: lambda: exc,
        asyncio.TimeoutError: lambda: f"TIMEOUT{str(exc.args or '')}",
        OSError: lambda: errorcode[exc.errno],
    }.get(exc.__class__, lambda: f"{exc.__class__.__name__}: {str(exc)}")()


class Report(object):
    TIME_FORMAT = "%Y-%b-%d %I:%M:%S %p"

    def __init__(self) -> None:
        self.start_ts: Union[None, datetime] = None
        self.start_tm: float = 0.0
        self.stop_ts: Union[None, datetime] = None
        self.stop_tm: float = 0.0
        self.task_results: Dict[bool, List[Dict[str, Any]]] = defaultdict(list)

    def start_timing(self) -> None:
        self.start_ts = datetime.now()
        self.start_tm = monotonic()

    def stop_timing(self) -> None:
        self.stop_ts = datetime.now()
        self.stop_tm = monotonic()

    @property
    def start_time(self) -> str:
        if self.start_ts is None:
            raise ValueError("start_ts is not set")
        return self.start_ts.strftime(self.TIME_FORMAT)

    @property
    def stop_time(self) -> str:
        if self.stop_ts is None:
            raise ValueError("stop_ts is not set")
        return self.stop_ts.strftime(self.TIME_FORMAT)

    @property
    def duration(self) -> float:
        return self.stop_tm - self.start_tm

    def save_report(
        self,
        filename: str,
        headers: List[str],
        data: List[List[Any]],
        summary_headers: Union[None, List[str]] = None,
        summary_data: Union[None, Dict[str, Dict[str, int]]] = None,
    ) -> None:
        data.sort(key=lambda x: x[0])  # Sorting by the first column (usually 'host')

        with open(filename, "w+", encoding="utf-8") as ofile:
            wr_csv = csv.writer(ofile)
            wr_csv.writerow(headers)
            wr_csv.writerows(data)

        if summary_headers and summary_data:
            base_filename = filename.rsplit(".", 1)[0]  # Ensure this is a string
            print(f"\n\n{base_filename.upper()} SUMMARY")
            summary_tabular_data: List[List[Any]] = []
            total_count = 0
            for key1, key2_data in summary_data.items():
                for key2, count in key2_data.items():
                    summary_tabular_data.append([key1, key2, count])
                    total_count += count

            summary_tabular_data.sort(
                key=lambda x: (x[0], x[1])
            )  # Sort by key1, then key2
            summary_tabular_data.append(["-" * 7, "-" * 10, "-" * 5])  # Separator line
            summary_tabular_data.append(["TOTAL", "", total_count])

            print(
                tabulate(
                    summary_tabular_data, headers=summary_headers, tablefmt="pretty"
                )
            )

    def save_login_report(self) -> None:
        headers = ["host", "os_name", "num_of_attempts", "login_used"]
        login_tabular_data: List[List[Any]] = []
        summary_data: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))

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
        headers = ["host", "os_name", "reason"]
        failure_tabular_data: List[List[Any]] = [
            [rec["host"], rec["os_name"], err_reason(exc)]
            for rec, exc in self.task_results[False]
        ]

        summary_data: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))
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
