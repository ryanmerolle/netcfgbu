"""This module manages the inventory of network devices."""

import os
from pathlib import Path

from .config_model import AppConfig, InventorySpec
from .filetypes import CommentedCsvReader
from .filtering import create_filter
from .logger import get_logger


def load(app_cfg: AppConfig, limits=None, excludes=None):
    """Load and filter inventory records based on the provided limits and excludes.

    Args:
        app_cfg: The application configuration containing the inventory file path.
        limits: Optional list of constraints to limit the inventory records.
        excludes: Optional list of constraints to exclude certain inventory records.

    Returns:
        List of filtered inventory records.

    Raises:
        FileNotFoundError: If the inventory file does not exist.
    """
    inventory_file = Path(app_cfg.defaults.inventory)
    if not inventory_file.exists():
        raise FileNotFoundError(f"Inventory file does not exist: {inventory_file.absolute()}")

    iter_recs = CommentedCsvReader(inventory_file.open(encoding="utf-8"))
    field_names = iter_recs.fieldnames

    if limits:
        filter_fn = create_filter(constraints=limits, field_names=field_names)
        iter_recs = filter(filter_fn, iter_recs)

    if excludes:
        filter_fn = create_filter(constraints=excludes, field_names=field_names, include=False)
        iter_recs = filter(filter_fn, iter_recs)

    return list(iter_recs)


def build(inv_def: InventorySpec) -> int:
    """Execute the script defined in the inventory specification.

    Args:
        inv_def: The inventory specification containing the script to execute.

    Returns:
        int: The result code of the executed script.

    Logs a warning if the script returns a non-zero exit code.
    """
    log = get_logger()

    # the script field is required so therefore it exists from
    # config-load-validation.

    script = inv_def.script
    log.info("Executing script: [%s]", script)

    # Note: if you want to check the pass/fail of this call os.system() will
    # return 0 or non-zero as the exit code from the underlying script.  There
    # is no exception handling.  If you want to do exception handling, then
    # you'll need to use subprocess.call in place of os.system.

    result_code = os.system(script)  # nosec
    if result_code != 0:  # nosec
        log.warning("inventory script returned non-zero return code: %s", result_code)

    return result_code
