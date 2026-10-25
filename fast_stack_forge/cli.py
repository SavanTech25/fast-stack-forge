import click
from fast_stack_forge import __version__
from fast_stack_forge.commands.init import init_project, DB_URLS
from fast_stack_forge.commands.init_dbt import init_dbt_project, ARCHITECTURES, ADAPTERS, LEGACY_CONNECTORS
from fast_stack_forge.commands.init_databricks import init_databricks_project, RUNTIMES, NODE_TYPES, COMPONENTS
from fast_stack_forge.commands.make_entity import make_entity
from fast_stack_forge.commands.make_dbt import make_dbt
from fast_stack_forge.commands.make_service import make_service, SERVICE_TYPES, PROVIDERS, VECTOR_STORES
from fast_stack_forge.commands.make_dashboard import make_dashboard
from fast_stack_forge.commands.init_ds_data import init_ds_data_project
from fast_stack_forge.commands.init_ds_make import init_ds_make
from fast_stack_forge.utils import Prompter

yes_option = click.option("--yes", "-y", is_flag=True, help="Don't ask questions: use the defaults for missing options.")


@click.group()
@click.version_option(__version__, prog_name="fast-stack-forge")
def cli():
    """⚡ fast-stack-forge - project scaffolder for FastAPI, dbt, Databricks and data science.

    \b
    Not sure where to start? Run the wizard:
      fast-stack-forge new
    """
    pass


@cli.command("new")
@yes_option
def new(yes):
    """Interactive wizard: choose what to create and answer a few questions."""
    kind = Prompter(yes).choice(
        "What do you want to create?",
        [
            ("fastapi", "FastAPI backend (entities, JWT, rate limiting, scheduler)"),
            ("dbt", "dbt project (DuckDB, Postgres, Snowflake, BigQuery, Databricks)"),
            ("databricks", "Databricks Asset Bundle (jobs, notebooks, pipelines, dbt)"),
            ("ds", "Data science project (notebooks, Streamlit, optional FastAPI)"),
        ],
        "fastapi",
    )
    if kind == "fastapi":
        init_project(None, None, assume_yes=yes)
    elif kind == "dbt":
        init_dbt_project(assume_yes=yes)
    elif kind == "databricks":
        init_databricks_project(assume_yes=yes)
    else:
        init_ds_data_project(None, include_api=None, include_data=None, assume_yes=yes)


@cli.command("init")
@click.argument("project_name", required=False)
@click.option("--db", default=None, type=click.Choice(list(DB_URLS)), help="Database backend (asked if omitted)")
@yes_option
def init(project_name, db, yes):
    """Initialize a new FastAPI project scaffold."""
    init_project(project_name, db, assume_yes=yes)


@cli.command("init:dbt")
@click.argument("project_name", required=False)
@click.option("--archi", type=click.Choice(list(ARCHITECTURES)), help="Model architecture (asked if omitted)")
@click.option("--adapter", type=click.Choice(list(ADAPTERS)), help="Warehouse adapter (asked if omitted)")
@click.option("--examples/--no-examples", default=None, help="Include example seeds, models, tests and snapshot")
@click.option("--python-model/--no-python-model", default=None, help="Include a dbt Python model example")
@yes_option
def init_dbt(project_name, archi, adapter, examples, python_model, yes):
    """
    Initialize a dbt project (uv, Makefile, profiles from env vars, example models).

    \b
    Example:
      fast-stack-forge init:dbt                       # answer the questions
      fast-stack-forge init:dbt analytics --archi medallion --adapter duckdb -y
    """
    init_dbt_project(project_name, archi, adapter, examples, python_model, assume_yes=yes)


@cli.command("init:etl", hidden=True)
@click.argument("project_name", required=False)
@click.option("--archi", type=click.Choice(list(ARCHITECTURES)))
@click.option("--connector", type=click.Choice(list(LEGACY_CONNECTORS) + list(ADAPTERS)))
@yes_option
def init_etl(project_name, archi, connector, yes):
    """Deprecated alias of init:dbt."""
    init_dbt_project(project_name, archi, connector, assume_yes=yes)


@cli.command("init:databricks")
@click.argument("project_name", required=False)
@click.option("--host", help="Workspace URL, e.g. https://adb-123.azuredatabricks.net")
@click.option("--catalog", help="Unity Catalog catalog (default: main)")
@click.option("--compute", type=click.Choice(["serverless", "classic"]), help="Job compute")
@click.option("--runtime", type=click.Choice(list(RUNTIMES)), help="Databricks Runtime LTS version")
@click.option("--cloud", type=click.Choice(list(NODE_TYPES)), help="Cloud (classic compute node types)")
@click.option(
    "--with", "components", multiple=True, type=click.Choice(list(COMPONENTS)),
    help="Job components, repeatable: --with wheel --with dbt (asked if omitted)",
)
@yes_option
def init_databricks(project_name, host, catalog, compute, runtime, cloud, components, yes):
    """
    Initialize a Databricks Asset Bundle project.

    \b
    Generates databricks.yml (dev/prod targets), a Unity Catalog schema, a daily job
    and, as you choose: a Python wheel task, an ingestion notebook, a Lakeflow (DLT)
    pipeline and a dbt project. Local dev with uv, pytest and Databricks Connect.

    \b
    Example:
      fast-stack-forge init:databricks                # answer the questions
      fast-stack-forge init:databricks lakehouse --with wheel --with pipeline -y
    """
    init_databricks_project(project_name, host, catalog, compute, runtime, cloud, components, assume_yes=yes)


@cli.command("make:entity")
@click.argument("entity_name")
@click.argument("fields", nargs=-1)
@click.option("--no-router", is_flag=True, help="Skip router generation")
@click.option("--no-controller", is_flag=True, help="Skip controller generation")
def make(entity_name, fields, no_router, no_controller):
    """
    Generate entity, schema, controller and router.

    \b
    Field syntax:  name:type[:modifier]
    Types:         string, int, float, bool, text, date, datetime
    Modifiers:     encrypt, hash, nullable, fk=ModelName

    \b
    Example:
      fast-stack-forge make:entity User nom:string prenom:string pwd:string:hash role:string:fk=Role
    """
    make_entity(entity_name, fields, no_router=no_router, no_controller=no_controller)


@cli.command("make:dbt")
@click.argument("model_name")
@click.option("--view", is_flag=True, help="Materialize as view")
@click.option("--incremental", is_flag=True, help="Materialize as incremental")
@click.option("--python", is_flag=True, help="Generate a Python model instead of SQL")
@click.option("--layer", default=None, help="Folder under models/ (e.g. staging, silver, marts)")
def make_dbt_cmd(model_name, view, incremental, python, layer):
    """
    Generate a dbt model. Run it from inside a dbt project or a FastForge project.
    """
    make_dbt(model_name, view, incremental, python, layer)


@cli.command("make:service")
@click.argument("service_name")
@click.option("--type", "service_type", type=click.Choice(SERVICE_TYPES), help="Type of AI service (asked if omitted)")
@click.option("--provider", type=click.Choice(PROVIDERS), help="AI provider (asked if omitted)")
@click.option("--vector-store", type=click.Choice(VECTOR_STORES), help="Vector store, RAG only (asked if omitted)")
@yes_option
def make_service_cmd(service_name, service_type, provider, vector_store, yes):
    """
    Generate an AI service and its JWT-protected router.

    \b
    Types:
      rag      answer questions from your documents (ingest + vector search)
      agent    tool-calling agent with per-session memory (LangChain create_agent)
      agentic  explicit LangGraph workflow you can extend with your own nodes
      ocr      extract text from uploaded images and PDFs

    \b
    Example:
      fast-stack-forge make:service Support --type rag --provider anthropic --vector-store qdrant
    """
    ask = Prompter(yes)
    service_type = service_type or ask.choice("Service type:", [
        ("rag", "answer questions from your documents"),
        ("agent", "tool-calling agent with memory"),
        ("agentic", "custom LangGraph workflow"),
        ("ocr", "text extraction from images and PDFs"),
    ], "rag")
    provider = provider or ask.choice("AI provider:", [
        ("openai", "OpenAI"), ("anthropic", "Anthropic Claude"), ("mistral", "Mistral AI"),
        ("gemini", "Google Gemini"), ("azure", "Azure OpenAI"),
    ], "openai")
    if service_type == "rag" and not vector_store:
        vector_store = ask.choice("Vector store:", [
            ("chroma", "local folder, zero setup"), ("qdrant", "Qdrant server or cloud"),
            ("supabase", "Postgres + pgvector (Supabase)"), ("upstash", "Upstash Vector (serverless)"),
        ], "chroma")
    make_service(service_name, service_type, provider, vector_store or "chroma")


@cli.command("make:sync")
@click.argument("sync_name")
@click.option("--source", default="mongodb", help="Source database")
@click.option("--dest", default="postgres", help="Destination database")
def make_sync_cmd(sync_name, source, dest):
    """
    Generate a database synchronization script (ELT).
    """
    from fast_stack_forge.commands.make_sync import make_sync
    make_sync(sync_name, source, dest)


@cli.command("make:discard")
@click.argument("entity_name")
def discard_entity_cmd(entity_name):
    """
    Remove entity, schema, controller and router.
    """
    from fast_stack_forge.commands.discard_entity import discard_entity
    discard_entity(entity_name)


@cli.command("make:dashboard")
@click.argument("pages", nargs=-1)
def make_dashboard_cmd(pages):
    """
    Generate a Streamlit dashboard with custom pages.

    Example:
      fast-stack-forge make:dashboard Atelier Analytics Chatbot
    """
    make_dashboard(pages)


@cli.command("init:ds-data")
@click.argument("package_name", required=False)
@click.option("--api/--no-api", default=None, help="Include FastAPI skeleton inside the DS project")
@click.option("--data/--no-data", default=None, help="Include ETL data folders raw/interim/processed/external")
@yes_option
def init_ds_data(package_name, api, data, yes):
    """
    Initialize an AstroData data science project.

    \b
    Features:
      - Interactive Python version selector (latest, latest-1, latest-2)
      - Open-source license (MIT, BSD-3-Clause, Apache-2.0, GPL-3.0)
      - Optional description & author
      - Name auto-sanitized: "test of test" → "test_of_test"
      - Asks if you want a companion FastAPI project (named <name>_api)
      - Uses loguru (no log files), python-decouple for config

    \b
    Flags:
      --api     Include FastAPI files inside src/<name>/api/
      --data    Create ETL data/ folders (raw, interim, processed, external)

    \b
    Example:
      fast-stack-forge init:ds-data my_project
      fast-stack-forge init:ds-data "test of test" --api --data
    """
    init_ds_data_project(package_name, include_api=api, include_data=data, assume_yes=yes)


@cli.command("init:ds-make")
@click.argument("project_dir", default=".", required=False)
def init_ds_make_cmd(project_dir):
    """
    Add FastAPI + Streamlit skeleton to an existing AstroData DS project.

    \b
    Run from the project root (or pass the path as argument).
    Detects the package name from src/ automatically.

    \b
    Example:
      cd my_project && fast-stack-forge init:ds-make
      fast-stack-forge init:ds-make ./my_project
    """
    init_ds_make(project_dir)


def main():
    cli()


if __name__ == "__main__":
    main()
