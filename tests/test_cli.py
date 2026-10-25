import ast
import tomllib
from pathlib import Path

import pytest
import yaml

from fast_stack_forge import __version__
from fast_stack_forge.commands.init_dbt import ADAPTERS, ARCHITECTURES
from fast_stack_forge.utils import sanitize_name


def assert_valid_files(root: Path) -> None:
    """Every generated YAML, TOML and Python file must parse."""
    for path in root.rglob("*"):
        if path.suffix in (".yml", ".yaml"):
            yaml.safe_load(path.read_text())
        elif path.suffix == ".toml":
            tomllib.loads(path.read_text())
        elif path.suffix == ".py":
            ast.parse(path.read_text(), filename=str(path))


def test_version(run):
    assert __version__ in run("--version").output


@pytest.mark.parametrize(
    "raw, clean",
    [("My Project", "my_project"), ("test of test", "test_of_test"), ("data-lake.v2", "data_lake_v2"), ("2024 sales", "p_2024_sales")],
)
def test_sanitize_name(raw, clean):
    assert sanitize_name(raw) == clean


# ── FastAPI ──────────────────────────────────────────────────────────────────

def test_init_fastapi_then_entity_and_discard(run, tmp_path):
    run("init", "shop", "--db", "sqlite")
    root = tmp_path / "shop"
    assert (root / "app/main.py").exists()
    assert (root / "src/shop/entity/files.py").exists()  # default entity
    assert_valid_files(root)

    import os
    os.chdir(root)
    run("make:entity", "Product", "name:string", "price:float", "stock:int:nullable")
    assert (root / "src/shop/router/r_product.py").exists()
    assert "r_product" in (root / "app/main.py").read_text()

    run("make:discard", "Product")
    assert not (root / "src/shop/entity/product.py").exists()
    assert "r_product" not in (root / "app/main.py").read_text()


def test_init_fastapi_asks_for_name_and_db(run, tmp_path, interactive):
    out = run("init", input="My Shop\n2\n").output
    assert "Database:" in out
    assert "postgresql" in (tmp_path / "my_shop/.env").read_text()


# ── dbt ──────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("archi", list(ARCHITECTURES))
@pytest.mark.parametrize("adapter", list(ADAPTERS))
def test_init_dbt_all_combinations(run, tmp_path, archi, adapter):
    run("init:dbt", "analytics", "--archi", archi, "--adapter", adapter, "-y")
    root = tmp_path / "analytics"
    assert_valid_files(root)

    layers = ARCHITECTURES[archi]["layers"]
    models = ARCHITECTURES[archi]["models"]
    assert (root / "models" / layers[2] / f"{models['l3']}.sql").exists()
    project = yaml.safe_load((root / "dbt_project.yml").read_text())
    assert list(project["models"]["analytics"]) == ["+materialized", *layers]

    profile = yaml.safe_load((root / "profiles.yml").read_text())
    assert profile["analytics"]["outputs"]["dev"]["type"] == adapter
    deps = tomllib.loads((root / "pyproject.toml").read_text())["project"]["dependencies"]
    assert any(d.startswith(ADAPTERS[adapter]["package"]) for d in deps)
    # The scaffolder's own Jinja must not leak into the dbt files
    for path in root.rglob("*"):
        if path.is_file():
            assert "[[" not in path.read_text() and "[%" not in path.read_text(), path


def test_init_dbt_python_model_only_where_supported(run, tmp_path):
    run("init:dbt", "duck", "--archi", "default", "--adapter", "duckdb", "-y")
    run("init:dbt", "pg", "--archi", "default", "--adapter", "postgres", "--python-model", "-y")
    assert (tmp_path / "duck/models/marts/order_status_stats.py").exists()
    assert not (tmp_path / "pg/models/marts/order_status_stats.py").exists()


def test_init_dbt_without_examples(run, tmp_path):
    run("init:dbt", "empty", "--no-examples", "-y")
    root = tmp_path / "empty"
    assert not list(root.glob("models/**/*.sql"))
    assert (root / "models/marts/.gitkeep").exists()


def test_init_dbt_interactive(run, tmp_path, interactive):
    # name, architecture=medallion, adapter=snowflake, examples=yes, python model=no, python=3.12, description
    run("init:dbt", input="lake\n2\n3\ny\nn\n1\nMy lakehouse\n")
    root = tmp_path / "lake"
    assert (root / "models/gold/gld_customers.sql").exists()
    assert "snowflake" in (root / "profiles.yml").read_text()
    assert "My lakehouse" in (root / "pyproject.toml").read_text()


def test_init_etl_legacy_alias(run, tmp_path):
    run("init:etl", "legacy", "--archi", "star", "--connector", "local", "-y")
    assert "duckdb" in (tmp_path / "legacy/profiles.yml").read_text()


def test_make_dbt_finds_project_and_writes_valid_models(run, tmp_path, monkeypatch):
    run("init:dbt", "analytics", "-y")
    monkeypatch.chdir(tmp_path / "analytics" / "models")
    run("make:dbt", "fct_events", "--layer", "marts", "--incremental")
    run("make:dbt", "py_events", "--layer", "marts", "--python", "--incremental")
    sql = (tmp_path / "analytics/models/marts/fct_events.sql").read_text()
    assert "materialized='incremental'" in sql and "is_incremental()" in sql
    ast.parse((tmp_path / "analytics/models/marts/py_events.py").read_text())


# ── Databricks ───────────────────────────────────────────────────────────────

def test_init_databricks_full_serverless(run, tmp_path):
    run("init:databricks", "lakehouse", "--host", "adb-1.azuredatabricks.net", "--compute", "serverless",
        "--with", "wheel", "--with", "notebook", "--with", "pipeline", "--with", "dbt", "-y")
    root = tmp_path / "lakehouse"
    assert_valid_files(root)

    bundle = yaml.safe_load((root / "databricks.yml").read_text())
    assert bundle["targets"]["dev"]["workspace"]["host"] == "https://adb-1.azuredatabricks.net"
    job = yaml.safe_load((root / "resources/lakehouse_job.yml").read_text())["resources"]["jobs"]["lakehouse_job"]
    tasks = [t["task_key"] for t in job["tasks"]]
    assert tasks == ["ingest", "refresh_pipeline", "transform", "dbt"]
    assert job["tasks"][3]["depends_on"] == [{"task_key": "transform"}]
    assert {e["environment_key"] for e in job["environments"]} == {"default", "dbt"}
    assert (root / "dbt_project/dbt_profiles/profiles.yml").exists()
    assert (root / "src/pipelines/lakehouse_pipeline.py").exists()

    pyproject = tomllib.loads((root / "pyproject.toml").read_text())
    assert pyproject["project"]["requires-python"] == ">=3.12,<3.13"
    assert "databricks-connect~=17.3.0" in pyproject["dependency-groups"]["dev"]


def test_init_databricks_classic_wheel_only(run, tmp_path):
    run("init:databricks", "etl", "--compute", "classic", "--runtime", "15.4", "--cloud", "azure", "--with", "wheel", "-y")
    root = tmp_path / "etl"
    job = yaml.safe_load((root / "resources/etl_job.yml").read_text())["resources"]["jobs"]["etl_job"]
    assert [t["task_key"] for t in job["tasks"]] == ["transform"]
    cluster = job["job_clusters"][0]["new_cluster"]
    assert cluster["spark_version"] == "15.4.x-scala2.12" and cluster["node_type_id"] == "Standard_D4ds_v5"
    assert not (root / "resources/etl_pipeline.yml").exists()
    assert not (root / "dbt_project").exists()


def test_init_databricks_interactive(run, tmp_path, interactive):
    # name, host, catalog, compute=serverless, runtime=16.4, wheel=y, notebook=n, pipeline=y, dbt=n, description
    run("init:databricks", input="Sales Lake\nhttps://dbc-9.cloud.databricks.com\nanalytics\n1\n2\ny\nn\ny\nn\n\n")
    root = tmp_path / "sales_lake"
    bundle = yaml.safe_load((root / "databricks.yml").read_text())
    assert bundle["variables"]["catalog"]["default"] == "analytics"
    assert (root / "resources/sales_lake_pipeline.yml").exists()
    assert not (root / "src/notebooks").exists()


# ── Data science + wizard ────────────────────────────────────────────────────

def test_init_ds_data_non_interactive(run, tmp_path):
    run("init:ds-data", "astro", "--api", "--data", "-y")
    root = tmp_path / "astro"
    assert (root / "src/astro/api/main.py").exists()
    assert (root / "data/raw/.gitkeep").exists()
    assert_valid_files(root)


@pytest.mark.parametrize(
    "choice, expected",
    [("1", "my_api/app/main.py"), ("2", "my_dbt_project/dbt_project.yml"),
     ("3", "my_databricks_project/databricks.yml"), ("4", "my_ds_project/pyproject.toml")],
)
def test_new_wizard_dispatches(run, tmp_path, monkeypatch, choice, expected):
    from fast_stack_forge import utils

    # Answer only the first question, then fall back to the defaults
    answers = iter([True, False])
    monkeypatch.setattr(utils, "is_interactive", lambda: next(answers, False))
    run("new", input=f"{choice}\n")
    assert (tmp_path / expected).exists()
