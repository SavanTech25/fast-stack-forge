import click
from fast_stack_forge.utils import render as render_template, resolve_package_or_exit, write as _write


def render(template_name, context):
    return render_template("sync", template_name, context)


def write(path, content):
    _write(path, content, overwrite=False)


def make_sync(sync_name, source, dest):
    click.echo(click.style(f"\n⚡ FastForge — make:sync {sync_name} (source: {source}, dest: {dest})\n", fg="cyan", bold=True))

    project_root, project_name = resolve_package_or_exit()
    base = project_root / "src" / project_name
    
    ctx = {
        "project_name": project_name,
        "sync_name": sync_name,
        "sync_name_lower": sync_name.lower(),
        "source": source,
        "dest": dest
    }
    
    sync_file = base / "sync" / f"{sync_name.lower()}.py"
    write(sync_file, render("sync_python.py.j2", ctx))
    
    # Generate requirements.txt
    req_file = base / "sync" / "requirements.txt"
    req_content = "pymongo\npandas\nsqlalchemy\npsycopg2-binary\napscheduler\npython-decouple\nloguru\n"
    write(req_file, req_content)
    
    click.echo(click.style(f"\n✔ Python Sync Script '{sync_name}' generated!\n", fg="green", bold=True))
    click.echo(click.style("  ⚠ Remember to install the required dependencies:", fg="yellow"))
    click.echo(f"    cd src/{project_name}/sync && uv pip install -r requirements.txt\n")
