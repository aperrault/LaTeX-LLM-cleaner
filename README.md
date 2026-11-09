# LaTeX LLM Cleaner

A CLI tool that turns a LaTeX project or a PowerPoint deck into one clean text file for a language model to read.

- **LaTeX:** inlines every `\input`/`\include`, strips comments, expands idiosyncratic macros, and inlines the bibliography, so the model sees one self-contained document instead of a directory of fragments and private shorthand.
- **PowerPoint:** extracts each slide's text, tables and notes, with equations converted from Office MathML to LaTeX. Readers built only on `python-pptx` silently drop every text box that contains an equation, because those boxes sit inside `mc:AlternateContent`; this tool reads them.

## What happened to PDF and Word input (1.0)

Versions before 1.0 also converted PDFs (with optional Surya OCR) and DOCX files, and could describe figures with the Gemini API. Each of those now has a better answer:

| Input | Use instead |
|---|---|
| Short PDF (≲ 20 pages) | Give it to the model directly. Current models read rendered page images, math included. |
| Long PDF | [Marker](https://github.com/datalab-to/marker) on a GPU: `marker_single paper.pdf --force_ocr --paginate_output`. On a 15-paper test battery it beat this tool's OCR on equations, two-column reading order, tables and figure captions. |
| `.docx` | `pandoc -t markdown file.docx` (equations come out as LaTeX). |
| Figure descriptions | Not needed: models can look at the figure (the file, or the rendered page) themselves. |

## Installation

```bash
uv tool install latex-llm-cleaner     # or: pipx install latex-llm-cleaner
```

Upgrading from 0.x: `uv tool install --force latex-llm-cleaner` (the old `[ocr]` extra no longer exists).

## Usage

```bash
latex-llm-cleaner paper.tex                        # cleaned LaTeX to stdout
latex-llm-cleaner paper.tex -o cleaned.tex         # to a file
latex-llm-cleaner paper.tex --no-bibliography      # skip bibliography inlining
latex-llm-cleaner slides.pptx -o slides.md         # slides as markdown
latex-llm-cleaner slides.pptx --notes -o slides.md # include speaker notes
```

All steps are on by default; disable them individually:

```
latex-llm-cleaner INPUT_FILE [options]

  -o, --output FILE     Write to FILE (default: stdout)
  --no-flatten          Disable \input/\include flattening
  --no-comments         Disable comment removal
  --no-macros           Disable macro expansion
  --keep-usepackage     Keep \usepackage lines (dropped by default)
  --no-bibliography     Disable bibliography inlining
  --notes               Include speaker notes (PPTX)
  --encoding ENC        File encoding (default: utf-8)
  -v, --verbose         Print processing info to stderr
```

## LaTeX pipeline

Four steps, in order:

1. **Flatten includes:** inline `\input{}`, `\include{}` and `\subfile{}` recursively, resolved from the main file's directory, with cycle detection.
2. **Remove comments:** strip `%` comments, respecting `\%` escapes and verbatim environments.
3. **Expand macros:** substitute `\newcommand`, `\renewcommand`, `\def` and `\DeclareMathOperator` where the expansion reads better than the name (`\Secref{x}` → `Section~\ref{x}`, `\train` → `\mathcal{D}`); leave self-documenting names like `\norm` alone and just drop their definitions. Pure-rendering preamble (`\usetikzlibrary`, `\definecolor`, `\newtheorem`, …) and `\usepackage` lines are removed (`--keep-usepackage` keeps the latter). Handles 0–9 arguments, optional arguments with defaults, and nested macros.
4. **Inline bibliography:** use the `.bbl` if present, otherwise parse the `.bib`, and replace `\bibliography{}` with a `thebibliography` block.

Figures are left as `\includegraphics{path}`: the path tells the reader which file to open.

## PowerPoint output

Each slide becomes `# Slide N: Title`, separated by `---`. Tables become pipe tables, equations become `$...$` LaTeX, and pictures become `[Image]` (with the picture's alt text when it has some). Speaker notes are excluded unless `--notes` is given.

## Development

```bash
uv run pytest
```
