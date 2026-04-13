"""Resolve \\input, \\include, and \\subfile commands by inlining file contents."""

import re
import sys
from pathlib import Path

# Matches \input{file}, \include{file}, \subfile{file}
_INCLUDE_RE = re.compile(r"\\(input|include|subfile)\{([^}]+)\}")

# Matches \includeonly{a,b,c} in the preamble
_INCLUDEONLY_RE = re.compile(r"\\includeonly\{([^}]+)\}")


def flatten_includes(content: str, base_dir: Path, options: dict) -> str:
    verbose = options.get("verbose", False)
    encoding = options.get("encoding", "utf-8")

    # Parse \includeonly from preamble (before \begin{document})
    includeonly = _parse_includeonly(content)

    visited: set[Path] = set()
    return _flatten_recursive(content, base_dir, visited, includeonly, encoding, verbose)


def _parse_includeonly(content: str) -> set[str] | None:
    """Extract the set of allowed filenames from \\includeonly, or None if absent."""
    m = _INCLUDEONLY_RE.search(content)
    if m is None:
        return None
    return {name.strip() for name in m.group(1).split(",")}


def _resolve_input_path(filename: str, root_dir: Path, current_dir: Path) -> Path:
    """Resolve an \\input path, trying the compilation root first, then the current file's dir."""
    for base in (root_dir, current_dir):
        candidate = base / filename
        if not candidate.suffix:
            candidate = candidate.with_suffix(".tex")
        candidate = candidate.resolve()
        if candidate.is_file():
            return candidate
    # Nothing found — return the root-relative path for the error message
    fallback = root_dir / filename
    if not fallback.suffix:
        fallback = fallback.with_suffix(".tex")
    return fallback.resolve()


def _flatten_recursive(
    content: str,
    current_dir: Path,
    visited: set[Path],
    includeonly: set[str] | None,
    encoding: str,
    verbose: bool,
    root_dir: Path | None = None,
) -> str:
    if root_dir is None:
        root_dir = current_dir

    def replacer(m: re.Match) -> str:
        cmd = m.group(1)  # input, include, or subfile
        filename = m.group(2).strip()

        # For \include, check against \includeonly
        if cmd == "include" and includeonly is not None:
            basename = Path(filename).stem if "." in filename else filename
            if basename not in includeonly:
                return ""

        # Resolve path: try compilation root first (standard LaTeX behavior),
        # then fall back to the directory of the file containing the \input
        file_path = _resolve_input_path(filename, root_dir, current_dir)

        # Cycle detection
        if file_path in visited:
            print(f"Warning: cycle detected for {file_path}", file=sys.stderr)
            return m.group(0)

        if not file_path.is_file():
            print(f"Warning: {file_path} not found", file=sys.stderr)
            return m.group(0)

        if verbose:
            print(f"  Inlining {file_path}", file=sys.stderr)

        visited.add(file_path)
        try:
            child_content = file_path.read_text(encoding=encoding)
        except OSError as e:
            print(f"Warning: could not read {file_path}: {e}", file=sys.stderr)
            return m.group(0)

        # For \subfile, strip document environment wrapper
        if cmd == "subfile":
            child_content = _strip_subfile_wrapper(child_content)

        # Recursively flatten the child content
        child_content = _flatten_recursive(
            child_content, file_path.parent, visited, includeonly, encoding, verbose,
            root_dir=root_dir,
        )
        visited.discard(file_path)

        # \include semantics: wrap with \clearpage
        if cmd == "include":
            child_content = f"\\clearpage\n{child_content}\n\\clearpage"

        return child_content

    # Process line-by-line so we can skip commented-out \input commands
    lines = content.split("\n")
    result_lines = []
    for line in lines:
        stripped = line.lstrip()
        if stripped.startswith("%"):
            result_lines.append(line)
        else:
            result_lines.append(_INCLUDE_RE.sub(replacer, line))
    return "\n".join(result_lines)


def _strip_subfile_wrapper(content: str) -> str:
    """Strip \\documentclass, preamble, \\begin{document} and \\end{document} from subfile content."""
    # Remove everything up to and including \begin{document}
    begin_match = re.search(r"\\begin\{document\}", content)
    if begin_match:
        content = content[begin_match.end():]
    # Remove \end{document}
    end_match = re.search(r"\\end\{document\}", content)
    if end_match:
        content = content[:end_match.start()]
    return content.strip()
