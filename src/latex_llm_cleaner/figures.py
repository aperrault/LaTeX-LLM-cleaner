"""Replace images with text summaries when available.

Figure summaries are plain-text files (e.g., ``plot_summary.txt``) placed
alongside their corresponding image files.  Each summary should be a faithful,
data-equivalent description of the figure's content — no editorializing or
interpretation beyond what the figure itself conveys.  This serves two purposes:

1. **LLM consumption** — as of early 2026, language models still struggle to
   extract precise information from complex figures (dense plots, multi-panel
   layouts, etc.).  A text summary lets the model reason over the same data.
2. **Accessibility** — LaTeX has limited built-in support for accessible output;
   these summaries can double as alt-text for screen readers when compiled to
   tagged PDF or HTML.
"""

import re
import sys
from pathlib import Path

# Matches \begin{figure}...\end{figure} (possibly with optional args like [htbp])
_FIGURE_ENV_RE = re.compile(
    r"\\begin\{figure\}\s*(\[.*?\])?(.*?)\\end\{figure\}", re.DOTALL
)

# Matches \includegraphics[opts]{filename}
_INCLUDEGRAPHICS_RE = re.compile(
    r"\\includegraphics\s*(?:\[[^\]]*\])?\s*\{([^}]+)\}"
)

# Matches \caption{...} (handles nested braces one level deep)
_CAPTION_RE = re.compile(r"\\caption\{((?:[^{}]|\{[^{}]*\})*)\}")

# Matches \label{...}
_LABEL_RE = re.compile(r"\\label\{([^}]+)\}")

# Matches \graphicspath{{dir1/}{dir2/}...}
_GRAPHICSPATH_RE = re.compile(r"\\graphicspath\s*\{((?:\s*\{[^}]*\}\s*)+)\}")

_IMAGE_EXTENSIONS = (".png", ".pdf", ".jpg", ".jpeg", ".eps", ".svg")


def _parse_graphicspath(content: str) -> list[str]:
    """Extract directory prefixes declared via \\graphicspath.

    ``\\graphicspath{{Proj1/}{proj2/figures/}}`` -> ``["Proj1/", "proj2/figures/"]``.
    Returns an empty list when no (well-formed) \\graphicspath is present.
    """
    m = _GRAPHICSPATH_RE.search(content)
    if m is None:
        return []
    return re.findall(r"\{([^}]*)\}", m.group(1))


def _search_roots(base_dir: Path, graphics_dirs: list[str] | None) -> list[Path]:
    """Directories to probe for an image, in LaTeX resolution order.

    ``base_dir`` first, then each \\graphicspath directory joined onto it,
    mirroring how LaTeX prepends each graphics path to the \\includegraphics
    argument.
    """
    roots = [base_dir]
    for d in graphics_dirs or []:
        roots.append(base_dir / d)
    return roots


def substitute_figures(content: str, base_dir: Path, options: dict) -> str:
    verbose = options.get("verbose", False)
    suffix = options.get("figure_summary_suffix", "_summary.txt")
    encoding = options.get("encoding", "utf-8")
    graphics_dirs = _parse_graphicspath(content)

    # Step 1: Replace figure environments that contain \includegraphics
    def replace_figure_env(m: re.Match) -> str:
        full_match = m.group(0)
        body = m.group(2)

        gfx_match = _INCLUDEGRAPHICS_RE.search(body)
        if not gfx_match:
            return full_match

        img_path_str = gfx_match.group(1).strip()
        summary = _find_summary(base_dir, img_path_str, suffix, encoding, graphics_dirs)

        if summary is None:
            if verbose:
                print(
                    f"Warning: no summary found for {img_path_str}", file=sys.stderr
                )
            return full_match

        # Extract caption and label
        caption_match = _CAPTION_RE.search(body)
        label_match = _LABEL_RE.search(body)

        parts = ["% --- Figure summary ---"]
        if label_match:
            parts.append(f"\\label{{{label_match.group(1)}}}")
        if caption_match:
            parts.append(f"% Caption: {caption_match.group(1)}")
        parts.append(f"% {summary}")
        parts.append("% --- End figure summary ---")

        return "\n".join(parts)

    content = _FIGURE_ENV_RE.sub(replace_figure_env, content)

    # Step 2: Replace standalone \includegraphics (not inside figure env)
    def replace_standalone(m: re.Match) -> str:
        img_path_str = m.group(1).strip()
        summary = _find_summary(base_dir, img_path_str, suffix, encoding, graphics_dirs)

        if summary is None:
            if verbose:
                print(
                    f"Warning: no summary found for {img_path_str}", file=sys.stderr
                )
            return m.group(0)

        return f"% [Image: {summary}]"

    content = _INCLUDEGRAPHICS_RE.sub(replace_standalone, content)

    return content


def _find_summary(
    base_dir: Path,
    img_path_str: str,
    suffix: str,
    encoding: str,
    graphics_dirs: list[str] | None = None,
) -> str | None:
    """Look for a summary file corresponding to the image path.

    Probes ``base_dir`` and any ``\\graphicspath`` directories (``graphics_dirs``)
    in LaTeX resolution order.
    """
    for root in _search_roots(base_dir, graphics_dirs):
        img_path = root / img_path_str

        # If the image has an extension, strip it
        if img_path.suffix.lower() in _IMAGE_EXTENSIONS:
            stem_path = img_path.with_suffix("")
        else:
            stem_path = img_path

        summary_path = Path(str(stem_path) + suffix)
        if summary_path.is_file():
            return summary_path.read_text(encoding=encoding).strip()

        # If no extension was given, try common extensions to find the stem
        if img_path.suffix.lower() not in _IMAGE_EXTENSIONS:
            for ext in _IMAGE_EXTENSIONS:
                candidate = root / (img_path_str + ext)
                if candidate.is_file():
                    summary_path = Path(str(candidate.with_suffix("")) + suffix)
                    if summary_path.is_file():
                        return summary_path.read_text(encoding=encoding).strip()

    return None
