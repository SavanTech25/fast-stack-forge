"""init:ds-data command — scaffold an AstroData-style data science project."""

import sys
import click
from pathlib import Path
from fast_stack_forge.commands.init import merge_pyproject_deps_and_scripts, merge_makefile_targets
from fast_stack_forge.utils import Prompter, find_project_root, render, write

DB_CHOICES = ["sqlite", "postgresql", "mysql", "mongodb"]

DS_REQUIREMENTS = [
    "loguru>=0.7.3",
    "pretty-errors>=1.2.25",
    "python-decouple>=3.8",
    "streamlit==1.42.0",
    "pygwalker>=0.4.9",
    "openpyxl>=3.1.5",
    "pandas>=2.2.0",
    "matplotlib>=3.8.0",
    "ipykernel>=6.29.0",
    "httpx>=0.27.0",
    "python-multipart>=0.0.9",
]

API_REQUIREMENTS = [
    "fastapi>=0.111",
    "uvicorn>=0.30",
    "pydantic>=2.7.0",
    "pydantic-settings>=2.2.0",
]


def get_python_versions() -> list[str]:
    c = sys.version_info
    return [f"{c.major}.{c.minor}", f"{c.major}.{c.minor - 1}", f"{c.major}.{c.minor - 2}"]


def render_ds(template_name: str, context: dict) -> str:
    return render("ds_data", template_name, context, trim_blocks=False, lstrip_blocks=False)


def init_ds_data_project(package_name: str, include_api: bool, include_data: bool, assume_yes: bool = False) -> None:
    ask = Prompter(assume_yes)
    repo_name = ask.name("Project name", package_name, default="my_ds_project")
    project_root = find_project_root(require_pyproject=True)

    if project_root:
        base = project_root
        click.echo(click.style(f"⚡ Project root detected: {project_root}", fg="blue"))
        if (base / "src" / repo_name).exists():
            click.echo(click.style(f"✗ Package '{repo_name}' already exists in src/.", fg="red"))
            raise SystemExit(1)
    else:
        base = Path(repo_name)
        if base.exists():
            click.echo(click.style(f"✗ '{repo_name}' already exists.", fg="red"))
            raise SystemExit(1)

    click.echo(click.style(f"\n⚡ FastForge ✕ AstroData — initializing '{repo_name}'\n", fg="cyan", bold=True))

    api_project_db = None
    create_api_project = False

    if include_api is None:
        include_api = ask.confirm("Include a FastAPI skeleton inside the package (src/<name>/api)?", default=False)
    if include_data is None:
        include_data = ask.confirm("Create data/ folders (raw, interim, processed, external)?", default=False)

    # Only ask for companion FastAPI project if NOT already inside an existing workspace
    if not project_root:
        create_api_project = ask.confirm(
            "Do you also want to create a companion FastAPI backend project "
            f"(named '{repo_name}_api')?",
            default=False,
        )
        if create_api_project:
            api_project_db = ask.choice("Database for the FastAPI project:", DB_CHOICES, "sqlite")

    py_versions = get_python_versions()
    python_version = ask.choice(
        "Python version:",
        [(v, "(current)" if i == 0 else f"(current-{i})") for i, v in enumerate(py_versions)],
        py_versions[0],
    )

    is_open_source = ask.confirm("\nIs this project open source?", default=True)
    if is_open_source:
        license_choice = ask.choice("License:", ["MIT", "BSD-3-Clause", "Apache-2.0", "GPL-3.0"], "MIT")
    else:
        license_choice = "Proprietary"

    description = ask.text("\nProject description (leave blank to skip)") or f"A data science project: {repo_name}"
    author_name = ask.text("Author name (leave blank to skip)")
    author_email = ask.text("Author email (leave blank to skip)") if author_name else ""

    click.echo()

    if create_api_project:
        api_name = f"{repo_name}_api"
        click.echo(click.style(f"\n⚡ Scaffolding companion FastAPI project '{api_name}'...\n", fg="cyan"))
        from fast_stack_forge.commands.init import init_project
        init_project(api_name, api_project_db)
        click.echo()

    ctx = {
        "repo_name": repo_name,
        "package_name": repo_name,
        "python_version": python_version,
        "open_source_license": license_choice,
        "description": description,
        "author_name": author_name,
        "author_email": author_email,
        "is_open_source": is_open_source,
        "include_api": include_api,
        "include_data": include_data,
        "project_url": f"https://github.com/<your-org>/{repo_name}",
    }

    _create_structure(base, repo_name, ctx, include_api=include_api, include_data=include_data, project_root=project_root)

    click.echo(click.style(f"\n✔ DS project '{repo_name}' created!\n", fg="green", bold=True))
    if not project_root:
        click.echo(f"  cd {repo_name}")
        click.echo("  make dev-install")
        click.echo("  cp .env.example .env")
        if not include_api:
            click.echo("  fast-stack-forge init:ds-make   # add FastAPI to this project later")
    else:
        click.echo("  make install")
        click.echo(f"  make run_{repo_name}_app        # run Streamlit dashboard")
        if include_api:
            click.echo(f"  make run_{repo_name}_api        # run FastAPI backend")
    click.echo()


def _create_structure(
    base: Path,
    pkg_name: str,
    ctx: dict,
    include_api: bool,
    include_data: bool,
    project_root: Path = None,
) -> None:
    packages = [
        f"src/{pkg_name}",
        f"src/{pkg_name}/data",
        f"src/{pkg_name}/features",
        f"src/{pkg_name}/models",
        f"src/{pkg_name}/visualization",
        f"src/{pkg_name}/front",
        "tests",
        "app",
    ]
    if include_api:
        packages += [
            f"src/{pkg_name}/api",
            f"src/{pkg_name}/api/routers",
            f"src/{pkg_name}/api/middlewares",
        ]
    for pkg in packages:
        write(base / pkg / "__init__.py", "")

    if include_data:
        for data_dir in ["raw", "interim", "processed", "external"]:
            write(base / "data" / data_dir / ".gitkeep", "")

    for d in ["notebooks", "scripts", "docs"]:
        write(base / d / ".gitkeep", "")

    write(base / "dockerfiles" / ".gitkeep", "")

    # Write root files only if it's a brand new project
    if not project_root:
        write(base / "pyproject.toml",          render_ds("pyproject.toml.j2", ctx))
        write(base / "Makefile",                render_ds("Makefile.j2", ctx))
        write(base / ".env.example",            render_ds("env.example.j2", ctx))
        write(base / ".gitignore",              render_ds("gitignore.j2", ctx))
        write(base / "README.md",               render_ds("README.md.j2", ctx))
        write(base / "ARCHITECTURE.md",         render_ds("ARCHITECTURE.md.j2", ctx))
        write(base / "CHANGELOG.md",            render_ds("CHANGELOG.md.j2", ctx))
        write(base / "VERSION",                 "0.1.0\n")
        write(base / ".pre-commit-config.yaml", render_ds("pre_commit_config.yaml.j2", ctx))
    else:
        # Merge DS requirements & scripts into the existing workspace pyproject.toml
        reqs = list(DS_REQUIREMENTS)
        if include_api:
            reqs += API_REQUIREMENTS
        
        scripts = {f"{pkg_name}-app": f"app.{pkg_name}_app:main"}
        if include_api:
            scripts[f"{pkg_name}-api"] = f"{pkg_name}.api.main:main"
            
        merge_pyproject_deps_and_scripts(base / "pyproject.toml", reqs, scripts)

        # Merge Makefile targets
        run_targets = f"run_{pkg_name}_app:\n\tuv run streamlit run app/{pkg_name}_app.py"
        if include_api:
            run_targets += f"\n\nrun_{pkg_name}_api:\n\tuv run {pkg_name}-api"
        merge_makefile_targets(base / "Makefile", run_targets)

    # Streamlit app (package specific naming)
    write(base / f"app/{pkg_name}_app.py",    render_ds("streamlit_app.py.j2", ctx))
    write(base / ".streamlit/config.toml",    render_ds("streamlit_config.toml.j2", ctx))

    if include_api:
        write(base / f"src/{pkg_name}/api/main.py",               render_ds("api_main.py.j2", ctx))
        write(base / f"src/{pkg_name}/api/middlewares/upload.py", render_ds("api_middleware.py.j2", ctx))
        write(base / f"src/{pkg_name}/api/routers/base.py",       render_ds("api_router_base.py.j2", ctx))
        write(base / f"src/{pkg_name}/api/routers/system.py",     render_ds("api_router_system.py.j2", ctx))
        write(base / f"src/{pkg_name}/api/routers/greetings.py",  render_ds("api_router_greetings.py.j2", ctx))
        write(base / "tests/test_api.py",                         render_ds("test_api.py.j2", ctx))
        write(base / "docker-compose.yml",                         render_ds("docker_compose.yml.j2", ctx))
        write(base / ".dockerignore",                              render_ds("dockerignore.j2", ctx))
        write(base / "dockerfiles/Dockerfile.api",                 render_ds("Dockerfile.api.j2", ctx))
        write(base / "dockerfiles/Dockerfile.app",                 render_ds("Dockerfile.app.j2", ctx))
    else:
        write(base / f"tests/test_{pkg_name}_placeholder.py",  render_ds("test_placeholder.py.j2", ctx))
