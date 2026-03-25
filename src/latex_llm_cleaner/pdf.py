"""Extract text from PDF files for LLM consumption."""

import re
import sys
from pathlib import Path

# Combining diacritics that pymupdf4llm splits from their base character
_DIACRITICS = "ˆˇ˜¯˙"


def extract_text_from_pdf(path: Path, verbose: bool = False) -> str:
    """Extract text from a PDF as markdown, preserving tables and structure.

    Requires pymupdf4llm: pip install latex-llm-cleaner[pdf]
    """
    try:
        import pymupdf4llm
    except ImportError:
        print(
            "Error: PDF support requires pymupdf4llm. "
            "Install it with: pip install latex-llm-cleaner[pdf]",
            file=sys.stderr,
        )
        sys.exit(1)

    if verbose:
        import fitz

        doc = fitz.open(path)
        print(f"  Extracting {doc.page_count} pages...", file=sys.stderr)
        doc.close()

    md = pymupdf4llm.to_markdown(path)
    return _clean_markdown(md)


def _clean_markdown(text: str) -> str:
    """Post-process pymupdf4llm output for LLM consumption.

    Strips italic markers (which garble math equations) and cleans up
    remaining artifacts like split diacritics and bracket superscripts.
    """
    # Strip all italic markers — they garble equations and add no value
    # for LLM consumption. Preserve bold (**) and code (`) markers.
    # Handle _content_ but not __content__ (which would be bold in some parsers)
    text = re.sub(r"(?<!\w)_([^_]+?)_(?!\w)", r"\1", text)

    lines = text.split("\n")
    result = []
    for line in lines:
        if not line.strip().startswith("|"):
            line = _merge_diacritics(line)
            line = _clean_bracket_superscripts(line)
        result.append(line)
    return "\n".join(result)


def _merge_diacritics(line: str) -> str:
    """Merge combining diacritics with their following base character."""
    for d in _DIACRITICS:
        line = re.sub(
            rf"{re.escape(d)}\s+([a-zA-Z])",
            rf"{d}\1",
            line,
        )
    return line


def _clean_bracket_superscripts(line: str) -> str:
    """Clean up bracket notation for superscripts/subscripts."""
    line = line.replace("[ˆ]", "^")

    # [(] content [)] → (content)
    line = re.sub(
        r"\[\(\]\s*\[?([^\]]*?)\]?\s*\[\)\]",
        r"(\1)",
        line,
    )

    # Adjacent brackets with optional spaces: [x][y][z] or [x] [y] [z] → x y z
    # But preserve citation-style [number] references
    line = re.sub(
        r"(\[[^\]\d][^\]]*?\]\s*){2,}",
        lambda m: " ".join(re.findall(r"\[([^\]]*)\]", m.group(0))) + " ",
        line,
    )

    return line
