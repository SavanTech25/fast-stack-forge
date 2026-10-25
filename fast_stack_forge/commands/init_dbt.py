"""init:dbt command — scaffold a dbt project that builds out of the box."""

from pathlib import Path

import click

from fast_stack_forge.commands.init import merge_makefile_targets, merge_pyproject_deps_and_scripts
from fast_stack_forge.utils import Prompter, find_project_root, render, write

# The scaffolder uses [[ ]] / [% %] so that dbt's own {{ ref() }} Jinja passes through untouched
DBT_JINJA = {
    "variable_start_string": "[[", "variable_end_string": "]]",
    "block_start_string": "[%", "block_end_string": "%]",
    "comment_start_string": "[#", "comment_end_string": "#]",
}

ARCHITECTURES = {
    "default": {
        "help": "staging → intermediate → marts (dbt Labs convention)",
        "layers": ["staging", "intermediate", "marts"],
        "roles": ["", "Join and reshape staging models", "Business-ready tables for BI and apps"],
        "models": {"customers": "stg_customers", "orders": "stg_orders", "l2": "int_customer_orders", "l3": "customers"},
    },
    "medallion": {
        "help": "bronze → silver → gold (lakehouse convention)",
        "layers": ["bronze", "silver", "gold"],
        "roles": ["", "Cleaned and conformed data", "Aggregated, business-ready data"],
        "models": {"customers": "brz_customers", "orders": "brz_orders", "l2": "slv_customer_orders", "l3": "gld_customers"},
    },
    "star": {
        "help": "staging → dimensions → facts (Kimball star schema)",
        "layers": ["staging", "dim", "fact"],
        "roles": ["", "Dimensions: one row per business entity", "Facts: one row per event, keyed to the dimensions"],
        "models": {"customers": "stg_customers", "orders": "stg_orders", "l2": "dim_customers", "l3": "fct_orders"},
    },
}

ADAPTERS = {
    "duckdb": {"package": "dbt-duckdb", "help": "local file database, zero setup", "python_models": True},
    "postgres": {"package": "dbt-postgres", "help": "PostgreSQL / Supabase", "python_models": False},
    "snowflake": {"package": "dbt-snowflake", "help": "Snowflake", "python_models": True},
    "bigquery": {"package": "dbt-bigquery", "help": "Google BigQuery", "python_models": False},
    "databricks": {"package": "dbt-databricks", "help": "Databricks SQL warehouse / Unity Catalog", "python_models": True},
}

# Values accepted by the old init:etl --connector option
LEGACY_CONNECTORS = {"local": "duckdb"}

PYTHON_VERSIONS = ["3.12", "3.13", "3.11"]


def dbt_dependencies(adapter: str) -> list[str]:
    return ["dbt-core>=1.10,<2.0", f"{ADAPTERS[adapter]['package']}>=1.9,<2.0"]


def scaffold_dbt(base: Path, ctx: dict, standalone: bool = True) -> None:
    """Write a dbt project into `base`. Shared by init:dbt and init:databricks.

    `ctx` needs: project_name, archi, adapter, examples, python_model, description, python_version,
    and for Databricks: catalog, warehouse_id. With standalone=False the uv/Makefile root files are skipped
    and profiles.yml goes in `<profiles_dir>/` (Databricks dbt tasks expect it there).
    """
    arch = ARCHITECTURES[ctx["archi"]]
    ctx = {"arch": arch, "m": arch["models"], "catalog": "main", "warehouse_id": "", "standalone": standalone,
           "dependencies": dbt_dependencies(ctx["adapter"]), **ctx}

    def put(rel_path: str, template: str) -> None:
        write(base / rel_path, render("dbt", template, ctx, **DBT_JINJA))

    put("dbt_project.yml", "dbt_project.yml.j2")
    put(f"{ctx.get('profiles_dir') or '.'}/profiles.yml", "profiles.yml.j2")
    put("packages.yml", "packages.yml.j2")
    put("README.md", "README.md.j2")
    if standalone:
        put("pyproject.toml", "pyproject.toml.j2")
        put("Makefile", "Makefile.j2")
        put(".env.example", "env.example.j2")
        put(".gitignore", "gitignore.j2")

    l1, l2, l3 = arch["layers"]
    m = arch["models"]
    put(f"models/{l1}/_sources.yml", "models/sources.yml.j2")
    if ctx["examples"]:
        put("seeds/raw_customers.csv", "seeds/raw_customers.csv.j2")
        put("seeds/raw_orders.csv", "seeds/raw_orders.csv.j2")
        put(f"models/{l1}/{m['customers']}.sql", "models/l1_customers.sql.j2")
        put(f"models/{l1}/{m['orders']}.sql", "models/l1_orders.sql.j2")
        put(f"models/{l2}/{m['l2']}.sql", "models/l2.sql.j2")
        put(f"models/{l3}/{m['l3']}.sql", "models/l3.sql.j2")
        put("models/schema.yml", "models/schema.yml.j2")
        put("models/exposures.yml", "models/exposures.yml.j2")
        put("snapshots/snapshots.yml", "snapshots/snapshots.yml.j2")
        put("tests/assert_no_negative_amounts.sql", "tests/assert_no_negative_amounts.sql.j2")
        if ctx["python_model"]:
            put(f"models/{l3}/order_status_stats.py", "models/python_model.py.j2")
    else:
        for layer in (l2, l3):
            write(base / "models" / layer / ".gitkeep", "")
        for d in ("seeds", "snapshots", "tests"):
            write(base / d / ".gitkeep", "")
    for d in ("macros", "analyses"):
        write(base / d / ".gitkeep", "")


def init_dbt_project(
    project_name: str = None,
    archi: str = None,
    adapter: str = None,
    examples: bool = None,
    python_model: bool = None,
    assume_yes: bool = False,
) -> Path:
    ask = Prompter(assume_yes)
    adapter = LEGACY_CONNECTORS.get(adapter, adapter)

    click.echo(click.style("\n⚡ FastForge — new dbt project\n", fg="cyan", bold=True))
    name = ask.name("dbt project name", project_name, default="my_dbt_project")

    project_root = find_project_root(require_pyproject=True)
    if project_root:
        # Inside an existing project: the dbt project lives next to the Python package, in src/
        base = project_root / "src" / name
        click.echo(click.style(f"⚡ Project root detected: {project_root}", fg="blue"))
    else:
        base = Path(name)
    if base.exists():
        click.echo(click.style(f"✗ '{base}' already exists.", fg="red"))
        raise SystemExit(1)

    archi = archi or ask.choice("Model architecture:", [(k, v["help"]) for k, v in ARCHITECTURES.items()], "default")
    adapter = adapter or ask.choice("Warehouse adapter:", [(k, v["help"]) for k, v in ADAPTERS.items()], "duckdb")
    if examples is None:
        examples = ask.confirm("\nInclude example seeds, models, tests and snapshot?", default=True)
    supports_python = ADAPTERS[adapter]["python_models"]
    if python_model and not supports_python:
        click.echo(click.style(f"  ℹ  dbt Python models are not set up for {adapter}: skipping the example.", fg="yellow"))
    if python_model is None:
        python_model = supports_python and examples and ask.confirm(
            "Include a dbt Python model example?", default=adapter == "duckdb"
        )
    python_model = bool(python_model and supports_python and examples)

    python_version = PYTHON_VERSIONS[0]
    description = f"dbt project {name}"
    if not project_root:
        python_version = ask.choice("Python version:", PYTHON_VERSIONS, PYTHON_VERSIONS[0])
        description = ask.text("\nShort description (optional)", default="") or description

    click.echo()
    ctx = {
        "project_name": name,
        "archi": archi,
        "adapter": adapter,
        "examples": examples,
        "python_model": python_model,
        "python_version": python_version,
        "description": description,
    }
    scaffold_dbt(base, ctx, standalone=not project_root)

    if project_root:
        merge_pyproject_deps_and_scripts(project_root / "pyproject.toml", dbt_dependencies(adapter))
        merge_makefile_targets(
            project_root / "Makefile",
            f"dbt_{name}:\n\tcd src/{name} && uv run dbt deps && uv run dbt build",
        )

    click.echo(click.style(f"\n✔ dbt project '{name}' created in {base}\n", fg="green", bold=True))
    if project_root:
        click.echo(f"  make dbt_{name}")
    else:
        click.echo(f"  cd {base}")
        if adapter != "duckdb":
            click.echo("  cp .env.example .env   # fill in your credentials")
        click.echo("  make install")
        click.echo("  make build")
    click.echo()
    return base
