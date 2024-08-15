import os
import re
from itertools import chain
from os.path import expandvars
from pathlib import Path
from typing import Annotated, Dict, List, Optional, Union

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
    model_config = ConfigDict(extra="forbid")


def expand_env_str(env_string):
    """
    When a string value contains a reference to an environment variable, use
    this type to expand the contents of the variable using os.path.expandvars.

    For example like:
        password = "$MY_PASSWORD"
        foo_password = "${MY_PASSWORD}_foo"

    will be expanded, given MY_PASSWORD is set to 'boo!' in the environment:
        password -> "boo!"
        foo_password -> "boo!_foo"
    """

    if found_vars := list(
        filter(len, chain.from_iterable(_var_re.findall(env_string)))
    ):
        for var in found_vars:
            if (var_val := os.getenv(var)) is None:
                raise EnvironmentError(f'Environment variable "{var}" missing.')

            if not len(var_val):
                raise EnvironmentError(f'Environment variable "{var}" empty.')

        return expandvars(env_string)

    return env_string


EnvExpand = Annotated[str, AfterValidator(expand_env_str)]
EnvSecretStr = Annotated[SecretStr, BeforeValidator(expand_env_str)]


class Credential(NoExtraBaseModel):
    username: EnvExpand
    password: EnvSecretStr


# TODO: extra='ignore' is a workaround as specified here
# https://github.com/pydantic/pydantic-settings/issues/178#issuecomment-2037795239
# but may be fixed in a future pydantic v2 release
class DefaultBaseSettings(BaseSettings):
    model_config = ConfigDict(extra="ignore", populate_by_name=True)


class DefaultCredential(DefaultBaseSettings):
    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    username: EnvExpand = Field(validation_alias="NETCFGBU_DEFAULT_USERNAME")
    password: EnvSecretStr = Field(validation_alias="NETCFGBU_DEFAULT_PASSWORD")


class Defaults(DefaultBaseSettings):
    configs_dir: Optional[EnvExpand] = Field(validation_alias="NETCFGBU_CONFIGSDIR")
    plugins_dir: Optional[EnvExpand] = Field(validation_alias="NETCFGBU_PLUGINSDIR")
    inventory: EnvExpand = Field(validation_alias="NETCFGBU_INVENTORY")
    credentials: DefaultCredential

    @field_validator("inventory")
    @classmethod
    def _inventory_provided(cls, value):  # noqa
        if not len(value):
            raise ValueError("inventory empty value not allowed")
        return value

    @field_validator("configs_dir")
    @classmethod
    def _configs_dir(cls, value):  # noqa
        return Path(value).absolute()

    @field_validator("plugins_dir", mode="after")
    @classmethod
    def _plugins_dir(cls, value):  # noqa
        if value == os.getenv("PWD") and "/plugins" not in value:
            value = value + "/plugins"
        return Path(value).absolute()


"""A FilePath field whose value can be interpolated from env vars"""
FilePathEnvExpand = Annotated[FilePath, BeforeValidator(expand_env_str)]


class GitSpec(NoExtraBaseModel):
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
    def validate_repo(cls, repo):  # noqa
        expected = ("https:", "git@")
        if not repo.startswith(expected):
            raise ValueError(
                f"Bad repo URL [{repo}]: expected to start with {expected}."
            )
        return repo

    @model_validator(mode="before")
    @classmethod
    def ensure_proper_auth(cls, values):
        req = ("token", "deploy_key", "password")
        auth_vals = list(filter(None, (values.get(auth) for auth in req)))
        auth_count = len(auth_vals)
        if auth_count == 0:
            raise ValueError(
                f'Missing one of required auth method fields: {"|".join(req)}'
            )

        if auth_count > 1:
            raise ValueError(f'Only one of {"|".join(req)} allowed')

        if values.get("deploy_passphrase") and not values.get("deploy_key"):
            raise ValueError("deploy_key required when using deploy_passphrase")

        return values


class OSNameSpec(NoExtraBaseModel):
    credentials: Optional[List[Credential]] = None
    pre_get_config: Optional[Union[str, List[str]]] = None
    get_config: Optional[str] = None
    connection: Optional[str] = None
    linter: Optional[str] = None
    timeout: PositiveInt = Field(consts.DEFAULT_GETCONFIG_TIMEOUT)
    ssh_configs: Optional[Dict] = None
    prompt_pattern: Optional[str] = None


class LinterSpec(NoExtraBaseModel):
    config_starts_after: Optional[str] = None
    config_ends_at: Optional[str] = None


class InventorySpec(NoExtraBaseModel):
    name: Optional[str] = None
    script: EnvExpand

    @field_validator("script")
    @classmethod
    def validate_script(cls, script_exec):  # noqa
        script_bin, *script_vargs = script_exec.split()
        if not os.path.isfile(script_bin):
            raise ValueError(f"File not found: {script_bin}")

        if not os.access(script_bin, os.X_OK):
            raise ValueError(f"{script_bin} is not executable")

        return script_exec


class JumphostSpec(NoExtraBaseModel):
    proxy: str
    name: Optional[str] = None
    include: Optional[List[str]] = None
    exclude: Optional[List[str]] = None
    timeout: PositiveInt = Field(consts.DEFAULT_LOGIN_TIMEOUT)

    @model_validator(mode="after")
    def default_name(self):  # noqa
        if not self.name:
            self.name = self.proxy
        return self


class AppConfig(NoExtraBaseModel):
    defaults: Defaults
    credentials: Optional[List[Credential]] = None
    linters: Optional[Dict[str, LinterSpec]] = None
    os_name: Optional[Dict[str, OSNameSpec]] = None
    inventory: Optional[List[InventorySpec]] = None
    logging: Optional[Dict] = None
    ssh_configs: Optional[Dict] = None
    git: Optional[List[GitSpec]] = None
    jumphost: Optional[List[JumphostSpec]] = None

    @field_validator("os_name")
    @classmethod
    def _linters(cls, v, info: ValidationInfo):  # noqa
        if (linters := info.data.get("linters")) is None:
            # sometimes it's still None
            # see tests/test_config.py::test_config_linter_fail
            linters = dict()
        if v is not None:
            for os_name, os_spec in v.items():
                if os_spec.linter and os_spec.linter not in linters:
                    raise ValueError(
                        f'OS spec "{os_name}" using undefined linter "{os_spec.linter}"'
                    )
        return v
