"""Tests for include flattening."""

from pathlib import Path

from latex_llm_cleaner.flatten import flatten_includes

OPTS = {"verbose": False, "encoding": "utf-8"}


def test_simple_input(tmp_path):
    (tmp_path / "chapter.tex").write_text("Chapter content")
    content = "Before\n\\input{chapter}\nAfter"
    result = flatten_includes(content, tmp_path, OPTS)
    assert result == "Before\nChapter content\nAfter"


def test_input_without_extension(tmp_path):
    (tmp_path / "chapter.tex").write_text("Chapter content")
    content = "\\input{chapter}"
    result = flatten_includes(content, tmp_path, OPTS)
    assert result == "Chapter content"


def test_input_with_extension(tmp_path):
    (tmp_path / "chapter.tex").write_text("Chapter content")
    content = "\\input{chapter.tex}"
    result = flatten_includes(content, tmp_path, OPTS)
    assert result == "Chapter content"


def test_include_adds_clearpage(tmp_path):
    (tmp_path / "chapter.tex").write_text("Chapter content")
    content = "\\include{chapter}"
    result = flatten_includes(content, tmp_path, OPTS)
    assert result == "\\clearpage\nChapter content\n\\clearpage"


def test_nested_input(tmp_path):
    (tmp_path / "outer.tex").write_text("Outer\\input{inner}")
    (tmp_path / "inner.tex").write_text("Inner")
    content = "\\input{outer}"
    result = flatten_includes(content, tmp_path, OPTS)
    assert result == "OuterInner"


def test_cycle_detection(tmp_path):
    (tmp_path / "a.tex").write_text("A\\input{b}")
    (tmp_path / "b.tex").write_text("B\\input{a}")
    content = "\\input{a}"
    result = flatten_includes(content, tmp_path, OPTS)
    # Should not infinitely recurse; the cycle reference stays unchanged
    assert "A" in result
    assert "B" in result


def test_missing_file_warning(tmp_path, capsys):
    content = "\\input{nonexistent}"
    result = flatten_includes(content, tmp_path, OPTS)
    assert result == "\\input{nonexistent}"
    assert "not found" in capsys.readouterr().err


def test_includeonly(tmp_path):
    (tmp_path / "chap1.tex").write_text("Chapter 1")
    (tmp_path / "chap2.tex").write_text("Chapter 2")
    content = "\\includeonly{chap1}\n\\include{chap1}\n\\include{chap2}"
    result = flatten_includes(content, tmp_path, OPTS)
    assert "Chapter 1" in result
    assert "Chapter 2" not in result


def test_subfile(tmp_path):
    subfile = (
        "\\documentclass[main]{subfiles}\n"
        "\\begin{document}\nSubfile content\n\\end{document}"
    )
    (tmp_path / "sub.tex").write_text(subfile)
    content = "\\subfile{sub}"
    result = flatten_includes(content, tmp_path, OPTS)
    assert result == "Subfile content"


def test_subdirectory_input(tmp_path):
    subdir = tmp_path / "chapters"
    subdir.mkdir()
    (subdir / "intro.tex").write_text("Intro content")
    content = "\\input{chapters/intro}"
    result = flatten_includes(content, tmp_path, OPTS)
    assert result == "Intro content"
