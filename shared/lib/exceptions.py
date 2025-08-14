"""Local exceptions for shared library modules."""


class DMCLIError(Exception):
    """Exception raised for DMCLI command execution errors."""

    def __init__(self, message: str) -> None:
        """Initialize DMCLIError.

        :param message: Error message
        :type message: str
        """
        self.message = message
        super().__init__(self.message)
