import base64
import os
import secrets
from pathlib import Path

import click

from fast_stack_forge.utils import Prompter, find_project_root, render as render_template, write

DB_URLS = {
    "sqlite": "sqlite:///./app.db",
    "postgresql": "postgresql://user:password@localhost/dbname",
    "mysql": "mysql+pymysql://user:password@localhost/dbname",
    "mongodb": "mongodb://localhost:27017/dbname",
}

COMMON_REQS = [
    "fastapi>=0.110.0",
    "uvicorn[standard]>=0.29.0",
    "pydantic>=2.0.0",
    "python-decouple>=3.8",
    "cryptography>=42.0.0",
    "passlib[bcrypt]>=1.7.4",
    "fastapi-cache2>=0.2.1",
    "PyJWT>=2.8.0",
    "slowapi>=0.1.9",
    "apscheduler>=3.10.4",
    "jinja2>=3.1.3",
    "loguru>=0.7.2",
    "python-multipart>=0.0.9",
    "requests>=2.31.0",
    "httpx>=0.27.0",
]
SQL_REQS = ["sqlalchemy>=2.0.0"]

REQUIREMENTS = {
    "sqlite": COMMON_REQS + SQL_REQS,
    "postgresql": COMMON_REQS + SQL_REQS + ["psycopg2-binary>=2.9.0"],
    "mysql": COMMON_REQS + SQL_REQS + ["pymysql>=1.1.0"],
    "mongodb": COMMON_REQS + ["motor>=3.3.0"],
}


DB_HELP = {
    "sqlite": "file database, zero setup",
    "postgresql": "PostgreSQL / Supabase",
    "mysql": "MySQL / MariaDB",
    "mongodb": "MongoDB (motor, async)",
}


def render(template_name, context):
    return render_template("project", template_name, context, trim_blocks=False, lstrip_blocks=False)


def merge_pyproject_deps_and_scripts(pyproject_path: Path, dependencies: list, scripts: dict = None) -> None:
    if not pyproject_path.exists():
        return
    
    text = pyproject_path.read_text()
    lines = text.splitlines()
    
    # 1. Merge dependencies
    deps_start = -1
    deps_end = -1
    for idx, line in enumerate(lines):
        if line.strip().startswith("dependencies = ["):
            deps_start = idx
            break
            
    if deps_start != -1:
        for idx in range(deps_start, len(lines)):
            # the closing bracket of the list, not the one of an extra like "uvicorn[standard]"
            if lines[idx].strip() == "]" or (idx == deps_start and lines[idx].rstrip().endswith("]")):
                deps_end = idx
                break
                
    if deps_start != -1 and deps_end != -1:
        existing_deps = set()
        for idx in range(deps_start + 1, deps_end):
            dep_str = lines[idx].strip().strip(",").strip('"').strip("'").strip()
            if dep_str:
                existing_deps.add(dep_str.split(">=")[0].split("==")[0].split("<=")[0].strip())
                
        deps_to_add = []
        for dep in dependencies:
            dep_name = dep.split(">=")[0].split("==")[0].split("<=")[0].strip()
            if dep_name not in existing_deps:
                deps_to_add.append(f'    "{dep}",')
                
        if deps_to_add:
            for dep in reversed(deps_to_add):
                lines.insert(deps_start + 1, dep)
                
    # 2. Merge scripts under [project.scripts]
    if scripts:
        scripts_idx = -1
        for idx, line in enumerate(lines):
            if line.strip() == "[project.scripts]":
                scripts_idx = idx
                break
                
        if scripts_idx != -1:
            for name, entrypoint in scripts.items():
                script_line = f'{name} = "{entrypoint}"'
                if script_line not in text:
                    lines.insert(scripts_idx + 1, script_line)
        else:
            lines.append("")
            lines.append("[project.scripts]")
            for name, entrypoint in scripts.items():
                lines.append(f'{name} = "{entrypoint}"')
                
    pyproject_path.write_text("\n".join(lines) + "\n")
    click.echo(f"  {'updated':>10}  {pyproject_path} (merged dependencies & scripts)")


def merge_makefile_targets(makefile_path: Path, new_targets: str) -> None:
    if not makefile_path.exists():
        return
    text = makefile_path.read_text()
    signature = new_targets.strip().splitlines()[0]
    if signature not in text:
        makefile_path.write_text(text + "\n\n" + new_targets + "\n")
        click.echo(f"  {'updated':>10}  {makefile_path} (appended custom make targets)")


def init_project(project_name, db, assume_yes=False):
    ask = Prompter(assume_yes)
    project_name = ask.name("Project name", project_name, default="my_api")
    project_root = find_project_root(require_pyproject=True)

    if project_root:
        base = project_root
        click.echo(click.style(f"⚡ Project root detected: {project_root}", fg="blue"))
    else:
        base = Path(project_name)
        if base.exists():
            click.echo(click.style(f"✗ '{project_name}' already exists.", fg="red"))
            raise SystemExit(1)

    db = db or ask.choice("Database:", list(DB_HELP.items()), "sqlite")
    click.echo(click.style(f"\n⚡ FastForge — initializing FastAPI package '{project_name}'\n", fg="cyan", bold=True))
    ctx = {"project_name": project_name, "db": db, "db_url": DB_URLS[db], "requirements": REQUIREMENTS[db]}

    pkg_name = project_name.lower()

    # Determine main file (if app/main.py exists, use a package-specific entry point)
    main_file = base / "app" / "main.py"
    if main_file.exists():
        main_file = base / "app" / f"{pkg_name}_main.py"
    
    write(main_file, render("main.py.j2", ctx))
    write(base / f"src/{pkg_name}/data/database.py", render("database.py.j2", ctx))
    write(base / f"src/{pkg_name}/utils/crypto.py", render("crypto.py.j2", ctx))
    write(base / f"src/{pkg_name}/utils/connection_manager.py", render("connection_manager.py.j2", ctx))
    write(base / f"src/{pkg_name}/utils/limiter.py", render("limiter.py.j2", ctx))
    write(base / f"src/{pkg_name}/utils/scheduling.py", render("scheduling.py.j2", ctx))
    write(base / f"src/{pkg_name}/utils/crud_router.py", render("crud_router.py.j2", ctx))
    write(base / f"src/{pkg_name}/utils/controller.py", render("controller.py.j2", ctx))
    write(base / f"src/{pkg_name}/middleware/middleware.py", render("middleware.py.j2", ctx))
    write(base / f"src/{pkg_name}/data/actions.py", render("actions.py.j2", ctx))
    write(base / f"src/{pkg_name}/entity/base_entity.py", render("base_entity.py.j2", ctx))

    for pkg in [
        f"src/{pkg_name}",
        f"src/{pkg_name}/entity",
        f"src/{pkg_name}/schema",
        f"src/{pkg_name}/controller",
        f"src/{pkg_name}/service",
        f"src/{pkg_name}/router",
        f"src/{pkg_name}/data",
        f"src/{pkg_name}/utils",
        f"src/{pkg_name}/middleware",
        "app"
    ]:
        write(base / pkg / "__init__.py", "")

    # If it's a new project, write pyproject.toml and other root files
    if not project_root:
        write(base / "pyproject.toml", render("pyproject.toml.j2", ctx))
        write(base / "Makefile", render("Makefile.j2", ctx))
        write(base / ".env", (
            "# ── Database ──────────────────────────────────────────────────────────────────\n"
            f"DATABASE_URL={DB_URLS[db]}\n\n"
            "# ── Security ──────────────────────────────────────────────────────────────────\n"
            f"SECRET_KEY={secrets.token_urlsafe(48)}\n"
            f"FERNET_KEY={base64.urlsafe_b64encode(os.urandom(32)).decode()}\n\n"
            "# ── JWT & Auth ─────────────────────────────────────────────────────────────────\n"
            "ALGORITHM=HS256\n"
            "ACCESS_TOKEN_EXPIRE_MINUTES=43200\n\n"
            "# ── App Settings ───────────────────────────────────────────────────────────────\n"
            "DB_NAME=\n"
            "ALLOW_ORIGIN=*\n"
            "WORKERS=4\n"
            "PORT=8000\n\n"
            "# ── Postgres / Supabase ────────────────────────────────────────────────────────\n"
            "POSTGRES_HOST=\n"
            "POSTGRES_PORT=5432\n"
            "POSTGRES_USER=\n"
            "POSTGRES_PASSWORD=\n"
            "POSTGRES_DB=\n"
            "POSTGRES_URL=\n\n"
            "# AI services add their own settings below (fast-stack-forge make:service)\n"
        ))
        write(base / ".gitignore", "__pycache__/\n*.pyc\n.env\n*.db\n.venv/\n")
        write(base / "README.md", f"# {project_name}\n\nGenerated by **FastForge ⚡**\n\n## Setup & Run\n\n```bash\nmake install\nsource .venv/bin/activate\nmake run\n```\n")
    else:
        # If it's an existing project, merge requirements and scripts into existing pyproject.toml
        merge_pyproject_deps_and_scripts(
            base / "pyproject.toml",
            REQUIREMENTS[db],
            {f"{pkg_name}-api": f"app.{pkg_name}_main:main" if main_file.name != "main.py" else "app.main:main"}
        )
        
        # Merge database URL into .env if present
        env_file = base / ".env"
        if env_file.exists():
            env_text = env_file.read_text()
            db_env_key = f"{pkg_name.upper()}_DATABASE_URL"
            if db_env_key not in env_text:
                env_file.write_text(env_text + f"\n{db_env_key}={DB_URLS[db]}\n")
                click.echo(f"  {'updated':>10}  {env_file} (added {db_env_key})")

        # Append Makefile target
        run_target = f"run_{pkg_name}:\n\tuv run uvicorn app.{pkg_name}_main:app --reload --port 8000" if main_file.name != "main.py" else "run:\n\tuv run uvicorn app.main:app --reload --port 8000"
        merge_makefile_targets(base / "Makefile", run_target)

    from fast_stack_forge.commands.make_entity import make_entity
    
    click.echo(click.style(f"\n⚡ Generating default Files entity...", fg="cyan"))
    original_dir = os.getcwd()
    os.chdir(base)
    try:
        make_entity("Files", ["filename:string", "content_type:string", "file_id:string"])
    except SystemExit:
        pass
    os.chdir(original_dir)

    click.echo(click.style(f"\n✔ Project '{project_name}' created!\n", fg="green", bold=True))
