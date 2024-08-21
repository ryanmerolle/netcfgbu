"""This module defines the data models for network configurations."""

import os
import re
from itertools import chain
from os.path import expandvars
from pathlib import Path
from typing import Annotated, Optional, Union

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    FilePath,
    PositiveInt,
    SecretStr,
    ValidationInfo,
    field_validator,
    model_validator,
)
from pydantic.functional_validators import AfterValidator, BeforeValidator
from pydantic_settings import BaseSettings

from . import consts

__all__ = [
    "AppConfig",
    "Credential",
    "InventorySpec",
    "OSNameSpec",
    "LinterSpec",
    "GitSpec",
    "JumphostSpec",
]

_var_re = re.compile(
    r"\${(?P<bname>[a-z0-9_]+)}" r"|" r"\$(?P<name>[^{][a-z_0-9]+)", flags=re.IGNORECASE
)


class NoExtraBaseModel(BaseModel):
    """A base model class that forbids extra fields in derived models."""

    model_config = ConfigDict(extra="forbid")


def expand_env_str(env_string: str) -> str:
    """Expand environment variables in a string.

    Args:
        env_string: The string containing environment variable references.

    Returns:
        str: The string with expanded environment variables.

    Raises:
        EnvironmentError: If an environment variable is missing or empty.
    """
    if found_variables := list(filter(len, chain.from_iterable(_var_re.findall(env_string)))):
        for var in found_variables:
            if (var_val := os.getenv(var)) is None:
                raise OSError(f"Environment variable '{var}' missing.")

            if not var_val:
                raise OSError(f"Environment variable '{var}' empty.")

        return expandvars(env_string)

    return env_string


EnvExpand = Annotated[str, AfterValidator(expand_env_str)]
EnvSecretStr = Annotated[SecretStr, BeforeValidator(expand_env_str)]


class Credential(NoExtraBaseModel):
    """Represents a credential w/ a username & password, supporting environment variable expansion.

    Attributes:
        username: The username for the credential.
        password: The password for the credential.
    """

    username: EnvExpand
    password: EnvSecretStr


# TODO: extra='ignore' is a workaround as specified here
# https://github.com/pydantic/pydantic-settings/issues/178#issuecomment-2037795239
# but may be fixed in a future pydantic v2 release
class DefaultBaseSettings(BaseSettings):
    """A base settings class that ignores extra fields and supports name-based population."""

    model_config = ConfigDict(extra="ignore", populate_by_name=True)


class DefaultCredential(DefaultBaseSettings):
    """Represents default credentials loaded from environment variables.

    Attributes:
        username: The default username for credentials.
        password: The default password for credentials.
    """

    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    username: EnvExpand = Field(validation_alias="NETCFGBU_DEFAULT_USERNAME")
    password: EnvSecretStr = Field(validation_alias="NETCFGBU_DEFAULT_PASSWORD")


class Defaults(DefaultBaseSettings):
    """Represents default application settings.

    Attributes:
        configs_dir: Directory for configuration files.
        plugins_dir: Directory for plugins.
        inventory: Path to the inventory file.
        credentials: Default credentials for the application.
    """

    configs_dir: Optional[EnvExpand] = Field(validation_alias="NETCFGBU_CONFIGSDIR")
    plugins_dir: Optional[EnvExpand] = Field(validation_alias="NETCFGBU_PLUGINSDIR")
    inventory: EnvExpand = Field(validation_alias="NETCFGBU_INVENTORY")
    credentials: DefaultCredential

    @field_validator("inventory")
    @classmethod
    def _inventory_provided(cls, value: str) -> str:  # noqa
        """Validate that the inventory path is not empty.

        Args:
            value: The inventory path.

        Returns:
            str: The validated inventory path.

        Raises:
            ValueError: If the inventory path is empty.
        """
        if not value:
            raise ValueError("inventory empty value not allowed")
        return value

    @field_validator("configs_dir")
    @classmethod
    def _configs_dir(cls, value: str) -> Path:  # noqa
        """Convert the configuration directory path to an absolute path.

        Args:
            value: The configuration directory path.

        Returns:
            Path: The absolute path of the configuration directory.
        """
        return Path(value).absolute()

    @field_validator("plugins_dir", mode="after")
    @classmethod
    def _plugins_dir(cls, value: str) -> Path:  # noqa
        """Convert the plugins directory path to an absolute path.

        If the value is the current working directory and doesn't contain "/plugins",
        append "/plugins" to the path.

        Args:
            value: The plugins directory path.

        Returns:
            Path: The absolute path of the plugins directory.
        """
        if value == os.getenv("PWD") and "/plugins" not in value:
            value += "/plugins"
        return Path(value).absolute()


# A FilePath field whose value can be interpolated from env vars
FilePathEnvExpand = Annotated[FilePath, BeforeValidator(expand_env_str)]


class GitSpec(NoExtraBaseModel):
    """Represents the configuration for a Git repository.

    Attributes:
        name: Optional name for the Git configuration.
        repo: The Git repository URL.
        add_tag: Whether to add a tag or not.
        email: Optional email for Git operations.
        username: Optional username for Git authentication.
        password: Optional password for Git authentication.
        token: Optional token for Git authentication.
        deploy_key: Optional deploy key file path for Git authentication.
        deploy_passphrase: Optional passphrase for the deploy key.
    """

    name: Optional[str] = None
    repo: EnvExpand
    add_tag: Optional[bool] = False
    email: Optional[str] = None
    username: Optional[EnvExpand] = None
    password: Optional[EnvExpand] = None
    token: Optional[EnvSecretStr] = None
    deploy_key: Optional[FilePathEnvExpand] = None
    deploy_passphrase: Optional[EnvSecretStr] = None

    @field_validator("repo")
    @classmethod
    def validate_repo(cls, repo: str) -> str:
        """Validate the Git repository URL.

        Args:
            repo: The repository URL.

        Returns:
            str: The validated repository URL.

        Raises:
            ValueError: If the repository URL does not start with the expected protocols.
        """
        expected = ("https:", "git@")
        if not repo.startswith(expected):
            raise ValueError(f"Bad repo URL [{repo}]: expected to start with {expected}.")
        return repo

    @model_validator(mode="before")
    @classmethod
    def ensure_proper_auth(cls, values: dict) -> dict:
        """Ensure that the correct authentication method is provided.

        Args:
            values: The dictionary of values provided to the model.

        Returns:
            dict: The validated values.

        Raises:
            ValueError: If no or multiple authentication methods are provided, or
            if deploy_passphrase is used without deploy_key.
        """
        req = ("token", "deploy_key", "password")
        auth_vals = list(filter(None, (values.get(auth) for auth in req)))
        auth_count = len(auth_vals)
        if auth_count == 0:
            raise ValueError(f'Missing one of required auth method fields: {"|".join(req)}')

        if auth_count > 1:
            raise ValueError(f'Only one of {"|".join(req)} allowed')

        if values.get("deploy_passphrase") and not values.get("deploy_key"):
            raise ValueError("deploy_key required when using deploy_passphrase")

        return values


class OSNameSpec(NoExtraBaseModel):
    """Represents the configuration for a specific OS name.

    Attributes:
        credentials: List of credentials for this OS.
        pre_get_config: Commands to run before getting the config.
        get_config: Command to get the config.
        connection: Connection type.
        linter: Linter to use for this OS.
        timeout: Timeout for getting the config.
        ssh_configs: SSH configurations.
        prompt_pattern: Pattern to match the prompt.
    """

    credentials: Optional[list[Credential]] = None
    pre_get_config: Optional[Union[str, list[str]]] = None
    get_config: Optional[str] = None
    connection: Optional[str] = None
    linter: Optional[str] = None
    timeout: PositiveInt = Field(consts.DEFAULT_GETCONFIG_TIMEOUT)
    ssh_configs: Optional[dict] = None
    prompt_pattern: Optional[str] = None


class LinterSpec(NoExtraBaseModel):
    """Represents the configuration for a linter.

    Attributes:
        config_starts_after: The marker indicating where the config starts.
        config_ends_at: The marker indicating where the config ends.
    """

    config_starts_after: Optional[str] = None
    config_ends_at: Optional[str] = None


class InventorySpec(NoExtraBaseModel):
    """Represents the configuration for an inventory specification.

    Attributes:
        name: Optional name for the inventory.
        script: The script to execute for the inventory.
    """

    name: Optional[str] = None
    script: EnvExpand

    @field_validator("script")
    @classmethod
    def validate_script(cls, script_exec: str) -> str:  # noqa
        """Validate the script field of the InventorySpec.

        Args:
            script_exec: The script execution string.

        Returns:
            str: The validated script execution string.

        Raises:
            ValueError: If the script is not executable, is invalid, or the file does not exist.
        """
        try:
            script_bin, *script_vargs = script_exec.split()
            if not os.path.isfile(script_bin):
                raise ValueError(f"File not found: {script_bin}")
            if not os.access(script_bin, os.X_OK):
                raise ValueError(f"{script_bin} is not executable")
        except Exception as exc:
            raise ValueError(f"Invalid script: {exc}") from exc
        return script_exec


class JumphostSpec(NoExtraBaseModel):
    """Represents the configuration for a jumphost.

    Attributes:
        proxy: The proxy host or address for the jumphost.
        name: Optional name for the jumphost.
        include: Optional list of hosts to include when using the jumphost.
        exclude: Optional list of hosts to exclude when using the jumphost.
        timeout: Timeout for connecting through the jumphost.
    """

    proxy: str
    name: Optional[str] = None
    include: Optional[list[str]] = None
    exclude: Optional[list[str]] = None
    timeout: PositiveInt = Field(consts.DEFAULT_LOGIN_TIMEOUT)

    @model_validator(mode="after")
    def default_name(self):  # noqa
        """Set the default name for the jumphost if not provided.

        If the name is not set, it will be set to the proxy value.

        Returns:
            JumphostSpec: The updated JumphostSpec instance.
        """
        if not self.name:
            self.name = self.proxy
        return self


class AppConfig(NoExtraBaseModel):
    """Represents the overall application configuration.

    Attributes:
        defaults: Default settings for the application.
        credentials: Optional list of credentials for the application.
        linters: Optional dictionary of linter specifications.
        os_name: Optional dictionary of OS-specific configurations.
        inventory: Optional list of inventory specifications.
        logging: Optional logging configuration.
        ssh_configs: Optional SSH configurations.
        git: Optional list of Git repository configurations.
        jumphost: Optional list of jumphost configurations.
    """

    defaults: Defaults
    credentials: Optional[list[Credential]] = None
    linters: Optional[dict[str, LinterSpec]] = None
    os_name: Optional[dict[str, OSNameSpec]] = None
    inventory: Optional[list[InventorySpec]] = None
    logging: Optional[dict] = None
    ssh_configs: Optional[dict] = None
    git: Optional[list[GitSpec]] = None
    jumphost: Optional[list[JumphostSpec]] = None

    @field_validator("os_name")
    @classmethod
    def _linters(
        cls, os_configs: dict[str, OSNameSpec], info: ValidationInfo
    ) -> dict[str, OSNameSpec]:  # noqa
        """Validate that the linters specified in os_name configurations are defined.

        Args:
            os_configs: The os_name configurations.
            info: Validation context information.

        Returns:
            Dict[str, OSNameSpec]: The validated os_name configurations.

        Raises:
            ValueError: If an OS spec uses an undefined linter.
        """
        if (linters := info.data.get("linters")) is None:
            # sometimes it's still None
            # see tests/test_config.py::test_config_linter_fail
            linters = {}
        if os_configs is not None:
            for os_name, os_spec in os_configs.items():
                if os_spec.linter and os_spec.linter not in linters:
                    raise ValueError(
                        f'OS spec "{os_name}" using undefined linter "{os_spec.linter}"'
                    )
        return os_configs
