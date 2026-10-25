"""init:ds-make command — add FastAPI + Streamlit to an existing DS project."""

import click
from pathlib import Path
from fast_stack_forge.commands.init_ds_data import render_ds
from fast_stack_forge.utils import find_package, write as _write


def write(path: Path, content: str, overwrite: bool = False) -> None:
    _write(path, content, overwrite=overwrite)


def init_ds_make(project_dir: str = ".") -> None:
    """Add FastAPI skeleton + Streamlit app to an existing AstroData DS project."""
    base = Path(project_dir).resolve()

    src_dir = base / "src"
    if not src_dir.exists():
        click.echo(click.style("✗ No 'src/' directory found. Run this command from a DS project root.", fg="red"))
        raise SystemExit(1)

    pkg_name = find_package(src_dir)
    if not pkg_name:
        click.echo(click.style("✗ No package found inside 'src/'. Run 'fast-stack-forge init:ds-data' first.", fg="red"))
        raise SystemExit(1)

    click.echo(click.style(f"\n⚡ FastForge ✕ AstroData — adding FastAPI + Streamlit to '{pkg_name}'\n", fg="cyan", bold=True))

    description = f"API for {pkg_name} package"
    pyproject = base / "pyproject.toml"
    if pyproject.exists():
        for line in pyproject.read_text().splitlines():
            if line.strip().startswith("description"):
                description = line.split("=", 1)[-1].strip().strip('"')
                break

    if pyproject.exists():
        text = pyproject.read_text()
        has_api_dep = "fastapi" in text
        if not has_api_dep:
            lines = text.splitlines()
            deps_idx = -1
            for idx, line in enumerate(lines):
                if line.strip() == "dependencies = [":
                    deps_idx = idx
                    break
            if deps_idx != -1:
                api_deps = [
                    '    "fastapi>=0.111",',
                    '    "uvicorn>=0.30",',
                    '    "pydantic>=2.7.0",',
                    '    "pydantic-settings>=2.2.0",',
                ]
                for d in reversed(api_deps):
                    lines.insert(deps_idx + 1, d)
            
            if f"{pkg_name}-api =" not in text:
                scripts_found = False
                for idx, line in enumerate(lines):
                    if line.strip() == "[project.scripts]":
                        lines.insert(idx + 1, f'{pkg_name}-api = "{pkg_name}.api.main:main"')
                        scripts_found = True
                        break
                if not scripts_found:
                    lines.append("\n[project.scripts]")
                    lines.append(f'{pkg_name}-api = "{pkg_name}.api.main:main"')
            
            pyproject.write_text("\n".join(lines) + "\n")
            click.echo("  updated     pyproject.toml with FastAPI dependencies")

    ctx = {
        "repo_name": pkg_name,
        "package_name": pkg_name,
        "description": description,
        "include_api": True,
    }

    pkg_base = src_dir / pkg_name

    api_packages = [
        "api",
        "api/middlewares",
        "api/routers",
    ]
    for ap in api_packages:
        init_file = pkg_base / ap / "__init__.py"
        write(init_file, "")

    write(pkg_base / "api/main.py",                render_ds("api_main.py.j2", ctx), overwrite=True)
    write(pkg_base / "api/middlewares/upload.py",  render_ds("api_middleware.py.j2", ctx), overwrite=True)
    write(pkg_base / "api/routers/base.py",        render_ds("api_router_base.py.j2", ctx), overwrite=True)
    write(pkg_base / "api/routers/system.py",      render_ds("api_router_system.py.j2", ctx), overwrite=True)
    write(pkg_base / "api/routers/greetings.py",   render_ds("api_router_greetings.py.j2", ctx), overwrite=True)

    write(base / "app/__init__.py",            "")
    write(base / f"app/{pkg_name}_app.py",     render_ds("streamlit_app.py.j2", ctx), overwrite=True)
    write(base / ".streamlit/config.toml",     render_ds("streamlit_config.toml.j2", ctx), overwrite=True)

    write(base / "docker-compose.yml",         render_ds("docker_compose.yml.j2", ctx), overwrite=True)
    write(base / ".dockerignore",              render_ds("dockerignore.j2", ctx), overwrite=True)
    write(base / "dockerfiles/Dockerfile.api", render_ds("Dockerfile.api.j2", ctx), overwrite=True)
    write(base / "dockerfiles/Dockerfile.app", render_ds("Dockerfile.app.j2", ctx), overwrite=True)

    write(base / "tests/test_api.py",          render_ds("test_api.py.j2", ctx), overwrite=True)

    click.echo(click.style(f"\n✔ FastAPI + Streamlit added to '{pkg_name}'!\n", fg="green", bold=True))
    click.echo("  make install")
    click.echo("  make run_api       # http://localhost:8000/docs")
    click.echo("  make run           # http://localhost:8501\n")
