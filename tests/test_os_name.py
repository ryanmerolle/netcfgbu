"""Tests for the OS name functionality."""

from netcfgbu.filetypes import CommentedCsvReader


def test_filetypes_csv_hascomments(request):
    """Test that the CommentedCsvReader correctly filters out commented lines.

    This test verifies that the `CommentedCsvReader` class reads a CSV file and
    excludes lines where the first column starts with a comment character ('#').
    It checks the presence and absence of specific host entries in the CSV data.

    Args:
        request: Fixture that provides information about the test request,
                 including the path to the test files.
    """
    filepath = f"{request.fspath.dirname}/files/test-csv-withcomments.csv"

    # Use context manager to handle file opening and closing
    with open(filepath, encoding="utf-8") as csvfile:
        csv_data = [rec["host"] for rec in CommentedCsvReader(csvfile)]

    assert "switch1" in csv_data
    assert "switch2" in csv_data
    assert "switch3" not in csv_data
    assert "switch4" not in csv_data
