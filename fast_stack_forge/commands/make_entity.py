import click
from fast_stack_forge.parser import parse_fields
from fast_stack_forge.utils import render as render_template, resolve_package_or_exit, write as _write


def render(template_name, context):
    return render_template("entity", template_name, context)


def write(path, content):
    _write(path, content, overwrite=False)


def sqlalchemy_imports(fields) -> list[str]:
    names = {"Column", "Integer"}
    for f in fields:
        if f.foreign_key:
            names.add("ForeignKey")
        elif f.encrypt or f.hash:
            names.add("Text")
        else:
            names.add(f.sqlalchemy_type.split("(")[0])
    return sorted(names)


def make_entity(entity_name, raw_fields, no_router=False, no_controller=False):
    click.echo(click.style(f"\n⚡ FastForge — make:entity {entity_name}\n", fg="cyan", bold=True))
    try:
        fields = parse_fields(raw_fields)
    except ValueError as e:
        click.echo(click.style(f"✗ {e}", fg="red"))
        raise SystemExit(1)

    project_root, project_name = resolve_package_or_exit()
    base = project_root / "src" / project_name

    db_type = "sql"
    db_file = base / "data" / "database.py"
    if db_file.exists():
        db_content = db_file.read_text()
        if "connect_to_mongo" in db_content or "motor" in db_content:
            db_type = "mongodb"

    table_name = entity_name.lower() if entity_name.lower().endswith("s") else entity_name.lower() + "s"

    ctx = {
        "project_name": project_name,
        "db_type": db_type,
        "entity_name": entity_name,
        "entity_name_lower": entity_name.lower(),
        "table_name": table_name,
        "fields": fields,
        "has_date": any(f.type == "date" for f in fields),
        "has_datetime": any(f.type == "datetime" for f in fields),
        "has_encrypt": any(f.encrypt for f in fields),
        "has_hash": any(f.hash for f in fields),
        "has_fk": any(f.foreign_key for f in fields),
        "sa_imports": sqlalchemy_imports(fields),
    }
    
    write(base / "entity" / f"{entity_name.lower()}.py", render("model.py.j2", ctx))
    write(base / "schema" / f"{entity_name.lower()}.py", render("schema.py.j2", ctx))
    if not no_controller:
        write(base / "controller" / f"{entity_name.lower()}.py", render("controller.py.j2", ctx))
    if not no_router:
        write(base / "router" / f"r_{entity_name.lower()}.py", render("router.py.j2", ctx))
        
        main_py_path = project_root / "app" / "main.py"
        if main_py_path.exists():
            content = main_py_path.read_text()
            import_statement = f"from {project_name}.router.r_{entity_name.lower()} import r_{entity_name.lower()}"
            include_statement = f"app.include_router(r_{entity_name.lower()})"
            
            if include_statement not in content:
                lines = content.rstrip('\n').split('\n')
                last_import_idx = 0
                for i, line in enumerate(lines):
                    if line.startswith("import ") or line.startswith("from "):
                        last_import_idx = i
                
                lines.insert(last_import_idx + 1, import_statement)
                lines.append(include_statement)
                
                main_py_path.write_text('\n'.join(lines) + '\n')
                click.echo(click.style(f"  {'updated':>10}  {main_py_path} (added router)", fg="blue"))

    click.echo(click.style(f"\n✔ Entity '{entity_name}' generated!\n", fg="green", bold=True))
    if ctx["has_encrypt"]:
        click.echo(click.style("  ⚠ Champ encrypt détecté — génère ta FERNET_KEY dans .env :", fg="yellow"))
        click.echo('    python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"')
        click.echo()
    for method, path in [("GET",f"/{table_name}"),("GET",f"/{table_name}/{{id}}"),("POST",f"/{table_name}"),("PATCH",f"/{table_name}/{{id}}"),("DELETE",f"/{table_name}/{{id}}")]:
        click.echo(f"    {method:<8} {path}")
    click.echo()
