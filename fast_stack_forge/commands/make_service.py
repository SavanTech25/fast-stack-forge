import re

import click

from fast_stack_forge.commands.init import merge_pyproject_deps_and_scripts
from fast_stack_forge.utils import render as render_template, resolve_package_or_exit, write as _write

SERVICE_TYPES = ["rag", "agent", "agentic", "ocr"]
PROVIDERS = ["openai", "anthropic", "mistral", "gemini", "azure"]
VECTOR_STORES = ["chroma", "qdrant", "supabase", "upstash"]

LANGCHAIN_PROVIDER_DEPS = {
    "openai": ["langchain-openai>=1.0"],
    "azure": ["langchain-openai>=1.0"],
    "anthropic": ["langchain-anthropic>=1.0"],
    "mistral": ["langchain-mistralai>=1.0"],
    "gemini": ["langchain-google-genai>=4.0"],
}
OCR_PROVIDER_DEPS = {
    "openai": ["openai>=2.0"],
    "azure": ["openai>=2.0"],
    "anthropic": ["anthropic>=1.17"],  # server-side refusal fallbacks
    "mistral": ["mistralai>=3.0"],  # client lives in mistralai.client since 3.0
    "gemini": ["google-genai>=1.0"],
}
VECTOR_STORE_DEPS = {
    "chroma": ["langchain-chroma>=1.0"],
    "qdrant": ["langchain-qdrant>=1.0"],
    "supabase": ["langchain-postgres>=0.0.15", "psycopg[binary]>=3.2"],
    "upstash": ["langchain-community>=0.4", "upstash-vector>=0.8"],
}

PROVIDER_ENV = {
    "openai": {"OPENAI_API_KEY": "", "OPENAI_MODEL": "gpt-5.5"},
    "azure": {
        "AZURE_OPENAI_ENDPOINT": "https://<resource>.openai.azure.com/",
        "AZURE_OPENAI_API_KEY": "",
        "AZURE_OPENAI_API_VERSION": "2024-10-21",
        "AZURE_OPENAI_CHAT_DEPLOYMENT": "",
    },
    "anthropic": {"ANTHROPIC_API_KEY": "", "ANTHROPIC_MODEL": "claude-opus-5-5"},
    "mistral": {"MISTRAL_API_KEY": "", "MISTRAL_MODEL": "mistral-large-latest"},
    "gemini": {"GEMINI_API_KEY": "", "GEMINI_MODEL": "gemini-flash-latest"},
}
EMBEDDING_ENV = {
    "openai": {"OPENAI_EMBEDDING_MODEL": "text-embedding-3-small"},
    "azure": {"AZURE_OPENAI_EMBEDDING_DEPLOYMENT": ""},
    "anthropic": {"VOYAGE_API_KEY": "", "VOYAGE_EMBEDDING_MODEL": "voyage-4"},
    "mistral": {"MISTRAL_EMBEDDING_MODEL": "mistral-embed"},
    "gemini": {"GEMINI_EMBEDDING_MODEL": "gemini-embedding-2"},
}
VECTOR_STORE_ENV = {
    "chroma": {"CHROMA_PERSIST_DIR": "./chroma_data"},
    "qdrant": {"QDRANT_URL": "http://localhost:6333", "QDRANT_API_KEY": ""},
    "supabase": {"PGVECTOR_URL": "postgresql+psycopg://postgres:password@localhost:5432/postgres"},
    "upstash": {"UPSTASH_VECTOR_REST_URL": "", "UPSTASH_VECTOR_REST_TOKEN": ""},
}


def render(template_name, context):
    return render_template("service", template_name, context)


def write(path, content):
    _write(path, content, overwrite=False)


def service_dependencies(service_type: str, provider: str, vector_store: str) -> list[str]:
    if service_type == "ocr":
        return list(OCR_PROVIDER_DEPS[provider])
    deps = ["langchain>=1.0", "langgraph>=1.0", *LANGCHAIN_PROVIDER_DEPS[provider]]
    if service_type == "rag":
        deps += ["langchain-text-splitters>=1.0", *VECTOR_STORE_DEPS[vector_store]]
        if provider == "anthropic":
            deps.append("langchain-voyageai>=0.1")
    return deps


def service_env(service_name: str, service_type: str, provider: str, vector_store: str, has_sql: bool) -> dict:
    prefix = service_name.upper()
    env = dict(PROVIDER_ENV[provider])
    if service_type == "ocr" and provider == "mistral":
        env = {"MISTRAL_API_KEY": "", "MISTRAL_OCR_MODEL": "mistral-ocr-latest"}
    if service_type == "rag":
        env |= EMBEDDING_ENV[provider] | VECTOR_STORE_ENV[vector_store]
        env |= {f"{prefix}_COLLECTION": service_name.lower(), f"{prefix}_TOP_K": "4"}
        if has_sql:
            env[f"{prefix}_SOURCE_QUERY"] = ""
    elif service_type == "agentic":
        env[f"{prefix}_MAX_STEPS"] = "10"
    elif service_type == "ocr":
        env[f"{prefix}_MAX_UPLOAD_MB"] = "20"
    return env


def merge_env(env_path, values: dict, title: str) -> list[str]:
    """Append the missing keys to .env (existing values are never touched). Returns the keys added."""
    text = env_path.read_text() if env_path.exists() else ""
    existing = set(re.findall(r"^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=", text, flags=re.M))
    missing = {k: v for k, v in values.items() if k not in existing}
    if missing:
        block = f"\n# ── {title} " + "─" * max(4, 74 - len(title)) + "\n"
        block += "".join(f"{k}={v}\n" for k, v in missing.items())
        env_path.write_text(text.rstrip("\n") + "\n" + block if text else block.lstrip("\n"))
    return list(missing)


def make_service(service_name, service_type, provider, vector_store="chroma"):
    if not re.fullmatch(r"[A-Za-z][A-Za-z0-9]*", service_name):
        click.echo(click.style(
            f"✗ Invalid service name '{service_name}': use letters and digits only, e.g. Support or DocReader.", fg="red"
        ))
        raise SystemExit(1)
    service_name = service_name[0].upper() + service_name[1:]

    details = f"type: {service_type}, provider: {provider}" + (f", vector store: {vector_store}" if service_type == "rag" else "")
    click.echo(click.style(f"\n⚡ FastForge — make:service {service_name} ({details})\n", fg="cyan", bold=True))

    project_root, project_name = resolve_package_or_exit()
    base = project_root / "src" / project_name

    db_file = base / "data" / "database.py"
    has_sql = db_file.exists() and "sessionmaker" in db_file.read_text()

    ctx = {
        "project_name": project_name,
        "service_name": service_name,
        "service_name_lower": service_name.lower(),
        "service_name_upper": service_name.upper(),
        "provider": provider,
        "service_type": service_type,
        "vector_store": vector_store,
        "has_sql": has_sql,
    }

    # 1. Service and router
    write(base / "service" / f"{service_name.lower()}.py", render(f"{service_type}.py.j2", ctx))
    write(base / "router" / f"r_{service_name.lower()}.py", render("r_service.py.j2", ctx))

    # 2. Register the router in app/main.py
    main_py_path = project_root / "app" / "main.py"
    if main_py_path.exists():
        content = main_py_path.read_text()
        import_statement = f"from {project_name}.router.r_{service_name.lower()} import r_{service_name.lower()}"
        include_statement = f"app.include_router(r_{service_name.lower()})"

        if include_statement not in content:
            lines = content.rstrip('\n').split('\n')
            last_import_idx = 0
            for i, line in enumerate(lines):
                if line.startswith("import ") or line.startswith("from "):
                    last_import_idx = i

            lines.insert(last_import_idx + 1, import_statement)
            lines.append(include_statement)

            main_py_path.write_text('\n'.join(lines).rstrip('\n') + '\n')
            click.echo(click.style(f"  {'updated':>10}  {main_py_path} (added router)", fg="blue"))

    # 3. Dependencies and settings
    deps = service_dependencies(service_type, provider, vector_store)
    pyproject = project_root / "pyproject.toml"
    if pyproject.exists():
        merge_pyproject_deps_and_scripts(pyproject, deps)
        click.echo(click.style(f"  {'updated':>10}  {pyproject} (dependencies)", fg="blue"))

    env_path = project_root / ".env"
    added = merge_env(env_path, service_env(service_name, service_type, provider, vector_store, has_sql),
                      f"{service_name} ({service_type}, {provider})")
    if added:
        click.echo(click.style(f"  {'updated':>10}  {env_path} ({', '.join(added)})", fg="blue"))

    click.echo(click.style(f"\n✔ Service '{service_name}' generated!\n", fg="green", bold=True))
    click.echo("  Next steps:")
    click.echo("    uv sync                      # install the new dependencies" if pyproject.exists()
               else f"    uv add {' '.join(repr(d) for d in deps)}")
    click.echo("    fill in the API keys in .env")
    route = f"/{service_name.lower()}"
    if service_type == "ocr":
        click.echo(f"    POST {route}  (multipart form, field 'file': image or PDF)")
    else:
        click.echo(f"    POST {route}  {{\"query\": \"...\", \"session_id\": null}}")
    if service_type == "rag":
        click.echo(f"    POST {route}/ingest  [{{\"id\": \"doc-1\", \"text\": \"...\", \"metadata\": {{}}}}]")
        if has_sql:
            click.echo(f"    POST {route}/refresh  (indexes {service_name.upper()}_SOURCE_QUERY)")
    click.echo("    All routes need a JWT: Authorization: Bearer <token>\n")
