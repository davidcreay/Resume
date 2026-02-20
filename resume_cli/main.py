import shutil
from datetime import datetime
from pathlib import Path

import typer
import yaml

from . import converters
from .latex.render import render_latex, compile_latex

app = typer.Typer(help="JSON Resume CLI Tool")


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


@app.command()
def render(
        profile: Path = typer.Option("resume.yaml", "--profile", "-p"),
        template_name: str = typer.Option("onepage", "--template", "-t"),
        style_name: str = typer.Option("enhancv", "--style", "-s"),
        output_dir: Path = typer.Option("build", "--outdir", "-d"),
        export_dir: Path = typer.Option("exports", "--export-dir", "-e"),
        name: str = typer.Option("default", "--name", "-n"),
):
    """Renders the resume, compiles it, and exports a timestamped PDF."""
    base_path = Path(__file__).parent
    template_folder = base_path / "templates" / template_name
    styles_folder = base_path / "styles" / style_name

    # 1. Setup Directories
    final_output_dir = output_dir / name
    final_output_dir.mkdir(parents=True, exist_ok=True)
    export_dir.mkdir(parents=True, exist_ok=True)

    # 2. Copy Template Assets
    if not template_folder.exists():
        typer.echo(f"❌ Template folder not found: {template_folder}")
        raise typer.Exit(1)

    for item in template_folder.iterdir():
        if item.name == "resume.tex.j2":
            continue
        dest = final_output_dir / item.name
        if item.is_dir():
            if dest.exists(): shutil.rmtree(dest)
            shutil.copytree(item, dest)
        else:
            shutil.copy2(item, dest)

    # 3. Copy Entire Style Directory (including fonts, schema, and .cls)
    if styles_folder.exists() and styles_folder.is_dir():
        # Copy everything from the style folder into the final output dir
        # dirs_exist_ok=True allows us to merge into the build folder
        shutil.copytree(styles_folder, final_output_dir, dirs_exist_ok=True)
        typer.echo(f"🎨 Style assets for '{style_name}' copied successfully.")
    else:
        typer.echo(f"❌ Style folder not found: {styles_folder}")
        raise typer.Exit(1)

    # 4. Load Data & Render .tex
    with open(profile, "r") as f:
        profile_data = yaml.safe_load(f)

    tex_file_path = final_output_dir / f"{name}.tex"
    try:
        render_latex(
            profile_data=profile_data,
            template_path=template_folder / "resume.tex.j2",
            output_path=tex_file_path,
            style_name=style_name,
        )
    except Exception as e:
        typer.echo(f"❌ Render failed: {e}")
        raise typer.Exit(1)

    # 5. Build PDF
    typer.echo(f"🔨 Building PDF for {name}...")
    try:
        compile_latex(tex_file_path, final_output_dir)

        # 6. Export with Timestamp
        timestamp = datetime.now().strftime("%Y%m%d")
        source_pdf = final_output_dir / f"{name}.pdf"
        export_pdf_name = f"{name}_{timestamp}.pdf"
        export_path = export_dir / export_pdf_name

        shutil.copy2(source_pdf, export_path)
        typer.echo(f"🚀 Success! PDF exported to: {export_path}")

    except Exception as e:
        typer.echo(f"❌ Build failed: {e}")
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