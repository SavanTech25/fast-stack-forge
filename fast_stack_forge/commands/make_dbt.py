import click
from pathlib import Path

from fast_stack_forge.utils import find_project_root, write as _write


def write(path, content):
    _write(path, content, overwrite=False)


def find_dbt_project(start: Path = None) -> Path | None:
    """The dbt project containing `start`, or one under <root>/src/ or <root>/ (e.g. a bundle's dbt_project/)."""
    start = start or Path.cwd()
    for p in [start, *start.parents]:
        if (p / "dbt_project.yml").is_file():
            return p
    root = find_project_root(start) or start
    for pattern in ("src/*/dbt_project.yml", "*/dbt_project.yml"):
        found = sorted(root.glob(pattern))
        if found:
            return found[0].parent
    return None


def sql_model(is_view: bool, is_incremental: bool) -> str:
    materialized = "incremental" if is_incremental else ("view" if is_view else "table")
    config = f"{{{{\n    config(\n        materialized='{materialized}'"
    if is_incremental:
        config += ",\n        unique_key='id'"
    config += "\n    )\n}}\n\n"

    body = (
        "with source as (\n"
        "    select * from {{ source('my_source', 'my_table') }}\n"
        ")\n\n"
        "select * from source\n"
    )
    if is_incremental:
        body += (
            "\n{% if is_incremental() %}\n"
            "-- only process rows that arrived since the last run\n"
            "where updated_at > (select max(updated_at) from {{ this }})\n"
            "{% endif %}\n"
        )
    return config + body


def python_model(is_view: bool, is_incremental: bool) -> str:
    materialized = "incremental" if is_incremental else "table"
    if is_view:
        click.echo(click.style("  ℹ  Python models can't be views: using 'table'.", fg="yellow"))
    return (
        "def model(dbt, session):\n"
        f'    dbt.config(materialized="{materialized}")\n'
        "\n"
        '    df = dbt.ref("my_upstream_model")\n'
        "\n"
        "    return df\n"
    )


def make_dbt(model_name, is_view, is_incremental, is_python, layer):
    click.echo(click.style(f"\n⚡ FastForge ETL — make:dbt {model_name}\n", fg="cyan", bold=True))

    dbt_project_dir = find_dbt_project()
    if not dbt_project_dir:
        click.echo(click.style("✗ Could not find a dbt project (dbt_project.yml). Run 'fast-stack-forge init:dbt' first.", fg="red"))
        raise SystemExit(1)

    models_dir = dbt_project_dir / "models"
    if not models_dir.exists():
        click.echo(click.style(f"✗ 'models' directory not found in {dbt_project_dir}. Is this a dbt project?", fg="red"))
        raise SystemExit(1)

    target_dir = models_dir / layer if layer else models_dir
    if layer and not target_dir.exists():
        layers = ", ".join(sorted(d.name for d in models_dir.iterdir() if d.is_dir()))
        click.echo(click.style(f"⚠ Layer '{layer}' does not exist (existing: {layers}), creating it...", fg="yellow"))

    if is_python:
        write(target_dir / f"{model_name}.py", python_model(is_view, is_incremental))
    else:
        write(target_dir / f"{model_name}.sql", sql_model(is_view, is_incremental))

    click.echo(click.style(f"\n✔ dbt model '{model_name}' generated!\n", fg="green", bold=True))
