"""Convert Office MathML (OMML) elements to LaTeX strings.

Works with both xml.etree.ElementTree and lxml element objects via duck typing.
"""

from __future__ import annotations

_OMML_NS = "http://schemas.openxmlformats.org/officeDocument/2006/math"


def _tag(local: str) -> str:
    return f"{{{_OMML_NS}}}{local}"


def _local_tag(element) -> str:
    """Return the local name of an element, stripping any namespace."""
    tag = element.tag
    if "}" in tag:
        return tag.split("}", 1)[1]
    return tag


# ---------------------------------------------------------------------------
# Unicode math character normalization
# ---------------------------------------------------------------------------

# Greek lowercase: alpha through omega
_GREEK_LOWER = {
    "\u03B1": "\\alpha",
    "\u03B2": "\\beta",
    "\u03B3": "\\gamma",
    "\u03B4": "\\delta",
    "\u03B5": "\\epsilon",
    "\u03B6": "\\zeta",
    "\u03B7": "\\eta",
    "\u03B8": "\\theta",
    "\u03B9": "\\iota",
    "\u03BA": "\\kappa",
    "\u03BB": "\\lambda",
    "\u03BC": "\\mu",
    "\u03BD": "\\nu",
    "\u03BE": "\\xi",
    "\u03BF": "o",  # omicron has no LaTeX command
    "\u03C0": "\\pi",
    "\u03C1": "\\rho",
    "\u03C2": "\\varsigma",
    "\u03C3": "\\sigma",
    "\u03C4": "\\tau",
    "\u03C5": "\\upsilon",
    "\u03C6": "\\phi",
    "\u03C7": "\\chi",
    "\u03C8": "\\psi",
    "\u03C9": "\\omega",
}

_GREEK_UPPER = {
    "\u0393": "\\Gamma",
    "\u0394": "\\Delta",
    "\u0398": "\\Theta",
    "\u039B": "\\Lambda",
    "\u039E": "\\Xi",
    "\u03A0": "\\Pi",
    "\u03A3": "\\Sigma",
    "\u03A6": "\\Phi",
    "\u03A8": "\\Psi",
    "\u03A9": "\\Omega",
}

_SYMBOLS = {
    "\u2212": "-",
    "\u00D7": "\\times ",
    "\u00B7": "\\cdot ",
    "\u2264": "\\leq ",
    "\u2265": "\\geq ",
    "\u2260": "\\neq ",
    "\u221E": "\\infty",
    "\u2211": "\\sum",
    "\u220F": "\\prod",
    "\u222B": "\\int",
    "\u2202": "\\partial ",
    "\u2208": "\\in ",
    "\u2209": "\\notin ",
    "\u2282": "\\subset ",
    "\u2286": "\\subseteq ",
    "\u2229": "\\cap ",
    "\u222A": "\\cup ",
    "\u2227": "\\land ",
    "\u2228": "\\lor ",
    "\u00AC": "\\neg ",
    "\u2200": "\\forall ",
    "\u2203": "\\exists ",
    "\u2026": "\\ldots ",
    "\u22EF": "\\cdots ",
    "\u2192": "\\to ",
    "\u21D2": "\\Rightarrow ",
    "\u2190": "\\leftarrow ",
    "\u21D0": "\\Leftarrow ",
    "\u2194": "\\leftrightarrow ",
    "\u21D4": "\\Leftrightarrow ",
    "\u221A": "\\sqrt",
    "\u2248": "\\approx ",
    "\u2261": "\\equiv ",
    "\u00B1": "\\pm ",
    "\u2213": "\\mp ",
    "\u22C5": "\\cdot ",
    "\u2223": "\\mid ",
    "\u2225": "\\parallel ",
    "\u22A5": "\\perp ",
    "\u2220": "\\angle ",
    "\u00B0": "^\\circ",
    "\u2032": "'",
    "\u2033": "''",
}

# Math alphabet ranges: (start_codepoint, length, ascii_start)
# Each range maps consecutive Unicode math codepoints back to ASCII.
_MATH_ALPHA_RANGES = [
    # Bold A-Z, a-z
    (0x1D400, 26, ord("A")),
    (0x1D41A, 26, ord("a")),
    # Italic A-Z, a-z (note: 1D455 is reserved, h is at 210E)
    (0x1D434, 26, ord("A")),
    (0x1D44E, 26, ord("a")),
    # Bold italic A-Z, a-z
    (0x1D468, 26, ord("A")),
    (0x1D482, 26, ord("a")),
    # Script A-Z, a-z
    (0x1D49C, 26, ord("A")),
    (0x1D4B6, 26, ord("a")),
    # Bold script A-Z, a-z
    (0x1D4D0, 26, ord("A")),
    (0x1D4EA, 26, ord("a")),
    # Fraktur A-Z, a-z
    (0x1D504, 26, ord("A")),
    (0x1D51E, 26, ord("a")),
    # Double-struck A-Z, a-z
    (0x1D538, 26, ord("A")),
    (0x1D552, 26, ord("a")),
    # Bold fraktur A-Z, a-z
    (0x1D56C, 26, ord("A")),
    (0x1D586, 26, ord("a")),
    # Sans-serif A-Z, a-z
    (0x1D5A0, 26, ord("A")),
    (0x1D5BA, 26, ord("a")),
    # Sans-serif bold A-Z, a-z
    (0x1D5D4, 26, ord("A")),
    (0x1D5EE, 26, ord("a")),
    # Sans-serif italic A-Z, a-z
    (0x1D608, 26, ord("A")),
    (0x1D622, 26, ord("a")),
    # Sans-serif bold italic A-Z, a-z
    (0x1D63C, 26, ord("A")),
    (0x1D656, 26, ord("a")),
    # Monospace A-Z, a-z
    (0x1D670, 26, ord("A")),
    (0x1D68A, 26, ord("a")),
]

# Digit ranges (bold, double-struck, sans-serif, etc.)
_MATH_DIGIT_RANGES = [
    (0x1D7CE, 10, ord("0")),  # bold
    (0x1D7D8, 10, ord("0")),  # double-struck
    (0x1D7E2, 10, ord("0")),  # sans-serif
    (0x1D7EC, 10, ord("0")),  # sans-serif bold
    (0x1D7F6, 10, ord("0")),  # monospace
]


def _normalize_math_text(text: str) -> str:
    """Map Unicode math characters to plain ASCII/LaTeX equivalents."""
    out = []
    for ch in text:
        # Check symbol table first
        if ch in _SYMBOLS:
            out.append(_SYMBOLS[ch])
            continue
        if ch in _GREEK_LOWER:
            out.append(_GREEK_LOWER[ch])
            continue
        if ch in _GREEK_UPPER:
            out.append(_GREEK_UPPER[ch])
            continue

        cp = ord(ch)

        # Math alphabet ranges
        mapped = False
        for start, length, ascii_start in _MATH_ALPHA_RANGES:
            if start <= cp < start + length:
                out.append(chr(ascii_start + (cp - start)))
                mapped = True
                break
        if mapped:
            continue

        # Digit ranges
        for start, length, ascii_start in _MATH_DIGIT_RANGES:
            if start <= cp < start + length:
                out.append(chr(ascii_start + (cp - start)))
                mapped = True
                break
        if mapped:
            continue

        out.append(ch)
    return "".join(out)


# ---------------------------------------------------------------------------
# OMML element handlers
# ---------------------------------------------------------------------------

def _find(element, local: str):
    """Find first child with the given local tag name."""
    tag = _tag(local)
    return element.find(tag)


def _find_text(element, local: str) -> str:
    """Recursively convert the content of a named child element."""
    child = _find(element, local)
    if child is None:
        return ""
    return _convert(child)


def _handle_r(element) -> str:
    """Text run: extract text from m:t child."""
    t = _find(element, "t")
    if t is not None and t.text:
        return _normalize_math_text(t.text)
    return ""


def _handle_sub(element) -> str:
    """Subscript: base_{sub}."""
    base = _find_text(element, "e")
    sub = _find_text(element, "sub")
    return f"{base}_{{{sub}}}"


def _handle_sup(element) -> str:
    """Superscript: base^{sup}."""
    base = _find_text(element, "e")
    sup = _find_text(element, "sup")
    return f"{base}^{{{sup}}}"


def _handle_subsup(element) -> str:
    """Sub-superscript: base_{sub}^{sup}."""
    base = _find_text(element, "e")
    sub = _find_text(element, "sub")
    sup = _find_text(element, "sup")
    return f"{base}_{{{sub}}}^{{{sup}}}"


def _handle_frac(element) -> str:
    """Fraction: \\frac{num}{den}."""
    num = _find_text(element, "num")
    den = _find_text(element, "den")
    return f"\\frac{{{num}}}{{{den}}}"


def _handle_rad(element) -> str:
    """Radical: \\sqrt{e} or \\sqrt[deg]{e}."""
    deg = _find_text(element, "deg")
    e = _find_text(element, "e")
    if deg:
        return f"\\sqrt[{deg}]{{{e}}}"
    return f"\\sqrt{{{e}}}"


def _handle_nary(element) -> str:
    """N-ary operator: \\sum, \\int, etc."""
    # Determine the operator character from naryPr/chr
    op = "\\sum"
    pr = _find(element, "naryPr")
    if pr is not None:
        chr_el = _find(pr, "chr")
        if chr_el is not None:
            val = chr_el.get(_tag("val")) or chr_el.get("val") or ""
            nary_map = {
                "\u2211": "\\sum",
                "\u220F": "\\prod",
                "\u222B": "\\int",
                "\u222C": "\\iint",
                "\u222D": "\\iiint",
                "\u222E": "\\oint",
                "\u22C0": "\\bigwedge",
                "\u22C1": "\\bigvee",
                "\u22C2": "\\bigcap",
                "\u22C3": "\\bigcup",
            }
            op = nary_map.get(val, "\\sum")

    sub = _find_text(element, "sub")
    sup = _find_text(element, "sup")
    e = _find_text(element, "e")

    result = op
    if sub:
        result += f"_{{{sub}}}"
    if sup:
        result += f"^{{{sup}}}"
    if e:
        result += f" {e}"
    return result


def _handle_d(element) -> str:
    """Delimiter: \\left( ... \\right)."""
    beg = "("
    end = ")"
    sep = "|"
    pr = _find(element, "dPr")
    if pr is not None:
        beg_el = _find(pr, "begChr")
        if beg_el is not None:
            beg = beg_el.get(_tag("val")) or beg_el.get("val") or "("
        end_el = _find(pr, "endChr")
        if end_el is not None:
            end = end_el.get(_tag("val")) or end_el.get("val") or ")"
        sep_el = _find(pr, "sepChr")
        if sep_el is not None:
            sep = sep_el.get(_tag("val")) or sep_el.get("val") or "|"

    # Map special delimiter characters
    delim_map = {
        "{": "\\{",
        "}": "\\}",
        "\u2329": "\\langle",
        "\u232A": "\\rangle",
        "\u27E8": "\\langle",
        "\u27E9": "\\rangle",
        "|": "|",
        "\u2016": "\\|",
        "": ".",
    }
    beg_latex = delim_map.get(beg, beg)
    end_latex = delim_map.get(end, end)

    # Collect m:e children
    parts = []
    for child in element:
        if _local_tag(child) == "e":
            parts.append(_convert(child))

    content = f" {sep} ".join(parts) if len(parts) > 1 else (parts[0] if parts else "")
    return f"\\left{beg_latex} {content} \\right{end_latex}"


def _handle_func(element) -> str:
    """Function application: \\fname{arg}."""
    fname_el = _find(element, "fName")
    fname = _convert(fname_el) if fname_el is not None else ""
    # Common function names
    known_funcs = {
        "sin", "cos", "tan", "sec", "csc", "cot",
        "arcsin", "arccos", "arctan",
        "sinh", "cosh", "tanh",
        "log", "ln", "exp", "lim", "max", "min",
        "sup", "inf", "det", "dim", "gcd", "arg",
    }
    fname_clean = fname.strip()
    if fname_clean.lower() in known_funcs:
        fname_clean = f"\\{fname_clean.lower()}"
    e = _find_text(element, "e")
    return f"{fname_clean}{e}"


def _handle_acc(element) -> str:
    """Accent: \\hat{e}, \\bar{e}, etc."""
    accent_map = {
        "\u0302": "\\hat",
        "\u0304": "\\bar",
        "\u0303": "\\tilde",
        "\u0307": "\\dot",
        "\u0308": "\\ddot",
        "\u20D7": "\\vec",
        "\u0305": "\\overline",
    }
    cmd = "\\hat"
    pr = _find(element, "accPr")
    if pr is not None:
        chr_el = _find(pr, "chr")
        if chr_el is not None:
            val = chr_el.get(_tag("val")) or chr_el.get("val") or ""
            cmd = accent_map.get(val, "\\hat")
    e = _find_text(element, "e")
    return f"{cmd}{{{e}}}"


def _handle_bar(element) -> str:
    """Bar: \\overline{e} or \\underline{e}."""
    pos = "top"
    pr = _find(element, "barPr")
    if pr is not None:
        pos_el = _find(pr, "pos")
        if pos_el is not None:
            pos = pos_el.get(_tag("val")) or pos_el.get("val") or "top"
    e = _find_text(element, "e")
    if pos == "bot":
        return f"\\underline{{{e}}}"
    return f"\\overline{{{e}}}"


def _handle_matrix(element) -> str:
    """Matrix: \\begin{pmatrix} ... \\end{pmatrix}."""
    rows = []
    for child in element:
        if _local_tag(child) == "mr":
            cells = []
            for cell in child:
                if _local_tag(cell) == "e":
                    cells.append(_convert(cell))
            rows.append(" & ".join(cells))
    content = " \\\\ ".join(rows)
    return f"\\begin{{pmatrix}} {content} \\end{{pmatrix}}"


def _handle_eqarr(element) -> str:
    """Equation array: \\begin{aligned} ... \\end{aligned}."""
    lines = []
    for child in element:
        if _local_tag(child) == "e":
            lines.append(_convert(child))
    content = " \\\\ ".join(lines)
    return f"\\begin{{aligned}} {content} \\end{{aligned}}"


def _handle_limlow(element) -> str:
    """Lower limit: base_{lim}."""
    e = _find_text(element, "e")
    lim = _find_text(element, "lim")
    return f"{e}_{{{lim}}}"


def _handle_limupp(element) -> str:
    """Upper limit: base^{lim}."""
    e = _find_text(element, "e")
    lim = _find_text(element, "lim")
    return f"{e}^{{{lim}}}"


def _handle_groupchr(element) -> str:
    """Grouping character: \\underbrace{e} or \\overbrace{e}."""
    chr_val = "\u23DF"  # bottom curly bracket default
    pr = _find(element, "groupChrPr")
    if pr is not None:
        chr_el = _find(pr, "chr")
        if chr_el is not None:
            chr_val = chr_el.get(_tag("val")) or chr_el.get("val") or chr_val
    e = _find_text(element, "e")
    if chr_val in ("\u23DE", "\uFE37"):  # top curly bracket
        return f"\\overbrace{{{e}}}"
    return f"\\underbrace{{{e}}}"


def _handle_spre(element) -> str:
    """Pre-script: {}_{pre-sub}^{pre-sup} base."""
    sub = _find_text(element, "sub")
    sup = _find_text(element, "sup")
    e = _find_text(element, "e")
    return f"{{}}_{{{sub}}}^{{{sup}}}{e}"


def _handle_container(element) -> str:
    """Box/borderBox: just recurse into m:e child."""
    return _find_text(element, "e")


# Handler dispatch table
_HANDLERS: dict[str, object] = {
    "r": _handle_r,
    "sSub": _handle_sub,
    "sSup": _handle_sup,
    "sSubSup": _handle_subsup,
    "f": _handle_frac,
    "rad": _handle_rad,
    "nary": _handle_nary,
    "d": _handle_d,
    "func": _handle_func,
    "acc": _handle_acc,
    "bar": _handle_bar,
    "m": _handle_matrix,
    "eqArr": _handle_eqarr,
    "limLow": _handle_limlow,
    "limUpp": _handle_limupp,
    "groupChr": _handle_groupchr,
    "sPre": _handle_spre,
    "box": _handle_container,
    "borderBox": _handle_container,
}


def _convert(element) -> str:
    """Recursively convert an OMML element to LaTeX."""
    local = _local_tag(element)

    handler = _HANDLERS.get(local)
    if handler:
        return handler(element)

    # Skip property elements
    if local.endswith("Pr"):
        return ""

    # Default: recurse into children
    parts = []
    for child in element:
        parts.append(_convert(child))
    return "".join(parts)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def omml_element_to_latex(element) -> str:
    """Convert an oMath or oMathPara element to a delimited LaTeX string.

    Returns ``$...$`` for inline math (oMath) or ``$$...$$`` for display math
    (oMathPara).
    """
    local = _local_tag(element)
    if local == "oMathPara":
        # Display math: may contain multiple oMath children
        parts = []
        for child in element:
            if _local_tag(child) == "oMath":
                parts.append(_convert(child))
        body = " \\\\ ".join(parts)
        return f"$${body}$$"
    elif local == "oMath":
        body = _convert(element)
        return f"${body}$"
    else:
        # Fallback for unexpected wrapper
        return f"${_convert(element)}$"
