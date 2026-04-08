"""Tests for OMML to LaTeX conversion."""

from xml.etree.ElementTree import fromstring

from latex_llm_cleaner.omml import omml_element_to_latex, _normalize_math_text

_NS = "http://schemas.openxmlformats.org/officeDocument/2006/math"


def _omath(inner: str) -> str:
    """Wrap inner OMML XML in an oMath element with namespace."""
    return f'<m:oMath xmlns:m="{_NS}">{inner}</m:oMath>'


def _omath_para(inner: str) -> str:
    """Wrap inner OMML XML in an oMathPara element."""
    return f'<m:oMathPara xmlns:m="{_NS}"><m:oMath>{inner}</m:oMath></m:oMathPara>'


def _r(text: str) -> str:
    """Create an OMML run element."""
    return f"<m:r><m:t>{text}</m:t></m:r>"


class TestSimpleText:
    def test_single_variable(self):
        el = fromstring(_omath(_r("x")))
        assert omml_element_to_latex(el) == "$x$"

    def test_multiple_runs(self):
        el = fromstring(_omath(_r("a") + _r("+") + _r("b")))
        assert omml_element_to_latex(el) == "$a+b$"

    def test_empty_math(self):
        el = fromstring(_omath(""))
        assert omml_element_to_latex(el) == "$$"


class TestUnicodeNormalization:
    def test_math_italic_Y(self):
        # U+1D44C = Mathematical Italic Capital Y
        el = fromstring(_omath(_r("\U0001D44C")))
        assert omml_element_to_latex(el) == "$Y$"

    def test_math_italic_lowercase(self):
        el = fromstring(_omath(_r("\U0001D44E")))
        assert omml_element_to_latex(el) == "$a$"

    def test_math_italic_it(self):
        # 'it' in math italic
        el = fromstring(_omath(_r("\U0001D456\U0001D461")))
        assert omml_element_to_latex(el) == "$it$"

    def test_greek_alpha(self):
        assert "\\alpha" in _normalize_math_text("\u03B1")

    def test_greek_sigma(self):
        assert "\\sigma" in _normalize_math_text("\u03C3")

    def test_symbol_leq(self):
        assert "\\leq" in _normalize_math_text("\u2264")

    def test_symbol_geq(self):
        assert "\\geq" in _normalize_math_text("\u2265")

    def test_symbol_neq(self):
        assert "\\neq" in _normalize_math_text("\u2260")

    def test_symbol_infty(self):
        assert "\\infty" in _normalize_math_text("\u221E")

    def test_bold_digits(self):
        # U+1D7CE = Mathematical Bold Digit Zero
        assert _normalize_math_text("\U0001D7CE\U0001D7CF") == "01"


class TestSubscript:
    def test_simple_subscript(self):
        xml = _omath(
            "<m:sSub>"
            "  <m:e>" + _r("Y") + "</m:e>"
            "  <m:sub>" + _r("it") + "</m:sub>"
            "</m:sSub>"
        )
        el = fromstring(xml)
        assert omml_element_to_latex(el) == "$Y_{it}$"

    def test_unicode_subscript(self):
        xml = _omath(
            "<m:sSub>"
            "  <m:e>" + _r("\U0001D44C") + "</m:e>"
            "  <m:sub>" + _r("\U0001D456\U0001D461") + "</m:sub>"
            "</m:sSub>"
        )
        el = fromstring(xml)
        assert omml_element_to_latex(el) == "$Y_{it}$"


class TestSuperscript:
    def test_simple_superscript(self):
        xml = _omath(
            "<m:sSup>"
            "  <m:e>" + _r("x") + "</m:e>"
            "  <m:sup>" + _r("2") + "</m:sup>"
            "</m:sSup>"
        )
        el = fromstring(xml)
        assert omml_element_to_latex(el) == "$x^{2}$"


class TestSubSuperscript:
    def test_subsup(self):
        xml = _omath(
            "<m:sSubSup>"
            "  <m:e>" + _r("x") + "</m:e>"
            "  <m:sub>" + _r("i") + "</m:sub>"
            "  <m:sup>" + _r("2") + "</m:sup>"
            "</m:sSubSup>"
        )
        el = fromstring(xml)
        assert omml_element_to_latex(el) == "$x_{i}^{2}$"


class TestFraction:
    def test_simple_fraction(self):
        xml = _omath(
            "<m:f>"
            "  <m:num>" + _r("a") + "</m:num>"
            "  <m:den>" + _r("b") + "</m:den>"
            "</m:f>"
        )
        el = fromstring(xml)
        assert omml_element_to_latex(el) == "$\\frac{a}{b}$"

    def test_nested_fraction(self):
        inner_frac = (
            "<m:f>"
            "  <m:num>" + _r("c") + "</m:num>"
            "  <m:den>" + _r("d") + "</m:den>"
            "</m:f>"
        )
        xml = _omath(
            "<m:f>"
            "  <m:num>" + _r("a") + "</m:num>"
            "  <m:den>" + inner_frac + "</m:den>"
            "</m:f>"
        )
        el = fromstring(xml)
        assert omml_element_to_latex(el) == "$\\frac{a}{\\frac{c}{d}}$"


class TestRadical:
    def test_sqrt(self):
        xml = _omath(
            "<m:rad>"
            "  <m:deg/>"
            "  <m:e>" + _r("x") + "</m:e>"
            "</m:rad>"
        )
        el = fromstring(xml)
        assert omml_element_to_latex(el) == "$\\sqrt{x}$"

    def test_nth_root(self):
        xml = _omath(
            "<m:rad>"
            "  <m:deg>" + _r("3") + "</m:deg>"
            "  <m:e>" + _r("x") + "</m:e>"
            "</m:rad>"
        )
        el = fromstring(xml)
        assert omml_element_to_latex(el) == "$\\sqrt[3]{x}$"


class TestNary:
    def test_sum(self):
        xml = _omath(
            '<m:nary>'
            '  <m:naryPr><m:chr m:val="\u2211"/></m:naryPr>'
            '  <m:sub>' + _r("i=1") + '</m:sub>'
            '  <m:sup>' + _r("n") + '</m:sup>'
            '  <m:e>' + _r("x") + '</m:e>'
            '</m:nary>'
        )
        el = fromstring(xml)
        result = omml_element_to_latex(el)
        assert "\\sum" in result
        assert "_{i=1}" in result
        assert "^{n}" in result

    def test_integral(self):
        xml = _omath(
            '<m:nary>'
            '  <m:naryPr><m:chr m:val="\u222B"/></m:naryPr>'
            '  <m:sub>' + _r("0") + '</m:sub>'
            '  <m:sup>' + _r("1") + '</m:sup>'
            '  <m:e>' + _r("f(x)dx") + '</m:e>'
            '</m:nary>'
        )
        el = fromstring(xml)
        result = omml_element_to_latex(el)
        assert "\\int" in result


class TestDelimiter:
    def test_parentheses(self):
        xml = _omath(
            "<m:d>"
            "  <m:e>" + _r("x+1") + "</m:e>"
            "</m:d>"
        )
        el = fromstring(xml)
        result = omml_element_to_latex(el)
        assert "\\left(" in result
        assert "\\right)" in result
        assert "x+1" in result


class TestAccent:
    def test_hat(self):
        xml = _omath(
            '<m:acc>'
            '  <m:accPr><m:chr m:val="\u0302"/></m:accPr>'
            '  <m:e>' + _r("x") + '</m:e>'
            '</m:acc>'
        )
        el = fromstring(xml)
        assert omml_element_to_latex(el) == "$\\hat{x}$"

    def test_bar(self):
        xml = _omath(
            '<m:acc>'
            '  <m:accPr><m:chr m:val="\u0304"/></m:accPr>'
            '  <m:e>' + _r("x") + '</m:e>'
            '</m:acc>'
        )
        el = fromstring(xml)
        assert omml_element_to_latex(el) == "$\\bar{x}$"


class TestDisplayMath:
    def test_omath_para(self):
        xml = _omath_para(_r("E=mc^2"))
        el = fromstring(xml)
        result = omml_element_to_latex(el)
        assert result.startswith("$$")
        assert result.endswith("$$")
        assert "E=mc^2" in result


class TestMatrix:
    def test_2x2_matrix(self):
        xml = _omath(
            "<m:m>"
            "  <m:mr>"
            "    <m:e>" + _r("a") + "</m:e>"
            "    <m:e>" + _r("b") + "</m:e>"
            "  </m:mr>"
            "  <m:mr>"
            "    <m:e>" + _r("c") + "</m:e>"
            "    <m:e>" + _r("d") + "</m:e>"
            "  </m:mr>"
            "</m:m>"
        )
        el = fromstring(xml)
        result = omml_element_to_latex(el)
        assert "\\begin{pmatrix}" in result
        assert "a & b" in result
        assert "c & d" in result
        assert "\\end{pmatrix}" in result


class TestComplexExpressions:
    def test_subscript_with_comparison(self):
        """Test Y_{it} >= S_{it} style expression."""
        xml = _omath(
            "<m:sSub>"
            "  <m:e>" + _r("Y") + "</m:e>"
            "  <m:sub>" + _r("it") + "</m:sub>"
            "</m:sSub>"
            + _r("\u2265")
            + "<m:sSub>"
            "  <m:e>" + _r("S") + "</m:e>"
            "  <m:sub>" + _r("it") + "</m:sub>"
            "</m:sSub>"
        )
        el = fromstring(xml)
        result = omml_element_to_latex(el)
        assert "Y_{it}" in result
        assert "\\geq" in result
        assert "S_{it}" in result

    def test_fraction_in_subscript(self):
        """Nested structure: fraction inside subscript."""
        frac = (
            "<m:f>"
            "  <m:num>" + _r("a") + "</m:num>"
            "  <m:den>" + _r("b") + "</m:den>"
            "</m:f>"
        )
        xml = _omath(
            "<m:sSub>"
            "  <m:e>" + _r("x") + "</m:e>"
            "  <m:sub>" + frac + "</m:sub>"
            "</m:sSub>"
        )
        el = fromstring(xml)
        result = omml_element_to_latex(el)
        assert "x_{\\frac{a}{b}}" in result
