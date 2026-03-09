from pathlib import Path

from jinja2 import Environment, FileSystemLoader
import re

MONTH_ABBREV = [
    "", "Jan", "Feb", "Mar", "Apr", "May", "Jun",
    "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
]


def format_date_month_year(date_str):
    """Format ISO date (YYYY-MM-DD or YYYY-MM) to 'Mon YYYY' e.g. Sep 2023. Returns original string if unparseable."""
    if not date_str:
        return ""
    s = (date_str or "").strip()
    if not s:
        return ""
    parts = s.split("-")
    year = parts[0] if len(parts) > 0 else ""
    month_num = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 0
    month = MONTH_ABBREV[month_num] if 1 <= month_num <= 12 else ""
    if month and year:
        return f"{month} {year}"
    return year or s


def get_jinja_env(template_dir: Path) -> Environment:
    """Configures the Jinja2 environment with LaTeX-friendly delimiters."""
    env = Environment(
        loader=FileSystemLoader(str(template_dir)),
        block_start_string=r'\BLOCK{',
        block_end_string=r'}',
        variable_start_string=r'\VAR{',
        variable_end_string=r'}',
        comment_start_string=r'\#{',
        comment_end_string=r'}',
        line_statement_prefix='%%',
        line_comment_prefix='%#',
        trim_blocks=True,
        autoescape=False,
    )
    env.filters["month_year"] = format_date_month_year
    return env

def escape_for_latex(data):
    """Recursively escapes LaTeX special characters in strings."""
    if isinstance(data, dict):
        return {k: escape_for_latex(v) for k, v in data.items()}
    elif isinstance(data, list):
        return [escape_for_latex(i) for i in data]
    elif isinstance(data, str):
        chars_map = {
            '\\': r'\textbackslash{}',
            '&': r'\&',
            '%': r'\%',
            '$': r'\$',
            '#': r'\#',
            '_': r'\_',
            '{': r'\{',
            '}': r'\}',
            '~': r'\textasciitilde{}',
            '^': r'\textasciicircum{}',
        }
        pattern = re.compile('|'.join(re.escape(str(k)) for k in sorted(chars_map.keys(), key=len, reverse=True)))
        return pattern.sub(lambda m: chars_map[m.group(0)], data)
    return data
