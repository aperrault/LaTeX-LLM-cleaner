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

    # Assemble into document text with column-aware ordering
    pages_text = []
    for i, pred in enumerate(predictions):
        reordered = _reorder_text_lines(pred.text_lines, images[i].width)
        if verbose:
            removed = len(pred.text_lines) - len(reordered)
            extra = f" ({removed} margin lines filtered)" if removed else ""
            print(
                f"  Page {i + 1}/{page_count}: {len(reordered)} lines{extra}",
                file=sys.stderr,
            )
        lines = [line.text for line in reordered]
        pages_text.append("\n".join(lines))

    text = "\n\n".join(pages_text)
    return _convert_surya_markup(text)


def _reorder_text_lines(text_lines: list, page_width: int) -> list:
    """Reorder OCR text lines for correct two-column reading order
    and filter out margin line numbers.

    For two-column papers, Surya detects lines in scan order (left-right
    alternating). This function groups lines by column and emits each
    column top-to-bottom. Full-width lines (titles, section headers)
    act as column-flush boundaries.
    """
    if not text_lines:
        return []

    page_mid = page_width / 2
    margin_threshold = page_width * 0.08

    # Step 1: Filter margin line numbers (spatial + content check)
    filtered = []
    for line in text_lines:
        bbox = line.bbox  # [x_min, y_min, x_max, y_max]
        x_center = (bbox[0] + bbox[2]) / 2
        in_margin = x_center < margin_threshold or x_center > page_width - margin_threshold
        is_number = bool(re.match(r"^\d{1,4}$", line.text.strip()))
        if in_margin and is_number:
            continue
        filtered.append(line)

    # Step 2: Classify lines
    full_width_threshold = page_width * 0.5

    def classify(line):
        bbox = line.bbox
        width = bbox[2] - bbox[0]
        center = (bbox[0] + bbox[2]) / 2
        if bbox[0] < page_mid and bbox[2] > page_mid and width > full_width_threshold:
            return "full"
        elif center < page_mid:
            return "left"
        else:
            return "right"

    # Step 3: Build reading order
    sorted_lines = sorted(filtered, key=lambda l: l.bbox[1])

    result: list = []
    left_buf: list = []
    right_buf: list = []

    def flush_columns():
        left_buf.sort(key=lambda l: l.bbox[1])
        right_buf.sort(key=lambda l: l.bbox[1])
        result.extend(left_buf)
        result.extend(right_buf)
        left_buf.clear()
        right_buf.clear()

    for line in sorted_lines:
        cat = classify(line)
        if cat == "full":
            flush_columns()
            result.append(line)
        elif cat == "left":
            left_buf.append(line)
        else:
            right_buf.append(line)

    flush_columns()
    return result


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
