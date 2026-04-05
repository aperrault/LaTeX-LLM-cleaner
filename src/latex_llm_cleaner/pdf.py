"""Extract text from PDF files for LLM consumption."""

import re
import sys
from pathlib import Path

import pymupdf4llm

# Combining diacritics that pymupdf4llm splits from their base character
_DIACRITICS = "ˆˇ˜¯˙"


_MIN_FIGURE_DIM = 64

_PICTURE_MARKER_RE = re.compile(
    r"\*\*==> picture \[(\d+) x (\d+)\] intentionally omitted <==\*\*"
)


def _find_pdf_image_summary(
    base_dir: Path, pdf_stem: str, page_num: int, image_index: int,
    suffix: str, encoding: str,
) -> str | None:
    """Look for {pdf_stem}_page{N}_image{M}{suffix} in base_dir."""
    stem = f"{pdf_stem}_page{page_num}_image{image_index}"
    summary_path = base_dir / (stem + suffix)
    if summary_path.is_file():
        return summary_path.read_text(encoding=encoding).strip()
    return None


def _replace_picture_markers(
    text: str, base_dir: Path, pdf_stem: str, page_num: int,
    suffix: str, encoding: str,
) -> str:
    """Replace significant picture markers with summaries if available."""
    image_index = 0

    def _replacer(m: re.Match) -> str:
        nonlocal image_index
        w, h = int(m.group(1)), int(m.group(2))
        if w <= _MIN_FIGURE_DIM or h <= _MIN_FIGURE_DIM:
            return m.group(0)  # keep small markers as-is
        image_index += 1
        summary = _find_pdf_image_summary(
            base_dir, pdf_stem, page_num, image_index, suffix, encoding,
        )
        if summary:
            return f"[Image: {summary}]"
        return m.group(0)

    return _PICTURE_MARKER_RE.sub(_replacer, text)


def extract_text_from_pdf(
    path: Path,
    verbose: bool = False,
    figure_summary_suffix: str = "_summary.txt",
    encoding: str = "utf-8",
) -> str:
    """Extract text from a PDF as markdown, preserving tables and structure."""
    if verbose:
        import fitz

        doc = fitz.open(path)
        print(f"  Extracting {doc.page_count} pages...", file=sys.stderr)
        doc.close()

    chunks = pymupdf4llm.to_markdown(str(path), page_chunks=True)
    base_dir = path.parent.resolve()
    pdf_stem = path.stem

    pages = []
    for page_num, chunk in enumerate(chunks, start=1):
        text = chunk["text"]
        text = _replace_picture_markers(
            text, base_dir, pdf_stem, page_num,
            figure_summary_suffix, encoding,
        )
        pages.append(text)

    md = "\n-----\n\n".join(pages)
    return _clean_markdown(md)


def _extract_table_markdowns(chunk_text: str) -> list[str]:
    """Extract contiguous blocks of pipe-delimited markdown table lines.

    Returns a list of table blocks (each a multi-line string), ordered
    top-to-bottom as they appear in the text.
    """
    blocks: list[list[str]] = []
    current: list[str] = []
    for line in chunk_text.split("\n"):
        if line.strip().startswith("|"):
            current.append(line)
        else:
            if current:
                blocks.append(current)
                current = []
    if current:
        blocks.append(current)
    return ["\n".join(b) for b in blocks]


def _filter_figure_lines(text_lines: list, picture_bboxes: list[list[float]]) -> list:
    """Remove OCR text lines that fall inside region bounding boxes.

    A line is considered inside a region if its vertical center is within
    the bbox and its horizontal span overlaps with it. Works for both
    picture and table regions.
    """
    if not picture_bboxes:
        return text_lines

    filtered = []
    for line in text_lines:
        bbox = line.bbox  # [x_min, y_min, x_max, y_max]
        y_center = (bbox[1] + bbox[3]) / 2
        inside = False
        for pb in picture_bboxes:
            # Check vertical center within picture and horizontal overlap
            if (pb[1] <= y_center <= pb[3]
                    and bbox[2] > pb[0] and bbox[0] < pb[2]):
                inside = True
                break
        if not inside:
            filtered.append(line)
    return filtered


def extract_text_from_pdf_ocr(
    path: Path,
    verbose: bool = False,
    figure_summary_suffix: str = "_summary.txt",
    encoding: str = "utf-8",
) -> str:
    """Extract text from a PDF using Surya vision-based OCR.

    Recovers LaTeX equations from compiled PDFs by running OCR on rendered
    page images. Slower than pymupdf4llm but produces accurate LaTeX math.

    When image summaries exist (from --auto-summarize), figure regions are
    masked from OCR and summaries are inserted at the correct position.

    Requires surya-ocr: pip install 'latex-llm-cleaner[ocr]'
    """
    try:
        from surya.detection import DetectionPredictor
        from surya.recognition import FoundationPredictor, RecognitionPredictor
    except ImportError:
        print(
            "Error: OCR support requires surya-ocr.\n"
            "Install with: pip install 'latex-llm-cleaner[ocr]'\n"
            "Or globally:  uv tool install 'latex-llm-cleaner[ocr]'\n"
            "Note: requires Python ≤ 3.13 and libjpeg (brew install jpeg on macOS).",
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

    # Get picture/table bounding boxes per page from pymupdf4llm structure analysis
    chunks = pymupdf4llm.to_markdown(str(path), page_chunks=True)
    zoom = 2  # must match the rendering matrix below
    page_picture_bboxes: list[list[list[float]]] = []
    page_table_bboxes: list[list[list[float]]] = []
    page_table_markdowns: list[list[str]] = []
    for chunk in chunks:
        pic_boxes = [
            [b["bbox"][0] * zoom, b["bbox"][1] * zoom,
             b["bbox"][2] * zoom, b["bbox"][3] * zoom]
            for b in chunk.get("page_boxes", [])
            if b["class"] == "picture"
            and (b["bbox"][2] - b["bbox"][0]) > _MIN_FIGURE_DIM
            and (b["bbox"][3] - b["bbox"][1]) > _MIN_FIGURE_DIM
        ]
        page_picture_bboxes.append(pic_boxes)
        tbl_boxes = [
            [b["bbox"][0] * zoom, b["bbox"][1] * zoom,
             b["bbox"][2] * zoom, b["bbox"][3] * zoom]
            for b in chunk.get("page_boxes", [])
            if b["class"] == "table"
        ]
        page_table_bboxes.append(tbl_boxes)
        page_table_markdowns.append(
            _extract_table_markdowns(chunk["text"]) if tbl_boxes else []
        )

    # Render all pages as images
    images = []
    for pno in range(page_count):
        page = doc[pno]
        mat = fitz.Matrix(zoom, zoom)
        pix = page.get_pixmap(matrix=mat)
        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
        images.append(img)
    doc.close()

    # Run OCR on all pages
    predictions = rec(images, det_predictor=det)

    # Assemble into document text with column-aware ordering
    base_dir = path.parent.resolve()
    pdf_stem = path.stem
    pages_text = []
    for i, pred in enumerate(predictions):
        reordered = _reorder_text_lines(pred.text_lines, images[i].width)
        pic_bboxes = page_picture_bboxes[i] if i < len(page_picture_bboxes) else []
        tbl_bboxes = page_table_bboxes[i] if i < len(page_table_bboxes) else []
        tbl_markdowns = page_table_markdowns[i] if i < len(page_table_markdowns) else []

        # Filter out OCR lines inside figure and table regions
        all_region_bboxes = pic_bboxes + tbl_bboxes
        if all_region_bboxes:
            before_count = len(reordered)
            reordered = _filter_figure_lines(reordered, all_region_bboxes)
            region_removed = before_count - len(reordered)
        else:
            region_removed = 0

        if verbose:
            removed = len(pred.text_lines) - len(reordered) - region_removed
            extra = f" ({removed} margin lines filtered)" if removed else ""
            if region_removed:
                extra += f" ({region_removed} figure/table lines filtered)"
            print(
                f"  Page {i + 1}/{page_count}: {len(reordered)} lines{extra}",
                file=sys.stderr,
            )

        # Build page text, inserting replacements at correct positions
        page_num = i + 1
        if all_region_bboxes:
            # Collect inserts keyed by y-position
            positional_inserts: list[tuple[float, str]] = []

            # Image summaries at bottom of picture bbox
            for img_idx, pb in enumerate(pic_bboxes, start=1):
                summary = _find_pdf_image_summary(
                    base_dir, pdf_stem, page_num, img_idx,
                    figure_summary_suffix, encoding,
                )
                if summary:
                    positional_inserts.append((pb[3], f"[Image: {summary}]"))

            # Table markdown at top of table bbox
            for tb, tbl_md in zip(tbl_bboxes, tbl_markdowns):
                if tbl_md:
                    positional_inserts.append((tb[1], tbl_md))

            # Merge text lines and positional inserts by y-position
            line_items: list[tuple[float, str]] = [
                (line.bbox[1], line.text) for line in reordered
            ]
            line_items.extend(positional_inserts)
            line_items.sort(key=lambda item: item[0])
            page_text = "\n".join(text for _, text in line_items)
        else:
            lines = [line.text for line in reordered]
            page_text = "\n".join(lines)
            # Append any image summaries (fallback for pages without detected boxes)
            img_idx = 1
            while True:
                summary = _find_pdf_image_summary(
                    base_dir, pdf_stem, page_num, img_idx,
                    figure_summary_suffix, encoding,
                )
                if summary is None:
                    break
                page_text += f"\n\n[Image: {summary}]"
                img_idx += 1

        pages_text.append(page_text)

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
