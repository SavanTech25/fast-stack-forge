import click
from fast_stack_forge.utils import render as render_template, resolve_package_or_exit, write as _write


def render(template_name, context):
    return render_template("dashboard", template_name, context)


def write(path, content):
    _write(path, content, overwrite=False)


def make_dashboard(pages):
    click.echo(click.style(f"\n⚡ FastForge — make:dashboard\n", fg="cyan", bold=True))

    project_root, project_name = resolve_package_or_exit(exclude_suffix="_etl")
    # The dbt project shown in the Atelier page: any src/ folder with a dbt_project.yml, else <name>_etl
    src_dir = project_root / "src"
    dbt_dirs = sorted(d.name for d in src_dir.iterdir() if (d / "dbt_project.yml").exists() or d.name.endswith("_etl"))
    etl_name = dbt_dirs[0] if dbt_dirs else f"{project_name}_etl"

    # Process pages
    # Default icons and descriptions
    defaults = {
        "Atelier": {"icon": "🏗️", "desc": "Manage entities, services and dbt models."},
        "Analytics": {"icon": "📊", "desc": "Data insights and KPIs."},
        "Chatbot": {"icon": "🤖", "desc": "Chat with your knowledge base."},
    }

    page_configs = []
    
    # Always ensure Atelier is there if requested or by default
    if not pages:
        pages = ["Atelier"]
    
    # Create the pages list for the home page cards
    for i, page_name in enumerate(pages):
        # Normalize name for file
        clean_name = page_name.replace(" ", "_")
        conf = defaults.get(page_name, {"icon": "📄", "desc": f"Custom page for {page_name}"})
        
        page_configs.append({
            "name": clean_name,
            "title": page_name,
            "filename": f"{i+1}_{conf['icon']}_{page_name}.py",
            "icon": conf["icon"],
            "description": conf["desc"]
        })

    ctx = {
        "project_name": project_name,
        "etl_name": etl_name,
        "pages": page_configs
    }

    dashboard_dir = project_root / "app" / "dashboard"
    pages_dir = dashboard_dir / "pages"

    # 1. Write Accueil.py
    write(dashboard_dir / "Accueil.py", render("Accueil.py.j2", ctx))

    # 2. Write each page
    for p in page_configs:
        page_file = pages_dir / p["filename"]
        if p["title"].lower() == "atelier":
            write(page_file, render("pages/atelier.py.j2", ctx))
        else:
            write(page_file, render("pages/blank.py.j2", {"page": p}))

    # 3. Update Makefile
    makefile_path = project_root / "Makefile"
    if makefile_path.exists():
        content = makefile_path.read_text()
        if "dashboard:" not in content:
            new_target = "\ndashboard:\n\tcd app/dashboard && uv run streamlit run Accueil.py\n"
            if ".PHONY:" in content:
                lines = content.split('\n')
                for i, line in enumerate(lines):
                    if line.startswith(".PHONY:"):
                        if "dashboard" not in line:
                            lines[i] = line + " dashboard"
                        break
                content = '\n'.join(lines)
            
            content += new_target
            makefile_path.write_text(content)
            click.echo(click.style(f"  {'updated':>10}  {makefile_path} (added dashboard target)", fg="blue"))

    click.echo(click.style(f"\n✔ Dashboard generated with {len(pages)} pages!\n", fg="green", bold=True))
    click.echo(click.style("  To start it:", fg="yellow"))
    click.echo("    make dashboard\n")
