"""Tests for bibliography inlining."""

from pathlib import Path

from latex_llm_cleaner.bibliography import inline_bibliography

OPTS = {"verbose": False, "encoding": "utf-8"}

SAMPLE_BIB = """\
@article{smith2020,
  author = {John Smith},
  title = {A Great Paper},
  journal = {Journal of Things},
  year = {2020},
  volume = {1},
  pages = {1--10},
}

@inproceedings{doe2021,
  author = {Jane Doe},
  title = {Another Paper},
  booktitle = {Conference on Stuff},
  year = {2021},
  pages = {100--110},
}
"""


def test_basic_bibliography(tmp_path):
    (tmp_path / "refs.bib").write_text(SAMPLE_BIB)
    content = (
        "As shown by \\cite{smith2020}.\n"
        "\\bibliographystyle{plain}\n"
        "\\bibliography{refs}"
    )
    result = inline_bibliography(content, tmp_path, OPTS)
    assert "\\begin{thebibliography}" in result
    assert "\\bibitem{smith2020}" in result
    assert "John Smith" in result
    assert "\\bibliography{" not in result
    assert "\\bibliographystyle{" not in result


def test_multiple_citations(tmp_path):
    (tmp_path / "refs.bib").write_text(SAMPLE_BIB)
    content = (
        "See \\cite{smith2020} and \\citep{doe2021}.\n"
        "\\bibliography{refs}"
    )
    result = inline_bibliography(content, tmp_path, OPTS)
    assert "\\bibitem{smith2020}" in result
    assert "\\bibitem{doe2021}" in result


def test_multi_key_cite(tmp_path):
    (tmp_path / "refs.bib").write_text(SAMPLE_BIB)
    content = "See \\cite{smith2020,doe2021}.\n\\bibliography{refs}"
    result = inline_bibliography(content, tmp_path, OPTS)
    assert "\\bibitem{smith2020}" in result
    assert "\\bibitem{doe2021}" in result


def test_nocite_star(tmp_path):
    (tmp_path / "refs.bib").write_text(SAMPLE_BIB)
    content = "\\nocite{*}\n\\bibliography{refs}"
    result = inline_bibliography(content, tmp_path, OPTS)
    assert "\\bibitem{smith2020}" in result
    assert "\\bibitem{doe2021}" in result


def test_addbibresource(tmp_path):
    (tmp_path / "refs.bib").write_text(SAMPLE_BIB)
    content = (
        "See \\autocite{smith2020}.\n"
        "\\addbibresource{refs.bib}"
    )
    result = inline_bibliography(content, tmp_path, OPTS)
    assert "\\bibitem{smith2020}" in result


def test_multiple_bib_files(tmp_path):
    bib1 = '@article{a1, author={A}, title={T1}, year={2020}}\n'
    bib2 = '@article{b1, author={B}, title={T2}, year={2021}}\n'
    (tmp_path / "one.bib").write_text(bib1)
    (tmp_path / "two.bib").write_text(bib2)
    content = "\\cite{a1} \\cite{b1}\n\\bibliography{one,two}"
    result = inline_bibliography(content, tmp_path, OPTS)
    assert "\\bibitem{a1}" in result
    assert "\\bibitem{b1}" in result


def test_no_bibliography_command():
    content = "Just text, no bibliography."
    result = inline_bibliography(content, Path("."), OPTS)
    assert result == content


def test_missing_bib_file(tmp_path, capsys):
    content = "\\cite{foo}\n\\bibliography{missing}"
    result = inline_bibliography(content, tmp_path, OPTS)
    assert "not found" in capsys.readouterr().err


def test_uncited_entries_excluded(tmp_path):
    (tmp_path / "refs.bib").write_text(SAMPLE_BIB)
    content = "See \\cite{smith2020}.\n\\bibliography{refs}"
    result = inline_bibliography(content, tmp_path, OPTS)
    assert "\\bibitem{smith2020}" in result
    assert "\\bibitem{doe2021}" not in result
