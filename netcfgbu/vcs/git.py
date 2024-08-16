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

from netcfgbu.config_model import GitSpec
from netcfgbu.consts import DEFAULT_GIT_BRANCH
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

    Returns:
        str: The generated commit message based on the current timestamp.
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
    """
    Save changes to the Git repository and optionally tag the commit.

    Args:
        gh_cfg (GitSpec): The Git configuration.
        repo_dir (Path): The path to the Git repository directory.
        add_tag (bool, optional): Whether to add a Git tag to the commit. Defaults to False.
        message (Optional[str], optional): The commit message. Defaults to None.

    Returns:
        bool: True if changes were committed, False otherwise.
    """
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
    """
    Prepare the Git repository by initializing it and pulling the latest changes.

    Args:
        spec (GitSpec): The Git configuration.
        repo_dir (Path): The path to the Git repository directory.
    """
    log = get_logger()
    log.info("VCS prepare git: %s", spec.repo)

    ghr = git_runner(spec, repo_dir)
    ghr.git_init()
    ghr.git_pull()


def vcs_status(spec: GitSpec, repo_dir: Path) -> str:
    """
    Display the current status of the Git repository.

    Args:
        spec (GitSpec): The Git configuration.
        repo_dir (Path): The path to the Git repository directory.

    Returns:
        str: The output of the Git status command.
    """
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


class GitRunner:
    """
    The GitRunner class is used to perform specific `git` command
    operations for the VCS use cases.

    Args:
        config (GitSpec): The Git configuration.
        repo_dir (Path): The path to the Git repository directory.
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
    def repo_exists(self) -> bool:
        """
        Check if the Git repository exists.

        Returns:
            bool: True if the repository exists, False otherwise.
        """
        return self.git_file.exists()

    @property
    def is_dir_empty(self) -> bool:
        """
        Check if the repository directory is empty.

        Returns:
            bool: True if the directory is empty, False otherwise.
        """
        return not any(self.repo_dir.iterdir())

    def run_noauth(self, cmd: str) -> str:
        """
        Run a Git command that does not require user authentication.

        Args:
            cmd (str): The Git command to run.

        Returns:
            str: The output of the Git command.

        Raises:
            RuntimeError: If the Git command fails.
        """
        output, result_code = pexpect.run(
            command=f"{GIT_BIN} {cmd}",
            withexitstatus=True,
            cwd=self.repo_dir,
            encoding="utf-8",
        )

        if result_code != 0:
            raise RuntimeError(f"git {cmd} failed: %s" % output)

        return output

    # run with auth is an alias to be created by subclass if needed
    run_auth = run_noauth

    def run(self, cmd: str, authreq=False) -> str:
        """
        Run a Git command, optionally with authentication.

        Args:
            cmd (str): The Git command to run.
            authreq (bool, optional): Whether authentication is required. Defaults to False.

        Returns:
            str: The output of the Git command.
        """
        return [self.run_noauth, self.run_auth][authreq](cmd)  # noqa

    def git_init(self) -> None:
        """
        Initialize the Git repository and set up the remote origin.
        """
        output = self.run("remote -v") if self.repo_exists else ""
        if self.repo_url not in output:
            commands = (("init", False), (f"remote add origin {self.repo_url}", False))

            for cmd, req_auth in commands:
                self.run(cmd, req_auth)

        self.git_config()

    def git_pull(self):
        """
        Pull the latest changes from the remote repository.
        """
        self.run(f"pull origin {DEFAULT_GIT_BRANCH}", authreq=True)

    def git_config(self) -> None:
        """
        Configure the Git user and push settings.
        """
        config = self.config

        config_opts = (
            ("user.email", config.email or self.user),
            ("user.name", self.user),
            ("push.default", "matching"),
        )

        for cfg_opt, cfg_val in config_opts:
            self.run(f"config --local {cfg_opt} {cfg_val}")

    def git_clone(self) -> None:
        """
        Clone the Git repository to the specified directory.
        """
        self.run(f"clone {self.repo_url} {str(self.repo_dir)}", authreq=True)
        self.git_config()


class GitAuthRunner(GitRunner):
    """
    GitRunner that handles authentication using either username/password or token.

    Attributes:
        PASSWORD_PROMPT (str): The prompt used to request the user's password.
    """

    PASSWORD_PROMPT = "Password for"  # nosec

    def _get_secret(self) -> str:
        """
        Retrieve the secret value for authentication.

        Returns:
            str: The secret value (e.g., password or token).
        """
        return self.config.token.get_secret_value()

    def run_auth(self, cmd) -> str:
        """
        Run a Git command that requires user authentication.

        Args:
            cmd (str): The Git command to run.

        Returns:
            str: The output of the Git command.

        Raises:
            RuntimeError: If the Git command fails.
        """
        output, result_code = pexpect.run(
            command=f"{GIT_BIN} {cmd}",
            cwd=self.repo_dir,
            withexitstatus=True,
            encoding="utf-8",
            events={self.PASSWORD_PROMPT: self._get_secret() + "\n"},
        )

        if result_code != 0:
            raise RuntimeError(output)

        return output


class GitTokenRunner(GitAuthRunner):
    """
    GitRunner that handles authentication using a token.
    """

    # use the default password prompt value
    pass


class GitDeployKeyRunner(GitRunner):
    """
    GitRunner used with deployment keys without a passphrase.

    This runner configures Git to use a specific SSH key for authentication.
    """

    def git_config(self) -> None:
        """
        Configure the Git repository to use the specified deployment key for SSH access.

        Raises:
            ValueError: If the deployment key is not configured.
            FileNotFoundError: If the deployment key file is not found.
        """
        super().git_config()
        if self.config.deploy_key is None:
            raise ValueError("Deploy key is not configured.")
        ssh_key_path = Path(self.config.deploy_key).absolute()
        if not ssh_key_path.exists():
            raise FileNotFoundError(f"Deploy key file not found: {ssh_key_path}")
        ssh_key = str(ssh_key_path)
        self.run(
            f"config --local core.sshCommand 'ssh -i {ssh_key} -o StrictHostKeyChecking=no'"
        )


class GitSecuredDeployKeyRunner(GitDeployKeyRunner, GitAuthRunner):
    """
    GitRunner used when a deployment key has a passphrase configured.

    This runner handles the additional authentication step required to provide the passphrase.

    Attributes:
        PASSWORD_PROMPT (str): The prompt used to request the passphrase for the key.
    """

    PASSWORD_PROMPT = "Enter passphrase for key"  # nosec

    def _get_secret(self):
        return self.config.deploy_passphrase.get_secret_value()


def git_runner(gh_cfg: GitSpec, repo_dir: Path) -> GitRunner:
    """
    Select the appropriate GitRunner based on the configuration file settings.

    Args:
        gh_cfg (GitSpec): The Git configuration.
        repo_dir (Path): The path to the Git repository directory.

    Returns:
        GitRunner: The appropriate GitRunner instance for the given configuration.

    Raises:
        RuntimeError: If the Git configuration is missing authentication settings.
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
