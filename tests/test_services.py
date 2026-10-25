import ast
import os
import tomllib

import pytest
from click.testing import CliRunner

from fast_stack_forge.cli import cli
from fast_stack_forge.commands.make_service import PROVIDERS, SERVICE_TYPES, VECTOR_STORES, service_dependencies


@pytest.fixture
def project(run, tmp_path):
    """A fresh FastAPI project; the cwd is its root."""
    def _project(db="sqlite"):
        run("init", "shop", "--db", db)
        root = tmp_path / "shop"
        os.chdir(root)
        return root
    return _project


def generated(root, name):
    service = (root / f"src/shop/service/{name.lower()}.py").read_text()
    router = (root / f"src/shop/router/r_{name.lower()}.py").read_text()
    ast.parse(service)
    ast.parse(router)
    return service, router


@pytest.mark.parametrize("service_type", SERVICE_TYPES)
@pytest.mark.parametrize("provider", PROVIDERS)
def test_every_service_generates_valid_python(project, run, service_type, provider):
    root = project()
    run("make:service", "Bot", "--type", service_type, "--provider", provider, "--vector-store", "chroma")
    service, router = generated(root, "Bot")

    assert "r_bot" in (root / "app/main.py").read_text()
    deps = tomllib.loads((root / "pyproject.toml").read_text())["project"]["dependencies"]
    assert set(service_dependencies(service_type, provider, "chroma")) <= set(deps)
    assert len(deps) == len(set(deps))

    # no hardcoded keys or temperature, model names come from .env
    assert "temperature" not in service
    assert "Depends(JWTBearer())" in router
    if provider == "azure":
        assert "api.openai.com" not in service and "AZURE_OPENAI_ENDPOINT" in service
    if provider == "anthropic" and service_type != "ocr":
        assert 'default="claude-opus-5-5"' in service
    if service_type == "ocr":
        assert "UploadFile" in router and "file_path" not in service
    if service_type == "agent":
        assert "from langchain.agents import create_agent" in service


@pytest.mark.parametrize("vector_store", VECTOR_STORES)
def test_rag_vector_stores(project, run, vector_store):
    root = project()
    run("make:service", "Docs", "--type", "rag", "--provider", "openai", "--vector-store", vector_store)
    service, router = generated(root, "Docs")
    assert "/ingest" in router and "/refresh" in router
    assert "def _build_vector_store" in service
    env = (root / ".env").read_text()
    assert "DOCS_SOURCE_QUERY=" in env and "OPENAI_API_KEY=" in env


def test_rag_on_mongodb_has_no_sql_refresh(project, run):
    root = project("mongodb")
    run("make:service", "Docs", "--type", "rag", "--provider", "mistral")
    service, router = generated(root, "Docs")
    assert "sqlalchemy" not in service + router
    assert "/refresh" not in router


def test_env_keys_are_added_once(project, run):
    root = project()
    run("make:service", "A", "--type", "agent", "--provider", "openai")
    run("make:service", "B", "--type", "agentic", "--provider", "openai")
    env = (root / ".env").read_text()
    assert env.count("OPENAI_API_KEY=") == 1
    assert "B_MAX_STEPS=10" in env


def test_init_generates_secrets(project):
    root = project()
    env = (root / ".env").read_text()
    assert "change-me-in-production" not in env
    assert "change-me-in-production" not in (root / "src/shop/middleware/middleware.py").read_text()
    secret = next(line.split("=", 1)[1] for line in env.splitlines() if line.startswith("SECRET_KEY="))
    assert len(secret) >= 32


def test_invalid_service_name_is_rejected(project):
    project()
    result = CliRunner().invoke(cli, ["make:service", "my-bot", "--type", "rag", "--provider", "openai"])
    assert result.exit_code == 1
    assert "Invalid service name" in result.output


def test_service_options_are_asked(project, run, interactive):
    root = project()
    run("make:service", "Reader", input="4\n3\n")  # ocr, mistral
    service, _ = generated(root, "Reader")
    assert "mistral-ocr-latest" in service


def test_sql_entity_model_is_importable_code(project, run):
    root = project()
    run("make:entity", "User", "email:string", "age:int:nullable", "pwd:string:hash", "note:text:encrypt", "role:string:fk=Files")
    model = (root / "src/shop/entity/user.py").read_text()
    ast.parse(model)
    assert "from shop.data.database import Base" in model
    assert "from shop.utils.crypto import encrypt_value, decrypt_value, hash_value" in model
    assert 'ForeignKey("files.id")' in model
    assert '"age", Integer, nullable=True' in model
