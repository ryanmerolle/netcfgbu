from typing import Any, Dict

from netcfgbu.plugins import Plugin


class TestPlugin(Plugin):
    """Test Plugin is used by the test suite to test the backup success and failure handlers."""

    def backup_success(rec: Dict[Any, Any], res: bool) -> Any:
        """Handles a successful backup.

        Args:
        ----
            rec (Dict[Any, Any]): The record associated with the backup.
            res (bool): The result of the backup.

        Returns:
        -------
            Any: The result of handling the successful backup.

        """
        return rec, res

    def backup_failed(rec: str, exc: str) -> Any:
        """Handles a failed backup.

        Args:
        ----
            rec (str): The identifier of the record that failed backup.
            exc (str): The exception message related to the failed backup.

        Returns:
        -------
            Any: The result of handling the failed backup.

        """
        return rec, exc
