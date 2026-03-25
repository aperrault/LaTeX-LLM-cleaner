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


def extract_text_from_pdf_ocr(path: Path, verbose: bool = False) -> str:
    """Extract text from a PDF using Surya vision-based OCR.

    Recovers LaTeX equations from compiled PDFs by running OCR on rendered
    page images. Slower than pymupdf4llm but produces accurate LaTeX math.

    Requires surya-ocr: pip install latex-llm-cleaner[ocr]
    """
    try:
        from surya.detection import DetectionPredictor
        from surya.recognition import FoundationPredictor, RecognitionPredictor
    except ImportError:
        print(
            "Error: OCR support requires surya-ocr. "
            "Install it with: pip install latex-llm-cleaner[ocr]",
            file=sys.stderr,
        )
        sys.exit(1)

    import fitz
    from PIL import Image

    if verbose:
        print("  Loading OCR models...", file=sys.stderr)

    foundation = FoundationPredictor()
    det = DetectionPredictor()
    rec = RecognitionPredictor(foundation)

    doc = fitz.open(path)
    page_count = doc.page_count

    if verbose:
        print(f"  OCR processing {page_count} pages...", file=sys.stderr)

    # Render all pages as images
    images = []
    for pno in range(page_count):
        page = doc[pno]
        mat = fitz.Matrix(2, 2)  # 2x zoom for OCR quality
        pix = page.get_pixmap(matrix=mat)
        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
        images.append(img)
    doc.close()

    # Run OCR on all pages
    predictions = rec(images, det_predictor=det)

    # Assemble into document text
    pages_text = []
    for i, pred in enumerate(predictions):
        if verbose:
            print(f"  Page {i + 1}/{page_count}: {len(pred.text_lines)} lines", file=sys.stderr)
        lines = [line.text for line in pred.text_lines]
        pages_text.append("\n".join(lines))

    text = "\n\n".join(pages_text)
    return _convert_surya_markup(text)


def _convert_surya_markup(text: str) -> str:
    """Convert Surya's HTML-style markup to markdown/LaTeX conventions."""
    # Display math: <math display="block">...</math> → $$...$$
    text = re.sub(
        r'<math display="block">(.*?)</math>',
        r"$$\1$$",
        text,
        flags=re.DOTALL,
    )
    # Inline math: <math>...</math> → $...$
    text = re.sub(r"<math>(.*?)</math>", r"$\1$", text)
    # Bold: <b>...</b> → **...**
    text = re.sub(r"<b>(.*?)</b>", r"**\1**", text)
    # Superscript: <sup>...</sup> → ^{...}
    text = re.sub(r"<sup>(.*?)</sup>", r"^{\1}", text)
    # Subscript: <sub>...</sub> → _{...}
    text = re.sub(r"<sub>(.*?)</sub>", r"_{\1}", text)
    return text


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
