"""Inline bibliography by parsing .bib files and generating \\thebibliography."""

import re
import sys
from pathlib import Path

import bibtexparser

# Commands that reference bib files
_BIBLIOGRAPHY_RE = re.compile(r"\\bibliography\{([^}]+)\}")
_ADDBIBRESOURCE_RE = re.compile(r"\\addbibresource\{([^}]+)\}")

# Citation commands
_CITE_RE = re.compile(
    r"\\(?:cite|citep|citet|autocite|textcite|parencite|fullcite|nocite)"
    r"(?:\[[^\]]*\])*"  # optional arguments like [p.~5]
    r"\{([^}]+)\}"
)

# \bibliographystyle{...}
_BIBSTYLE_RE = re.compile(r"\\bibliographystyle\{[^}]+\}\s*\n?")


def inline_bibliography(content: str, base_dir: Path, options: dict) -> str:
    verbose = options.get("verbose", False)
    encoding = options.get("encoding", "utf-8")

    # Build list of directories to search for bib/bbl files:
    # compilation root (base_dir) + input file's directory
    search_dirs = [base_dir]
    input_file = options.get("input_file")
    if input_file is not None:
        input_dir = Path(input_file).resolve().parent
        if input_dir != base_dir.resolve():
            search_dirs.append(input_dir)

    # Check if there are any bibliography commands to process
    has_bib_cmd = _BIBLIOGRAPHY_RE.search(content) or _ADDBIBRESOURCE_RE.search(content)
    if not has_bib_cmd:
        return content

    # Try .bbl file first (common in arXiv downloads)
    bbl_block = _try_bbl_file(content, base_dir, options, search_dirs)
    if bbl_block is not None:
        if verbose:
            print("  Using pre-compiled .bbl file", file=sys.stderr)
        return _replace_bib_commands(content, bbl_block)

    # Fall back to .bib file parsing
    bib_files = _find_bib_files(content, base_dir, search_dirs)
    if not bib_files:
        return content

    all_entries = {}
    for bib_path in bib_files:
        if not bib_path.is_file():
            print(f"Warning: bib file {bib_path} not found", file=sys.stderr)
            continue
        if verbose:
            print(f"  Parsing {bib_path}", file=sys.stderr)
        entries = _parse_bib_file(bib_path, encoding)
        all_entries.update(entries)

    if not all_entries:
        return content

    # Extract cited keys
    cited_keys = _extract_cited_keys(content)

    # Handle \nocite{*}
    if "*" in cited_keys:
        cited_keys = set(all_entries.keys())

    # Filter to only cited entries, preserving citation order
    ordered_keys = []
    seen = set()
    for m in _CITE_RE.finditer(content):
        for key in m.group(1).split(","):
            key = key.strip()
            if key and key != "*" and key not in seen and key in all_entries:
                ordered_keys.append(key)
                seen.add(key)
    # Add any from nocite{*} that weren't explicitly cited
    for key in sorted(all_entries.keys()):
        if key not in seen and key in cited_keys:
            ordered_keys.append(key)

    if not ordered_keys:
        return content

    bib_block = _generate_thebibliography(ordered_keys, all_entries)
    return _replace_bib_commands(content, bib_block)


def _replace_bib_commands(content: str, bib_block: str) -> str:
    """Replace \\bibliography/\\addbibresource commands with bib_block and remove \\bibliographystyle."""
    replaced = False

    def replace_bib_cmd(m: re.Match) -> str:
        nonlocal replaced
        if not replaced:
            replaced = True
            return bib_block
        return ""

    content = _BIBLIOGRAPHY_RE.sub(replace_bib_cmd, content)
    content = _ADDBIBRESOURCE_RE.sub(replace_bib_cmd, content)
    content = _BIBSTYLE_RE.sub("", content)
    return content


def _try_bbl_file(content: str, base_dir: Path, options: dict,
                   search_dirs: list[Path] | None = None) -> str | None:
    """Look for a .bbl file and return its contents if found."""
    encoding = options.get("encoding", "utf-8")
    if search_dirs is None:
        search_dirs = [base_dir]
    candidates: list[Path] = []

    # Try <input_file_stem>.bbl (e.g., main.tex → main.bbl)
    input_file = options.get("input_file")
    if input_file is not None:
        candidates.append(Path(input_file).with_suffix(".bbl"))

    # Try <bib_name>.bbl from \bibliography{name}
    for m in _BIBLIOGRAPHY_RE.finditer(content):
        for name in m.group(1).split(","):
            name = name.strip()
            for search_dir in search_dirs:
                candidates.append(search_dir / (name + ".bbl"))

    for candidate in candidates:
        if candidate.is_file():
            return candidate.read_text(encoding=encoding).strip()

    return None


def _find_bib_files(content: str, base_dir: Path, search_dirs: list[Path] | None = None) -> list[Path]:
    """Find all referenced .bib file paths."""
    if search_dirs is None:
        search_dirs = [base_dir]
    files: list[Path] = []

    for m in _BIBLIOGRAPHY_RE.finditer(content):
        for name in m.group(1).split(","):
            name = name.strip()
            if not name.endswith(".bib"):
                name += ".bib"
            for search_dir in search_dirs:
                candidate = search_dir / name
                if candidate.is_file():
                    files.append(candidate)
                    break
            else:
                files.append(base_dir / name)

    for m in _ADDBIBRESOURCE_RE.finditer(content):
        name = m.group(1).strip()
        if not name.endswith(".bib"):
            name += ".bib"
        for search_dir in search_dirs:
            candidate = search_dir / name
            if candidate.is_file():
                files.append(candidate)
                break
        else:
            files.append(base_dir / name)

    return files


def _parse_bib_file(bib_path: Path, encoding: str) -> dict[str, dict]:
    """Parse a .bib file and return a dict of key -> entry."""
    bib_text = bib_path.read_text(encoding=encoding)
    library = bibtexparser.parse_string(bib_text)

    entries = {}
    for entry in library.entries:
        key = entry.key
        entries[key] = {
            "type": entry.entry_type,
            "fields": {k: f.value for k, f in entry.fields_dict.items()},
            "key": key,
        }
    return entries


def _extract_cited_keys(content: str) -> set[str]:
    """Extract all citation keys from the document."""
    keys: set[str] = set()
    for m in _CITE_RE.finditer(content):
        for key in m.group(1).split(","):
            key = key.strip()
            if key:
                keys.add(key)
    return keys


def _generate_thebibliography(keys: list[str], entries: dict[str, dict]) -> str:
    """Generate a \\begin{thebibliography} block."""
    lines = [f"\\begin{{thebibliography}}{{{len(keys)}}}"]
    lines.append("")

    for key in keys:
        entry = entries[key]
        fields = entry["fields"]
        formatted = _format_entry(fields, entry["type"])
        lines.append(f"\\bibitem{{{key}}}")
        lines.append(formatted)
        lines.append("")

    lines.append("\\end{thebibliography}")
    return "\n".join(lines)


def _format_entry(fields: dict[str, str], entry_type: str) -> str:
    """Format a bibliography entry as a human-readable string."""
    parts: list[str] = []

    author = fields.get("author", "")
    if author:
        parts.append(author + ".")

    title = fields.get("title", "")
    if title:
        # Remove braces used for capitalization protection
        title = title.replace("{", "").replace("}", "")
        parts.append(f"\\textit{{{title}}}.")

    journal = fields.get("journal", "")
    booktitle = fields.get("booktitle", "")
    if journal:
        parts.append(journal + ".")
    elif booktitle:
        parts.append(f"In {booktitle}.")

    volume = fields.get("volume", "")
    number = fields.get("number", "")
    pages = fields.get("pages", "")
    if volume:
        vol_str = volume
        if number:
            vol_str += f"({number})"
        if pages:
            vol_str += f":{pages}"
        parts.append(vol_str + ".")
    elif pages:
        parts.append(f"pp.~{pages}.")

    year = fields.get("year", "")
    if year:
        parts.append(f"{year}.")

    publisher = fields.get("publisher", "")
    if publisher and entry_type in ("book", "inbook"):
        parts.append(publisher + ".")

    return " ".join(parts)
