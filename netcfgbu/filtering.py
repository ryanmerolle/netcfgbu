"""This file contains the filtering functions that are used to process the
'--include' and '--exclude' command line options.

The code in this module is not specific to the netcfgbu inventory column names and can be
re-used for other CSV-related tools and use cases.
"""

import csv
import ipaddress
import operator
import re
from abc import ABC, abstractmethod
from collections.abc import Callable
from pathlib import Path
from typing import AnyStr, Optional

__all__ = ["create_filter"]

VALUE_PATTERN = r"(?P<value>\S+)$"
file_reg = re.compile(r"@(?P<filename>.+)$")
wordsep_re = re.compile(r"\s+|,")


class Filter(ABC):
    """Filter is a type that supports comparisons against inventory fields.

    An implementation of Filter should capture:
     - The record fieldname to compare
     - The filter expression

    A Filter instance will be passed an inventory record when called, returning
    a boolean result indicating whether the record matches the filter.
    """

    @abstractmethod
    def __call__(self, record: dict[str, AnyStr]) -> bool:
        """Apply the filter to the given record.

        Args:
            record: The inventory record to filter.

        Returns:
            bool: True if the record matches the filter, False otherwise.
        """
        pass


class RegexFilter(Filter):
    """Filter an inventory record field with a given regex pattern."""

    def __init__(self, fieldname: str, expr: str) -> None:
        """Initialize the RegexFilter.

        Args:
            fieldname: The name of the field to filter on.
            expr: The regular expression to match against the field's value.
        """
        self.fieldname = fieldname
        try:
            self.regex = re.compile(f"^{expr}$", re.IGNORECASE)
        except re.error as exc:
            raise ValueError(f"Invalid filter regular-expression: {expr!r}: {exc}") from None

    def __call__(self, record: dict[str, AnyStr]) -> bool:
        """Apply the regex filter to the specified field in the record.

        Args:
            record: The inventory record to filter.

        Returns:
            bool: True if the field's value matches the regex, False otherwise.
        """
        return bool(self.regex.match(record[self.fieldname]))

    def __repr__(self) -> str:
        """Return a string representation of the RegexFilter.

        This method provides a clear and concise description of the filter, including
        the field name and the regular expression being used.

        Returns:
            str: A string representation of the RegexFilter instance.
        """
        return f"RegexFilter(fieldname={self.fieldname!r}, expr={self.regex})"


class IPFilter(Filter):
    """Filter an inventory record field based on an IP address or IP prefix.

    This filter checks whether the specified field's IP address is within a
    given IP range or matches a specific IP address.
    """

    def __init__(self, fieldname: str, ip_address: str) -> None:
        """Initialize the IPFilter.

        Args:
            fieldname: The name of the field containing the IP address.
            ip_address: The IP address or IP prefix to filter by.
        """
        self.fieldname = fieldname
        self.ip_address = ipaddress.ip_network(ip_address)

    def __call__(self, record: dict[str, AnyStr]) -> bool:
        """Apply the IP filter to the specified field in the record.

        Args:
            record: The inventory record to filter.

        Returns:
            bool: True if the field's IP address is within the specified range, False otherwise.
        """
        return ipaddress.ip_address(record[self.fieldname]) in self.ip_address

    def __repr__(self) -> str:
        """Return a string representation of the IPFilter.

        This method provides a clear and concise description of the filter, including
        the field name and the IP address or IP prefix being used for filtering.

        Returns:
            str: A string representation of the IPFilter instance.
        """
        return f"IPFilter(fieldname={self.fieldname!r}, ip='{self.ip_address}')"


def parse_constraint(
    constraint: str, field_value_reg: re.Pattern, field_names: Optional[list[AnyStr]] = None
) -> Filter:
    """Parse a filter constraint expression and return the appropriate Filter instance.

    Args:
        constraint: The constraint expression in the form "<field-name>=<value>".
        field_value_reg: Compiled regular expression to match field-value constraints.
        field_names: List of valid field names for filtering (optional).

    Returns:
        Filter: The corresponding Filter instance (RegexFilter or IPFilter).
    """
    if match_obj := file_reg.match(constraint):
        return handle_file_filter(match_obj)

    if (match_obj := field_value_reg.match(constraint)) is None:
        raise ValueError(f"Invalid filter expression: {constraint}")

    fieldn, value = match_obj.groupdict().values()

    if fieldn.casefold() == "ipaddr":
        return create_ip_or_regex_filter(fieldn, value)

    return RegexFilter(fieldn, value)


def handle_file_filter(match_obj: re.Match) -> Filter:
    """Handle a file-based filter specified by the "@filename" syntax.

    Args:
        match_obj: The regex match object containing the filename.

    Returns:
        Filter: A filter function based on the contents of the specified file.
    """
    filepath = match_obj.group(1)
    if not Path(filepath).exists():
        raise FileNotFoundError(filepath)
    return mk_file_filter(filepath, key="host")


def create_ip_or_regex_filter(fieldn: str, value: str) -> Filter:
    """Create an IPFilter or RegexFilter based on the value provided.

    Args:
        fieldn: The field name to filter.
        value: The value to match against.

    Returns:
        Filter: An IPFilter if the value is a valid IP address or prefix, otherwise a RegexFilter.
    """
    try:
        return IPFilter(fieldn, value)
    except ValueError:
        return RegexFilter(fieldn, value)


def create_filter_function(op_filters, optest_fn):
    """Create a filter function that applies a list of filters to a record.

    Args:
        op_filters: List of filter functions.
        optest_fn: Function to test filter results.

    Returns:
        Callable: A filter function that returns True/False based on the filters.
    """

    def filter_fn(rec):
        """Apply the list of filters to a given record.

        This function iterates over the filters in `op_filters` and applies each one to the
        provided record. It uses the `optest_fn` to determine whether any of the filters match.
        If any filter matches, the function returns False; otherwise, it returns True.

        Args:
            rec (dict): The inventory record to filter.

        Returns:
            bool: True if none of the filters match the record, False otherwise.
        """
        return not any(optest_fn(op_fn(rec)) for op_fn in op_filters)

    return filter_fn


def mk_file_filter(filepath, key):
    """Create a filter function based on the contents of a CSV file.

    Args:
        filepath: Path to the CSV file containing filter criteria.
        key: The key (column name) to filter on.

    Returns:
        Callable: A filter function that returns True if the record matches the CSV file contents.
    """
    if filepath.endswith(".csv"):
        with open(filepath, encoding="utf-8") as csvfile:
            reader = csv.DictReader(csvfile)
            if reader.fieldnames is None:
                raise ValueError(f"File '{filepath}' does not contain headers or is empty.")
            if key not in reader.fieldnames:
                raise ValueError(f"File '{filepath}' does not contain {key} content as expected")
            filter_hostnames = [rec[key] for rec in reader if rec.get(key)]
            print(f"Filter hostnames: {filter_hostnames}")  # Debugging print
    else:
        raise ValueError(f"File '{filepath}' not a CSV file. Only CSV files are supported.")

    def op_filter(rec):
        """Check if the record matches any of the hostnames in the CSV file.

        Args:
            rec (dict): The inventory record to check.

        Returns:
            bool: True if the record matches the filter criteria from the CSV file, False otherwise.
        """
        return rec.get(key) in filter_hostnames

    return op_filter


def create_filter(
    constraints: list[AnyStr], field_names: list[AnyStr], include: Optional[bool] = True
) -> Callable[[dict], bool]:
    """Create a filter function based on the provided constraints.

    Args:
        constraints: A list of constraint expressions in the form "<field-name>=<value>".
        field_names: A list of valid field names for filtering.
        include: If True, the filter matches when the constraint is true. If False, the filter
        matches when the constraint is not true.

    Returns:
        Callable: A filter function that takes an inventory record as input and returns True/False
        based on the constraints.
    """
    fieldn_pattern = "^(?P<keyword>" + "|".join(fieldn for fieldn in field_names) + ")"
    field_value_reg = re.compile(fieldn_pattern + "=" + VALUE_PATTERN)

    op_filters = [
        parse_constraint(constraint, field_value_reg, field_names) for constraint in constraints
    ]

    optest_fn = operator.not_ if include else operator.truth
    filter_fn = create_filter_function(op_filters, optest_fn)
    filter_fn.op_filters = op_filters
    filter_fn.constraints = constraints

    return filter_fn
