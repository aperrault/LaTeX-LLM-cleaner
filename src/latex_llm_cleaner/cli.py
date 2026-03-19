"""Command-line interface for latex-llm-cleaner."""

import argparse
import sys
from pathlib import Path

from .pipeline import run_pipeline


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="latex-llm-cleaner",
        description="Flatten and clean LaTeX files for LLM consumption.",
    )
    parser.add_argument("input_file", type=Path, help="Input .tex file")
    parser.add_argument(
        "-o", "--output", type=Path, default=None, help="Output file (default: stdout)"
    )
    parser.add_argument(
        "--no-flatten", action="store_true", help="Disable include/input flattening"
    )
    parser.add_argument(
        "--no-bibliography", action="store_true", help="Disable bibliography inlining"
    )
    parser.add_argument(
        "--no-comments", action="store_true", help="Disable comment removal"
    )
    parser.add_argument(
        "--no-figures", action="store_true", help="Disable figure summary substitution"
    )
    parser.add_argument(
        "--figure-summary-suffix",
        default="_summary.txt",
        help=(
            "Suffix for figure summary files (default: _summary.txt). "
            "Each summary should contain a data-equivalent text description "
            "of its figure — no editorial commentary."
        ),
    )
    parser.add_argument(
        "--encoding", default="utf-8", help="File encoding (default: utf-8)"
    )
    parser.add_argument(
        "-v", "--verbose", action="store_true", help="Print processing info to stderr"
    )
    return parser


def main(argv: list[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)

    input_path: Path = args.input_file
    if not input_path.is_file():
        print(f"Error: {input_path} not found", file=sys.stderr)
        sys.exit(1)

    content = input_path.read_text(encoding=args.encoding)

    options = {
        "flatten": not args.no_flatten,
        "comments": not args.no_comments,
        "bibliography": not args.no_bibliography,
        "figures": not args.no_figures,
        "figure_summary_suffix": args.figure_summary_suffix,
        "encoding": args.encoding,
        "verbose": args.verbose,
    }

    result = run_pipeline(content, input_path.parent.resolve(), options)

    if args.output:
        args.output.write_text(result, encoding=args.encoding)
        if args.verbose:
            print(f"Written to {args.output}", file=sys.stderr)
    else:
        sys.stdout.write(result)
