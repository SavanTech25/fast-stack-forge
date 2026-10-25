import pytest
from click.testing import CliRunner

from fast_stack_forge import utils
from fast_stack_forge.cli import cli


@pytest.fixture
def run(tmp_path, monkeypatch):
    """Run the CLI inside an empty temporary folder. Returns the click Result."""
    monkeypatch.chdir(tmp_path)

    def _run(*args, input=None):
        result = CliRunner().invoke(cli, list(args), input=input, catch_exceptions=False)
        assert result.exit_code == 0, result.output
        return result

    return _run


@pytest.fixture
def interactive(monkeypatch):
    """Make the Prompter ask questions even though CliRunner's stdin is not a TTY."""
    monkeypatch.setattr(utils, "is_interactive", lambda: True)
