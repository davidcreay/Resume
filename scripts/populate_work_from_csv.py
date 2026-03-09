#!/usr/bin/env python3
"""
Populate resume.yaml work section from exports/linkedin/Positions.csv.
Preserves LinkedIn content verbatim (no summarisation).
Run from repo root: python scripts/populate_work_from_csv.py
"""
import csv
import re
import sys
from pathlib import Path

MONTHS = {
    "Jan": "01", "Feb": "02", "Mar": "03", "Apr": "04", "May": "05", "Jun": "06",
    "Jul": "07", "Aug": "08", "Sep": "09", "Oct": "10", "Nov": "11", "Dec": "12",
}


def parse_date(s: str | None) -> str | None:
    """Parse 'Mon YYYY' (e.g. 'Apr 2024') to 'YYYY-MM-01'. Returns None if empty or 'Present'."""
    if not s or not str(s).strip():
        return None
    s = str(s).strip()
    if s.lower() == "present":
        return None
    parts = s.split()
    if not parts:
        return None
    month_key = parts[0][:3] if len(parts[0]) >= 3 else parts[0]
    month = MONTHS.get(month_key, "01")
    year = parts[-1] if parts else "2000"
    if not year.isdigit():
        return None
    return f"{year}-{month}-01"


def description_to_highlights(description: str) -> list[str]:
    """
    Derive highlights from description by splitting on double newline or double space.
    If a block is very long (> 400 chars), split on '. ' so each sentence is a highlight.
    No summarisation; same content as list items.
    """
    if not description or not description.strip():
        return []
    # Split on double newline or "  " (double space) into blocks
    blocks = re.split(r"\n\n+|  +", description)
    highlights = []
    for block in blocks:
        block = block.strip()
        if not block:
            continue
        if len(block) > 400:
            # Split long block into sentences
            for sent in re.split(r"\.\s+", block):
                sent = sent.strip()
                if sent:
                    if not sent.endswith("."):
                        sent += "."
                    highlights.append(sent)
        else:
            highlights.append(block)
    return highlights


def read_work_entries(csv_path: Path) -> list[dict]:
    """Read CSV and return list of work entry dicts for resume.yaml."""
    work = []
    with open(csv_path, "r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            company = (row.get("Company Name") or "").strip()
            title = (row.get("Title") or "").strip()
            description = (row.get("Description") or "").strip()
            location = (row.get("Location") or "").strip() or None
            started = parse_date(row.get("Started On"))
            finished = parse_date(row.get("Finished On"))
            if not company or not title:
                continue
            if not started:
                started = "2000-01-01"  # fallback required by schema
            entry = {
                "name": company,
                "position": title,
                "startDate": started,
                "endDate": finished,
            }
            if location:
                entry["location"] = location
            if description:
                entry["summary"] = description
                entry["highlights"] = description_to_highlights(description)
            work.append(entry)
    return work


def main() -> None:
    repo_root = Path(__file__).resolve().parent.parent
    csv_path = repo_root / "exports" / "linkedin" / "Positions.csv"
    resume_path = repo_root / "resume.yaml"

    if not csv_path.exists():
        print(f"CSV not found: {csv_path}", file=sys.stderr)
        sys.exit(1)
    if not resume_path.exists():
        print(f"resume.yaml not found: {resume_path}", file=sys.stderr)
        sys.exit(1)

    work = read_work_entries(csv_path)
    if not work:
        print("No work entries read from CSV.", file=sys.stderr)
        sys.exit(1)

    try:
        import yaml
    except ImportError:
        print("PyYAML required: pip install pyyaml", file=sys.stderr)
        sys.exit(1)

    # Represent long/multiline strings as literal block in YAML
    def str_representer(dumper, data):
        if "\n" in data or len(data) > 100:
            return dumper.represent_scalar("tag:yaml.org,2002:str", data, style="|")
        return dumper.represent_scalar("tag:yaml.org,2002:str", data)

    yaml.add_representer(str, str_representer)

    # Generate work section YAML only (list of entries)
    work_yaml = yaml.dump(
        work,
        default_flow_style=False,
        allow_unicode=True,
        width=1000,
        sort_keys=False,
    )
    # Indent each line by 2 spaces so it sits under "work:"
    indented = "\n".join("  " + line for line in work_yaml.rstrip().split("\n"))

    # Replace only the work section in resume.yaml to preserve rest of file
    text = resume_path.read_text(encoding="utf-8")
    work_start = text.find("work:\n")
    if work_start == -1:
        print("Could not find 'work:' in resume.yaml", file=sys.stderr)
        sys.exit(1)
    work_end = text.find("\nachievements:", work_start)
    if work_end == -1:
        work_end = len(text)
    new_text = (
        text[:work_start]
        + "work:\n"
        + indented.rstrip()
        + "\n"
        + text[work_end:]
    )
    resume_path.write_text(new_text, encoding="utf-8")

    print(f"Updated {resume_path} with {len(work)} work entries from {csv_path}")


if __name__ == "__main__":
    main()
