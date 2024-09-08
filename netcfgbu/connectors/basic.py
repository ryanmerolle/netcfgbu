"""This module provides basic connection functionality for network devices."""

import asyncio
import io
import re
from copy import copy
from pathlib import Path
from typing import Optional

import aiofiles
import asyncssh

from netcfgbu import consts, jumphosts, linter
from netcfgbu.config_model import AppConfig, Credential, OSNameSpec
from netcfgbu.logger import get_logger

__all__ = ["BasicSSHConnector", "set_max_startups"]

# TODO: FIX mypy errors


class BasicSSHConnector:
    """Defines and manages SSH-based configuration file backups.

    This class is initialized with the host configuration, OS specification, and application
    configuration. The primary function is to execute the configuration backup process via SSH.
    Callers should await `backup_config()` to start the backup process.

    If `pre_get_config` is defined, it executes those commands before running `get_config`.
    If not, only the `get_config` command is executed.

    Attributes:
    ----------
    cls.prompt_pattern: re.Pattern
        Compiled regex pattern to detect the CLI prompt.

    cls.get_config: str
        CLI command to retrieve the running configuration.

    cls.pre_get_config: Optional[Union[str, list]]
        CLI command(s) to disable paging, preventing output blocking by the "--More--" prompt.
    """

    prompt_pattern = re.compile(
        (
            "^\r?(["
            + consts.PROMPT_VALID_CHARS
            + f"]{{{1},{consts.PROMPT_MAX_CHARS}}}"  # pylint: disable=C0209
            + r"\s*[#>$])\s*$"
        ).encode("utf-8"),
        flags=(re.M | re.I),
    )

    get_config = "show running-config"
    pre_get_config = None

    _max_startups_sem4 = asyncio.Semaphore(consts.DEFAULT_MAX_STARTUPS)

    def __init__(self, host_cfg: dict, os_spec: OSNameSpec, app_cfg: AppConfig):
        """Initializes the BasicSSHConnector with host, OS, and application configurations.

        Args:
            host_cfg (dict): Host configuration details.
            os_spec (OSNameSpec): OS-specific configuration details.
            app_cfg (AppConfig): Application configuration details.
        """
        self.host_cfg = host_cfg
        self.name = host_cfg.get("host") or host_cfg.get("ipaddr")
        self.app_cfg = app_cfg
        self.os_spec = copy(os_spec)
        self.log = get_logger()

        if not self.os_spec.pre_get_config:
            self.os_spec.pre_get_config = self.pre_get_config

        if not self.os_spec.get_config:
            self.os_spec.get_config = self.get_config

        self.os_name = host_cfg["os_name"]

        self.conn_args = {
            "host": self.host_cfg.get("ipaddr") or self.host_cfg.get("host"),
            "known_hosts": None,
        }

        if app_cfg.ssh_configs:
            self.conn_args.update(app_cfg.ssh_configs)

        if os_spec.ssh_configs:
            self.conn_args.update(os_spec.ssh_configs)

        if os_spec.prompt_pattern:
            self.prompt_pattern = re.compile(
                (r"^\r?(" + os_spec.prompt_pattern + r")\s*$").encode("utf-8"),
                flags=(re.M | re.I),
            )

        self._cur_prompt: Optional[str] = None
        self.config = None
        self.save_file = None
        self.failed = None

        self.conn = None
        self.process: Optional[asyncssh.SSHClientProcess] = None
        self.creds = self._setup_creds()

        if not self.creds:
            raise RuntimeError(f"{self.name}: No credentials")

    @classmethod
    def set_max_startups(cls, max_startups):
        """Sets the maximum number of concurrent SSH connections.

        Args:
            max_startups: The maximum number of concurrent SSH connections allowed.
        """
        cls._max_startups_sem4 = asyncio.Semaphore(value=max_startups)

    # -------------------------------------------------------------------------
    #
    #                       Backup Config Coroutine Task
    #
    # -------------------------------------------------------------------------

    async def backup_config(self) -> Optional[bool]:
        """Main coroutine to back up the running configuration to a text file.

        Returns:
            True if the backup process succeeds, otherwise returns an exception.
        """
        async with await self.login():
            try:
                await self.get_running_config()
                retval = True
            except Exception as exc:
                retval = exc

            finally:
                await self.close()

        if self.config:
            await self.save_config()

        return retval

    # -------------------------------------------------------------------------
    #
    #                       Test Login Coroutine Task
    #
    # -------------------------------------------------------------------------

    async def test_login(self, timeout: int) -> Optional[str]:
        """Tests SSH login to the target device.

        Args:
            timeout: Timeout for the login attempt.

        Returns:
            The username used if login is successful, None otherwise.
        """
        login_as = None
        self.os_spec.timeout = timeout

        try:
            async with await self.login():
                login_as = self.conn_args["username"]

        except asyncssh.PermissionDenied:
            pass

        return login_as

    # -------------------------------------------------------------------------
    #
    #                            Get Configuration
    #
    # -------------------------------------------------------------------------

    async def get_running_config(self) -> None:
        """Retrieves the running configuration from the device.

        Raises:
            asyncio.TimeoutError: If any step of the process times out.
        """
        command = self.os_spec.get_config
        timeout = self.os_spec.timeout
        log_msg = f"GET-CONFIG: {self.name} timeout={timeout}"

        if not self.process:
            self.log.info(log_msg)
            res = await self.conn.run(command)
            self.conn.close()
            ln_at = res.stdout.find(command) + len(command) + 1
            self.config = res.stdout[ln_at:]
            return

        at_prompt = False
        paging_disabled = False

        try:
            res = await asyncio.wait_for(self.read_until_prompt(), timeout=15)
            at_prompt = True
            # TODO - Add hostname to debug of AT-PROMPT
            self.log.debug("AT-PROMPT: %s", res)

            res = await asyncio.wait_for(self.run_disable_paging(), timeout=timeout)
            paging_disabled = True
            # TODO - Add hostname to debug of AFTER-PRE-GET-RUNNING
            self.log.debug("AFTER-PRE-GET-RUNNING: %s", res)

            self.log.info(log_msg)
            self.config = await asyncio.wait_for(self.run_command(command), timeout=timeout)

        except asyncio.TimeoutError as exc:
            if not at_prompt:
                msg = "Timeout awaiting prompt"
            elif not paging_disabled:
                msg = "Timeout executing pre-get-running commands"
            else:
                msg = "Timeout getting running configuration"

            raise asyncio.TimeoutError(msg) from exc

    # -------------------------------------------------------------------------
    #
    #                                  Login
    #
    # -------------------------------------------------------------------------

    def _setup_creds(self) -> list:
        """Sets up the credentials for the SSH connection.

        Returns:
            List of credentials to try for the connection.
        """
        creds = []

        # use credential from inventory host record first, if defined
        # TODO: bug-fix where these values are None; but exist in dict :-(
        if all(key in self.host_cfg for key in ("username", "password")):
            creds.append(
                Credential(
                    username=self.host_cfg.get("username"),
                    password=self.host_cfg.get("password"),
                )
            )

        # add any addition credentials defined in the os spec
        if self.os_spec.credentials:
            creds.extend(self.os_spec.credentials)

        # add the default credentials
        creds.append(self.app_cfg.defaults.credentials)

        # add any additional global credentials
        if self.app_cfg.credentials:
            creds.extend(self.app_cfg.credentials)

        return creds

    async def login(self) -> asyncssh.SSHClientConnection:
        """Executes the SSH login process to the target device.

        Tries each credential provided in the app configuration in order.

        Returns:
            An SSHClientConnection if login is successful.

        Raises:
            asyncssh.PermissionDenied: If none of the credentials result in a successful login.
            asyncio.TimeoutError: If attempting to connect to a device exceeds the timeout value.
            Exception: If a specific exception is raised other than the above, it will raise it so
            we can fail the ssh connection quicker. Examples: DNS resolution issues & no route to
            host.
        """
        timeout: int = self.os_spec.timeout

        # if this host requires the use of a JumpHost, then configure the
        # connection args to include the supporting jumphost tunnel connection.

        if jump_host := jumphosts.get_jumphost(self.host_cfg):
            self.conn_args["tunnel"] = jump_host.tunnel

        # interate through all of the credential options until one is accepted.
        # the number of max setup connections is controlled by a semaphore
        # instance so that the server running this code is not overwhelmed.

        for try_cred in self.creds:
            try:
                self.failed = None
                self.conn_args.update(
                    {
                        "username": try_cred.username,
                        "password": try_cred.password.get_secret_value(),
                    }
                )
                async with self.__class__._max_startups_sem4:
                    login_msg = (
                        f"LOGIN: {self.name} ({self.os_name}) timeout={timeout}s "
                        f"as {self.conn_args['username']}"
                    )

                    self.log.info(login_msg)
                    self.conn = await asyncio.wait_for(asyncssh.connect(**self.conn_args), timeout)
                    self.log.info("CONNECTED: %s", self.name)

                    if self.os_spec.pre_get_config:
                        self.process = await self.conn.create_process(
                            term_type="vt100", encoding=None
                        )

                    return self.conn

            except asyncssh.PermissionDenied as exc:
                self.failed = exc
                continue
            except Exception as exc:
                raise exc  # Re-raise any other exceptions

        # Indicate that the login failed with the number of credential
        # attempts.

        raise asyncssh.PermissionDenied(
            reason=f"No valid username/password, attempted {len(self.creds)} credentials."
        )

    async def close(self) -> None:
        """Closes the SSH connection."""
        self.conn.close()
        await self.conn.wait_closed()
        self.log.info("CLOSED: %s", self.name)

    # -------------------------------------------------------------------------
    #
    #                                    Helpers
    #
    # -------------------------------------------------------------------------

    async def read_until_prompt(self) -> bytes:
        """Reads from the SSH process until the prompt is detected.

        Returns:
            The output read until the prompt is found as a byte string.
        """
        output = b""
        while True:
            self.log.debug("%s - %s", self.name, output)
            output += await self.process.stdout.read(io.DEFAULT_BUFFER_SIZE)
            nl_at = output.rfind(b"\n")
            if mobj := self.prompt_pattern.match(output[nl_at + 1 :]):
                self._cur_prompt = mobj.group(1)
                return output[0:nl_at]

    async def run_command(self, command: str) -> bytes:
        """Runs a command on the SSH process and reads the output until the prompt is detected.

        Args:
            command: The command to run on the SSH device.

        Returns:
            The output of the command as a byte string.
        """
        wr_cmd = command + "\n"
        self.process.stdin.write(wr_cmd.encode("utf-8"))
        output = await self.read_until_prompt()
        return output[len(wr_cmd) + 1 :]

    async def run_disable_paging(self) -> None:
        """Executes the pre-get configuration commands to disable paging on the device."""
        disable_paging_commands = self.os_spec.pre_get_config
        if not isinstance(disable_paging_commands, list):
            disable_paging_commands = [disable_paging_commands]

        for cmd in disable_paging_commands:
            # TODO: need to check result for errors
            await self.run_command(cmd)

    # -------------------------------------------------------------------------
    #
    #                         Store Config to Filesystem
    #
    # -------------------------------------------------------------------------

    async def save_config(self) -> None:
        """Saves the retrieved configuration to a file on the filesystem.

        If a linter is specified in the OS spec, the configuration content is processed by the
        linter before saving.
        """
        if isinstance(self.config, bytes):
            self.config = self.config.decode("utf-8", "ignore")

        config_content = self.config.replace("\r", "")

        if linter_name := self.os_spec.linter:
            lint_spec = self.app_cfg.linters[linter_name]
            orig = config_content
            config_content = linter.lint_content(config_content, lint_spec)
            if orig == config_content:
                self.log.debug("LINT no change on %s", self.name)

        self.save_file = Path(self.app_cfg.defaults.configs_dir) / f"{self.name}.cfg"

        async with aiofiles.open(self.save_file, mode="w+", encoding="utf-8") as ofile:
            await ofile.write(config_content)
            await ofile.write("\n")


def set_max_startups(count: int, cls=BasicSSHConnector) -> None:
    """Sets the maximum number of concurrent SSH connections for the specified class.

    Args:
        count: The maximum number of concurrent connections.
        cls: The class for which to set the maximum startups. Defaults to BasicSSHConnector.
    """
    cls.set_max_startups(count)
