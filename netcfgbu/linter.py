import re
from pathlib import Path

from .config_model import LinterSpec
from .logger import get_logger

log = get_logger()


def lint_content(config_content, lint_spec: LinterSpec) -> str:
    """
    Lint the configuration content based on the provided linting specification.

    Args:
        config_content: The original configuration content as a string.
        lint_spec: An instance of LinterSpec containing the linting rules.

    Returns:
        The linted configuration content as a string.
    """
    start_offset = 0
    end_offset = None

    if not start_offset and lint_spec.config_starts_after and (start_mo := re.search(
        f"^{lint_spec.config_starts_after}.*$", config_content, re.MULTILINE
    )):
        start_offset = start_mo.end() + 1

    if lint_spec.config_ends_at:
        # if not found, rfind returns -1 to indciate; therefore need to make
        # this check
        if (found := config_content.rfind("\n" + lint_spec.config_ends_at)) > 0:
            end_offset = found

    config_content = config_content[start_offset:end_offset]

    # if remove_lines := lint_spec.remove_lines:
    #     remove_lines_reg = "|".join(remove_lines)
    #     config_content = re.sub(remove_lines_reg, "", config_content, flags=re.M)

    return config_content


def lint_file(fileobj: Path, lint_spec) -> bool:
    """
    Perform the linting function on the content of the given file.

    Args:
        fileobj: A Path object representing the file to lint.
        lint_spec: An instance of LinterSpec containing the linting rules.

    Returns:
        bool: True if the content was changed, False otherwise.
    """
    orig_config_content = fileobj.read_text()

    config_content = lint_content(orig_config_content, lint_spec)
    if config_content == orig_config_content:
        log.debug("LINT no change on %s", fileobj.name)
        return False

    fileobj.rename(str(fileobj.absolute()) + ".orig")
    fileobj.write_text(config_content)
    return True
