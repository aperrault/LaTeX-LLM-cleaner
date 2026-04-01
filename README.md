# LaTeX LLM Cleaner

A Python CLI tool that takes a LaTeX `.tex` file, compiled `.pdf`, or PowerPoint `.pptx` and produces a cleaned text version optimized for LLM consumption. Combines functionality from tools like [flachtex](https://github.com/simonsan/flachtex), [arxiv_latex_cleaner](https://github.com/google-research/arxiv-latex-cleaner), and [pandoc](https://pandoc.org/) into a single utility.

## Installation

```bash
pip install latex-llm-cleaner
```

This includes support for `.tex`, `.pdf`, and `.pptx` files out of the box.

For OCR-based equation recovery from PDFs (requires Python ≤ 3.13):

```bash
pip install 'latex-llm-cleaner[ocr]'
```

### Global install

```bash
# Recommended — handles extras natively:
uv tool install --prerelease=allow latex-llm-cleaner
uv tool install --prerelease=allow 'latex-llm-cleaner[ocr]'

# Alternative (pipx):
pipx install latex-llm-cleaner
# For OCR with pipx, inject the heavy dependencies:
pipx inject latex-llm-cleaner surya-ocr 'transformers<5'
```

> **Note:** The `--prerelease=allow` flag is needed because bibtexparser v2 is still in beta. `pip install` handles this automatically.

> **Note:** OCR requires `libjpeg` headers. On macOS: `brew install jpeg`

### From source

```bash
pip install -e ".[dev]"
```

## Usage

```bash
latex-llm-cleaner paper.tex                    # output to stdout
latex-llm-cleaner paper.tex -o cleaned.tex     # output to file
latex-llm-cleaner paper.tex --no-bibliography  # skip bib inlining
latex-llm-cleaner paper.tex --no-macros        # skip macro expansion
latex-llm-cleaner thesis.pdf -o thesis.md      # extract text from PDF
latex-llm-cleaner thesis.pdf --ocr -o thesis.md  # OCR with LaTeX equation recovery
latex-llm-cleaner slides.pptx -o slides.md       # extract slides from PPTX
latex-llm-cleaner slides.pptx --notes -o slides.md  # include speaker notes
```

All features are **on by default**. Disable individual steps with `--no-*` flags:

```
latex-llm-cleaner INPUT_FILE [options]

Options:
  -o, --output FILE          Write to FILE (default: stdout)
  --no-flatten               Disable \input/\include flattening
  --no-comments              Disable comment removal
  --no-macros                Disable macro expansion
  --keep-usepackage          Keep \usepackage lines (dropped by default)
  --no-bibliography          Disable bibliography inlining
  --no-figures               Disable figure summary substitution
  --figure-summary-suffix S  Suffix for summary files (default: _summary.txt)
  --notes                    Include speaker notes (PPTX only)
  --ocr                      Use Surya vision OCR (recovers LaTeX equations, slower)
  --encoding ENC             File encoding (default: utf-8)
  -v, --verbose              Print processing info to stderr
```

## PDF Input

For compiled PDFs (e.g., theses, published papers), latex-llm-cleaner extracts the text as markdown, preserving table structure and dropping images. Tables are output as markdown tables with `|` delimiters. Images are noted as `[picture omitted]` placeholders. The `.tex` pipeline flags (`--no-flatten`, etc.) are ignored for PDF input since they don't apply.

### OCR mode (equation recovery)

The default PDF extraction is fast but loses display equations. For compiled LaTeX PDFs, the `--ocr` flag uses [Surya](https://github.com/VikParuchuri/surya) vision-based OCR to recover equations as LaTeX source:

```bash
pip install 'latex-llm-cleaner[ocr]'
latex-llm-cleaner thesis.pdf --ocr -o thesis.md
```

This reconstructs inline math as `$...$` and display equations as `$$...$$` with full LaTeX notation. It's slower (~30s/page on Apple Silicon) but dramatically more accurate for math-heavy documents. Requires Python ≤ 3.13.

## PPTX Input

Each slide becomes a markdown section with a heading (`# Slide N: Title`), separated by `---`. Tables are output as markdown pipe-tables. Images are shown as `[Image]` placeholders unless a summary file is provided (see below).

Speaker notes are excluded by default. Use `--notes` to include them:

```bash
latex-llm-cleaner slides.pptx --notes -o slides.md
```

Equations stored as Office MathML (OMML) in the presentation are passed through as XML, which LLMs can read directly.

### Image summaries for PPTX

Since images are embedded in PPTX files (no file paths), summaries use a slide/image numbering convention. Place summary files in the same directory as the `.pptx`:

```
slides.pptx
slide1_image1_summary.txt    ← first image on slide 1
slide3_image1_summary.txt    ← first image on slide 3
slide3_image2_summary.txt    ← second image on slide 3
```

The `--figure-summary-suffix` flag works here too (default: `_summary.txt`).

## Processing Pipeline (.tex files)

The five steps run in this order (each operates on the output of the previous step):

1. **Flatten includes** — inline `\input{}`, `\include{}`, and `\subfile{}` recursively, with cycle detection
2. **Remove comments** — strip `%` comments while respecting `\%` escapes and verbatim environments
3. **Expand macros** — substitute user-defined macros (`\newcommand`, `\renewcommand`, `\def`, `\DeclareMathOperator`) inline and remove definitions. Handles macros with 0–9 arguments, optional arguments with defaults, and nested macros via multi-pass expansion. `\newtheorem` and `\let` commands are preserved. Also strips `\usepackage` lines (use `--keep-usepackage` to retain them).
4. **Inline bibliography** — use a pre-compiled `.bbl` file if available (common in arXiv downloads), otherwise parse `.bib` files; replaces `\bibliography{}` with a `\begin{thebibliography}` block
5. **Figure summary substitution** — replace `\includegraphics` with text descriptions when summary files are available

## Figure Summaries

LLMs (as of early 2026) are still poor at extracting precise information from complex figures in papers — dense plots, multi-panel layouts, small labels, etc. To work around this, latex-llm-cleaner can replace figures with equivalent text descriptions.

For each image (e.g., `figs/plot.png`), place a summary file alongside it with the configured suffix:

```
figs/plot.png              ← the image
figs/plot_summary.txt      ← the text summary
```

### What to put in a summary

A summary should be **data-equivalent** to the figure: it should convey the same information a reader would get from looking at the figure, and nothing more. Avoid editorial commentary, interpretation, or conclusions that aren't visually present in the figure itself.

Good example:
> Bar chart with four groups (A, B, C, D). Method X scores 0.92, 0.87, 0.76, 0.81. Method Y scores 0.85, 0.91, 0.80, 0.74. Error bars show standard deviation across 5 runs.

Bad example:
> This figure clearly demonstrates the superiority of Method X, which aligns with our hypothesis.

### Accessibility benefits

LaTeX has limited built-in support for producing accessible output — generated PDFs typically lack alt-text for figures, making them difficult to navigate with screen readers. These same summary files can serve as alt-text source material when compiling to tagged PDF or HTML, improving accessibility beyond the LLM use case.

## Development

```bash
pip install -e ".[dev]"
pytest
```
