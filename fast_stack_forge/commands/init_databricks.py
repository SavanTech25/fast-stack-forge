"""init:databricks command — scaffold a Databricks Asset Bundle (jobs, notebooks, pipelines, dbt)."""

import os
from pathlib import Path

import click

from fast_stack_forge.commands.init_dbt import ARCHITECTURES, scaffold_dbt
from fast_stack_forge.utils import Prompter, render, write

# Databricks Runtime LTS versions -> local Python, Databricks Connect and serverless environment
RUNTIMES = {
    "17.3": {"label": "17.3 LTS", "python": "3.12", "python_next": "3.13", "connect": "17.3",
             "env_version": "4", "spark_version": "17.3.x-scala2.13"},
    "16.4": {"label": "16.4 LTS", "python": "3.12", "python_next": "3.13", "connect": "16.4",
             "env_version": "3", "spark_version": "16.4.x-scala2.12"},
    "15.4": {"label": "15.4 LTS", "python": "3.11", "python_next": "3.12", "connect": "15.4",
             "env_version": "2", "spark_version": "15.4.x-scala2.12"},
}

NODE_TYPES = {"aws": "i3.xlarge", "azure": "Standard_D4ds_v5", "gcp": "n2-highmem-4"}

COMPONENTS = {
    "wheel": "Python package run as a wheel task (src/<name>/main.py)",
    "notebook": "Ingestion notebook task",
    "pipeline": "Lakeflow Declarative Pipeline (DLT) bronze → silver → gold",
    "dbt": "dbt project run by a dbt task on a SQL warehouse",
}


def init_databricks_project(
    project_name: str = None,
    host: str = None,
    catalog: str = None,
    compute: str = None,
    runtime: str = None,
    cloud: str = None,
    components: tuple = (),
    assume_yes: bool = False,
) -> Path:
    ask = Prompter(assume_yes)

    click.echo(click.style("\n⚡ FastForge — new Databricks project (Asset Bundle)\n", fg="cyan", bold=True))
    name = ask.name("Project name", project_name, default="my_databricks_project")
    base = Path(name)
    if base.exists():
        click.echo(click.style(f"✗ '{base}' already exists.", fg="red"))
        raise SystemExit(1)

    host = host or ask.text(
        "Workspace URL", default=os.getenv("DATABRICKS_HOST", "https://<your-workspace>.cloud.databricks.com")
    )
    if not host.startswith("http"):
        host = f"https://{host}"
    host = host.rstrip("/")
    catalog = catalog or ask.text("Unity Catalog catalog", default="main")

    compute = compute or ask.choice(
        "Compute:", [("serverless", "no cluster to manage (recommended)"), ("classic", "job cluster")], "serverless"
    )
    runtime = runtime or ask.choice(
        "Databricks Runtime (sets the local Python and Databricks Connect versions):",
        [(k, f"{v['label']}, Python {v['python']}") for k, v in RUNTIMES.items()],
        "17.3",
    )
    node_type = None
    if compute == "classic":
        cloud = cloud or ask.choice("Cloud:", list(NODE_TYPES), "aws")
        node_type = NODE_TYPES[cloud]

    if components:
        chosen = set(components)
    else:
        click.echo("\nWhat should the job run?")
        defaults = {"wheel": True, "notebook": True, "pipeline": False, "dbt": False}
        chosen = {key for key, help_text in COMPONENTS.items() if ask.confirm(f"  {help_text}?", default=defaults[key])}
    if not chosen:
        click.echo(click.style("  ℹ  Nothing selected: adding the Python wheel task.", fg="yellow"))
        chosen = {"wheel"}

    warehouse = archi = None
    if "dbt" in chosen:
        warehouse = ask.text("SQL warehouse name for dbt", default="Serverless Starter Warehouse")
        archi = ask.choice("dbt model architecture:", [(k, v["help"]) for k, v in ARCHITECTURES.items()], "medallion")

    description = ask.text("\nShort description (optional)", default="") or f"Databricks project {name}"
    click.echo()

    tasks = [t for t, key in [("ingest", "notebook"), ("refresh_pipeline", "pipeline"),
                              ("transform", "wheel"), ("dbt", "dbt")] if key in chosen]
    ctx = {
        "name": name,
        "description": description,
        "host": host,
        "catalog": catalog,
        "serverless": compute == "serverless",
        "runtime": RUNTIMES[runtime],
        "node_type": node_type,
        "warehouse": warehouse,
        "tasks": tasks,
        **{key: key in chosen for key in COMPONENTS},
    }

    def put(rel_path: str, template: str) -> None:
        write(base / rel_path, render("databricks", template, ctx))

    put("databricks.yml", "databricks.yml.j2")
    put("resources/schema.yml", "resources/schema.yml.j2")
    put(f"resources/{name}_job.yml", "resources/job.yml.j2")
    if ctx["pipeline"]:
        put(f"resources/{name}_pipeline.yml", "resources/pipeline.yml.j2")
        put(f"src/pipelines/{name}_pipeline.py", "src/pipeline.py.j2")
    if ctx["notebook"]:
        put("src/notebooks/ingest.py", "src/notebook.py.j2")
    write(base / "src" / name / "__init__.py", "")
    put(f"src/{name}/main.py", "src/main.py.j2")
    put("tests/conftest.py", "tests/conftest.py.j2")
    put("tests/test_main.py", "tests/test_main.py.j2")
    put("pyproject.toml", "pyproject.toml.j2")
    put("Makefile", "Makefile.j2")
    put(".env.example", "env.example.j2")
    put(".gitignore", "gitignore.j2")
    put("README.md", "README.md.j2")

    if ctx["dbt"]:
        scaffold_dbt(
            base / "dbt_project",
            {
                "project_name": f"{name}_dbt",
                "archi": archi,
                "adapter": "databricks",
                "examples": True,
                "python_model": False,
                "python_version": RUNTIMES[runtime]["python"],
                "description": f"dbt models of {name}",
                "catalog": catalog,
                "profiles_dir": "dbt_profiles",
            },
            standalone=False,
        )

    click.echo(click.style(f"\n✔ Databricks project '{name}' created in {base}\n", fg="green", bold=True))
    click.echo(f"  cd {base}")
    click.echo("  cp .env.example .env")
    click.echo("  make login      # databricks auth login")
    click.echo("  make install    # uv sync")
    click.echo("  make deploy     # databricks bundle deploy -t dev")
    click.echo("  make run\n")
    return base
