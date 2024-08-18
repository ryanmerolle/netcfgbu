from functools import lru_cache
from importlib import import_module

from .basic import BasicSSHConnector, set_max_startups  # noqa: F401


@lru_cache
def get_connector_class(mod_cls_name=None):
    """Retrieves the connector class based on the provided module and class name.

    Args:
        mod_cls_name: A string representing the module and class name in the format
                      'module.ClassName'. If not provided, defaults to `BasicSSHConnector`.

    Returns:
        The connector class specified by `mod_cls_name`, or `BasicSSHConnector` if not specified.

    Example:
        get_connector_class("my_module.MyConnectorClass")
    """
    if not mod_cls_name:
        return BasicSSHConnector

    mod_name, _, cls_name = mod_cls_name.rpartition(".")
    mod_obj = import_module(mod_name)
    return getattr(mod_obj, cls_name)
