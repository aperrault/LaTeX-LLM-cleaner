"""Strip LaTeX comments while respecting verbatim environments and escaped percent signs."""

import re
from pathlib import Path


# Environments whose content should not be modified
VERBATIM_ENVS = ("verbatim", "lstlisting", "minted")

# Pattern to match \verb|...|  (any delimiter character)
_VERB_INLINE_RE = re.compile(r"\\verb(.)(.+?)\1")

# Pattern to match \begin{comment}...\end{comment}
_COMMENT_ENV_RE = re.compile(
    r"\\begin\{comment\}.*?\\end\{comment\}", re.DOTALL
)


def remove_comments(content: str, base_dir: Path, options: dict) -> str:
    # Step 1: Remove \begin{comment}...\end{comment} environments
    content = _COMMENT_ENV_RE.sub("", content)

    # Step 2: Mask verbatim environments and \verb|...|
    content, verbatim_store = mask_verbatim(content)

    # Step 3: Strip line comments using character scanning
    lines = content.split("\n")
    result_lines: list[str] = []
    for line in lines:
        stripped = _strip_line_comment(line)
        if stripped is None:
            # Entire line was a comment — remove it
            continue
        result_lines.append(stripped)

    content = "\n".join(result_lines)

    # Step 4: Restore verbatim content
    content = unmask_verbatim(content, verbatim_store)

    return content


def _strip_line_comment(line: str) -> str | None:
    """Strip comment from a single line.

    Returns None if the entire line is a comment (should be removed).
    Returns the line (possibly truncated) otherwise.
    """
    i = 0
    while i < len(line):
        ch = line[i]
        if ch == "%":
            # Count preceding backslashes
            num_backslashes = 0
            j = i - 1
            while j >= 0 and line[j] == "\\":
                num_backslashes += 1
                j -= 1
            if num_backslashes % 2 == 0:
                # This is a real comment
                before = line[:i]
                if before.strip() == "":
                    # Comment-only line
                    return None
                return before.rstrip()
            # Escaped percent — not a comment
        i += 1
    return line


def mask_verbatim(content: str) -> tuple[str, dict[str, str]]:
    """Replace verbatim environments and \\verb|...| with placeholders."""
    store: dict[str, str] = {}
    counter = 0

    # Mask \verb|...|
    def replace_verb(m: re.Match) -> str:
        nonlocal counter
        key = f"\x00VERB{counter}\x00"
        counter += 1
        store[key] = m.group(0)
        return key

    content = _VERB_INLINE_RE.sub(replace_verb, content)

    # Mask verbatim environments
    for env in VERBATIM_ENVS:
        pattern = re.compile(
            rf"\\begin\{{{env}\}}.*?\\end\{{{env}\}}", re.DOTALL
        )

        def replace_env(m: re.Match, _env=env) -> str:
            nonlocal counter
            key = f"\x00ENV{counter}\x00"
            counter += 1
            store[key] = m.group(0)
            return key

        content = pattern.sub(replace_env, content)

    return content, store


def unmask_verbatim(content: str, store: dict[str, str]) -> str:
    """Restore masked verbatim content."""
    for key, value in store.items():
        content = content.replace(key, value)
    return content
