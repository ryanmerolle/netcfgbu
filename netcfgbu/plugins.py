from collections import defaultdict
from pathlib import Path

from netcfgbu.logger import get_logger

_registered_plugins = defaultdict(dict)

_PLUGIN_NAME = "hooks"

log = get_logger()


def load_plugins(plugins_dir: Path) -> None:
    """Loads all Python files in the specified directory as plugins and registers
    subclasses of the Plugin class.

    Args:
        plugins_dir (Path): The directory containing plugin Python files.

    Returns:
        None
    """
    if not plugins_dir.is_dir():
        log.warning("Plugin directory %s does not exist.", plugins_dir)
        return

    from importlib.machinery import FileFinder, SourceFileLoader

    finder = FileFinder(str(plugins_dir), (SourceFileLoader, [".py"]))  # noqa

    log.info("Loading plugins from %s", plugins_dir)
    for py_file in plugins_dir.glob("*.py"):
        mod_name = py_file.stem
        finder.find_spec(mod_name).loader.load_module(mod_name)

    _registered_plugins[_PLUGIN_NAME] = []
    for subclass in Plugin.__subclasses__():
        _registered_plugins[_PLUGIN_NAME].append(subclass)


class Plugin:
    """base plugin class to use for subclassed plugins to enable custom methods to be run"""

    name = None

    def report(report):
        """Returns a report specific plugin once the netcfgbu backup process completes"""
        pass

    def backup_success(rec: dict, res: bool):
        """Returns a backup success specific plugin once the netcfgbu backup process completes"""
        pass

    def backup_failed(rec: dict, exc: str):
        """Returns a backup failed specific plugin once the netcfgbu backup process completes"""
        pass

    def git_report(success: bool, message: str):
        """Returns a git report specific plugin once the netcfgbu vcs save process completes"""
        pass

    def run_backup_failed(rec: dict, exc: str) -> None:
        """Execute plugins submodules for backup failed plugins"""
        tasks = _registered_plugins[_PLUGIN_NAME] or Plugin
        if isinstance(tasks, list):
            for task in tasks:
                task.backup_failed(rec, exc)
        else:
            tasks.backup_failed(rec, exc)

    def run_backup_success(rec: dict, res: str) -> None:
        """Execute plugins submodules for backup success plugins"""
        tasks = _registered_plugins[_PLUGIN_NAME] or Plugin
        if isinstance(tasks, list):
            for task in tasks:
                task.backup_success(rec, res)
        else:
            tasks.backup_success(rec, res)

    def run_report(task_results) -> None:
        """Execute plugins submodules for report plugins"""
        tasks = _registered_plugins[_PLUGIN_NAME] or Plugin
        if isinstance(tasks, list):
            for task in tasks:
                task.report(task_results)
        else:
            tasks.report(task_results)

    def run_git_report(success: bool, message: str) -> None:
        """Execute plugins submodules for vcs save plugins"""
        tasks = _registered_plugins[_PLUGIN_NAME] or Plugin
        if isinstance(tasks, list):
            for task in tasks:
                task.git_report(success, message)
        else:
            tasks.git_report(success, message)
