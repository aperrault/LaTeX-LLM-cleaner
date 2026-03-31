"""Command-line interface for latex-llm-cleaner."""

import argparse
import os
import sys
from pathlib import Path

from .pdf import extract_text_from_pdf, extract_text_from_pdf_ocr
from .pipeline import run_pipeline
from .powerpoint import extract_text_from_pptx


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="latex-llm-cleaner",
        description="Flatten and clean LaTeX files for LLM consumption. "
        "Accepts .tex files (full pipeline), .pdf files (text extraction), "
        "or .pptx files (slide extraction).",
    )
    parser.add_argument("input_file", type=Path, help="Input .tex, .pdf, or .pptx file")
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
        "--notes",
        action="store_true",
        help="Include speaker notes in PPTX output (default: off)",
    )
    parser.add_argument(
        "--ocr",
        action="store_true",
        help="Use Surya vision OCR for PDF extraction (recovers LaTeX equations, slower). "
        "Requires: pip install latex-llm-cleaner[ocr]",
    )
    parser.add_argument(
        "--auto-summarize",
        action="store_true",
        help="Auto-generate figure summaries using Gemini vision API. "
        "Requires: pip install latex-llm-cleaner[summarize]",
    )
    parser.add_argument(
        "--google-api-key",
        default=None,
        help="Google API key for --auto-summarize (default: GOOGLE_API_KEY env var)",
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

    if input_path.suffix.lower() == ".pdf":
        if args.ocr:
            if args.verbose:
                print("PDF input detected, using Surya OCR...", file=sys.stderr)
            result = extract_text_from_pdf_ocr(input_path, verbose=args.verbose)
        else:
            if args.verbose:
                print("PDF input detected, extracting text...", file=sys.stderr)
            result = extract_text_from_pdf(input_path, verbose=args.verbose)
    elif input_path.suffix.lower() == ".pptx":
        if args.auto_summarize:
            from .summarize import auto_summarize_pptx

            auto_summarize_pptx(input_path, {
                "google_api_key": args.google_api_key or os.environ.get("GOOGLE_API_KEY"),
                "verbose": args.verbose,
                "figure_summary_suffix": args.figure_summary_suffix,
                "encoding": args.encoding,
            })
        if args.verbose:
            print("PPTX input detected, extracting slides...", file=sys.stderr)
        result = extract_text_from_pptx(
            input_path,
            verbose=args.verbose,
            notes=args.notes,
            figure_summary_suffix=args.figure_summary_suffix,
            encoding=args.encoding,
        )
    else:
        content = input_path.read_text(encoding=args.encoding)

        options = {
            "flatten": not args.no_flatten,
            "comments": not args.no_comments,
            "macros": not args.no_macros,
            "bibliography": not args.no_bibliography,
            "figures": not args.no_figures,
            "figure_summary_suffix": args.figure_summary_suffix,
            "encoding": args.encoding,
            "verbose": args.verbose,
            "input_file": input_path,
            "auto_summarize": args.auto_summarize,
            "google_api_key": args.google_api_key or os.environ.get("GOOGLE_API_KEY"),
        }

        result = run_pipeline(content, Path.cwd(), options)

    if args.output:
        args.output.write_text(result, encoding=args.encoding)
        if args.verbose:
            print(f"Written to {args.output}", file=sys.stderr)
    else:
        sys.stdout.write(result)
