"""Tests for PDF text extraction."""

from pathlib import Path

from latex_llm_cleaner.pdf import (
    extract_text_from_pdf,
    _find_pdf_image_summary,
    _insert_picture_summaries,
    _replace_picture_markers,
)


def _create_test_pdf(path: Path, pages: list[str]) -> None:
    """Create a simple PDF with text pages using pymupdf."""
    import fitz

    doc = fitz.open()
    for text in pages:
        page = doc.new_page()
        page.insert_text((72, 72), text)
    doc.save(str(path))
    doc.close()


def _create_pdf_with_image(path: Path) -> None:
    """Create a PDF with an embedded image on page 1."""
    import fitz

    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), "Text before figure.")
    # Create a 200x200 red PNG image
    pix = fitz.Pixmap(fitz.csRGB, fitz.IRect(0, 0, 200, 200), 1)
    pix.set_rect(pix.irect, (255, 0, 0, 255))
    img_bytes = pix.tobytes("png")
    rect = fitz.Rect(100, 150, 400, 450)
    page.insert_image(rect, stream=img_bytes)
    page.insert_text((72, 500), "Text after figure.")
    doc.save(str(path))
    doc.close()


def test_basic_extraction(tmp_path):
    pdf_path = tmp_path / "test.pdf"
    _create_test_pdf(pdf_path, ["Page one content.", "Page two content."])
    result = extract_text_from_pdf(pdf_path)
    assert "Page one content." in result
    assert "Page two content." in result


def test_output_is_markdown(tmp_path):
    pdf_path = tmp_path / "test.pdf"
    _create_test_pdf(pdf_path, ["Some text here."])
    result = extract_text_from_pdf(pdf_path)
    assert isinstance(result, str)


def test_multipage(tmp_path):
    pdf_path = tmp_path / "test.pdf"
    _create_test_pdf(pdf_path, ["First.", "Second.", "Third."])
    result = extract_text_from_pdf(pdf_path)
    assert "First." in result
    assert "Second." in result
    assert "Third." in result


def test_find_pdf_image_summary(tmp_path):
    """Should find summary file by naming convention."""
    summary = tmp_path / "doc_page1_image1_summary.txt"
    summary.write_text("A chart showing data.")
    result = _find_pdf_image_summary(tmp_path, "doc", 1, 1, "_summary.txt", "utf-8")
    assert result == "A chart showing data."


def test_find_pdf_image_summary_missing(tmp_path):
    """Should return None when no summary file exists."""
    result = _find_pdf_image_summary(tmp_path, "doc", 1, 1, "_summary.txt", "utf-8")
    assert result is None


def test_extraction_inserts_summary(tmp_path):
    """Should replace picture markers with summaries when available."""
    pdf_path = tmp_path / "test.pdf"
    _create_pdf_with_image(pdf_path)

    # Create a summary file for the image
    summary_path = tmp_path / "test_page1_image1_summary.txt"
    summary_path.write_text("A red square image.")

    result = extract_text_from_pdf(pdf_path)
    assert "[Image: A red square image.]" in result
    assert "intentionally omitted" not in result


def test_extraction_drops_marker_without_summary(tmp_path):
    """Should silently drop picture markers when no summary exists."""
    pdf_path = tmp_path / "test.pdf"
    _create_pdf_with_image(pdf_path)

    result = extract_text_from_pdf(pdf_path)
    # No summary -> the picture is dropped entirely, leaving no marker spam.
    assert "intentionally omitted" not in result
    assert "[Image:" not in result
    # Surrounding text is preserved.
    assert "Text before figure." in result
    assert "Text after figure." in result


def test_small_picture_markers_dropped(tmp_path):
    """Small pictures (formulas, decorations) are dropped without a summary
    lookup, and do not consume the image index — only significant pictures do.
    """
    # A summary exists for the first *significant* image on the page.
    (tmp_path / "doc_page1_image1_summary.txt").write_text("A real figure.")
    text = (
        "Before. "
        "**==> picture [32 x 32] intentionally omitted <==** "
        "Middle. "
        "**==> picture [200 x 200] intentionally omitted <==** "
        "After."
    )
    result = _replace_picture_markers(text, tmp_path, "doc", 1, "_summary.txt", "utf-8")

    # The small marker is removed entirely (no marker spam).
    assert "32 x 32" not in result
    assert "intentionally omitted" not in result
    # Because the small marker did not consume the index, image1 is the
    # significant 200x200 picture, so its summary is the one inserted.
    assert "[Image: A real figure.]" in result
    assert "Before." in result
    assert "Middle." in result
    assert "After." in result


# --- _insert_picture_summaries: layout-box positions, not text markers ---

_MARKER = "**==> picture [300 x 300] intentionally omitted <==**"


def test_insert_summary_replaces_marker_span(tmp_path):
    """pymupdf4llm 1.27 emits a marker at the picture's span; it is
    replaced by the summary."""
    (tmp_path / "doc_page1_image1_summary.txt").write_text("A chart.")
    text = "Before. \n\n" + _MARKER + "\n\nAfter. \n\n"
    start = text.index(_MARKER)
    boxes = [{"class": "picture", "bbox": (100, 150, 400, 450),
              "pos": (start, start + len(_MARKER))}]
    result = _insert_picture_summaries(text, boxes, tmp_path, "doc", 1, "_summary.txt", "utf-8")
    assert result == "Before. \n\n[Image: A chart.]\n\nAfter. \n\n"


def test_insert_summary_into_empty_span(tmp_path):
    """pymupdf4llm 1.28 emits nothing for a picture; its span is just the
    blank line where the picture sits. The summary still lands there."""
    (tmp_path / "doc_page1_image1_summary.txt").write_text("A chart.")
    text = "Before. \n\n\n\nAfter. \n\n"
    # As observed from pymupdf4llm 1.28: the span is the two newlines
    # immediately before the following text block.
    boxes = [{"class": "picture", "bbox": (100, 150, 400, 450), "pos": (10, 12)}]
    assert text[12:] == "After. \n\n"
    result = _insert_picture_summaries(text, boxes, tmp_path, "doc", 1, "_summary.txt", "utf-8")
    assert result == "Before. \n\n[Image: A chart.]\n\nAfter. \n\n"


def test_insert_summary_drops_picture_without_summary(tmp_path):
    text = "Before. \n\n" + _MARKER + "\n\nAfter. \n\n"
    start = text.index(_MARKER)
    boxes = [{"class": "picture", "bbox": (100, 150, 400, 450),
              "pos": (start, start + len(_MARKER))}]
    result = _insert_picture_summaries(text, boxes, tmp_path, "doc", 1, "_summary.txt", "utf-8")
    assert result == "Before. \n\nAfter. \n\n"


def test_insert_summary_small_pictures_do_not_consume_index(tmp_path):
    """A sub-threshold picture is dropped and does not shift image numbering."""
    (tmp_path / "doc_page1_image1_summary.txt").write_text("A real figure.")
    small = "**==> picture [32 x 32] intentionally omitted <==**"
    text = "Before. " + small + " Middle. " + _MARKER + " After."
    s1 = text.index(small)
    s2 = text.index(_MARKER)
    boxes = [
        {"class": "picture", "bbox": (10, 10, 42, 42), "pos": (s1, s1 + len(small))},
        {"class": "picture", "bbox": (100, 150, 400, 450), "pos": (s2, s2 + len(_MARKER))},
    ]
    result = _insert_picture_summaries(text, boxes, tmp_path, "doc", 1, "_summary.txt", "utf-8")
    assert result == "Before.  Middle. \n\n[Image: A real figure.]\n\n After."


def test_insert_summary_merged_subboxes_share_one_slot(tmp_path):
    """Two adjacent picture boxes merged into one figure get one summary,
    at the first box's position; the other box's span is blanked."""
    (tmp_path / "doc_page1_image1_summary.txt").write_text("One figure.")
    text = "Before. \n\nAAAA\n\nBBBB\n\nAfter. \n\n"
    a = text.index("AAAA"); b = text.index("BBBB")
    boxes = [
        {"class": "picture", "bbox": (117, 41, 289, 224), "pos": (a, a + 4)},
        {"class": "picture", "bbox": (37, 85, 87, 200), "pos": (b, b + 4)},  # strip
    ]
    result = _insert_picture_summaries(text, boxes, tmp_path, "doc", 1, "_summary.txt", "utf-8")
    assert result == "Before. \n\n[Image: One figure.]\n\nAfter. \n\n"
    assert not (tmp_path / "doc_page1_image2_summary.txt").exists()
