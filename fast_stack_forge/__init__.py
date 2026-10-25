from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("fast-stack-forge")
except PackageNotFoundError:  # running from a source checkout that is not installed
    __version__ = "0.0.0"

from .cli import cli, main  # noqa: E402

__all__ = ["cli", "main", "__version__"]
