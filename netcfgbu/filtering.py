"""
This file contains the filtering functions that are using to process the
'--include' and '--exclude' command line options.  The code in this module is
not specific to the netcfgbu inventory column names, can could be re-used for
other CSV related tools and use-cases.
"""

import csv
import ipaddress
import operator
import re
from abc import ABC, abstractmethod
from pathlib import Path
from typing import AnyStr, Callable, Dict, List, Optional

__all__ = ["create_filter"]


VALUE_PATTERN = r"(?P<value>\S+)$"
file_reg = re.compile(r"@(?P<filename>.+)$")
wordsep_re = re.compile(r"\s+|,")


class Filter(ABC):
    """Filter is a type that supports op comparisons against inventory fields

    An implementation of Filter should capture:
     - The record fieldname to compare
     - The filter expression

    A Filter instance will be passed an inventory record when called, returning
        the bool result of whether the record matches the filter
    """

    @abstractmethod
    def __call__(self, record: Dict[str, AnyStr]) -> bool:
        pass


class RegexFilter(Filter):
    """Filter an inventory record field with a given regex"""

    def __init__(self, fieldname: str, expr: str) -> None:
        self.fieldname = fieldname
        try:
            self.re = re.compile(f"^{expr}$", re.IGNORECASE)
        except re.error as exc:
            raise ValueError(
                f"Invalid filter regular-expression: {expr!r}: {exc}"
            ) from None

    def __call__(self, record: Dict[str, AnyStr]) -> bool:
        return bool(self.re.match(record[self.fieldname]))

    def __repr__(self) -> str:
        return f"RegexFilter(fieldname={self.fieldname!r}, expr={self.re})"


class IPFilter(Filter):
    """Filter an inventory record field based on IP address

    When the specified filter ip address is a prefix (E.g 192.168.0.0/28), will
        check that the record IP is within the prefix range
    Will interpret single IP addresses (E.g. 2620:abcd:10::10) as an absolute match
    """

    def __init__(self, fieldname: str, ip: str) -> None:
        self.fieldname = fieldname
        self.ip = ipaddress.ip_network(ip)

    def __call__(self, record: Dict[str, AnyStr]) -> bool:
        return ipaddress.ip_address(record[self.fieldname]) in self.ip

    def __repr__(self) -> str:
        return f"IpFilter(fieldname={self.fieldname!r}, ip='{self.ip}')"


def parse_constraint(
    constraint: str, field_value_reg: re.Pattern, field_names: List[AnyStr]
) -> Filter:
    if mo := file_reg.match(constraint):
        return handle_file_filter(mo)

    if (mo := field_value_reg.match(constraint)) is None:
        raise ValueError(f"Invalid filter expression: {constraint}")

    fieldn, value = mo.groupdict().values()

    if fieldn.casefold() == "ipaddr":
        return create_ip_or_regex_filter(fieldn, value)

    return RegexFilter(fieldn, value)


def handle_file_filter(mo: re.Match) -> Filter:
    filepath = mo.group(1)
    if not Path(filepath).exists():
        raise FileNotFoundError(filepath)
    return mk_file_filter(filepath, key="host")


def create_ip_or_regex_filter(fieldn: str, value: str) -> Filter:
    try:
        return IPFilter(fieldn, value)
    except ValueError:
        return RegexFilter(fieldn, value)


def create_filter_function(op_filters, optest_fn):
    def filter_fn(rec):
        return not any(optest_fn(op_fn(rec)) for op_fn in op_filters)

    return filter_fn


def mk_file_filter(filepath, key):
    if filepath.endswith(".csv"):
        with open(filepath, "r", encoding="utf-8") as csvfile:
            reader = csv.DictReader(csvfile)
            if reader.fieldnames is None:
                raise ValueError(
                    f"File '{filepath}' does not contain headers or is empty."
                )
            if key not in reader.fieldnames:
                raise ValueError(
                    f"File '{filepath}' does not contain {key} content as expected"
                )
            filter_hostnames = [rec[key] for rec in reader if rec.get(key)]
            print(f"Filter hostnames: {filter_hostnames}")  # Debugging print
    else:
        raise ValueError(
            f"File '{filepath}' not a CSV file. Only CSV files are supported."
        )

    def op_filter(rec):
        return rec.get(key) in filter_hostnames

    return op_filter


def create_filter(
    constraints: List[AnyStr], field_names: List[AnyStr], include: Optional[bool] = True
) -> Callable[[Dict], bool]:
    """
    This function returns a function that is used to filter inventory records.

    Parameters
    ----------
    constraints:
        A list of contraint expressions that are in the form "<field-name>=<value>".

    field_names:
        A list of known field names

    include:
        When True, the filter function will match when the constraint is true,
        for example if the contraint is "os_name=eos", then it would match
        records that have os_name field euqal to "eos".

        When False, the filter function will match when the constraint is not
        true. For exampl if the constraint is "os_name=eos", then the filter
        function would match recoreds that have os_name fields not equal to
        "eos".

    Returns
    -------
    The returning filter function expects an inventory record as the single
    input parameter, and the function returns True/False on match.
    """
    fieldn_pattern = "^(?P<keyword>" + "|".join(fieldn for fieldn in field_names) + ")"
    field_value_reg = re.compile(fieldn_pattern + "=" + VALUE_PATTERN)

    op_filters = [
        parse_constraint(constraint, field_value_reg, field_names)
        for constraint in constraints
    ]

    optest_fn = operator.not_ if include else operator.truth
    filter_fn = create_filter_function(op_filters, optest_fn)
    filter_fn.op_filters = op_filters
    filter_fn.constraints = constraints

    return filter_fn
