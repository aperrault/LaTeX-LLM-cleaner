"""Extract text from PPTX files for LLM consumption.

Equations (OMML) become LaTeX. Text boxes that hold equations sit inside
mc:AlternateContent, which python-pptx does not expose as shapes; readers
built only on python-pptx silently drop those boxes, so they are walked here
directly. Pictures become an "[Image]" placeholder (with the alt text when the
deck has one): to see a picture, render that slide.
"""

import re
from pathlib import Path
from pptx import Presentation
from pptx.enum.shapes import MSO_SHAPE_TYPE

_OMML_NS = "http://schemas.openxmlformats.org/officeDocument/2006/math"
_MC_NS = "http://schemas.openxmlformats.org/markup-compatibility/2006"
_DML_NS = "http://schemas.openxmlformats.org/drawingml/2006/main"
_PML_NS = "http://schemas.openxmlformats.org/presentationml/2006/main"
_FILENAME_RE = re.compile(
    r"[^\n]{0,200}\.(png|jpe?g|gif|bmp|tiff?|emf|wmf|svg|pdf)", re.IGNORECASE
)


def shape_has_embedded_image(shape) -> bool:
    """True if `shape.image` is accessible without raising.

    python-pptx's `image` property raises ValueError on shapes that report
    as picture-like but have no embedded blob (linked images, empty picture
    placeholders), so `hasattr(shape, "image")` propagates that ValueError.
    """
    try:
        shape.image
    except (ValueError, AttributeError):
        return False
    return True


def extract_text_from_pptx(
    path: Path,
    verbose: bool = False,
    notes: bool = False,
) -> str:
    """Extract text from a PPTX as markdown."""
    prs = Presentation(str(path))
    slides_md = [
        _slide_to_markdown(slide, slide_num, notes)
        for slide_num, slide in enumerate(prs.slides, start=1)
    ]
    return "\n\n---\n\n".join(slides_md) + "\n"


def _slide_to_markdown(slide, slide_num, notes):
    """Convert a single slide to markdown."""
    # Title
    title_shape = slide.shapes.title
    if title_shape and title_shape.has_text_frame:
        title_text = title_shape.text_frame.text.strip()
    else:
        title_text = None

    if title_text:
        heading = f"# Slide {slide_num}: {title_text}"
    else:
        heading = f"# Slide {slide_num}"

    parts = [heading]

    # Collect IDs of shapes python-pptx already exposes, so we can
    # detect AlternateContent elements whose Choice branch is hidden.
    exposed_ids = set()
    for shape in slide.shapes:
        cNvPr = shape._element.find(f".//{{{_PML_NS}}}cNvPr")
        if cNvPr is not None:
            exposed_ids.add(cNvPr.get("id"))

    # Collect shapes (skip the title shape since we already used it)
    for shape in slide.shapes:
        if shape == title_shape:
            continue
        text = _shape_to_text(shape)
        if text:
            parts.append(text)

    # Process mc:AlternateContent elements whose Choice branch shapes
    # are not exposed by python-pptx (e.g. content with OMML math).
    sp_tree = slide._element.find(f"{{{_PML_NS}}}cSld/{{{_PML_NS}}}spTree")
    if sp_tree is not None:
        for ac in sp_tree.findall(f"{{{_MC_NS}}}AlternateContent"):
            choice = ac.find(f"{{{_MC_NS}}}Choice")
            if choice is None:
                continue
            for sp in choice:
                cNvPr = sp.find(f".//{{{_PML_NS}}}cNvPr")
                if cNvPr is not None and cNvPr.get("id") in exposed_ids:
                    continue  # already processed via python-pptx
                text = _extract_text_from_sp_element(sp)
                if text:
                    parts.append(text)

    # Speaker notes
    if notes and slide.has_notes_slide:
        notes_frame = slide.notes_slide.notes_text_frame
        notes_text = notes_frame.text.strip()
        if notes_text:
            parts.append(f"> **Notes:** {notes_text}")

    return "\n\n".join(parts)


def _shape_to_text(shape):
    """Convert a shape to text (None if it has none)."""
    # Group shape — recurse
    if shape.shape_type == MSO_SHAPE_TYPE.GROUP:
        group_parts = [t for t in map(_shape_to_text, shape.shapes) if t]
        return "\n\n".join(group_parts)

    # Table
    if shape.has_table:
        return _table_to_markdown(shape.table)

    # Picture / image (including placeholders with embedded images)
    if shape.shape_type == MSO_SHAPE_TYPE.PICTURE or (
        shape.shape_type == MSO_SHAPE_TYPE.PLACEHOLDER
        and shape_has_embedded_image(shape)
    ):
        cNvPr = shape._element.find(f".//{{{_PML_NS}}}cNvPr")
        alt = (cNvPr.get("descr") or "").strip() if cNvPr is not None else ""
        if _FILENAME_RE.fullmatch(alt):  # default alt text is often the file name
            alt = ""
        return f"[Image: {alt}]" if alt else "[Image]"

    # Text frame
    if shape.has_text_frame:
        paragraphs = [t for t in map(_process_paragraph, shape.text_frame.paragraphs) if t]
        return "\n\n".join(paragraphs)

    return None


def _extract_text_from_sp_element(sp):
    """Extract text from a raw sp XML element (for mc:AlternateContent shapes)."""
    txBody = sp.find(f"{{{_PML_NS}}}txBody")
    if txBody is None:
        return None
    paragraphs = []
    for p_elem in txBody.findall(f"{{{_DML_NS}}}p"):
        text = _process_paragraph_element(p_elem)
        if text:
            paragraphs.append(text)
    return "\n\n".join(paragraphs) if paragraphs else None


def _process_paragraph(paragraph):
    """Extract text from a python-pptx Paragraph object."""
    return _process_paragraph_element(paragraph._element)


def _process_paragraph_element(element):
    """Extract text from a paragraph XML element, converting OMML math to LaTeX."""
    from latex_llm_cleaner.omml import omml_element_to_latex

    ns_math = f"{{{_OMML_NS}}}"

    parts = []
    # Walk the paragraph's XML children to interleave text and math
    for child in element:
        tag = child.tag
        # OMML math paragraph (display math) or inline math
        if tag == f"{ns_math}oMathPara" or tag == f"{ns_math}oMath":
            parts.append(omml_element_to_latex(child))
        # Regular text run (a:r in drawingML)
        elif tag.endswith("}r"):
            # Get text from <a:t> child
            for t_elem in child:
                if t_elem.tag.endswith("}t") and t_elem.text:
                    parts.append(t_elem.text)
        # a14:m wrapper around OMML math (used in mc:Choice branches)
        elif tag.endswith("}m"):
            for math_child in child:
                if ns_math in math_child.tag:
                    parts.append(omml_element_to_latex(math_child))

    result = "".join(parts).strip()
    return result if result else None


def _table_to_markdown(table):
    """Convert a pptx Table to markdown pipe-table format."""
    rows = []
    for row in table.rows:
        cells = [cell.text.strip().replace("|", "\\|") for cell in row.cells]
        rows.append("| " + " | ".join(cells) + " |")

    if not rows:
        return ""

    # Insert separator after header row
    col_count = len(table.columns)
    separator = "| " + " | ".join(["---"] * col_count) + " |"
    rows.insert(1, separator)

    return "\n".join(rows)
