"""Errors a caller can catch without importing the modules that raise them."""


class ConfigError(Exception):
    """The project file or the command line does not describe a valid run."""


class ProviderError(Exception):
    """An answer engine could not be called or did not return an answer."""

    def __init__(self, provider: str, message: str) -> None:
        self.provider = provider
        self.message = message
        super().__init__(f"{provider}: {message}")


class StoreError(Exception):
    """The run database is missing a row or holds a value this version cannot read."""
