"""Command-line interface for latex-llm-cleaner."""

import argparse
import sys
from pathlib import Path

from .pipeline import run_pipeline
from .powerpoint import extract_text_from_pptx

_ELSEWHERE = {
    ".pdf": (
        "PDF input was removed in 1.0. Short PDFs: give them to the model "
        "directly (it reads page images). Long PDFs: convert with Marker "
        "(https://github.com/datalab-to/marker), e.g. "
        "`marker_single paper.pdf --force_ocr --paginate_output`."
    ),
    ".docx": (
        "DOCX input was removed in 1.0: `pandoc -t markdown file.docx` keeps "
        "equations as LaTeX."
    ),
}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="latex-llm-cleaner",
        description="Flatten and clean LaTeX projects, or extract PowerPoint "
        "decks with their equations, for LLM consumption.",
    )
    parser.add_argument("input_file", type=Path, help="Input .tex or .pptx file")
    parser.add_argument(
        "-o", "--output", type=Path, default=None, help="Output file (default: stdout)"
    )
    parser.add_argument(
        "--no-flatten", action="store_true", help="Disable include/input flattening"
    )
    parser.add_argument(
        "--no-bibliography",
        action="store_true",
        help="Disable bibliography inlining (supports .bbl and .bib files)",
    )
    parser.add_argument(
        "--no-comments", action="store_true", help="Disable comment removal"
    )
    parser.add_argument(
        "--no-macros", action="store_true", help="Disable macro expansion"
    )
    parser.add_argument(
        "--keep-usepackage",
        action="store_true",
        help="Keep \\usepackage lines (dropped by default during macro expansion)",
    )
    parser.add_argument(
        "--encoding", default="utf-8", help="File encoding (default: utf-8)"
    )
    parser.add_argument(
        "--notes",
        action="store_true",
        help="Include speaker notes (PPTX) in output (default: off)",
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

    suffix = input_path.suffix.lower()
    if suffix in _ELSEWHERE:
        print(f"Error: {_ELSEWHERE[suffix]}", file=sys.stderr)
        sys.exit(2)

    if suffix == ".pptx":
        if args.verbose:
            print("PPTX input detected, extracting slides...", file=sys.stderr)
        result = extract_text_from_pptx(
            input_path, verbose=args.verbose, notes=args.notes,
        )
    else:
        content = input_path.read_text(encoding=args.encoding)
        options = {
            "flatten": not args.no_flatten,
            "comments": not args.no_comments,
            "macros": not args.no_macros,
            "keep_usepackage": args.keep_usepackage,
            "bibliography": not args.no_bibliography,
            "encoding": args.encoding,
            "verbose": args.verbose,
            "input_file": input_path,
        }
        # Resolve includes relative to the .tex file's directory
        # (the compilation root), not the arbitrary invocation directory.
        result = run_pipeline(content, input_path.parent.resolve(), options)

    if args.output:
        args.output.write_text(result, encoding=args.encoding)
        if args.verbose:
            print(f"Written to {args.output}", file=sys.stderr)
    else:
        sys.stdout.write(result)
