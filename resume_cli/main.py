import shutil
from datetime import datetime
from pathlib import Path

import typer
import yaml

from . import converters
from .job_reader import read_job_text
from .latex.render import render_latex, compile_latex
from .llm_tailor import (
    enforce_schema_max_items,
    load_schema,
    load_limits,
    tailor_with_bedrock,
    tailor_with_openai,
    validate_and_trim,
)

app = typer.Typer(help="JSON Resume CLI Tool")

# Layouts built when --layout is omitted (style + layout model)
LAYOUTS = ("onepage", "twopage", "full")


def _resolve_template_name(style_name: str, layout: str) -> str:
    """Resolve template folder name from style and layout. For enhancv, use unified template for all layouts."""
    if style_name == "standard" and layout == "onepage":
        return "standard"
    if style_name == "enhancv":
        return "enhancv"
    return layout


@app.command()
def convert(
        input_file: Path = typer.Argument(..., help="Path to the source file"),
        output_file: Path = typer.Argument(..., help="Path to save the result"),
):
    """Convert between JSON and YAML based on file extensions."""
    if input_file.suffix == '.yaml' and output_file.suffix == '.json':
        result = converters.yaml_to_json(input_file)
    elif input_file.suffix == '.json' and output_file.suffix == '.yaml':
        result = converters.json_to_yaml(input_file)
    else:
        typer.echo("Extension mismatch. Support: .json <-> .yaml")
        raise typer.Exit(1)

    output_file.write_text(result)
    typer.echo(f"Successfully converted {input_file} to {output_file}")


def _run_render(
    profile: Path,
    template_name: str,
    style_name: str,
    layout: str,
    output_dir: Path,
    export_dir: Path,
    name: str,
) -> None:
    """Shared render logic: copy template/style, trim profile by layout, render LaTeX, compile PDF, export."""
    base_path = Path(__file__).parent
    template_folder = base_path / "templates" / template_name
    styles_folder = base_path / "styles" / style_name

    final_output_dir = output_dir / name
    final_output_dir.mkdir(parents=True, exist_ok=True)
    export_dir.mkdir(parents=True, exist_ok=True)

    if not template_folder.exists():
        raise FileNotFoundError(f"Template folder not found: {template_folder}")
    for item in template_folder.iterdir():
        if item.name == "resume.tex.j2":
            continue
        dest = final_output_dir / item.name
        if item.is_dir():
            if dest.exists():
                shutil.rmtree(dest)
            shutil.copytree(item, dest)
        else:
            shutil.copy2(item, dest)

    if not styles_folder.exists() or not styles_folder.is_dir():
        raise FileNotFoundError(f"Style folder not found: {styles_folder}")
    shutil.copytree(styles_folder, final_output_dir, dirs_exist_ok=True)
    typer.echo(f"🎨 Style assets for '{style_name}' copied successfully.")

    with open(profile, "r", encoding="utf-8") as f:
        profile_data = yaml.safe_load(f)

    limits = None
    if style_name == "enhancv" and layout:
        limits_path = base_path / "schemas" / "enhancv_limits.yaml"
        if limits_path.exists():
            limits = load_limits(limits_path, layout) or {}
        if layout in ("onepage", "twopage") and limits:
            schema_path = base_path / "schemas" / "enhancv.json"
            if schema_path.exists():
                schema = load_schema(schema_path)
                profile_data = enforce_schema_max_items(profile_data, schema, limits=limits)

    tex_file_path = final_output_dir / f"{name}.tex"
    render_latex(
        profile_data=profile_data,
        template_path=template_folder / "resume.tex.j2",
        output_path=tex_file_path,
        style_name=style_name,
        template_name=template_name,
        layout=layout,
        limits=limits,
    )
    typer.echo(f"🔨 Building PDF for {name}...")
    compile_latex(tex_file_path, final_output_dir)
    timestamp = datetime.now().strftime("%Y%m%d")
    source_pdf = final_output_dir / f"{name}.pdf"
    export_path = export_dir / f"{name}_{timestamp}.pdf"
    shutil.copy2(source_pdf, export_path)
    abs_export = export_path.resolve()
    abs_build = source_pdf.resolve()
    typer.echo(f"🚀 PDF exported to: {abs_export}")
    typer.echo(f"   (also in build: {abs_build})")


@app.command()
def render(
        profile: Path = typer.Option("resume.yaml", "--profile", "-p"),
        layout: str | None = typer.Option(
            None,
            "--layout", "-l",
            help="Layout: onepage, twopage, or full. Omit to build all layouts.",
        ),
        style_name: str = typer.Option("enhancv", "--style", "-s"),
        output_dir: Path = typer.Option("build", "--outdir", "-d"),
        export_dir: Path = typer.Option("exports", "--export-dir", "-e"),
        name: str = typer.Option("default", "--name", "-n"),
):
    """Renders the resume, compiles it, and exports a timestamped PDF. Omit --layout to build onepage, twopage, and full."""
    base_path = Path(__file__).parent

    # When name is default, use profile basics.name with spaces replaced by underscores
    if name == "default":
        try:
            with open(profile, "r", encoding="utf-8") as f:
                profile_data = yaml.safe_load(f)
            profile_name = (profile_data.get("basics") or {}).get("name")
            if profile_name and isinstance(profile_name, str):
                name = profile_name.replace(" ", "_").strip() or "default"
        except Exception:
            pass

    if layout is not None:
        layout = layout.lower()
        if layout not in LAYOUTS:
            typer.echo(f"❌ Layout must be one of: {', '.join(LAYOUTS)}")
            raise typer.Exit(1)
        layouts_to_build = [layout]
    else:
        layouts_to_build = list(LAYOUTS)

    for lay in layouts_to_build:
        template_name = _resolve_template_name(style_name, lay)
        template_folder = base_path / "templates" / template_name
        if not template_folder.exists():
            typer.echo(f"⏭️ Skipping {lay} (template {template_name} not found)")
            continue
        render_name = f"{name}_{lay}" if len(layouts_to_build) > 1 else name
        try:
            _run_render(profile, template_name, style_name, lay, output_dir, export_dir, render_name)
        except Exception as e:
            typer.echo(f"❌ {e}")
            raise typer.Exit(1)


@app.command()
def tailor(
    job_file: Path = typer.Argument(..., help="Path to job description (.txt, .pdf, or .docx)"),
    profile: Path = typer.Option("resume.yaml", "--profile", "-p", help="Source resume YAML"),
    output: Path = typer.Option(..., "--output", "-o", help="Path to write tailored resume YAML"),
    schema_path: Path = typer.Option(
        None,
        "--schema",
        help="JSON Schema path (optional; default: schemas/{style}.json)",
    ),
    layout: str | None = typer.Option(
        None,
        "--layout", "-l",
        help="Layout for limits: onepage, twopage, or full. Omit for no trimming (full).",
    ),
    provider: str = typer.Option("openai", "--provider", help="LLM provider: openai or bedrock"),
    render_after: bool = typer.Option(False, "--render", "-r", help="Run render and build PDF after tailoring"),
    style_name: str = typer.Option("enhancv", "--style"),
):
    """Tailor resume to a job description using an LLM. Schema and limits derived from --style and --layout."""
    base_path = Path(__file__).parent
    if schema_path is None:
        schema_path = base_path / "schemas" / f"{style_name}.json"
    else:
        schema_path = schema_path.resolve()
    if not schema_path.exists():
        typer.echo(f"❌ Schema not found: {schema_path}")
        raise typer.Exit(1)

    limits = None
    if layout is not None:
        layout = layout.lower()
        if layout not in LAYOUTS:
            typer.echo(f"❌ Layout must be one of: {', '.join(LAYOUTS)}")
            raise typer.Exit(1)
        limits_path = base_path / "schemas" / f"{style_name}_limits.yaml"
        if limits_path.exists():
            limits = load_limits(limits_path, layout)

    typer.echo("📄 Reading job description...")
    try:
        job_text = read_job_text(job_file)
    except Exception as e:
        typer.echo(f"❌ Failed to read job file: {e}")
        raise typer.Exit(1)

    typer.echo("📋 Loading profile and schema...")
    with open(profile, "r", encoding="utf-8") as f:
        profile_yaml = f.read()
    schema = load_schema(schema_path)

    typer.echo(f"🤖 Calling {provider}...")
    try:
        if provider.lower() == "openai":
            yaml_str = tailor_with_openai(job_text, profile_yaml, schema, limits=limits)
        elif provider.lower() == "bedrock":
            yaml_str = tailor_with_bedrock(job_text, profile_yaml, schema, limits=limits)
        else:
            typer.echo(f"❌ Unknown provider: {provider}. Use openai or bedrock.")
            raise typer.Exit(1)
    except Exception as e:
        typer.echo(f"❌ LLM call failed: {e}")
        raise typer.Exit(1)

    try:
        data, warnings = validate_and_trim(yaml_str, schema, limits=limits)
        for w in warnings:
            typer.echo(f"⚠️ {w}")
    except Exception as e:
        typer.echo(f"❌ Invalid YAML from LLM: {e}")
        raise typer.Exit(1)

    output.parent.mkdir(parents=True, exist_ok=True)
    with open(output, "w", encoding="utf-8") as f:
        yaml.dump(data, f, sort_keys=False, default_flow_style=False, allow_unicode=True)
    typer.echo(f"✅ Tailored resume written to: {output}")

    if render_after:
        typer.echo("🔨 Rendering PDF...")
        layout_to_render = layout if layout else "onepage"
        template_name = _resolve_template_name(style_name, layout_to_render)
        try:
            _run_render(
                profile=output,
                template_name=template_name,
                style_name=style_name,
                layout=layout_to_render,
                output_dir=Path("build"),
                export_dir=Path("exports"),
                name=output.stem,
            )
        except Exception as e:
            typer.echo(f"❌ Render failed: {e}")
            raise typer.Exit(1)


@app.command()
def import_linkedin(
        csv_path: Path = typer.Argument(..., help="Path to LinkedIn Experience.csv"),
        output_path: Path = typer.Option("resume.yaml", "--output", "-o")
):
    """Import LinkedIn CSV and save as JSON Resume YAML."""
    data = converters.linkedin_csv_to_dict(csv_path)
    with open(output_path, 'w') as f:
        yaml.dump(data, f, sort_keys=False)
    typer.echo(f"Imported {len(data['work'])} roles to {output_path}")


def main():
    app()


if __name__ == "__main__":
    main()