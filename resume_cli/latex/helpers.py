from pathlib import Path

from jinja2 import Environment, FileSystemLoader
import re

def get_jinja_env(template_dir: Path) -> Environment:
    """Configures the Jinja2 environment with LaTeX-friendly delimiters."""
    return Environment(
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
