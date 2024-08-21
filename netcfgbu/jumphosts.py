"""Provides jumphost functionality for devices requiring a proxy server in inventory."""

import asyncio

# -----------------------------------------------------------------------------
# System Imports
# -----------------------------------------------------------------------------
from typing import AnyStr, Optional
from urllib.parse import urlparse

# -----------------------------------------------------------------------------
# Public Imports
# -----------------------------------------------------------------------------
import asyncssh
from first import first

# -----------------------------------------------------------------------------
# Private Imports
# -----------------------------------------------------------------------------
from .config_model import JumphostSpec
from .filtering import create_filter
from .logger import get_logger


class JumpHost:
    """Represents a tunnel connection for devices in inventory that require one."""

    available = []

    def __init__(self, spec: JumphostSpec, field_names: list[AnyStr]):
        """Prepare a jump host instance for potential use.

        This method does not connect to the proxy system.

        Args:
            spec: The jumphost configuraiton
            field_names: List of inventory field names that are used to prepare any necessary
            filtering functionality
        """
        self._spec = spec
        self.filters = []
        self._conn = None
        self._init_filters(field_names)

    @property
    def tunnel(self):
        """Returns the SSH client connection for the jumphost, used as a tunnel to target devices.

        Raises:
            RuntimeError: If the SSH client is not connected.
        """
        if not self.is_active:
            raise RuntimeError(f"Attempting to use JumpHost {self.name}, but not connected")
        return self._conn

    @property
    def name(self):
        """Returns the string-name of the jump host."""
        return self._spec.name

    @property
    def is_active(self):
        """Return True if the jumphost is connected, False otherwise."""
        return bool(self._conn)

    def _init_filters(self, field_names):
        """Called only by init, prepares the jump host filter functions to later use."""
        include, exclude = self._spec.include, self._spec.exclude
        if include:
            self.filters.append(
                create_filter(constraints=include, field_names=field_names, include=True)
            )

        if exclude:
            self.filters.append(
                create_filter(constraints=exclude, field_names=field_names, include=False)
            )

    async def connect(self):
        """Establishes a connection to the jumphost for later use as a tunnel to other devices."""
        proxy_parts = urlparse("ssh://" + self._spec.proxy)

        conn_args = {"host": proxy_parts.hostname, "known_hosts": None}
        if proxy_parts.username:
            conn_args["username"] = proxy_parts.username

        if proxy_parts.port:
            conn_args["port"] = proxy_parts.port

        async def connect_to_jh():
            """Obtain the SSH client connection."""
            self._conn = await asyncssh.connect(**conn_args)

        await asyncio.wait_for(connect_to_jh(), timeout=self._spec.timeout)

    def filter(self, inv_rec):
        """Determines if this jump host is needed for the given inventory record.

        Args:
            inv_rec: The inventory record to check.

        Returns:
            bool: True if the jump host is required, False otherwise.
        """
        return any(_f(inv_rec) for _f in self.filters)


# -----------------------------------------------------------------------------
#
#                               CODE BEGINS
#
# -----------------------------------------------------------------------------


def init_jumphosts(jumphost_specs: list[JumphostSpec], inventory: list[dict]):
    """Initializes Jump Host instances for accessing devices that require jump hosts.

    Args:
        jumphost_specs (list[JumphostSpec]): List of jump host specifications from the app
        configuration.
        inventory (list[dict]): List of inventory records to determine which jump hosts are required
        based on inventory filtering.
    """
    field_names = inventory[0].keys()

    # create a list of jump host instances so that we can determine which, if
    # any, will be used during the execution of the command.

    jh_list = [JumpHost(spec, field_names=field_names) for spec in jumphost_specs]

    req_jh = {
        use_jh for rec in inventory if (use_jh := first(jh for jh in jh_list if jh.filter(rec)))
    }

    JumpHost.available = list(req_jh)


async def connect_jumphosts():
    """Connects to all required jump host servers.

    This coroutine should be called before executing any SSH tasks, such as login or backup.

    Returns:
        bool: True if all jump host servers are connected, False otherwise (check logs for errors).
    """
    log = get_logger()
    jump_host_connected = True

    for jump_host in JumpHost.available:
        try:
            await jump_host.connect()
            log.info("JUMPHOST: connected to %s", jump_host.name)

        except (asyncio.TimeoutError, asyncssh.Error) as exc:
            errmsg = str(exc) or exc.__class__.__name__
            log.error("JUMPHOST: connect to %s failed: %s", jump_host.name, errmsg)
            jump_host_connected = False

    return jump_host_connected


def get_jumphost(inv_rec: dict) -> Optional[JumpHost]:
    """Returns the jumphost instance for the given inventory record if tunneling is required.

    Args:
        inv_rec (dict): Inventory record for which to determine the jumphost.

    Returns:
        Optional[JumpHost]: The jumphost instance if required, otherwise None.
    """
    return first(jh for jh in JumpHost.available if jh.filter(inv_rec))
