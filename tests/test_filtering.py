import csv

import pytest  # noqa

from netcfgbu.filtering import create_filter

# Test data
TEST1 = {"ipaddr": "10.10.0.2", "host": "switch1.nyc1"}
TEST2 = {"ipaddr": "10.10.0.3", "host": "switch1.nyc1"}
TEST3 = {"ipaddr": "10.10.0.4", "host": "switch1.dc1"}
TEST4 = {"ipaddr": "3001:10:10::2", "host": "switch1.nyc1"}
TEST5 = {"ipaddr": "3001:10:10::3", "host": "switch1.nyc1"}
TEST6 = {"ipaddr": "3001:10:10::4", "host": "switch1.dc1"}


def create_and_test_filter(
    constraints, field_names, include, test_data, expected_results
):
    """Helper function to create a filter and run assertions.

    Args:
        constraints (list): List of constraints for the filter.
        field_names (list): List of field names used in the filter.
        include (bool): Whether to include or exclude constraints.
        test_data (list): List of dictionaries representing test data.
        expected_results (list): List of expected results (True/False).
    """
    filter_fn = create_filter(constraints=constraints, field_names=field_names, include=include)
    for test_rec, expected in zip(test_data, expected_results):
        assert filter_fn(test_rec) is expected


def write_csv(tmpfile, fieldnames, rows):
    """Helper function to write rows to a CSV file.

    Args:
        tmpfile (Path): Path to the file.
        fieldnames (list): List of field names for the CSV.
        rows (list): List of dictionaries representing rows to write.
    """
    with open(tmpfile, "w+", encoding="utf-8") as ofile:
        csv_wr = csv.DictWriter(ofile, fieldnames=fieldnames)
        csv_wr.writeheader()
        csv_wr.writerows(rows)


def test_filtering_pass_include():
    create_and_test_filter(
        constraints=["os_name=eos", "host=.*nyc1"],
        field_names=["os_name", "host"],
        include=True,
        test_data=[
            {"os_name": "eos", "host": "switch1.nyc1"},
            {"os_name": "ios", "host": "switch1.nyc1"},
            {"os_name": "eos", "host": "switch1.dc1"},
        ],
        expected_results=[True, False, False],
    )


def test_filtering_pass_exclude():
    create_and_test_filter(
        constraints=["os_name=eos", "host=.*nyc1"],
        field_names=["os_name", "host"],
        include=False,
        test_data=[
            {"os_name": "ios", "host": "switch1.nyc1"},
            {"os_name": "eos", "host": "switch1.dc1"},
            {"os_name": "ios", "host": "switch1.dc1"},
        ],
        expected_results=[False, False, True],
    )


def test_filtering_fail_constraint_field():
    constraints = ["os_name2=eos", "host=.*nyc1"]
    field_names = ["os_name", "host"]

    with pytest.raises(ValueError) as excinfo:
        create_filter(constraints=constraints, field_names=field_names, include=False)

    assert "Invalid filter expression: os_name2=eos" in excinfo.value.args[0]


def test_filtering_fail_constraint_regex():
    with pytest.raises(ValueError) as excinfo:
        create_filter(constraints=["os_name=***"], field_names=["os_name"], include=False)

    assert "Invalid filter regular-expression" in excinfo.value.args[0]


def test_filtering_pass_filepath(tmpdir):
    filename = "failures.csv"
    tmpfile = tmpdir.join(filename)

    write_csv(
        tmpfile,
        ["host", "os_name"],
        [
            {"host": "switch1.nyc1", "os_name": "eos"},
            {"host": "switch2.dc1", "os_name": "ios"},
        ],
    )

    abs_filepath = str(tmpfile)
    create_filter(constraints=[f"@{abs_filepath}"], field_names=["host"])


def test_filtering_fail_filepath(tmpdir):
    filename = "failures.csv"
    tmpfile = tmpdir.join(filename)
    abs_filepath = str(tmpfile)

    with pytest.raises(FileNotFoundError) as excinfo:
        create_filter(constraints=[f"@{abs_filepath}"], field_names=["host"])

    assert excinfo.value.args[0] == abs_filepath


def test_filtering_pass_csv_filecontents(tmpdir):
    filename = "failures.csv"
    tmpfile = tmpdir.join(filename)

    inventory_recs = [
        {"host": "switch1.nyc1", "os_name": "eos"},
        {"host": "switch2.dc1", "os_name": "ios"},
    ]

    not_inventory_recs = [
        {"host": "switch3.nyc1", "os_name": "eos"},
        {"host": "switch4.dc1", "os_name": "ios"},
    ]

    write_csv(tmpfile, ["host", "os_name"], inventory_recs)

    abs_filepath = str(tmpfile)
    filter_fn = create_filter(constraints=[f"@{abs_filepath}"], field_names=["host"])

    for rec in inventory_recs:
        assert filter_fn(rec) is True

    for rec in not_inventory_recs:
        assert filter_fn(rec) is False


def test_filtering_fail_csv_missinghostfield(tmpdir):
    filename = "failures.csv"
    tmpfile = tmpdir.join(filename)

    write_csv(
        tmpfile,
        ["hostname", "os_name"],
        [
            {"hostname": "switch1.nyc1", "os_name": "eos"},
            {"hostname": "switch2.dc1", "os_name": "ios"},
        ],
    )

    abs_filepath = str(tmpfile)

    with pytest.raises(ValueError) as excinfo:
        create_filter(constraints=[f"@{abs_filepath}"], field_names=["hostname"])

    assert "does not contain host content as expected" in excinfo.value.args[0]


def test_filtering_fail_csv_filecontentsnotcsv(tmpdir):
    filepath = tmpdir.join("dummy.csv")
    filepath.mklinkto(__file__)

    with pytest.raises(ValueError) as excinfo:
        create_filter(constraints=[f"@{filepath}"], field_names=["host"])

    assert "does not contain host content as expected" in excinfo.value.args[0]


def test_filtering_fail_csv_notcsvfile():
    with pytest.raises(ValueError) as excinfo:
        create_filter(constraints=[f"@{__file__}"], field_names=["host, os_name"])

    assert "not a CSV file." in excinfo.value.args[0]


def test_filtering_ipaddr_v4_include():
    create_and_test_filter(
        constraints=["ipaddr=10.10.0.2"],
        field_names=["ipaddr"],
        include=True,
        test_data=[TEST1, TEST2, TEST3],
        expected_results=[True, False, False],
    )
    create_and_test_filter(
        constraints=["ipaddr=10.10.0.2/31"],
        field_names=["ipaddr"],
        include=True,
        test_data=[TEST1, TEST2, TEST3],
        expected_results=[True, True, False],
    )
    create_and_test_filter(
        constraints=["ipaddr=10.10.0.0/16"],
        field_names=["ipaddr"],
        include=True,
        test_data=[TEST1, TEST2, TEST3],
        expected_results=[True, True, True],
    )


def test_filtering_ipaddr_v4_exclude():
    create_and_test_filter(
        constraints=["ipaddr=10.10.0.2"],
        field_names=["ipaddr"],
        include=False,
        test_data=[TEST1, TEST2, TEST3],
        expected_results=[False, True, True],
    )
    create_and_test_filter(
        constraints=["ipaddr=10.10.0.2/31"],
        field_names=["ipaddr"],
        include=False,
        test_data=[TEST1, TEST2, TEST3],
        expected_results=[False, False, True],
    )
    create_and_test_filter(
        constraints=["ipaddr=10.10.0.0/16"],
        field_names=["ipaddr"],
        include=False,
        test_data=[TEST1, TEST2, TEST3],
        expected_results=[False, False, False],
    )


def test_filtering_ipaddr_v6_include():
    create_and_test_filter(
        constraints=["ipaddr=3001:10:10::2"],
        field_names=["ipaddr"],
        include=True,
        test_data=[TEST4, TEST5, TEST6],
        expected_results=[True, False, False],
    )
    create_and_test_filter(
        constraints=["ipaddr=3001:10:10::2/127"],
        field_names=["ipaddr"],
        include=True,
        test_data=[TEST4, TEST5, TEST6],
        expected_results=[True, True, False],
    )
    create_and_test_filter(
        constraints=["ipaddr=3001:10:10::0/64"],
        field_names=["ipaddr"],
        include=True,
        test_data=[TEST4, TEST5, TEST6],
        expected_results=[True, True, True],
    )


def test_filtering_ipaddr_v6_exclude():
    create_and_test_filter(
        constraints=["ipaddr=3001:10:10::2"],
        field_names=["ipaddr"],
        include=False,
        test_data=[TEST4, TEST5, TEST6],
        expected_results=[False, True, True],
    )
    create_and_test_filter(
        constraints=["ipaddr=3001:10:10::2/127"],
        field_names=["ipaddr"],
        include=False,
        test_data=[TEST4, TEST5, TEST6],
        expected_results=[False, False, True],
    )
    create_and_test_filter(
        constraints=["ipaddr=3001:10:10::0/64"],
        field_names=["ipaddr"],
        include=False,
        test_data=[TEST4, TEST5, TEST6],
        expected_results=[False, False, False],
    )


def test_filtering_ipaddr_regex_fallback():
    """Test the use-case of ipaddr filtering when a regex is used."""
    create_and_test_filter(
        constraints=["ipaddr=3001:10:(10|20)::2"],
        field_names=["ipaddr"],
        include=True,
        test_data=[
            {"ipaddr": "3001:10:10::1", "host": "switch1.nyc1"},
            {"ipaddr": "3001:10:20::2", "host": "switch1.nyc1"},
            {"ipaddr": "3001:10:30::3", "host": "switch1.dc1"},
        ],
        expected_results=[False, True, False],
    )

    create_and_test_filter(
        constraints=[r"ipaddr=10.10.10.\d{2}"],
        field_names=["ipaddr"],
        include=False,
        test_data=[
            {"ipaddr": "10.10.10.1", "host": "switch1.nyc1"},
            {"ipaddr": "10.10.10.10", "host": "switch1.nyc1"},
            {"ipaddr": "10.10.10.12", "host": "switch1.nyc1"},
        ],
        expected_results=[True, False, False],
    )
