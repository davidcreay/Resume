"""Read job description from .txt, .pdf, or .docx files."""
from pathlib import Path


def read_job_text(path: Path) -> str:
    """
    Read job description from a file. Supports .txt, .pdf, and .docx.
    Raises ValueError if the format is unsupported or reading fails.
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Job file not found: {path}")

    suffix = path.suffix.lower()

    if suffix == ".txt":
        return path.read_text(encoding="utf-8", errors="replace")

    if suffix == ".pdf":
        return _read_pdf(path)

    if suffix in (".doc", ".docx"):
        return _read_docx(path)

    raise ValueError(
        f"Unsupported job file format: {suffix}. Use .txt, .pdf, or .docx"
    )


def _read_pdf(path: Path) -> str:
    try:
        from pypdf import PdfReader
    except ImportError:
        raise ImportError(
            "PDF support requires: pip install pypdf"
        ) from None
    reader = PdfReader(path)
    parts = []
    for page in reader.pages:
        text = page.extract_text()
        if text:
            parts.append(text)
    return "\n\n".join(parts) if parts else ""


def _read_docx(path: Path) -> str:
    try:
        from docx import Document
    except ImportError:
        raise ImportError(
            "DOCX support requires: pip install python-docx"
        ) from None
    doc = Document(path)
    return "\n\n".join(p.text for p in doc.paragraphs if p.text.strip())
