"""Tests for auto_summarize_figures and auto_summarize_pdf."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from latex_llm_cleaner.summarize import auto_summarize_figures


@pytest.fixture
def options():
    return {
        "figure_summary_suffix": "_summary.txt",
        "encoding": "utf-8",
        "verbose": False,
        "google_api_key": "fake-key",
        "auto_summarize": True,
    }


@pytest.fixture
def mock_genai():
    """Mock google.genai module and client."""
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.text = "A table showing X vs Y."
    mock_client.models.generate_content.return_value = mock_response

    mock_module = MagicMock()
    mock_module.Client.return_value = mock_client

    with patch.dict("sys.modules", {"google": MagicMock(), "google.genai": mock_module}):
        with patch("latex_llm_cleaner.summarize.genai", mock_module, create=True):
            # Patch the import inside auto_summarize_figures
            with patch(
                "latex_llm_cleaner.summarize.auto_summarize_figures.__code__",
            ):
                pass
    # Simpler approach: patch at the point of use
    return mock_module, mock_client, mock_response


def _run_summarize(content, base_dir, options):
    """Run auto_summarize_figures with google.genai mocked."""
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.text = "A table showing X vs Y."
    mock_client.models.generate_content.return_value = mock_response

    mock_genai = MagicMock()
    mock_genai.Client.return_value = mock_client

    with patch.dict(
        "sys.modules",
        {"google": MagicMock(), "google.genai": MagicMock()},
    ):
        with patch("latex_llm_cleaner.summarize.genai", mock_genai, create=True):
            # We need to patch the import inside the function
            import latex_llm_cleaner.summarize as mod

            original_func = mod.auto_summarize_figures

            # Directly patch the google import
            with patch.object(mod, "_call_gemini", return_value="A table showing X vs Y."):
                result = original_func(content, base_dir, options)

    return result, mock_client


def test_skips_when_summary_exists(tmp_path, options):
    """Should skip figures that already have summary files."""
    # Create image and existing summary
    img = tmp_path / "plot.png"
    img.write_bytes(b"\x89PNG fake")
    summary = tmp_path / "plot_summary.txt"
    summary.write_text("Existing summary.")

    content = r"\includegraphics{plot.png}"

    with patch("latex_llm_cleaner.summarize._call_gemini") as mock_call:
        mock_genai = MagicMock()
        mock_genai.Client.return_value = MagicMock()
        with patch.dict(
            "sys.modules",
            {"google": MagicMock(), "google.genai": MagicMock()},
        ):
            with patch("latex_llm_cleaner.summarize.genai", mock_genai, create=True):
                # Import and call directly, patching the genai import
                import importlib
                import latex_llm_cleaner.summarize as mod

                # Monkey-patch the import
                original = mod.auto_summarize_figures.__globals__
                with patch.dict(original, {"genai": mock_genai}):
                    result = mod.auto_summarize_figures(content, tmp_path, options)

        mock_call.assert_not_called()

    assert result == content
    assert summary.read_text() == "Existing summary."


def test_generates_summary_for_missing(tmp_path, options):
    """Should generate and write a summary when none exists."""
    img = tmp_path / "chart.png"
    img.write_bytes(b"\x89PNG fake")

    content = r"\includegraphics[width=\textwidth]{chart.png}"

    mock_client = MagicMock()
    mock_genai = MagicMock()
    mock_genai.Client.return_value = mock_client

    with patch.dict(
        "sys.modules",
        {"google": MagicMock(), "google.genai": MagicMock()},
    ):
        with patch(
            "latex_llm_cleaner.summarize._call_gemini",
            return_value="| Col A | Col B |\n|-------|-------|\n| 1 | 2 |",
        ):
            import latex_llm_cleaner.summarize as mod

            with patch.dict(
                mod.auto_summarize_figures.__globals__, {"genai": mock_genai}
            ):
                result = mod.auto_summarize_figures(content, tmp_path, options)

    summary_path = tmp_path / "chart_summary.txt"
    assert summary_path.is_file()
    assert "Col A" in summary_path.read_text()
    assert result == content


def test_handles_image_not_found(tmp_path, options):
    """Should warn and skip when image file doesn't exist."""
    content = r"\includegraphics{missing.png}"

    mock_genai = MagicMock()
    mock_genai.Client.return_value = MagicMock()

    with patch.dict(
        "sys.modules",
        {"google": MagicMock(), "google.genai": MagicMock()},
    ):
        with patch("latex_llm_cleaner.summarize._call_gemini") as mock_call:
            import latex_llm_cleaner.summarize as mod

            with patch.dict(
                mod.auto_summarize_figures.__globals__, {"genai": mock_genai}
            ):
                result = mod.auto_summarize_figures(content, tmp_path, options)

    mock_call.assert_not_called()
    assert result == content


def test_handles_api_error(tmp_path, options):
    """Should warn and continue when API call fails."""
    img = tmp_path / "fig.png"
    img.write_bytes(b"\x89PNG fake")

    content = r"\includegraphics{fig.png}"

    mock_genai = MagicMock()
    mock_genai.Client.return_value = MagicMock()

    with patch.dict(
        "sys.modules",
        {"google": MagicMock(), "google.genai": MagicMock()},
    ):
        with patch(
            "latex_llm_cleaner.summarize._call_gemini",
            side_effect=RuntimeError("Auth failed"),
        ):
            import latex_llm_cleaner.summarize as mod

            with patch.dict(
                mod.auto_summarize_figures.__globals__, {"genai": mock_genai}
            ):
                result = mod.auto_summarize_figures(content, tmp_path, options)

    # No summary file written
    assert not (tmp_path / "fig_summary.txt").exists()
    assert result == content


def test_respects_custom_suffix(tmp_path, options):
    """Should use the configured suffix for summary files."""
    options["figure_summary_suffix"] = "_desc.md"
    img = tmp_path / "data.png"
    img.write_bytes(b"\x89PNG fake")

    content = r"\includegraphics{data.png}"

    mock_genai = MagicMock()
    mock_genai.Client.return_value = MagicMock()

    with patch.dict(
        "sys.modules",
        {"google": MagicMock(), "google.genai": MagicMock()},
    ):
        with patch(
            "latex_llm_cleaner.summarize._call_gemini",
            return_value="Summary text.",
        ):
            import latex_llm_cleaner.summarize as mod

            with patch.dict(
                mod.auto_summarize_figures.__globals__, {"genai": mock_genai}
            ):
                mod.auto_summarize_figures(content, tmp_path, options)

    assert (tmp_path / "data_desc.md").is_file()
    assert not (tmp_path / "data_summary.txt").exists()


def test_subdirectory_images(tmp_path, options):
    """Should write summaries next to images in subdirectories."""
    figs_dir = tmp_path / "figs"
    figs_dir.mkdir()
    img = figs_dir / "result.jpg"
    img.write_bytes(b"\xff\xd8\xff fake jpg")

    content = r"\includegraphics{figs/result.jpg}"

    mock_genai = MagicMock()
    mock_genai.Client.return_value = MagicMock()

    with patch.dict(
        "sys.modules",
        {"google": MagicMock(), "google.genai": MagicMock()},
    ):
        with patch(
            "latex_llm_cleaner.summarize._call_gemini",
            return_value="Result table.",
        ):
            import latex_llm_cleaner.summarize as mod

            with patch.dict(
                mod.auto_summarize_figures.__globals__, {"genai": mock_genai}
            ):
                mod.auto_summarize_figures(content, tmp_path, options)

    assert (figs_dir / "result_summary.txt").is_file()
    assert (figs_dir / "result_summary.txt").read_text() == "Result table."


def test_deduplicates_images(tmp_path, options):
    """Should only call API once for duplicate image references."""
    img = tmp_path / "plot.png"
    img.write_bytes(b"\x89PNG fake")

    content = (
        r"\includegraphics{plot.png}"
        "\n"
        r"\includegraphics[width=0.5\textwidth]{plot.png}"
    )

    mock_genai = MagicMock()
    mock_genai.Client.return_value = MagicMock()

    with patch.dict(
        "sys.modules",
        {"google": MagicMock(), "google.genai": MagicMock()},
    ):
        with patch(
            "latex_llm_cleaner.summarize._call_gemini",
            return_value="Plot data.",
        ) as mock_call:
            import latex_llm_cleaner.summarize as mod

            with patch.dict(
                mod.auto_summarize_figures.__globals__, {"genai": mock_genai}
            ):
                mod.auto_summarize_figures(content, tmp_path, options)

    assert mock_call.call_count == 1


# --- PDF auto-summarization tests ---


def _create_pdf_with_image(path: Path) -> None:
    """Create a PDF with an embedded 200x200 image on page 1."""
    import fitz

    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), "Text before figure.")
    pix = fitz.Pixmap(fitz.csRGB, fitz.IRect(0, 0, 200, 200), 1)
    pix.set_rect(pix.irect, (255, 0, 0, 255))
    page.insert_image(fitz.Rect(100, 150, 400, 450), stream=pix.tobytes("png"))
    page.insert_text((72, 500), "Text after figure.")
    doc.save(str(path))
    doc.close()


@pytest.fixture
def pdf_options():
    return {
        "figure_summary_suffix": "_summary.txt",
        "encoding": "utf-8",
        "verbose": False,
        "google_api_key": "fake-key",
    }


def test_auto_summarize_pdf_generates_summaries(tmp_path, pdf_options):
    """Should generate summary files for embedded images."""
    pdf_path = tmp_path / "doc.pdf"
    _create_pdf_with_image(pdf_path)

    mock_genai = MagicMock()
    mock_genai.Client.return_value = MagicMock()

    with patch(
        "latex_llm_cleaner.summarize._call_gemini_bytes",
        return_value="A red square image.",
    ):
        import latex_llm_cleaner.summarize as mod

        with patch.dict(mod.auto_summarize_pdf.__globals__, {"genai": mock_genai}):
            mod.auto_summarize_pdf(pdf_path, pdf_options)

    summary_path = tmp_path / "doc_page1_image1_summary.txt"
    assert summary_path.is_file()
    assert "red square" in summary_path.read_text()


def test_auto_summarize_pdf_skips_existing(tmp_path, pdf_options):
    """Should skip images that already have summary files."""
    pdf_path = tmp_path / "doc.pdf"
    _create_pdf_with_image(pdf_path)

    # Pre-create summary
    summary_path = tmp_path / "doc_page1_image1_summary.txt"
    summary_path.write_text("Existing summary.")

    mock_genai = MagicMock()
    mock_genai.Client.return_value = MagicMock()

    with patch(
        "latex_llm_cleaner.summarize._call_gemini_bytes",
    ) as mock_call:
        import latex_llm_cleaner.summarize as mod

        with patch.dict(mod.auto_summarize_pdf.__globals__, {"genai": mock_genai}):
            mod.auto_summarize_pdf(pdf_path, pdf_options)

    mock_call.assert_not_called()
    assert summary_path.read_text() == "Existing summary."


def test_auto_summarize_pdf_skips_text_only(tmp_path, pdf_options):
    """Should not generate summaries for text-only PDFs."""
    import fitz

    pdf_path = tmp_path / "text.pdf"
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), "Just text, no figures.")
    doc.save(str(pdf_path))
    doc.close()

    mock_genai = MagicMock()
    mock_genai.Client.return_value = MagicMock()

    with patch(
        "latex_llm_cleaner.summarize._call_gemini_bytes",
    ) as mock_call:
        import latex_llm_cleaner.summarize as mod

        with patch.dict(mod.auto_summarize_pdf.__globals__, {"genai": mock_genai}):
            mod.auto_summarize_pdf(pdf_path, pdf_options)

    mock_call.assert_not_called()
