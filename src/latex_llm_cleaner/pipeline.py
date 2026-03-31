"""Orchestrates the processing pipeline."""

import sys
from pathlib import Path

from .flatten import flatten_includes
from .comments import remove_comments
from .macros import expand_macros
from .bibliography import inline_bibliography
from .figures import substitute_figures


def run_pipeline(content: str, base_dir: Path, options: dict) -> str:
    verbose = options.get("verbose", False)

    if options.get("flatten", True):
        if verbose:
            print("Step 1: Flattening includes...", file=sys.stderr)
        content = flatten_includes(content, base_dir, options)

    if options.get("comments", True):
        if verbose:
            print("Step 2: Removing comments...", file=sys.stderr)
        content = remove_comments(content, base_dir, options)

    if options.get("macros", True):
        if verbose:
            print("Step 3: Expanding macros...", file=sys.stderr)
        content = expand_macros(content, base_dir, options)

    if options.get("bibliography", True):
        if verbose:
            print("Step 4: Inlining bibliography...", file=sys.stderr)
        content = inline_bibliography(content, base_dir, options)

    if options.get("auto_summarize", False):
        if verbose:
            print("Step 5: Auto-generating figure summaries...", file=sys.stderr)
        from .summarize import auto_summarize_figures

        auto_summarize_figures(content, base_dir, options)

    if options.get("figures", True):
        if verbose:
            print("Step 6: Substituting figures...", file=sys.stderr)
        content = substitute_figures(content, base_dir, options)

    return content
