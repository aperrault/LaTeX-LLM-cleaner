"""Tests for comment removal."""

from pathlib import Path

from latex_llm_cleaner.comments import remove_comments

OPTS = {"verbose": False}
BASE = Path(".")


def test_simple_line_comment():
    content = "Hello % this is a comment\nWorld"
    result = remove_comments(content, BASE, OPTS)
    assert result == "Hello\nWorld"


def test_comment_only_line_removed():
    content = "Line 1\n% full comment\nLine 2"
    result = remove_comments(content, BASE, OPTS)
    assert result == "Line 1\nLine 2"


def test_escaped_percent_preserved():
    content = r"50\% of the time"
    result = remove_comments(content, BASE, OPTS)
    assert result == r"50\% of the time"


def test_double_backslash_then_percent():
    # \\ is a line break, so % starts a comment
    content = "text\\\\% comment"
    result = remove_comments(content, BASE, OPTS)
    assert result == "text\\\\"


def test_verbatim_preserved():
    content = "\\begin{verbatim}\n% not a comment\n\\end{verbatim}"
    result = remove_comments(content, BASE, OPTS)
    assert "% not a comment" in result


def test_lstlisting_preserved():
    content = "\\begin{lstlisting}\n% not a comment\n\\end{lstlisting}"
    result = remove_comments(content, BASE, OPTS)
    assert "% not a comment" in result


def test_minted_preserved():
    content = "\\begin{minted}{python}\n# comment % with percent\n\\end{minted}"
    result = remove_comments(content, BASE, OPTS)
    assert "% with percent" in result


def test_verb_inline_preserved():
    content = "Use \\verb|%| for comments"
    result = remove_comments(content, BASE, OPTS)
    assert "\\verb|%|" in result


def test_comment_environment():
    content = "Before\n\\begin{comment}\nHidden text\n\\end{comment}\nAfter"
    result = remove_comments(content, BASE, OPTS)
    assert "Hidden text" not in result
    assert "Before" in result
    assert "After" in result


def test_no_trailing_whitespace():
    content = "code  % comment"
    result = remove_comments(content, BASE, OPTS)
    assert result == "code"


def test_multiple_percent_signs():
    content = "a % b % c"
    result = remove_comments(content, BASE, OPTS)
    assert result == "a"


def test_empty_input():
    assert remove_comments("", BASE, OPTS) == ""


def test_indented_comment():
    content = "  % indented comment\ncode"
    result = remove_comments(content, BASE, OPTS)
    assert result == "code"
