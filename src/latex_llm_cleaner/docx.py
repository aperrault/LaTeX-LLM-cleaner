"""Extract text from DOCX files for LLM consumption."""

import sys
from pathlib import Path

from docx import Document
from lxml import etree

_WML_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
_DML_NS = "http://schemas.openxmlformats.org/drawingml/2006/main"
_WP_NS = "http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing"
_REL_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
_OMML_NS = "http://schemas.openxmlformats.org/officeDocument/2006/math"
_COMMENTS_RELTYPE = (
    "http://schemas.openxmlformats.org/officeDocument/2006/relationships/comments"
)


def extract_text_from_docx(
    path: Path,
    verbose: bool = False,
    notes: bool = False,
    figure_summary_suffix: str = "_summary.txt",
    encoding: str = "utf-8",
) -> str:
    """Extract text from a DOCX as markdown."""
    doc = Document(str(path))
    base_dir = path.parent.resolve()
    docx_stem = path.stem

    # Load comments if requested
    comments: dict[str, tuple[str, str]] = {}  # id -> (author, text)
    if notes:
        comments = _load_comments(doc)

    # Walk body elements to preserve ordering
    parts: list[str] = []
    image_counter = 0

    for child in doc.element.body:
        tag = etree.QName(child.tag).localname

        if tag == "p":
            text, image_counter = _paragraph_to_markdown(
                child, image_counter, base_dir, docx_stem,
                figure_summary_suffix, encoding, verbose, doc,
            )
            if text:
                # Append inline comments if present
                if notes and comments:
                    comment_refs = child.findall(f".//{{{_WML_NS}}}commentReference")
                    for ref in comment_refs:
                        cid = ref.get(f"{{{_WML_NS}}}id")
                        if cid in comments:
                            author, comment_text = comments[cid]
                            text += f"\n\n> **Comment ({author}):** {comment_text}"
                parts.append(text)

        elif tag == "tbl":
            table_md = _table_to_markdown(child)
            if table_md:
                parts.append(table_md)

    return "\n\n".join(parts) + "\n"


def _paragraph_to_markdown(
    element, image_counter, base_dir, docx_stem,
    suffix, encoding, verbose, doc,
):
    """Convert a paragraph element to markdown. Returns (text, updated_image_counter)."""
    # Check heading style
    heading_level = _get_heading_level(element)

    # Collect (text, fmt) pairs then merge adjacent runs with same formatting.
    # fmt is one of: None, "bold", "italic", "bolditalic", "raw" (pre-formatted)
    spans: list[tuple[str, str | None]] = []

    for child in element:
        child_tag = etree.QName(child.tag).localname

        if child_tag == "r":
            # Check for images (w:drawing with a:blip) in both inline
            # and anchor drawings.  Use descendant search since drawings
            # may be inside mc:AlternateContent/mc:Choice wrappers.
            inlines = (
                child.findall(f".//{{{_WP_NS}}}inline")
                + child.findall(f".//{{{_WP_NS}}}anchor")
            )
            has_inline_image = False
            if inlines:
                for inline in inlines:
                    blips = inline.findall(f".//{{{_DML_NS}}}blip")
                    if blips:
                        has_inline_image = True
                        image_counter += 1
                        summary = _find_image_summary(
                            base_dir, docx_stem, image_counter, suffix, encoding,
                        )
                        if summary:
                            spans.append((f"[Image: {summary}]", "raw"))
                        else:
                            if verbose:
                                print(
                                    f"Warning: no summary found for "
                                    f"{docx_stem}_image{image_counter}",
                                    file=sys.stderr,
                                )
                            spans.append(("[Image]", "raw"))
            if not has_inline_image:
                pair = _run_to_pair(child)
                if pair:
                    spans.append(pair)

        elif child_tag == "hyperlink":
            for r in child.findall(f"{{{_WML_NS}}}r"):
                pair = _run_to_pair(r)
                if pair:
                    spans.append(pair)

        elif child_tag in ("oMathPara", "oMath"):
            from latex_llm_cleaner.omml import omml_element_to_latex
            spans.append((omml_element_to_latex(child), "raw"))

    # Merge adjacent spans with identical formatting, then wrap
    run_parts: list[str] = []
    for text, fmt in _merge_spans(spans):
        if heading_level is not None or fmt is None or fmt == "raw":
            run_parts.append(text)
        elif fmt == "bolditalic":
            run_parts.append(f"***{text}***")
        elif fmt == "bold":
            run_parts.append(f"**{text}**")
        elif fmt == "italic":
            run_parts.append(f"*{text}*")

    result = "".join(run_parts).strip()
    if not result:
        return None, image_counter

    if heading_level:
        result = f"{'#' * heading_level} {result}"

    return result, image_counter


def _run_to_pair(run_element) -> tuple[str, str | None] | None:
    """Return (text, fmt) for a run element, or None if empty."""
    texts = []
    for child in run_element:
        child_tag = etree.QName(child.tag).localname
        if child_tag == "t" and child.text:
            texts.append(child.text)
        elif child_tag == "tab":
            texts.append("\t")
        elif child_tag == "br":
            texts.append("\n")

    if not texts:
        return None

    text = "".join(texts)
    fmt = None

    rPr = run_element.find(f"{{{_WML_NS}}}rPr")
    if rPr is not None:
        bold = rPr.find(f"{{{_WML_NS}}}b")
        italic = rPr.find(f"{{{_WML_NS}}}i")
        is_bold = bold is not None and bold.get(f"{{{_WML_NS}}}val", "true") != "false"
        is_italic = (
            italic is not None and italic.get(f"{{{_WML_NS}}}val", "true") != "false"
        )
        if is_bold and is_italic:
            fmt = "bolditalic"
        elif is_bold:
            fmt = "bold"
        elif is_italic:
            fmt = "italic"

    return text, fmt


def _merge_spans(spans):
    """Merge adjacent spans with identical formatting."""
    if not spans:
        return
    cur_text, cur_fmt = spans[0]
    for text, fmt in spans[1:]:
        if fmt == cur_fmt and fmt != "raw":
            cur_text += text
        else:
            yield cur_text, cur_fmt
            cur_text, cur_fmt = text, fmt
    yield cur_text, cur_fmt


def _get_heading_level(paragraph_element) -> int | None:
    """Return heading level (1-6) or None for non-heading paragraphs."""
    pPr = paragraph_element.find(f"{{{_WML_NS}}}pPr")
    if pPr is None:
        return None
    pStyle = pPr.find(f"{{{_WML_NS}}}pStyle")
    if pStyle is None:
        return None
    val = pStyle.get(f"{{{_WML_NS}}}val", "")
    # Styles like "Heading1", "Heading2", etc.
    if val.startswith("Heading"):
        try:
            level = int(val[7:])
            return min(level, 6)
        except ValueError:
            pass
    return None


def _table_to_markdown(tbl_element):
    """Convert a table element to markdown pipe-table format."""
    rows = []
    for tr in tbl_element.findall(f"{{{_WML_NS}}}tr"):
        cells = []
        for tc in tr.findall(f"{{{_WML_NS}}}tc"):
            cell_parts = []
            # Collect plain text
            texts = tc.findall(f".//{{{_WML_NS}}}t")
            plain = " ".join(t.text or "" for t in texts).strip()
            if plain:
                cell_parts.append(plain)
            # Collect OMML math elements
            for omath in tc.findall(f".//{{{_OMML_NS}}}oMath"):
                from latex_llm_cleaner.omml import omml_element_to_latex
                cell_parts.append(omml_element_to_latex(omath))
            cell_text = " ".join(cell_parts)
            cells.append(cell_text.replace("|", "\\|"))
        rows.append("| " + " | ".join(cells) + " |")

    if not rows:
        return ""

    # Insert separator after header row
    col_count = len(tbl_element.findall(f"{{{_WML_NS}}}tr/{{{_WML_NS}}}tc"))
    if col_count == 0:
        # Fall back to counting cells in first row
        first_row = tbl_element.find(f"{{{_WML_NS}}}tr")
        if first_row is not None:
            col_count = len(first_row.findall(f"{{{_WML_NS}}}tc"))
    separator = "| " + " | ".join(["---"] * col_count) + " |"
    rows.insert(1, separator)

    return "\n".join(rows)


def _find_image_summary(base_dir, docx_stem, image_index, suffix, encoding):
    """Look for {docx_stem}_image{M}{suffix} in base_dir."""
    stem = f"{docx_stem}_image{image_index}"
    summary_path = base_dir / (stem + suffix)
    if summary_path.is_file():
        return summary_path.read_text(encoding=encoding).strip()
    return None


def _load_comments(doc) -> dict[str, tuple[str, str]]:
    """Load comments from the DOCX OPC package. Returns {id: (author, text)}."""
    comments: dict[str, tuple[str, str]] = {}
    for rel in doc.part.rels.values():
        if rel.reltype != _COMMENTS_RELTYPE:
            continue
        tree = etree.fromstring(rel.target_part.blob)
        for comment_elem in tree.findall(f"{{{_WML_NS}}}comment"):
            cid = comment_elem.get(f"{{{_WML_NS}}}id")
            author = comment_elem.get(f"{{{_WML_NS}}}author", "")
            texts = comment_elem.findall(f".//{{{_WML_NS}}}t")
            text = " ".join(t.text or "" for t in texts).strip()
            if cid is not None and text:
                comments[cid] = (author, text)
    return comments
