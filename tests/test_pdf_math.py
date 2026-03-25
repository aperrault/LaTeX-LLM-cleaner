"""Tests for math/equation cleanup in PDF extraction."""

from latex_llm_cleaner.pdf import _clean_markdown


def test_italic_stripping():
    """Italic markers should be removed for LLM consumption."""
    garbled = "predictor _Y_ = _gw_ ( _R_ )"
    result = _clean_markdown(garbled)
    assert "_Y_" not in result
    assert "_gw_" not in result
    assert "Y" in result and "gw" in result


def test_bold_preserved():
    """Bold markers should be preserved."""
    text = "**Definition 2.2.1** is important"
    result = _clean_markdown(text)
    assert "**Definition 2.2.1**" in result


def test_merge_hat_diacritic():
    garbled = "ˆ Y"
    result = _clean_markdown(garbled)
    assert "ˆY" in result


def test_merge_check_diacritic():
    garbled = "ˇ x"
    result = _clean_markdown(garbled)
    assert "ˇx" in result


def test_bracket_hat_cleaned():
    assert "[ˆ]" not in _clean_markdown("Y[ˆ]")
    assert "^" in _clean_markdown("Y[ˆ]")


def test_bracket_sequence_cleaned():
    garbled = "[suffices][to][minimize][the]"
    result = _clean_markdown(garbled)
    assert "[suffices]" not in result
    assert "suffices" in result
    assert "minimize" in result


def test_bracket_sequence_has_spaces():
    garbled = "[non-descendant][features][of]"
    result = _clean_markdown(garbled)
    assert "non-descendant features of" in result


def test_citations_preserved():
    text = "As shown in [97] and [98]."
    result = _clean_markdown(text)
    assert "[97]" in result
    assert "[98]" in result


def test_table_structure_preserved():
    """Table pipe structure should survive, even if italics are stripped."""
    table = "| _Method_ | _Accuracy_ |"
    result = _clean_markdown(table)
    assert "|" in result
    assert "Method" in result
    assert "Accuracy" in result


def test_parenthesized_index():
    garbled = "[(] [i] [)]"
    result = _clean_markdown(garbled)
    assert "(i)" in result


def test_real_cf_equation():
    """The CF definition equation should be readable after cleanup."""
    garbled = (
        "Pr _{Y_[ˆ] _A←a_ ( _U_ ) = _y|X_ = _x, A_ = _a}_ = "
        "Pr _{Y_[ˆ] _A←a′_ ( _U_ ) = _y|X_ = _x, A_ = _a}_, "
        "∀y ∈Y, a[′] ∈A._"
    )
    result = _clean_markdown(garbled)
    # No italic markers
    assert "_Y_" not in result
    assert "_U_" not in result
    # No bracket hat
    assert "[ˆ]" not in result
    # Key symbols preserved
    assert "Pr" in result
    assert "←" in result
    assert "∀" in result
    assert "∈" in result


def test_empty_input():
    assert _clean_markdown("") == ""


def test_no_math():
    plain = "Regular paragraph with no math at all."
    assert _clean_markdown(plain) == plain
