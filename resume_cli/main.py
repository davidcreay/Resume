import typer
from pathlib import Path
from . import converters

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
def import_linkedin(
        csv_path: Path = typer.Argument(..., help="Path to LinkedIn Experience.csv"),
        output_path: Path = typer.Option("resume.yaml", "--output", "-o")
):
    """Import LinkedIn CSV and save as JSON Resume YAML."""
    data = converters.linkedin_csv_to_dict(csv_path)
    with open(output_path, 'w') as f:
        import yaml
        yaml.dump(data, f, sort_keys=False)
    typer.echo(f"Imported {len(data['work'])} roles to {output_path}")


def main():
    app()

if __name__ == "__main__":
    main()