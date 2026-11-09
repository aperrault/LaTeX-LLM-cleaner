"""Integration test using the fixtures directory."""

from pathlib import Path

from latex_llm_cleaner.pipeline import run_pipeline

FIXTURES = Path(__file__).parent / "fixtures"


def test_full_pipeline():
    content = (FIXTURES / "main.tex").read_text()
    options = {
        "flatten": True,
        "comments": True,
        "bibliography": True,
        "encoding": "utf-8",
        "verbose": False,
    }
    result = run_pipeline(content, FIXTURES, options)

    # Flattening happened
    assert "\\section{Introduction}" in result
    assert "This is the introduction." in result
    assert "\\section{Methods}" in result
    assert "\\input{" not in result
    assert "\\include{" not in result or "\\include{" not in result.split("thebibliography")[0]

    # Comments removed
    assert "% This comment should be removed" not in result
    assert "% TODO: expand this section" not in result
    assert "% cite needed" not in result

    # Bibliography inlined
    assert "\\begin{thebibliography}" in result
    assert "\\bibitem{smith2020}" in result
    assert "\\bibitem{doe2021}" in result
    assert "\\bibliography{refs}" not in result
    assert "\\bibliographystyle{" not in result

    # Figures pass through untouched: the path points the reader at the file
    assert "\\includegraphics[width=0.8\\textwidth]{figs/result.png}" in result
    assert "\\label{fig:result}" in result


def test_all_disabled():
    content = (FIXTURES / "main.tex").read_text()
    options = {
        "flatten": False,
        "comments": False,
        "macros": False,
        "bibliography": False,
        "encoding": "utf-8",
        "verbose": False,
    }
    result = run_pipeline(content, FIXTURES, options)
    assert result == content
