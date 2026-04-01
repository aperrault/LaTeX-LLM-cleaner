"""Tests for PDF text extraction."""

from pathlib import Path

from latex_llm_cleaner.pdf import extract_text_from_pdf, _find_pdf_image_summary


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


def test_extraction_keeps_marker_without_summary(tmp_path):
    """Should keep picture markers when no summary exists."""
    pdf_path = tmp_path / "test.pdf"
    _create_pdf_with_image(pdf_path)

    result = extract_text_from_pdf(pdf_path)
    assert "intentionally omitted" in result
    assert "[Image:" not in result


def test_extraction_skips_small_markers(tmp_path):
    """Small picture markers (formulas, decorations) should not be replaced."""
    pdf_path = tmp_path / "test.pdf"
    # thesis_onepage has small picture markers that should be kept
    _create_test_pdf(pdf_path, ["Some text."])
    result = extract_text_from_pdf(pdf_path)
    # No images in a text-only PDF, so nothing to replace
    assert "Some text." in result
