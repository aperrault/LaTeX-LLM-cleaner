"""Orchestrates the processing pipeline."""

import sys
from pathlib import Path

from .flatten import flatten_includes
from .comments import remove_comments
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

    if options.get("bibliography", True):
        if verbose:
            print("Step 3: Inlining bibliography...", file=sys.stderr)
        content = inline_bibliography(content, base_dir, options)

    if options.get("figures", True):
        if verbose:
            print("Step 4: Substituting figures...", file=sys.stderr)
        content = substitute_figures(content, base_dir, options)

    return content
