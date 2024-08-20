"""This module handles the loading and validation of the application configuration from a TOML file.

The module provides functionality to read a TOML configuration file, validate its contents using
Pydantic, and set up logging based on the configuration. If any validation errors occur, they are
formatted into a human-readable string and raised as a RuntimeError.
"""

from pathlib import Path
from typing import Optional

import toml
from pydantic import ValidationError

from .config_model import AppConfig
from .logger import setup_logging

__all__ = ["load"]


def validation_errors(filepath: str, errors: list) -> str:
    """Format validation errors into a human-readable string.

    Args:
        filepath: The path to the configuration file.
        errors: A list of validation errors.

    Returns:
        str: A formatted string describing the validation errors.
    """
    sp_4 = " " * 4
    as_human = ["Configuration errors", f"{sp_4}File:[{filepath}]"]

    for _err in errors:
        loc_str = ".".join(map(str, _err["loc"]))
        as_human.append(f"{sp_4}Section: [{loc_str}]: {_err['msg']}")

    return "\n".join(as_human)


def load(*, filepath: Optional[str] = None, fileio=None) -> AppConfig:
    """Load and validate the application configuration from a TOML file.

    Args:
        filepath: Optional path to the configuration file.
        fileio: Optional file object to read the configuration from.

    Returns:
        AppConfig: The validated application configuration object.

    Raises:
        RuntimeError: If validation fails, including details of the validation errors.
    """
    app_cfg = {}

    if filepath:
        app_cfg_file = Path(filepath)
        fileio = app_cfg_file.open(mode="r", encoding="utf-8")

    if fileio:
        app_cfg = toml.load(fileio)

    setup_logging(app_cfg)

    app_defaults = app_cfg.get("defaults")
    if not app_defaults:
        app_cfg["defaults"] = {"credentials": {}}

    try:
        cfg_obj = AppConfig.model_validate(app_cfg)
    except ValidationError as exc:
        filepath = fileio.name if fileio else ""
        raise RuntimeError(validation_errors(filepath=filepath, errors=exc.errors())) from exc

    configs_dir: Path = cfg_obj.defaults.configs_dir
    if not configs_dir.is_dir():
        configs_dir.mkdir()

    plugins_dir: Path = cfg_obj.defaults.plugins_dir
    if not plugins_dir.is_dir():
        plugins_dir.mkdir()

    return cfg_obj
