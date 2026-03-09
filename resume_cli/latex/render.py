import subprocess
from datetime import datetime
from pathlib import Path

import typer

from .helpers import get_jinja_env, escape_for_latex

MONTH_NAMES = [
    "", "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
]


def transform_enhancv(safe_data):
    """Adapter for the enhancv/altacv style requirements."""

    # 1. Handle achievements and interests icons (reverse backslash escaping for LaTeX)
    achievements = safe_data.get("achievements", [])
    for ach in achievements:
        if "icon" in ach:
            ach["icon"] = ach["icon"].replace(r'\textbackslash{}', '\\')
    interests = safe_data.get("interests", [])
    for item in interests:
        if "icon" in item:
            item["icon"] = item["icon"].replace(r'\textbackslash{}', '\\')

    # 2. Extract LinkedIn username specifically
    profiles = safe_data.get("basics", {}).get("profiles", [])
    linkedin_user = next(
        (p.get("username", "") for p in profiles if p.get("network", "").lower() == "linkedin"),
        ""
    )

    # 3. Handle Skills (Map the 'all' group to a flat list for \cvtaga)
    skills_data = safe_data.get("skills", [])
    all_skills_list = next(
        (s.get("keywords", []) for s in skills_data if (s.get("name") or "").lower() == "all"),
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


def _parse_iso_date(date_str):
    """Parse YYYY-MM-DD to {month, year} for standard template."""
    if not date_str:
        return {}
    try:
        parts = date_str.strip().split("-")
        year = parts[0] if len(parts) > 0 else ""
        month_num = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 0
        month = MONTH_NAMES[month_num] if 1 <= month_num <= 12 else ""
        return {"month": month, "year": year}
    except (IndexError, ValueError):
        return {"month": "", "year": str(date_str) if date_str else ""}


def _build_standard_context(style_context):
    """Build personal, experience, skill_groups, etc. for the standard template from JSON Resume / enhancv context."""
    basics = style_context.get("basics", {})
    profiles = basics.get("profiles", [])
    linkedin = next(
        (p.get("url", p.get("username", "")) for p in profiles if p.get("network", "").lower() == "linkedin"),
        "",
    )
    github = next(
        (p.get("url", p.get("username", "")) for p in profiles if p.get("network", "").lower() == "github"),
        "",
    )
    loc = basics.get("location", {})
    if isinstance(loc, dict):
        location_str = ", ".join(
            filter(None, [loc.get("city"), loc.get("region"), loc.get("countryCode") or loc.get("country")])
        )
    else:
        location_str = str(loc) if loc else ""

    # Flatten interests to a list of strings for personal.interests
    interests_raw = style_context.get("interests", [])
    interests_list = []
    for item in interests_raw:
        if isinstance(item, dict):
            name = item.get("name", "")
            keywords = item.get("keywords", [])
            if isinstance(keywords, str):
                kw_str = keywords
            else:
                kw_str = ", ".join(keywords) if keywords else ""
            if kw_str:
                interests_list.append(f"{name}: {kw_str}" if name else kw_str)
            elif name:
                interests_list.append(name)
        else:
            interests_list.append(str(item))

    personal = {
        "name": basics.get("name", ""),
        "title": basics.get("label", ""),
        "location": location_str,
        "email": basics.get("email", ""),
        "phone": basics.get("phone", ""),
        "linkedin": linkedin,
        "github": github,
        "summary": basics.get("summary", ""),
        "interests": interests_list,
    }

    # Map work -> experience (standard template shape)
    work = style_context.get("work", [])
    experience = []
    for w in work:
        start = _parse_iso_date(w.get("startDate", ""))
        end = _parse_iso_date(w.get("endDate", ""))
        experience.append({
            "company": w.get("name", ""),
            "position": w.get("position", ""),
            "employment_type": w.get("employmentType", "Full-time"),
            "start_date": start,
            "end_date": end,
            "current": False,
            "location": w.get("location", ""),
            "location_type": "Remote",
            "description": w.get("summary", ""),
            "achievements": w.get("highlights", []),
            "responsibilities": [],
            "skills": [],
            "logo": "",
        })

    # Map skills -> skill_groups (category + entries with label). Skip "all" so the
    # full technical skills blob is not shown at the top; only named groups are used.
    skills_data = style_context.get("skills", [])
    if isinstance(skills_data, list) and skills_data and isinstance(skills_data[0], dict):
        skill_groups = []
        for s in skills_data:
            name = s.get("name", "")
            keywords = s.get("keywords", [])
            if name.lower() == "all":
                continue  # Drop the full technical skills group from the top
            category = name
            entries = [{"label": kw, "yrs": ""} for kw in keywords]
            skill_groups.append({
                "category": category,
                "has_years": False,
                "entries": entries,
            })
    else:
        # Flat list of strings (e.g. from enhancv)
        skill_groups = [{
            "category": "Skills",
            "has_years": False,
            "entries": [{"label": kw, "yrs": ""} for kw in (skills_data or [])],
        }]

    # Map education to standard shape (degree, institution, year)
    education_raw = style_context.get("education", [])
    education_std = []
    for e in education_raw:
        start = e.get("startDate", "") or ""
        end = e.get("endDate", "") or ""
        year_str = f"{start[:4]} – {end[:4]}" if (start and end) else (start[:4] or end[:4] or "")
        education_std.append({
            "degree": f"{e.get('studyType', '')} {e.get('area', '')}".strip() or "—",
            "institution": e.get("institution", ""),
            "year": year_str,
        })

    # Map certificates -> certifications_and_training
    certs = style_context.get("certifications", style_context.get("certificates", []))
    certs_std = []
    for c in certs:
        date_str = c.get("date", "") or ""
        year = date_str[:4] if date_str else ""
        certs_std.append({
            "name": c.get("name", ""),
            "category": c.get("issuer", ""),
            "year": year,
            "credential_id": c.get("credential_id", ""),
        })

    return {
        "personal": personal,
        "experience": experience,
        "skill_groups": skill_groups,
        "education": education_std,
        "certifications_and_training": certs_std,
    }


def _merge_skills_from_experience(work, existing_skills, max_skills=None):
    """Merge skills from work + existing 'all', count occurrences, assign size tiers (tag cloud), cap by max_skills.
    Returns list of {"name": str, "size": "large"|"medium"|"small"} sorted by count desc."""
    # normalized -> (display_name, count); use first occurrence as display
    by_key = {}
    for s in existing_skills or []:
        raw = s if isinstance(s, str) else str(s)
        sn = (raw or "").strip().lower()
        if sn:
            if sn not in by_key:
                by_key[sn] = [raw, 0]
            by_key[sn][1] += 1
    for job in work or []:
        raw = job.get("skills")
        if raw is None:
            continue
        if isinstance(raw, str):
            raw = [raw]
        for s in raw:
            raw_s = s if isinstance(s, str) else str(s)
            sn = (raw_s or "").strip().lower()
            if sn:
                if sn not in by_key:
                    by_key[sn] = [raw_s, 0]
                by_key[sn][1] += 1
    # Sort by count descending; ties keep stable order
    ordered = sorted(by_key.values(), key=lambda x: (-x[1], x[0]))
    if max_skills is not None and max_skills > 0 and len(ordered) > max_skills:
        ordered = ordered[:max_skills]
    # Quantile-based size tiers: top 25% -> large, next 25% -> medium, rest -> small
    n = len(ordered)
    if n == 0:
        return []
    if n == 1:
        return [{"name": ordered[0][0], "size": "large"}]
    n_large = max(1, (n + 3) // 4)
    n_medium = (n + 3) // 4
    result = []
    for i, (display, _count) in enumerate(ordered):
        if i < n_large:
            size = "large"
        elif i < n_large + n_medium:
            size = "medium"
        else:
            size = "small"
        result.append({"name": display, "size": size})
    return result


def _build_achievements_from_work(work, max_achievements=None):
    """Build Key Achievements list from work entries' key_achievement (object or legacy string)."""
    result = []
    for job in work or []:
        ka = job.get("key_achievement")
        if ka is None:
            continue
        if isinstance(ka, dict):
            icon = (ka.get("icon") or "\\faStar").replace(r"\textbackslash{}", "\\")
            result.append({
                "icon": icon,
                "title": ka.get("title") or "",
                "description": ka.get("description") or "",
            })
        else:
            # Legacy: key_achievement is a string
            result.append({
                "icon": "\\faStar",
                "title": (job.get("position") or job.get("name") or "Achievement").strip(),
                "description": (ka if isinstance(ka, str) else str(ka)).strip(),
            })
    if max_achievements is not None and max_achievements > 0 and len(result) > max_achievements:
        result = result[:max_achievements]
    return result


def prepare_render_context(profile_data, style_name, template_name=None, layout=None, graphics=True, swap_columns=False, limits=None):
    """Orchestrates data transformation based on the selected style."""
    # 1. Global LaTeX escaping
    safe_data = escape_for_latex(profile_data)

    # 2. Dispatch to the style-specific transformer
    # This identifies if we use enhancv, hipster, etc.
    transformer = STYLE_TRANSFORMERS.get(style_name, lambda x: x)
    style_context = transformer(safe_data)

    # 2b. For enhancv: merge skills from experience (work) with existing "all" skills, dedupe, apply layout cap
    # 2c. For enhancv: build Key Achievements from work entries' key_achievement (icon, title, description)
    if style_name == "enhancv":
        work = style_context.get("work", [])
        existing = style_context.get("skills", [])
        skills_max = (limits or {}).get("skills") if limits else None
        style_context["skills"] = _merge_skills_from_experience(work, existing, max_skills=skills_max)
        achievements_max = (limits or {}).get("achievements") if limits else None
        style_context["achievements"] = _build_achievements_from_work(work, max_achievements=achievements_max)

    # 3. Create the 'settings' object for the template; add layout-derived flags for unified template
    settings = {
        "style": style_name,
        "graphics": graphics,
    }
    use_paracol = layout in ("onepage", "twopage", "full") if layout else True
    font_size = "8pt" if layout == "onepage" else ("9pt" if layout == "twopage" else "9pt")
    if layout == "full":
        font_size = "9pt"
    include_projects = layout in ("twopage", "full") if layout else True

    # 4. When using the standard template, add personal, experience, skill_groups, etc.
    context = {
        "today": datetime.now(),
        "swap_columns": swap_columns,
        "settings": settings,
        "layout": layout or "full",
        "use_paracol": use_paracol,
        "font_size": font_size,
        "include_projects": include_projects,
        **style_context
    }
    if template_name == "standard":
        context.update(_build_standard_context(context))
    return context


def render_latex(profile_data, template_path: Path, output_path: Path, style_name="enhancv", template_name=None, layout=None, limits=None, **kwargs):
    """The clean, style-agnostic entry point for rendering."""
    env = get_jinja_env(template_path.parent)
    template = env.get_template(template_path.name)
    if template_name is None and template_path.parent.name:
        template_name = template_path.parent.name

    # Build the context specifically for the chosen style and template
    context = prepare_render_context(profile_data, style_name, template_name=template_name, layout=layout, limits=limits, **kwargs)

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