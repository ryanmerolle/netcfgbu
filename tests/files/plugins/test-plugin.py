from typing import Any

from netcfgbu.plugins import Plugin


class TestPlugin(Plugin):
    """Test Plugin is used by the test suite to test the backup success and failure handlers."""

    def backup_success(self: dict[Any, Any], res: bool) -> Any:
        """Handles a successful backup.

        Args:
        ----
            rec (Dict[Any, Any]): The record associated with the backup.
            res (bool): The result of the backup.

        Returns:
        -------
            Any: The result of handling the successful backup.

        """
        return self, res

    def backup_failed(self: str, exc: str) -> Any:
        """Handles a failed backup.

        Args:
        ----
            rec (str): The identifier of the record that failed backup.
            exc (str): The exception message related to the failed backup.

        Returns:
        -------
            Any: The result of handling the failed backup.

        """
        return self, exc
