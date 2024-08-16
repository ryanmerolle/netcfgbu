"""
This file contains the Version Control System (VCS) integration
using Git as the backend.   The following functions are exported
for use:

   * vcs_prepare:
      Used to prepare the repo directory for VCS use.

   * vcs_save:
      Used to save files in the repo directory into VCS and tag the collection
      with a git tag.

   * vcs_status:
      Used to show the current target status of file changes.

"""

# -----------------------------------------------------------------------------
# System Imports
# -----------------------------------------------------------------------------

import os
from datetime import datetime
from pathlib import Path
from typing import Optional
from urllib.parse import urlsplit

import pexpect

from netcfgbu import consts
from netcfgbu.config_model import GitSpec
from netcfgbu.logger import get_logger
from netcfgbu.plugins import Plugin

# -----------------------------------------------------------------------------
# Public Imports
# -----------------------------------------------------------------------------


# -----------------------------------------------------------------------------
# Private Imports
# -----------------------------------------------------------------------------


GIT_BIN = "git"


def generate_commit_message() -> str:
    """
    Create a commit message using the current timestamp with
    format <year><month#><day#>_<24hr><minute><sec>
    """
    return datetime.now().strftime("%Y%m%d_%H%M%S")  # pragma: no cover


# -----------------------------------------------------------------------------
#
#                             Git VCS Entrypoints
#
# -----------------------------------------------------------------------------


def vcs_save(
    gh_cfg: GitSpec,
    repo_dir: Path,
    add_tag: bool = False,
    message: Optional[str] = None,
) -> bool:
    log = get_logger()
    log.info("VCS update git: %s", gh_cfg.repo)

    ghr = git_runner(gh_cfg, repo_dir)
    if not message:
        message = generate_commit_message()

    output = ghr.run("status")
    if "nothing to commit" in output:
        log.info("VCS no changes, skipping")
        Plugin.run_git_report(success=False, message=message if add_tag else None)
        return False

    log.info("VCS saving changes%s", f", tag={message}" if add_tag else "")

    # Always execute these commands
    commands = [("add -A", False), (f"commit -m '{message}'", False), ("push", True)]

    # Execute these commands only if tagging is not skipped
    if add_tag:
        commands.extend(
            [
                (f"tag -a '{message}' -m '{message}'", False),
                ("push --tags", True),
            ]
        )

    for cmd, req_auth in commands:
        ghr.run(cmd, req_auth)

    Plugin.run_git_report(success=True, message=message)
    return True


def vcs_prepare(spec: GitSpec, repo_dir: Path) -> None:
    log = get_logger()
    log.info("VCS prepare git: %s", spec.repo)

    ghr = git_runner(spec, repo_dir)
    ghr.git_init()
    ghr.git_pull()


def vcs_status(spec: GitSpec, repo_dir: Path):
    log = get_logger()
    log.info(
        """
VCS diffs git: %s
             dir: %s
""",
        spec.repo,
        str(repo_dir),
    )

    ghr = git_runner(spec, repo_dir)
    return ghr.run("status")


# -----------------------------------------------------------------------------
#
#                      Git Runners to perform commands
#
# -----------------------------------------------------------------------------


class GitRunner(object):
    """
    The GitRunner class is used to peform the specific `git` command
    operations requested for the VCS use cases.
    """

    def __init__(self, config: GitSpec, repo_dir) -> None:
        self.user = config.username or os.environ["USER"]
        self.config = config
        self.repo_dir = repo_dir
        self.git_file = repo_dir.joinpath(".git", "config")

        parsed = urlsplit(config.repo)
        if parsed.scheme == "https":
            self.repo_url = f"https://{self.user}@{parsed.netloc}{parsed.path}"
        else:
            self.repo_url = config.repo

    @property
    def repo_exists(self):
        return self.git_file.exists()

    @property
    def is_dir_empty(self):
        return not any(self.repo_dir.iterdir())

    def run_noauth(self, cmd: str):
        """
        Run the git command that does not require any user authentication
        """
        output, rc = pexpect.run(
            command=f"{GIT_BIN} {cmd}",
            withexitstatus=True,
            cwd=self.repo_dir,
            encoding="utf-8",
        )

        if rc != 0:
            raise RuntimeError(f"git {cmd} failed: %s" % output)

        return output

    # run with auth is an alias to be created by subclass if needed
    run_auth = run_noauth

    def run(self, cmd: str, authreq=False):
        return [self.run_noauth, self.run_auth][authreq](cmd)  # noqa

    def git_init(self) -> None:
        output = self.run("remote -v") if self.repo_exists else ""
        if self.repo_url not in output:
            commands = (("init", False), (f"remote add origin {self.repo_url}", False))

            for cmd, req_auth in commands:
                self.run(cmd, req_auth)

        self.git_config()

    def git_pull(self):
        self.run(f"pull origin {consts.DEFAULT_GIT_BRANCH}", authreq=True)

    def git_config(self) -> None:
        config = self.config

        config_opts = (
            ("user.email", config.email or self.user),
            ("user.name", self.user),
            ("push.default", "matching"),
        )

        for cfg_opt, cfg_val in config_opts:
            self.run(f"config --local {cfg_opt} {cfg_val}")

    def git_clone(self) -> None:
        self.run(f"clone {self.repo_url} {str(self.repo_dir)}", authreq=True)
        self.git_config()


class GitAuthRunner(GitRunner):
    """
    Git Runner that is used for either User/Password or Token cases
    """

    #
    PASSWORD_PROMPT = "Password for"  # nosec

    def _get_secret(self):
        return self.config.token.get_secret_value()

    def run_auth(self, cmd):
        output, rc = pexpect.run(
            command=f"{GIT_BIN} {cmd}",
            cwd=self.repo_dir,
            withexitstatus=True,
            encoding="utf-8",
            events={self.PASSWORD_PROMPT: self._get_secret() + "\n"},
        )

        if rc != 0:
            raise RuntimeError(output)

        return output


class GitTokenRunner(GitAuthRunner):
    # use the default password prompt value
    pass


class GitDeployKeyRunner(GitRunner):
    """
    Git Runner used with deployment keys without passphrase
    """

    def git_config(self) -> None:
        super().git_config()
        if self.config.deploy_key is None:
            raise ValueError("Deploy key is not configured.")
        ssh_key = str(Path(self.config.deploy_key).absolute())
        self.run(
            f"config --local core.sshCommand 'ssh -i {ssh_key} -o StrictHostKeyChecking=no'"
        )


class GitSecuredDeployKeyRunner(GitDeployKeyRunner, GitAuthRunner):
    """
    Git Runner used when deployment key has passphrase configured
    """

    PASSWORD_PROMPT = "Enter passphrase for key"  # nosec

    def _get_secret(self):
        return self.config.deploy_passphrase.get_secret_value()


def git_runner(gh_cfg: GitSpec, repo_dir: Path) -> GitRunner:
    """
    Used to select the Git Runner based on the configuration file
    settings.
    """
    if gh_cfg.token:
        return GitTokenRunner(gh_cfg, repo_dir)

    if gh_cfg.deploy_key:
        if not gh_cfg.deploy_passphrase:
            return GitDeployKeyRunner(gh_cfg, repo_dir)

        return GitSecuredDeployKeyRunner(gh_cfg, repo_dir)

    # Note: this is unreachable code since the config-model validation should
    # have ensured the proper fields exist in the spec.

    raise RuntimeError("Git config missing authentication settings")  # pragma: no cover
