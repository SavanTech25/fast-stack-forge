"""Shared helpers for the scaffolding commands: templates, file writing, project detection and prompts."""

import re
import sys
from pathlib import Path

import click
from jinja2 import Environment, FileSystemLoader

TEMPLATES_DIR = Path(__file__).parent / "templates"


def render(template_dir: str, template_name: str, context: dict, **env_options) -> str:
    """Render `templates/<template_dir>/<template_name>` with the given context."""
    options = {"trim_blocks": True, "lstrip_blocks": True, "keep_trailing_newline": True, **env_options}
    env = Environment(loader=FileSystemLoader(str(TEMPLATES_DIR / template_dir)), **options)
    return env.get_template(template_name).render(**context)


def write(path: Path, content: str, overwrite: bool = True) -> None:
    """Write a file, creating parent folders. With overwrite=False an existing file is kept."""
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and not overwrite:
        click.echo(click.style(f"  {'skipped':>10}  {path}  (already exists)", fg="yellow"))
        return
    path.write_text(content)
    click.echo(click.style(f"  {'created':>10}  {path}", fg="green"))


def find_project_root(start: Path = None, require_pyproject: bool = False) -> Path | None:
    """Walk up from `start` (default: cwd) to the first folder containing `src/`."""
    start = start or Path.cwd()
    for p in [start, *start.parents]:
        if (p / "src").is_dir() and (not require_pyproject or (p / "pyproject.toml").is_file()):
            return p
    return None


def find_package(src_dir: Path, exclude_suffix: str = None) -> str | None:
    """Return the Python package inside `src/`, ignoring dbt projects, egg-info and caches."""
    candidates = sorted(
        d for d in src_dir.iterdir()
        if d.is_dir()
        and not d.name.startswith(("_", "."))
        and not d.name.endswith(".egg-info")
        and not (d / "dbt_project.yml").exists()
        and not (exclude_suffix and d.name.endswith(exclude_suffix))
    )
    # Prefer real packages (with __init__.py), then fall back to any folder
    packages = [d for d in candidates if (d / "__init__.py").exists()] or candidates
    return packages[0].name if packages else None


def resolve_package_or_exit(exclude_suffix: str = None) -> tuple[Path, str]:
    """Return (project_root, package_name) or exit with a friendly error."""
    project_root = find_project_root()
    if not project_root:
        click.echo(click.style("✗ Could not resolve project root. Are you inside a FastForge project?", fg="red"))
        raise SystemExit(1)
    package = find_package(project_root / "src", exclude_suffix=exclude_suffix)
    if not package:
        click.echo(click.style("✗ No project package found inside 'src/'.", fg="red"))
        raise SystemExit(1)
    return project_root, package


def sanitize_name(name: str) -> str:
    """'My Project-Name' -> 'my_project_name' (valid Python / dbt identifier)."""
    name = name.strip().lower()
    name = re.sub(r"[\s\-\.]+", "_", name)
    name = re.sub(r"[^a-z0-9_]", "", name)
    name = re.sub(r"_+", "_", name).strip("_")
    if name and name[0].isdigit():
        name = f"p_{name}"
    return name


def is_interactive() -> bool:
    return sys.stdin.isatty()


class Prompter:
    """Asks simple questions in a terminal. Uses defaults with --yes or when stdin is not a TTY (CI, pipes)."""

    def __init__(self, assume_yes: bool = False):
        self.auto = assume_yes or not is_interactive()

    def text(self, label: str, default: str = "") -> str:
        if self.auto:
            return default
        return click.prompt(label, default=default, show_default=bool(default)).strip()

    def confirm(self, label: str, default: bool = False) -> bool:
        if self.auto:
            return default
        return click.confirm(label, default=default)

    def choice(self, label: str, options: list, default: str = None) -> str:
        """`options` is a list of values or (value, help) tuples. Returns the chosen value."""
        opts = [o if isinstance(o, tuple) else (o, "") for o in options]
        values = [v for v, _ in opts]
        default = default if default in values else values[0]
        if self.auto:
            return default
        click.echo(f"\n{label}")
        for i, (value, help_text) in enumerate(opts, 1):
            suffix = click.style(f"  {help_text}", dim=True) if help_text else ""
            click.echo(f"  [{i}] {value}{suffix}")
        idx = click.prompt("Choice", type=click.IntRange(1, len(values)), default=values.index(default) + 1)
        return values[idx - 1]

    def name(self, label: str, value: str = None, default: str = "my_project") -> str:
        """Ask for (or sanitize) a project name."""
        raw = value or self.text(label, default=default)
        clean = sanitize_name(raw)
        if not clean:
            raise click.UsageError(f"Invalid project name: {raw!r}")
        if clean != raw:
            click.echo(click.style(f"  ℹ  Name sanitized: '{raw}' → '{clean}'", fg="yellow"))
        return clean
