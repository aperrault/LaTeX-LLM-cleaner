"""Tests for Surya OCR-based PDF extraction."""

import pytest
from unittest.mock import patch

from latex_llm_cleaner.pdf import (
    _convert_surya_markup,
    _reorder_text_lines,
    extract_text_from_pdf_ocr,
)


def test_inline_math_conversion():
    text = "We define <math>x = y + z</math> as the sum."
    result = _convert_surya_markup(text)
    assert result == "We define $x = y + z$ as the sum."


def test_display_math_conversion():
    text = 'The equation is:\n<math display="block">E = mc^2</math>\nas shown.'
    result = _convert_surya_markup(text)
    assert "$$E = mc^2$$" in result
    assert "<math" not in result


def test_bold_conversion():
    text = "<b>Definition 2.1</b> (Fairness)."
    result = _convert_surya_markup(text)
    assert result == "**Definition 2.1** (Fairness)."


def test_superscript_conversion():
    text = "x<sup>2</sup> + y<sup>n</sup>"
    result = _convert_surya_markup(text)
    assert "x^{2}" in result
    assert "y^{n}" in result


def test_subscript_conversion():
    text = "a<sub>i</sub> + b<sub>j</sub>"
    result = _convert_surya_markup(text)
    assert "a_{i}" in result
    assert "b_{j}" in result


def test_mixed_markup():
    text = (
        "<b>Theorem 1.</b> For <math>\\hat{Y} = g_w(R)</math>, "
        'we have:\n<math display="block">\\sum_{i=1}^n x_i = 0</math>'
    )
    result = _convert_surya_markup(text)
    assert "**Theorem 1.**" in result
    assert "$\\hat{Y} = g_w(R)$" in result
    assert "$$\\sum_{i=1}^n x_i = 0$$" in result


def test_no_markup():
    text = "Plain text with no markup."
    assert _convert_surya_markup(text) == text


def test_import_error_message(tmp_path):
    pdf_path = tmp_path / "test.pdf"
    pdf_path.write_bytes(b"%PDF-1.4 fake")

    with patch.dict("sys.modules", {
        "surya": None,
        "surya.detection": None,
        "surya.recognition": None,
    }):
        with pytest.raises(SystemExit):
            extract_text_from_pdf_ocr(pdf_path)


# --- Column reordering and line number filtering tests ---


class MockTextLine:
    """Mock Surya TextLine with bbox and text."""

    def __init__(self, text: str, bbox: list[float]):
        self.text = text
        self._bbox = bbox

    @property
    def bbox(self):
        return self._bbox


def test_two_column_reordering():
    """Lines interleaved L/R should be reordered to L-then-R."""
    page_width = 1000
    lines = [
        MockTextLine("Left 1", [50, 100, 450, 120]),
        MockTextLine("Right 1", [550, 100, 950, 120]),
        MockTextLine("Left 2", [50, 130, 450, 150]),
        MockTextLine("Right 2", [550, 130, 950, 150]),
    ]
    result = _reorder_text_lines(lines, page_width)
    texts = [l.text for l in result]
    assert texts == ["Left 1", "Left 2", "Right 1", "Right 2"]


def test_full_width_line_flushes_columns():
    """A full-width line (title) should appear between column blocks."""
    page_width = 1000
    lines = [
        MockTextLine("Title", [100, 50, 900, 70]),  # full-width
        MockTextLine("Left 1", [50, 100, 450, 120]),
        MockTextLine("Right 1", [550, 100, 950, 120]),
    ]
    result = _reorder_text_lines(lines, page_width)
    texts = [l.text for l in result]
    assert texts[0] == "Title"
    assert "Left 1" in texts
    assert "Right 1" in texts


def test_margin_line_numbers_filtered():
    """Numbers in the margin should be removed."""
    page_width = 1000
    lines = [
        MockTextLine("074", [10, 100, 40, 115]),  # left margin number
        MockTextLine("Some text", [100, 100, 450, 120]),
        MockTextLine("075", [10, 130, 40, 145]),  # left margin number
    ]
    result = _reorder_text_lines(lines, page_width)
    texts = [l.text for l in result]
    assert "074" not in texts
    assert "075" not in texts
    assert "Some text" in texts


def test_body_text_numbers_preserved():
    """Numbers in the body text area should NOT be removed."""
    page_width = 1000
    lines = [
        MockTextLine("42", [200, 100, 230, 120]),  # in body, not margin
        MockTextLine("Some text", [50, 130, 450, 150]),
    ]
    result = _reorder_text_lines(lines, page_width)
    texts = [l.text for l in result]
    assert "42" in texts


def test_single_column_passthrough():
    """Single-column docs should pass through in y-order."""
    page_width = 1000
    lines = [
        MockTextLine("Line 1", [100, 100, 900, 120]),
        MockTextLine("Line 2", [100, 130, 900, 150]),
        MockTextLine("Line 3", [100, 160, 900, 180]),
    ]
    result = _reorder_text_lines(lines, page_width)
    texts = [l.text for l in result]
    assert texts == ["Line 1", "Line 2", "Line 3"]


def test_empty_input():
    assert _reorder_text_lines([], 1000) == []


try:
    from surya.recognition import RecognitionPredictor
    HAS_SURYA = True
except ImportError:
    HAS_SURYA = False

skip_no_surya = pytest.mark.skipif(not HAS_SURYA, reason="surya-ocr not installed")


@skip_no_surya
def test_ocr_extraction_basic(tmp_path):
    """Create a simple PDF and verify OCR extracts text."""
    import fitz

    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), "Hello World", fontsize=14)
    pdf_path = tmp_path / "test.pdf"
    doc.save(str(pdf_path))
    doc.close()

    result = extract_text_from_pdf_ocr(pdf_path)
    assert "Hello" in result
    assert "World" in result
