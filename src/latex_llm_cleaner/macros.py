"""Expand user-defined LaTeX macros inline and remove definitions."""

import re
import sys
from dataclasses import dataclass
from pathlib import Path

from .comments import VERBATIM_ENVS, mask_verbatim, unmask_verbatim


@dataclass
class Macro:
    name: str  # command name without backslash, e.g. "figref"
    num_args: int  # 0-9
    default_opt: str | None  # default value for optional first arg
    body: str  # replacement text with #1, #2 placeholders


def expand_macros(content: str, base_dir: Path, options: dict) -> str:
    verbose = options.get("verbose", False)

    # Protect verbatim environments from expansion
    content, verbatim_store = mask_verbatim(content)

    # Resolve \ifodd 1 ... \else ... \fi blocks
    content = _resolve_conditionals(content)

    # Parse all macro definitions
    macros: dict[str, Macro] = {}
    spans_to_remove: list[tuple[int, int]] = []

    for parser in (_parse_newcommand, _parse_def, _parse_declaremathoperator):
        for span, macro, kind in parser(content):
            if kind == "provide" and macro.name in macros:
                spans_to_remove.append(span)
                continue
            macros[macro.name] = macro
            spans_to_remove.append(span)

    if verbose:
        print(f"  Found {len(macros)} macro definitions", file=sys.stderr)

    # Remove definition lines (process spans in reverse to preserve indices)
    spans_to_remove.sort(reverse=True)
    for start, end in spans_to_remove:
        # Also consume the trailing newline if present
        if end < len(content) and content[end] == "\n":
            end += 1
        content = content[:start] + content[end:]

    # Remove \DeclareMathAlphabet and \SetMathAlphabet lines
    content = re.sub(
        r"\\(?:Declare|Set)MathAlphabet\{[^}]*\}.*\n?", "", content
    )

    # Strip \usepackage lines unless told to keep them
    if not options.get("keep_usepackage", False):
        content = re.sub(r"\\usepackage\s*(\[[^\]]*\])?\s*\{[^}]*\}\s*\n?", "", content)

    # Multi-pass expansion
    max_passes = 10
    for pass_num in range(max_passes):
        new_content = _expand_one_pass(content, macros)
        if new_content == content:
            if verbose:
                print(
                    f"  Macro expansion stable after {pass_num + 1} pass(es)",
                    file=sys.stderr,
                )
            break
        content = new_content
    else:
        if verbose:
            print(
                f"  Warning: macro expansion did not stabilize after {max_passes} passes",
                file=sys.stderr,
            )

    # Collapse runs of 3+ blank lines into a single blank line
    content = re.sub(r"\n{3,}", "\n\n", content)

    # Restore verbatim environments
    content = unmask_verbatim(content, verbatim_store)

    return content


# ---------------------------------------------------------------------------
# Brace matching
# ---------------------------------------------------------------------------


def _find_brace_group(content: str, start: int) -> tuple[str, int] | None:
    """Extract content of a brace group starting at position start.

    Expects content[start] == '{'. Returns (inner_content, end_pos) where
    end_pos is the index after the closing '}'.
    Returns None if no matching brace found.
    """
    if start >= len(content) or content[start] != "{":
        return None
    depth = 1
    i = start + 1
    while i < len(content) and depth > 0:
        ch = content[i]
        if ch == "\\" and i + 1 < len(content):
            i += 2  # skip escaped character
            continue
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
        i += 1
    if depth != 0:
        return None
    return content[start + 1 : i - 1], i


def _find_bracket_group(content: str, start: int) -> tuple[str, int] | None:
    """Extract content of a bracket group [...]  starting at position start.

    Returns (inner_content, end_pos) or None.
    """
    if start >= len(content) or content[start] != "[":
        return None
    depth = 1
    i = start + 1
    while i < len(content) and depth > 0:
        ch = content[i]
        if ch == "\\" and i + 1 < len(content):
            i += 2
            continue
        if ch == "[":
            depth += 1
        elif ch == "]":
            depth -= 1
        i += 1
    if depth != 0:
        return None
    return content[start + 1 : i - 1], i


# ---------------------------------------------------------------------------
# Conditional resolution
# ---------------------------------------------------------------------------

# Match \ifodd 1 ... \else ... \fi  and  \ifodd 1 ... \fi
_IFODD_RE = re.compile(
    r"\\ifodd\s+1\s*\n?(.*?)(?:\\else\s*\n?(.*?))?\\fi",
    re.DOTALL,
)


def _resolve_conditionals(content: str) -> str:
    """Resolve \\ifodd 1 ... \\else ... \\fi blocks by keeping the then-branch."""
    return _IFODD_RE.sub(lambda m: m.group(1), content)


# ---------------------------------------------------------------------------
# Parsing: \newcommand, \renewcommand, \providecommand
# ---------------------------------------------------------------------------

# Matches the prefix up to where the body brace group starts
_NEWCMD_PREFIX_RE = re.compile(
    r"\\(new|renew|provide)command\s*\*?\s*"
    r"\{?(\\[a-zA-Z@]+)\}?\s*"
    r"(?:\[(\d)\])?\s*"  # optional [num_args]
    r"(?:\[([^\]]*)\])?\s*"  # optional [default]
)


def _parse_newcommand(
    content: str,
) -> list[tuple[tuple[int, int], Macro, str]]:
    results = []
    for m in _NEWCMD_PREFIX_RE.finditer(content):
        kind = m.group(1)  # "new", "renew", or "provide"
        name = m.group(2)[1:]  # strip leading backslash
        num_args = int(m.group(3)) if m.group(3) else 0
        default_opt = m.group(4)  # None if no optional default

        body_start = m.end()
        # Skip whitespace to find opening brace
        while body_start < len(content) and content[body_start] in " \t\n":
            body_start += 1

        result = _find_brace_group(content, body_start)
        if result is None:
            continue
        body, end_pos = result

        span = (m.start(), end_pos)
        macro = Macro(
            name=name,
            num_args=num_args,
            default_opt=default_opt,
            body=body,
        )
        results.append((span, macro, kind))
    return results


# ---------------------------------------------------------------------------
# Parsing: \def
# ---------------------------------------------------------------------------

# Matches \def\name possibly followed by #1#2... then the body brace
_DEF_PREFIX_RE = re.compile(
    r"\\def\s*(\\(?:[a-zA-Z@]+|[0-9]))\s*((?:#[0-9])*)\s*"
)


def _parse_def(
    content: str,
) -> list[tuple[tuple[int, int], Macro, str]]:
    results = []
    for m in _DEF_PREFIX_RE.finditer(content):
        name = m.group(1)[1:]  # strip leading backslash
        arg_spec = m.group(2)  # e.g. "#1#2" or ""
        num_args = arg_spec.count("#")

        body_start = m.end()
        result = _find_brace_group(content, body_start)
        if result is None:
            continue
        body, end_pos = result

        span = (m.start(), end_pos)
        macro = Macro(
            name=name,
            num_args=num_args,
            default_opt=None,
            body=body,
        )
        results.append((span, macro, "def"))
    return results


# ---------------------------------------------------------------------------
# Parsing: \DeclareMathOperator
# ---------------------------------------------------------------------------

_MATHOP_PREFIX_RE = re.compile(
    r"\\DeclareMathOperator\s*(\*)?\s*"
)


def _parse_declaremathoperator(
    content: str,
) -> list[tuple[tuple[int, int], Macro, str]]:
    results = []
    for m in _MATHOP_PREFIX_RE.finditer(content):
        star = m.group(1) or ""
        pos = m.end()

        # Skip whitespace
        while pos < len(content) and content[pos] in " \t\n":
            pos += 1

        # Extract command name {\\name}
        name_result = _find_brace_group(content, pos)
        if name_result is None:
            continue
        name_inner, pos = name_result
        name_inner = name_inner.strip()
        if not name_inner.startswith("\\"):
            continue
        name = name_inner[1:]

        # Skip whitespace
        while pos < len(content) and content[pos] in " \t\n":
            pos += 1

        # Extract operator text {text}
        body_result = _find_brace_group(content, pos)
        if body_result is None:
            continue
        op_text, end_pos = body_result

        span = (m.start(), end_pos)
        body = f"\\operatorname{star}{{{op_text}}}"
        macro = Macro(name=name, num_args=0, default_opt=None, body=body)
        results.append((span, macro, "new"))
    return results


# ---------------------------------------------------------------------------
# Expansion
# ---------------------------------------------------------------------------


def _expand_one_pass(content: str, macros: dict[str, Macro]) -> str:
    """Perform one pass of macro expansion over the content."""
    # Sort macros by name length descending so longer names match first
    # (e.g. \rvepsilon before \rv)
    sorted_names = sorted(macros.keys(), key=len, reverse=True)

    # Build a combined regex that matches any macro usage
    # Need to handle both alpha names (\foo followed by non-alpha)
    # and single-char numeric names (\1)
    if not sorted_names:
        return content

    # Escape names for regex and build pattern
    patterns = []
    for name in sorted_names:
        escaped = re.escape(name)
        if name[-1].isalpha() or name[-1] == "@":
            # Alpha name: must be followed by non-alpha (word boundary)
            patterns.append(rf"\\{escaped}(?![a-zA-Z@])")
        else:
            # Non-alpha name (e.g. \1): just match literally
            patterns.append(rf"\\{escaped}")

    combined = "|".join(patterns)
    macro_re = re.compile(combined)

    result_parts: list[str] = []
    last_end = 0

    for m in macro_re.finditer(content):
        # Extract the macro name from the match
        matched = m.group(0)
        # The name is everything after the backslash
        name = matched.lstrip("\\")
        # But we need the actual name from our dict (the regex may include
        # lookahead chars that aren't in the match)
        if name not in macros:
            continue

        macro = macros[name]
        pos = m.end()

        # Skip optional {} after 0-arg macros (TeX spacing trick)
        if macro.num_args == 0:
            # Check for {} right after
            temp_pos = pos
            while temp_pos < len(content) and content[temp_pos] in " \t":
                temp_pos += 1
            if (
                temp_pos + 1 < len(content)
                and content[temp_pos] == "{"
                and content[temp_pos + 1] == "}"
            ):
                pos = temp_pos + 2

            result_parts.append(content[last_end : m.start()])
            result_parts.append(macro.body)
            last_end = pos
            continue

        # Extract arguments for macros with args
        args = []
        arg_pos = pos

        # Handle optional first argument
        if macro.default_opt is not None:
            # Skip whitespace
            while arg_pos < len(content) and content[arg_pos] in " \t\n":
                arg_pos += 1
            if arg_pos < len(content) and content[arg_pos] == "[":
                bracket_result = _find_bracket_group(content, arg_pos)
                if bracket_result is not None:
                    opt_val, arg_pos = bracket_result
                    args.append(opt_val)
                else:
                    args.append(macro.default_opt)
            else:
                args.append(macro.default_opt)

        # Extract required brace arguments
        remaining = macro.num_args - len(args)
        ok = True
        for _ in range(remaining):
            # Skip whitespace
            while arg_pos < len(content) and content[arg_pos] in " \t\n":
                arg_pos += 1
            brace_result = _find_brace_group(content, arg_pos)
            if brace_result is None:
                ok = False
                break
            arg_val, arg_pos = brace_result
            args.append(arg_val)

        if not ok:
            # Couldn't extract all arguments; leave unchanged
            continue

        # Substitute #1, #2, ... in body
        expanded = macro.body
        for i, arg in enumerate(args, 1):
            expanded = expanded.replace(f"#{i}", arg)

        result_parts.append(content[last_end : m.start()])
        result_parts.append(expanded)
        last_end = arg_pos

    result_parts.append(content[last_end:])
    return "".join(result_parts)
