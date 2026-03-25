"""Extract text from PDF files for LLM consumption."""

import sys
from pathlib import Path


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

    return pymupdf4llm.to_markdown(path)
