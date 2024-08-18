import asyncio

from netcfgbu.connectors.basic import BasicSSHConnector


class LoginPromptUserPass(BasicSSHConnector):
    """A custom SSH connector that handles login prompts for both username and password.

    This class extends `BasicSSHConnector` and is used to handle devices that
    prompt for a username and password separately during the SSH login process.

    Methods:
        login: Performs the SSH login by interacting with the username and password prompts.
    """

    async def login(self):
        """Perform the SSH login process by handling prompts for username and password.

        This method waits for the "User:" and "Password:" prompts, and then sends the
        corresponding username and password from the connection arguments.

        Returns:
            The SSH connection object after successful login.

        Raises:
            asyncio.TimeoutError: If the expected prompts do not appear within the timeout period.
        """
        await super().login()

        await asyncio.wait_for(self.process.stdout.readuntil(b"User:"), timeout=60)

        username = (self.conn_args["username"] + "\n").encode("utf-8")
        self.process.stdin.write(username)

        await asyncio.wait_for(self.process.stdout.readuntil(b"Password:"), timeout=60)

        password = (self.conn_args["password"] + "\n").encode("utf-8")
        self.process.stdin.write(password)

        return self.conn
