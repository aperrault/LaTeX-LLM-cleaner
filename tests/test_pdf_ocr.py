"""Tests for Surya OCR-based PDF extraction."""

import pytest
from unittest.mock import patch

from latex_llm_cleaner.pdf import _convert_surya_markup, extract_text_from_pdf_ocr


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
