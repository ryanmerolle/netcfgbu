"""This module defines constants used throughout the netcfgbu package."""

DEFAULT_MAX_STARTUPS = 100
DEFAULT_LOGIN_TIMEOUT = 30
DEFAULT_GETCONFIG_TIMEOUT = 60
DEFAULT_PROBE_TIMEOUT = 10
DEFAULT_GIT_BRANCH = "main"

# DEFAULT_CONFIG_STARTS_AFTER = "Current configuration"
# DEFAULT_CONFIG_ENDS_WITH = "end"

PROMPT_VALID_CHARS = r"a-z0-9.\-_@()/:~"
PROMPT_MAX_CHARS = 65

INVENTORY_FIELDNAMES = ["host", "ipaddr", "os_name", "username", "password"]
