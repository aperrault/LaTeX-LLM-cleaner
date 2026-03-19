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

    # Find bib file references
    bib_files = _find_bib_files(content, base_dir)
    if not bib_files:
        return content

    # Parse all bib entries
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

    # Generate \thebibliography block
    bib_block = _generate_thebibliography(ordered_keys, all_entries)

    # Replace \bibliography{...} or \addbibresource{...} with the block
    replaced = False

    def replace_bib_cmd(m: re.Match) -> str:
        nonlocal replaced
        if not replaced:
            replaced = True
            return bib_block
        return ""

    content = _BIBLIOGRAPHY_RE.sub(replace_bib_cmd, content)
    content = _ADDBIBRESOURCE_RE.sub(replace_bib_cmd, content)

    # Remove \bibliographystyle
    content = _BIBSTYLE_RE.sub("", content)

    return content


def _find_bib_files(content: str, base_dir: Path) -> list[Path]:
    """Find all referenced .bib file paths."""
    files: list[Path] = []

    for m in _BIBLIOGRAPHY_RE.finditer(content):
        for name in m.group(1).split(","):
            name = name.strip()
            if not name.endswith(".bib"):
                name += ".bib"
            files.append(base_dir / name)

    for m in _ADDBIBRESOURCE_RE.finditer(content):
        name = m.group(1).strip()
        if not name.endswith(".bib"):
            name += ".bib"
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
