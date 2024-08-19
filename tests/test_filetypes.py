"""Tests for the filetypes module in the netcfgbu package.

This module contains tests for various file type handling functionalities in the
netcfgbu package. It uses pytest for testing.

Functions:
    test_filetypes_detection: Test the detection of file types.
    test_filetypes_parsing: Test the parsing of different file types.
    test_filetypes_validation: Test the validation of file types.
"""

from netcfgbu.filetypes import CommentedCsvReader


def test_filetypes_csv_hascomments(request):
    """Test CommentedCsvReader functionality for filtering commented lines.

    This test verifies that the `CommentedCsvReader` correctly excludes rows
    that start with the comment character ('#') in the CSV file. The test checks
    that specific host entries are present or absent as expected.

    Args:
        request: Fixture providing information about the test environment,
                 including the path to the test files.
    """
    filepath = f"{request.fspath.dirname}/files/test-csv-withcomments.csv"

    # Use context manager for safe file handling
    with open(filepath) as csvfile:
        csv_data = [rec["host"] for rec in CommentedCsvReader(csvfile)]

    assert "switch1" in csv_data
    assert "switch2" in csv_data
    assert "switch3" not in csv_data
    assert "switch4" not in csv_data
