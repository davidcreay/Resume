import subprocess
from datetime import datetime
from pathlib import Path

import typer

from .helpers import get_jinja_env, escape_for_latex


def transform_enhancv(safe_data):
    """Adapter for the enhancv/altacv style requirements."""

    # 1. Handle achievements icons (reverse backslash escaping)
    achievements = safe_data.get("achievements", [])
    for ach in achievements:
        if "icon" in ach:
            ach["icon"] = ach["icon"].replace(r'\textbackslash{}', '\\')

    # 2. Extract LinkedIn username specifically
    profiles = safe_data.get("basics", {}).get("profiles", [])
    linkedin_user = next(
        (p.get("username", "") for p in profiles if p.get("network", "").lower() == "linkedin"),
        ""
    )

    # 3. Handle Skills (Map the 'all' group to a flat list for \cvtaga)
    skills_data = safe_data.get("skills", [])
    all_skills_list = next(
        (s.get("keywords", []) for s in skills_data if s.get("name").lower() == "all"),
        []
    )

    # 4. Map the final context dictionary
    return {
        "basics": {
            **safe_data.get("basics", {}),
            "linkedin": linkedin_user,
            # Ensure post_nominals exists to prevent Jinja2 errors
            "post_nominals": safe_data.get("basics", {}).get("post_nominals", "")
        },
        "skills": all_skills_list,
        "achievements": achievements,
        "education": safe_data.get("education", []),
        "work": safe_data.get("work", []),
        "languages": safe_data.get("languages", []),
        "interests": safe_data.get("interests", []),
        "certifications": safe_data.get("certificates", []),
        "projects": safe_data.get("projects", []),
        "volunteer": safe_data.get("volunteer", []),
    }

# Registry for style transformations
STYLE_TRANSFORMERS = {
    "enhancv": transform_enhancv,
}

def prepare_render_context(profile_data, style_name, graphics=True, swap_columns=False):
    """Orchestrates data transformation based on the selected style."""
    # 1. Global LaTeX escaping
    safe_data = escape_for_latex(profile_data)

    # 2. Dispatch to the style-specific transformer
    # This identifies if we use enhancv, hipster, etc.
    transformer = STYLE_TRANSFORMERS.get(style_name, lambda x: x)
    style_context = transformer(safe_data)

    # 3. Create the 'settings' object for the template
    settings = {
        "style": style_name,
        "graphics": graphics
    }

    # 4. Final merge including 'settings'
    return {
        "today": datetime.now(),
        "swap_columns": swap_columns,
        "settings": settings,  # This fixes the 'undefined' error
        **style_context
    }


def render_latex(profile_data, template_path: Path, output_path: Path, style_name="enhancv", **kwargs):
    """The clean, style-agnostic entry point for rendering."""
    env = get_jinja_env(template_path.parent)
    template = env.get_template(template_path.name)

    # Build the context specifically for the chosen style
    context = prepare_render_context(profile_data, style_name, **kwargs)

    tex = template.render(context)
    output_path.write_text(tex)


def compile_latex(tex_file: Path, working_dir: Path):
    """Compiles the LaTeX file using xelatex."""
    job_name = tex_file.stem
    command = ["xelatex", "-interaction=nonstopmode", f"-jobname={job_name}", tex_file.name]

    try:
        typer.echo(f"🏃 Running xelatex (Pass 1)...")
        subprocess.run(command, cwd=working_dir, check=True, capture_output=True, text=True)
        typer.echo(f"🏃 Running xelatex (Pass 2)...")
        subprocess.run(command, cwd=working_dir, check=True, capture_output=True, text=True)
    except subprocess.CalledProcessError as e:
        log_file = working_dir / f"{job_name}.log"
        typer.echo(f"❌ xelatex failed. Checking {log_file.name}...")
        if log_file.exists():
            log_content = log_file.read_text(errors='replace')
            errors = [line for line in log_content.splitlines() if line.startswith('!')]
            for err in errors[:5]:
                typer.echo(f"  {err}")
        raise e