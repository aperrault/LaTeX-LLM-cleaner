"""Tests for macro expansion."""

from pathlib import Path

import pytest

from latex_llm_cleaner.macros import expand_macros, _find_brace_group, _resolve_conditionals


@pytest.fixture
def opts():
    return {"verbose": False}


# ---------------------------------------------------------------------------
# Brace matching
# ---------------------------------------------------------------------------


class TestFindBraceGroup:
    def test_simple(self):
        assert _find_brace_group("{hello}", 0) == ("hello", 7)

    def test_nested(self):
        assert _find_brace_group("{a{b}c}", 0) == ("a{b}c", 7)

    def test_escaped_brace(self):
        assert _find_brace_group(r"{a\}b}", 0) == (r"a\}b", 6)

    def test_no_opening(self):
        assert _find_brace_group("hello", 0) is None

    def test_unmatched(self):
        assert _find_brace_group("{hello", 0) is None

    def test_offset(self):
        assert _find_brace_group("xx{hi}yy", 2) == ("hi", 6)


# ---------------------------------------------------------------------------
# Conditional resolution
# ---------------------------------------------------------------------------


class TestResolveConditionals:
    def test_ifodd_1_then_branch(self):
        content = "\\ifodd 1\nTHEN\n\\else\nELSE\n\\fi"
        result = _resolve_conditionals(content)
        assert "THEN" in result
        assert "ELSE" not in result

    def test_ifodd_1_no_else(self):
        content = "\\ifodd 1\nTHEN\n\\fi"
        result = _resolve_conditionals(content)
        assert "THEN" in result

    def test_preserves_surrounding(self):
        content = "before\n\\ifodd 1\nmiddle\n\\fi\nafter"
        result = _resolve_conditionals(content)
        assert "before" in result
        assert "middle" in result
        assert "after" in result


# ---------------------------------------------------------------------------
# 0-arg macros: \newcommand
# ---------------------------------------------------------------------------


class TestZeroArgNewcommand:
    def test_simple(self, opts):
        content = "\\newcommand{\\E}{\\mathbb{E}}\n$\\E[X]$"
        result = expand_macros(content, Path("."), opts)
        assert "\\mathbb{E}" in result
        assert "\\newcommand" not in result

    def test_with_braces_spacing(self, opts):
        """\\E{} should expand (empty braces consumed as TeX spacing)."""
        content = "\\newcommand{\\E}{\\mathbb{E}}\nthe \\E{} value"
        result = expand_macros(content, Path("."), opts)
        assert "\\mathbb{E}" in result

    def test_renewcommand(self, opts):
        content = (
            "\\newcommand{\\foo}{old}\n"
            "\\renewcommand{\\foo}{new}\n"
            "\\foo"
        )
        result = expand_macros(content, Path("."), opts)
        assert "new" in result
        assert "old" not in result

    def test_providecommand_skips_existing(self, opts):
        content = (
            "\\newcommand{\\foo}{first}\n"
            "\\providecommand{\\foo}{second}\n"
            "\\foo"
        )
        result = expand_macros(content, Path("."), opts)
        assert "first" in result
        assert "second" not in result


# ---------------------------------------------------------------------------
# 0-arg macros: \def
# ---------------------------------------------------------------------------


class TestZeroArgDef:
    def test_simple(self, opts):
        content = "\\def\\eps{{\\epsilon}}\n$\\eps$"
        result = expand_macros(content, Path("."), opts)
        assert "{\\epsilon}" in result
        assert "\\def" not in result

    def test_numeric_name(self, opts):
        content = "\\def\\1{\\bm{1}}\n$\\1$"
        result = expand_macros(content, Path("."), opts)
        assert "\\bm{1}" in result


# ---------------------------------------------------------------------------
# Macros with arguments
# ---------------------------------------------------------------------------


class TestArgsExpansion:
    def test_newcommand_one_arg(self, opts):
        content = "\\newcommand{\\newterm}[1]{{\\bf #1}}\n\\newterm{hello}"
        result = expand_macros(content, Path("."), opts)
        assert "{\\bf hello}" in result

    def test_def_one_arg(self, opts):
        content = "\\def\\figref#1{figure~\\ref{#1}}\n\\figref{fig:1}"
        result = expand_macros(content, Path("."), opts)
        assert "figure~\\ref{fig:1}" in result

    def test_def_two_args(self, opts):
        content = (
            "\\def\\twofigref#1#2{figures \\ref{#1} and \\ref{#2}}\n"
            "\\twofigref{fig:a}{fig:b}"
        )
        result = expand_macros(content, Path("."), opts)
        assert "figures \\ref{fig:a} and \\ref{fig:b}" in result

    def test_def_four_args(self, opts):
        content = (
            "\\def\\quadfigref#1#2#3#4{figures \\ref{#1}, \\ref{#2}, "
            "\\ref{#3} and \\ref{#4}}\n"
            "\\quadfigref{a}{b}{c}{d}"
        )
        result = expand_macros(content, Path("."), opts)
        assert "figures \\ref{a}, \\ref{b}, \\ref{c} and \\ref{d}" in result

    def test_optional_arg_with_default(self, opts):
        content = (
            "\\newcommand{\\greeting}[2][World]{Hello #1, #2!}\n"
            "\\greeting{bye}\n"
            "\\greeting[Earth]{bye}"
        )
        result = expand_macros(content, Path("."), opts)
        assert "Hello World, bye!" in result
        assert "Hello Earth, bye!" in result

    def test_missing_args_leaves_unchanged(self, opts):
        content = "\\def\\foo#1{bar #1}\n\\foo"
        result = expand_macros(content, Path("."), opts)
        # Can't extract argument, macro usage left as-is
        assert "\\foo" in result


# ---------------------------------------------------------------------------
# \DeclareMathOperator
# ---------------------------------------------------------------------------


class TestDeclareMathOperator:
    def test_basic(self, opts):
        content = "\\DeclareMathOperator{\\sign}{sign}\n$\\sign(x)$"
        result = expand_macros(content, Path("."), opts)
        assert "\\operatorname{sign}" in result
        assert "\\DeclareMathOperator" not in result

    def test_star(self, opts):
        content = "\\DeclareMathOperator*{\\argmax}{arg\\,max}\n$\\argmax_x$"
        result = expand_macros(content, Path("."), opts)
        assert "\\operatorname*{arg\\,max}" in result


# ---------------------------------------------------------------------------
# Nested macros (multi-pass)
# ---------------------------------------------------------------------------


class TestNestedExpansion:
    def test_two_levels(self, opts):
        content = (
            "\\newcommand{\\tens}[1]{\\bm{\\mathsfit{#1}}}\n"
            "\\def\\tA{{\\tens{A}}}\n"
            "$\\tA$"
        )
        result = expand_macros(content, Path("."), opts)
        assert "\\bm{\\mathsfit{A}}" in result

    def test_three_levels(self, opts):
        content = (
            "\\newcommand{\\inner}{X}\n"
            "\\newcommand{\\mid}{\\inner}\n"
            "\\newcommand{\\outer}{\\mid}\n"
            "\\outer"
        )
        result = expand_macros(content, Path("."), opts)
        assert result.strip() == "X"


# ---------------------------------------------------------------------------
# Definition removal
# ---------------------------------------------------------------------------


class TestDefinitionRemoval:
    def test_newcommand_removed(self, opts):
        content = "\\newcommand{\\foo}{bar}\ntext"
        result = expand_macros(content, Path("."), opts)
        assert "\\newcommand" not in result
        assert "text" in result

    def test_def_removed(self, opts):
        content = "\\def\\foo{bar}\ntext"
        result = expand_macros(content, Path("."), opts)
        assert "\\def" not in result

    def test_declaremathalphabet_removed(self, opts):
        content = (
            "\\DeclareMathAlphabet{\\mathsfit}{\\encodingdefault}"
            "{\\sfdefault}{m}{sl}\ntext"
        )
        result = expand_macros(content, Path("."), opts)
        assert "\\DeclareMathAlphabet" not in result
        assert "text" in result

    def test_setmathalphabet_removed(self, opts):
        content = (
            "\\SetMathAlphabet{\\mathsfit}{bold}{\\encodingdefault}"
            "{\\sfdefault}{bx}{n}\ntext"
        )
        result = expand_macros(content, Path("."), opts)
        assert "\\SetMathAlphabet" not in result


# ---------------------------------------------------------------------------
# Verbatim protection
# ---------------------------------------------------------------------------


class TestVerbatimProtection:
    def test_verbatim_env_untouched(self, opts):
        content = (
            "\\newcommand{\\foo}{bar}\n"
            "\\begin{verbatim}\n\\foo\n\\end{verbatim}\n"
            "\\foo"
        )
        result = expand_macros(content, Path("."), opts)
        assert "\\begin{verbatim}\n\\foo\n\\end{verbatim}" in result
        # Outside verbatim should be expanded
        lines = result.strip().split("\n")
        last_line = lines[-1]
        assert last_line == "bar"

    def test_lstlisting_untouched(self, opts):
        content = (
            "\\newcommand{\\foo}{bar}\n"
            "\\begin{lstlisting}\n\\foo\n\\end{lstlisting}"
        )
        result = expand_macros(content, Path("."), opts)
        assert "\\foo" in result


# ---------------------------------------------------------------------------
# Conditional handling in definitions
# ---------------------------------------------------------------------------


class TestConditionalDefinitions:
    def test_ifodd_1_picks_then_branch(self, opts):
        content = (
            "\\ifodd 1\n"
            "\\newcommand{\\mrev}[1]{{\\color{magenta}#1}}\n"
            "\\else\n"
            "\\newcommand{\\mrev}[1]{#1}\n"
            "\\fi\n"
            "\\mrev{text}"
        )
        result = expand_macros(content, Path("."), opts)
        assert "\\color{magenta}" in result


# ---------------------------------------------------------------------------
# Longer-name priority
# ---------------------------------------------------------------------------


class TestNamePriority:
    def test_longer_name_matched_first(self, opts):
        """\\rvepsilon should not be partially matched as \\rv + epsilon."""
        content = (
            "\\def\\rv{WRONG}\n"
            "\\def\\rvepsilon{{\\mathbf{\\epsilon}}}\n"
            "$\\rvepsilon$"
        )
        result = expand_macros(content, Path("."), opts)
        assert "\\mathbf{\\epsilon}" in result
        assert "WRONG" not in result


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestEdgeCases:
    def test_newcommand_star_variant(self, opts):
        content = "\\newcommand*{\\foo}{bar}\n\\foo"
        result = expand_macros(content, Path("."), opts)
        assert "bar" in result
        assert "\\newcommand" not in result

    def test_newcommand_without_braces_around_name(self, opts):
        content = "\\newcommand\\foo{bar}\n\\foo"
        result = expand_macros(content, Path("."), opts)
        assert "bar" in result

    def test_empty_content(self, opts):
        result = expand_macros("", Path("."), opts)
        assert result == ""

    def test_no_macros(self, opts):
        content = "Just some text with $x^2$."
        result = expand_macros(content, Path("."), opts)
        assert result == content

    def test_let_commands_left_alone(self, opts):
        content = "\\let\\ab\\allowbreak\n\\ab"
        result = expand_macros(content, Path("."), opts)
        assert "\\let\\ab\\allowbreak" in result


# ---------------------------------------------------------------------------
# \usepackage stripping
# ---------------------------------------------------------------------------


class TestUsepackageStripping:
    def test_stripped_by_default(self, opts):
        content = "\\usepackage{amsmath}\ntext"
        result = expand_macros(content, Path("."), opts)
        assert "\\usepackage" not in result
        assert "text" in result

    def test_with_options(self, opts):
        content = "\\usepackage[utf8]{inputenc}\ntext"
        result = expand_macros(content, Path("."), opts)
        assert "\\usepackage" not in result

    def test_keep_usepackage_flag(self, opts):
        opts["keep_usepackage"] = True
        content = "\\usepackage{amsmath}\ntext"
        result = expand_macros(content, Path("."), opts)
        assert "\\usepackage{amsmath}" in result

    def test_multiple_packages(self, opts):
        content = (
            "\\usepackage{amsmath}\n"
            "\\usepackage[ruled]{algorithm2e}\n"
            "\\usepackage{hyperref}\n"
            "text"
        )
        result = expand_macros(content, Path("."), opts)
        assert "\\usepackage" not in result
        assert "text" in result
