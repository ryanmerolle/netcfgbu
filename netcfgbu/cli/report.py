import asyncio

from collections import defaultdict
from errno import errorcode
import csv
from time import monotonic
from datetime import datetime

from tabulate import tabulate

LN_SEP = "\n# " + "-" * 78 + "\n"
SPACES_4 = " " * 4


def err_reason(exc):
    return {
        str: lambda: exc,
        asyncio.TimeoutError: lambda: "TIMEOUT%s" % (str(exc.args or "")),
        OSError: lambda: errorcode[exc.errno],
    }.get(exc.__class__, lambda: "%s: %s" % (str(exc.__class__.__name__), str(exc)))()


class Report(object):
    TIME_FORMAT = "%Y-%b-%d %I:%M:%S %p"

    def __init__(self):
        self.start_ts = None
        self.start_tm = 0

        self.stop_ts = None
        self.stop_tm = 0

        self.task_results = defaultdict(list)

    def start_timing(self):
        self.start_ts = datetime.now()
        self.start_tm = monotonic()

    def stop_timing(self):
        self.stop_ts = datetime.now()
        self.stop_tm = monotonic()

    @property
    def start_time(self):
        return self.start_ts.strftime(self.TIME_FORMAT)

    @property
    def stop_time(self):
        return self.stop_ts.strftime(self.TIME_FORMAT)

    @property
    def duration(self):
        return self.stop_tm - self.start_tm

    def save_login_report(self):
        headers = ["host", "os_name", "num_of_attempts", "login_used"]

        login_tabular_data = []
        summary_data = defaultdict(lambda: defaultdict(lambda: defaultdict(int)))

        for rec in self.task_results[True]:
            host = rec["host"]
            os_name = rec["os_name"]
            attempts = rec.get("attempts", 1)  # Default to 1 if not specified
            login_used = rec["login_user"]

            login_tabular_data.append([host, os_name, attempts, login_used])

            # Update summary data
            summary_data[os_name][login_used][attempts] += 1

        login_tabular_data.sort(key=lambda x: x[0])  # Sorting by host

        with open("login.csv", "w+") as ofile:
            wr_csv = csv.writer(ofile)
            wr_csv.writerow(headers)
            wr_csv.writerows(login_tabular_data)

        # Print summary
        print("\n\nSUCCESS SUMMARY")

        login_tabular_data = []
        login_total = 0
        for os_name, user_data in summary_data.items():
            for login_used, attempt_data in user_data.items():
                for attempts, count in attempt_data.items():
                    login_tabular_data.append([os_name, login_used, attempts, count])
                    login_total += count

        if login_total > 0:
            summary_headers = ["os_name", "login_used", "attempts", "count"]
            login_tabular_data.sort(key=lambda x: (x[0], x[1], x[2]))  # Sort by os_name, login_used, then attempts
            login_tabular_data.append(["-" * 7, "-" * 10, "-" * 8, "-" * 5]) # SEPARATING_LINE does not work with tablefmt="pretty"
            login_tabular_data.append(["TOTAL", "", "", login_total])

            print(tabulate(headers=summary_headers, tabular_data=login_tabular_data, tablefmt="pretty"))
        else:
            print("No successful logins")

    def save_failure_report(self):
        headers = ["host", "os_name", "reason"]

        failure_tabular_data = [
            [rec["host"], rec["os_name"], err_reason(exc)]
            for rec, exc in self.task_results[False]
        ]

        # Sort failure_tabular_data by 'host'
        failure_tabular_data.sort(key=lambda x: x[0])  # Sorting by host
        #failure_tabular_data.append(SEPARATING_LINE)

        with open("failures.csv", "w+") as ofile:
            wr_csv = csv.writer(ofile)
            wr_csv.writerow(headers)
            wr_csv.writerows(failure_tabular_data)

        # Summarizing failures
        summary_data = defaultdict(lambda: defaultdict(int))
        for _, os_name, reason in failure_tabular_data:
            summary_data[os_name][reason] += 1

        # Print summary
        print("\n\nFAILURE SUMMARY")
        login_tabular_data = []
        login_total = 0
        for os_name, reason_data in summary_data.items():
            for reason, count in reason_data.items():
                login_tabular_data.append([os_name, reason, count])
                login_total += count

        if login_total > 0:
            summary_headers = ["os_name", "reason", "count"]
            login_tabular_data.sort(key=lambda x: (x[0], x[1]))  # Sort by os_name, then reason
            login_tabular_data.append(["-" * 7, "-" * 6, "-" * 8, "-" * 5]) # SEPARATING_LINE does not work with tablefmt="pretty"
            login_tabular_data.append([ "TOTAL", "", login_total])
            print(tabulate(headers=summary_headers, tabular_data=login_tabular_data, tablefmt="pretty"))
        else:
            print("No logins failures")


        if len(failure_tabular_data) > 0:
            # Also print the detailed failures
            print("\nDETAILED FAILURE REPORT")
            print(tabulate(headers=headers, tabular_data=failure_tabular_data, tablefmt="pretty"))

        print(LN_SEP)

    def print_report(self):
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

        self.save_login_report()
        self.save_failure_report()
