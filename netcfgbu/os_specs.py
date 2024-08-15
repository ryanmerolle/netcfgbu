from netcfgbu.config_model import AppConfig, OSNameSpec
from netcfgbu.connectors import get_connector_class


def get_os_spec(rec: dict, app_cfg: AppConfig):
    os_name = rec["os_name"]
    os_specs = app_cfg.os_name or {}
    return os_specs.get(os_name) or OSNameSpec()


def make_host_connector(rec: dict, app_cfg: AppConfig):
    os_spec_def = get_os_spec(rec, app_cfg)
    os_spec_cls = get_connector_class(os_spec_def.connection)
    return os_spec_cls(host_cfg=rec, os_spec=os_spec_def, app_cfg=app_cfg)
