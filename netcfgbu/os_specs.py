"""This module defines operating system specifications for network devices."""

from netcfgbu.config_model import AppConfig, OSNameSpec
from netcfgbu.connectors import get_connector_class


def get_os_spec(rec: dict, app_cfg: AppConfig) -> OSNameSpec:
    """Retrieve the OS specification for a given record from the application configuration.

    Args:
        rec: A dictionary representing an inventory record.
        app_cfg: The application configuration object.

    Returns:
        OSNameSpec: The OS specification for the record, or a default OSNameSpec if not found.
    """
    os_name = rec["os_name"]
    os_specs = app_cfg.os_name or {}
    return os_specs.get(os_name) or OSNameSpec()


def make_host_connector(rec: dict, app_cfg: AppConfig):
    """Create a host connector instance based on the inventory record and application configuration.

    Args:
        rec: A dictionary representing an inventory record.
        app_cfg: The application configuration object.

    Returns:
        A connector class instance for the host, configured with the appropriate OS spec and
        application settings.
    """
    os_spec_def = get_os_spec(rec, app_cfg)
    os_spec_cls = get_connector_class(os_spec_def.connection)
    return os_spec_cls(host_cfg=rec, os_spec=os_spec_def, app_cfg=app_cfg)
