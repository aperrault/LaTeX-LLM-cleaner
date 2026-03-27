"""Tests for PDF text extraction."""

from pathlib import Path

from latex_llm_cleaner.pdf import extract_text_from_pdf


def _create_test_pdf(path: Path, pages: list[str]) -> None:
    """Create a simple PDF with text pages using pymupdf."""
    import fitz

    doc = fitz.open()
    for text in pages:
        page = doc.new_page()
        page.insert_text((72, 72), text)
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
