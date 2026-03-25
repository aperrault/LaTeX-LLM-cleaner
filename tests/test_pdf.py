"""Tests for PDF text extraction."""

import pytest
from pathlib import Path
from unittest.mock import patch

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


try:
    import pymupdf4llm

    HAS_PYMUPDF4LLM = True
except ImportError:
    HAS_PYMUPDF4LLM = False

skip_no_pymupdf = pytest.mark.skipif(
    not HAS_PYMUPDF4LLM, reason="pymupdf4llm not installed"
)


@skip_no_pymupdf
def test_basic_extraction(tmp_path):
    pdf_path = tmp_path / "test.pdf"
    _create_test_pdf(pdf_path, ["Page one content.", "Page two content."])
    result = extract_text_from_pdf(pdf_path)
    assert "Page one content." in result
    assert "Page two content." in result


@skip_no_pymupdf
def test_output_is_markdown(tmp_path):
    pdf_path = tmp_path / "test.pdf"
    _create_test_pdf(pdf_path, ["Some text here."])
    result = extract_text_from_pdf(pdf_path)
    assert isinstance(result, str)


@skip_no_pymupdf
def test_multipage(tmp_path):
    pdf_path = tmp_path / "test.pdf"
    _create_test_pdf(pdf_path, ["First.", "Second.", "Third."])
    result = extract_text_from_pdf(pdf_path)
    assert "First." in result
    assert "Second." in result
    assert "Third." in result


def test_import_error_message(tmp_path):
    """When pymupdf4llm is not installed, should exit with helpful message."""
    pdf_path = tmp_path / "test.pdf"
    pdf_path.write_bytes(b"%PDF-1.4 fake")

    with patch.dict("sys.modules", {"pymupdf4llm": None}):
        with pytest.raises(SystemExit):
            extract_text_from_pdf(pdf_path)
