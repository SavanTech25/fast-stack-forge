# ⚡ fast-stack-forge

[![PyPI version](https://badge.fury.io/py/fast-stack-forge.svg)](https://badge.fury.io/py/fast-stack-forge)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

fast-stack-forge is a Symfony-style CLI scaffolder: answer a few questions and get a ready-to-run project, managed with `uv`.
It covers FastAPI backends, **dbt** projects, **Databricks** Asset Bundles, AI services and data science projects.

## ✨ Features

- **Interactive wizard**: `fast-stack-forge new` asks what you want to build, then a few simple questions. Every question also has a flag, and `--yes` takes the defaults (CI friendly).
- **Rapid Scaffolding**: Generate full FastAPI projects with a single command.
- **Entity Generation**: Automatically create models, schemas, controllers, and routers for your database entities.
- **AI Service Integration**: Scaffold RAG, agent, agentic (LangGraph) and OCR services for OpenAI, Anthropic, Mistral, Gemini and Azure OpenAI, with dependencies and settings wired in.
- **dbt projects**: DuckDB, Postgres, Snowflake, BigQuery or Databricks; 3 architectures; example seeds, models, tests and snapshot that `dbt build` out of the box.
- **Databricks projects**: Asset Bundle with dev/prod targets, Unity Catalog schema, a daily job (Python wheel, notebook, Lakeflow/DLT pipeline, dbt), serverless or classic compute, local tests with Databricks Connect.
- **Data Sync**: Generate ELT scripts to sync NoSQL databases (like MongoDB) to relational databases (like PostgreSQL).
- **Production-Ready**: Includes pre-configured JWT middleware, rate limiting (slowapi), background scheduling (apscheduler), and WebSockets.

## 🚀 Installation

Since FastForge manages virtual environments and dependencies via `uv`, you should install it globally using `uv tool`:

```bash
uv tool install fast-stack-forge
```

*(Alternatively, you can install from source: `uv tool install git+https://github.com/SavanTech25/fast-stack-forge.git`)*

## 🛠️ Usage

### 0. Quick start: the wizard

```bash
fast-stack-forge new
```

```text
What do you want to create?
  [1] fastapi  FastAPI backend (entities, JWT, rate limiting, scheduler)
  [2] dbt  dbt project (DuckDB, Postgres, Snowflake, BigQuery, Databricks)
  [3] databricks  Databricks Asset Bundle (jobs, notebooks, pipelines, dbt)
  [4] ds  Data science project (notebooks, Streamlit, optional FastAPI)
Choice [1]:
```

Every `init*` command works the same way: options you don't pass on the command line are asked interactively.
Add `-y` / `--yes` to skip the questions and use the defaults.

### 1. Initialize a Project

To bootstrap a new project, use the `init` command. You can specify your preferred database engine (`sqlite`, `postgresql`, `mysql`, or `mongodb`), or leave it out to be asked.

```bash
fast-stack-forge init my_project --db mongodb
```

This will create a structured FastAPI project that utilizes `pyproject.toml` and a `Makefile` for streamlined development.

### 2. Run the Scaffolded Project

Navigate into your generated project and install dependencies:

```bash
cd my_project
make install
source .venv/bin/activate
```

Start the development server:

```bash
make run
```

### 3. Generate Entities (Models, Schemas, Controllers, Routers)

FastForge features a `make:entity` command that automatically generates your boilerplate code for a given entity. Make sure you run this from the root of your newly created project!

```bash
fast-stack-forge make:entity User name:string age:int email:string:hash is_active:bool
```

**Field Syntax:** `name:type[:modifier]`
- **Types:** `string`, `int`, `float`, `bool`, `text`, `date`, `datetime`
- **Modifiers:** `encrypt`, `hash`, `nullable`, `fk=ModelName`

### 4. dbt projects

```bash
fast-stack-forge init:dbt                      # asks: name, architecture, adapter, examples, Python version
fast-stack-forge init:dbt analytics --archi medallion --adapter duckdb -y
cd analytics && make install && make build
```

- **`--archi`**: `default` (staging → intermediate → marts), `medallion` (bronze → silver → gold) or `star` (staging → dim → fact).
- **`--adapter`**: `duckdb` (local, zero setup), `postgres`, `snowflake`, `bigquery` or `databricks`.
- **`--examples/--no-examples`**: example seeds, models, tests (incl. `dbt_utils`), a snapshot and an exposure.
- **`--python-model`**: a dbt Python model example (DuckDB, Snowflake, Databricks).

The project comes with a `pyproject.toml` (uv), a `Makefile` (`make help`), a `profiles.yml` that reads its secrets from environment variables, and a `.env.example`.
Run inside an existing FastForge project, the dbt project goes into `src/<name>/` and its dependencies are merged into the root `pyproject.toml`.
(`init:etl` still works as an alias.)

Add a model from anywhere inside the project:

```bash
fast-stack-forge make:dbt fct_user --layer gold --incremental
fast-stack-forge make:dbt py_scores --layer gold --python
```

### 4b. Databricks projects

```bash
fast-stack-forge init:databricks               # asks: name, workspace URL, catalog, compute, runtime, components
fast-stack-forge init:databricks lakehouse --host https://adb-123.azuredatabricks.net \
    --compute serverless --runtime 17.3 --with wheel --with pipeline --with dbt -y
```

Generates a [Databricks Asset Bundle](https://docs.databricks.com/dev-tools/bundles/):

```text
lakehouse/
├── databricks.yml              <-- dev (default) and prod targets, catalog/schema variables
├── resources/
│   ├── schema.yml              <-- Unity Catalog schema
│   ├── lakehouse_pipeline.yml  <-- Lakeflow Declarative Pipeline (--with pipeline)
│   └── lakehouse_job.yml       <-- daily job: ingest → refresh_pipeline → transform → dbt
├── src/
│   ├── notebooks/ingest.py     <-- (--with notebook)
│   ├── pipelines/              <-- bronze/silver/gold DLT tables
│   └── lakehouse/main.py       <-- Python package built as a wheel (--with wheel)
├── dbt_project/                <-- dbt-databricks project (--with dbt)
├── tests/                      <-- pytest through Databricks Connect
├── pyproject.toml  Makefile  .env.example
```

- **`--compute`**: `serverless` (no cluster to manage) or `classic` (job cluster, with `--cloud aws|azure|gcp`).
- **`--runtime`**: `17.3`, `16.4` or `15.4` LTS. Sets the local Python and Databricks Connect versions.
- **`--with`**: `wheel`, `notebook`, `pipeline`, `dbt` (repeatable).

```bash
cd lakehouse
make login     # databricks auth login
make install   # uv sync
make deploy    # databricks bundle deploy -t dev
make run       # databricks bundle run lakehouse_job
```

### 5. Generate AI Services

`make:service` scaffolds an AI service and its JWT-protected router, adds the dependencies to `pyproject.toml` and the settings to `.env`. Run it without options to answer the questions.

```bash
fast-stack-forge make:service HelpdeskBot --type rag --provider anthropic --vector-store qdrant
uv sync            # install the new dependencies, then fill in the API keys in .env
```

| `--type` | What you get | Endpoints |
|---|---|---|
| `rag` | Answers from your documents: chunking, vector search, sources in the answer | `POST /<name>` `{"query"}`, `POST /<name>/ingest` (list of `{"id", "text", "metadata"}`), `POST /<name>/refresh` (SQL projects: indexes `<NAME>_SOURCE_QUERY`) |
| `agent` | Tool-calling agent (LangChain `create_agent`) with per-session memory | `POST /<name>` `{"query", "session_id"}` |
| `agentic` | Explicit LangGraph workflow (LLM ↔ tools loop) to extend with your own nodes | `POST /<name>` `{"query", "session_id"}` |
| `ocr` | Text extraction from an uploaded image or PDF, returned as Markdown | `POST /<name>` (multipart, field `file`) |

- **`--provider`**: `openai`, `anthropic`, `mistral`, `gemini` or `azure` (Azure OpenAI deployments). Models are set in `.env` (`OPENAI_MODEL`, `ANTHROPIC_MODEL`, ... ) with current defaults, so you can change them without touching the code.
- **`--vector-store`** (RAG only): `chroma` (local folder), `qdrant` (collection created automatically), `supabase` (Postgres + pgvector) or `upstash`.
- Anthropic has no embeddings API: Anthropic RAG services use [Voyage AI](https://www.voyageai.com/) embeddings (`VOYAGE_API_KEY`).
- Agent memory is in-process (`InMemorySaver`): use a persistent LangGraph checkpointer when you run several workers.

### 6. Generate Data Sync Scripts (ELT)

To support the standard dbt architecture (where your operational database needs to be replicated to your analytical database), you can use the `make:sync` command.

```bash
fast-stack-forge make:sync MongoToPg --source mongodb --dest postgres
```
This scaffolds a pure-Python sync script utilizing `pymongo`, `pandas`, and `sqlalchemy`. The generated script handles flattening NoSQL documents and automatically syncing them to PostgreSQL, with built-in `APScheduler` boilerplate for continuous execution.

## 🏗️ Architecture

When you initialize a project with FastForge, it generates a clean, modular structure. 

### Generated Directory Structure

*(Note: PyPI does not support Mermaid diagrams natively, so here is the ASCII representation of the architecture)*

```text
my_project/
├── Makefile
├── pyproject.toml
├── README.md
├── app/
│   └── main.py          <-- FastAPI entry point, imports db & limiter
└── src/
    └── my_project/
        ├── controller/  <-- Business logic
        ├── data/        <-- database.py
        ├── entity/      <-- ORM Models
        ├── middleware/  <-- middleware.py (JWTBearer)
        ├── router/      <-- API Routes
        ├── schema/      <-- Pydantic Models
        ├── service/     <-- Generated AI Services
        └── utils/
            ├── connection_manager.py
            ├── crud_router.py
            ├── limiter.py
            └── scheduling.py
```

### Explanation of Components

- **`app/main.py`**: The main FastAPI entry point. It handles lifecycle events (connecting to the database, starting schedulers) and attaches rate limiters.
- **`src/{project_name}/`**: Your primary application package, automatically recognized by `pyproject.toml` and `uv`.
  - **`entity/`**: Database models (SQLAlchemy or motor/MongoDB depending on your `init` choice).
  - **`schema/`**: Pydantic models for validation and serialization.
  - **`controller/`**: Business logic and database interaction functions.
  - **`router/`**: API route definitions, connected to your controllers.
  - **`data/`**: Database configuration and connection setup.
  - **`middleware/`**: Contains pre-configured `JWTBearer` middleware for instant authentication handling.
  - **`utils/`**:
    - `limiter.py`: Pre-configured `slowapi` rate limiting.
    - `scheduling.py`: Asynchronous background task scheduler via `apscheduler`.
    - `connection_manager.py`: Generic WebSocket manager.
    - `crud_router.py`: A generic factory for building standard CRUD routes effortlessly.

## 🤝 Contributing
Contributions are welcome! Feel free to open an issue or submit a pull request if you have ideas for new features or improvements.

## 📄 License
This project is licensed under the MIT License.
