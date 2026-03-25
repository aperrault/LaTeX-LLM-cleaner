# LaTeX LLM Cleaner

A Python CLI tool that takes a LaTeX `.tex` file or compiled `.pdf` and produces a cleaned text version optimized for LLM consumption. Combines functionality from tools like [flachtex](https://github.com/simonsan/flachtex), [arxiv_latex_cleaner](https://github.com/google-research/arxiv-latex-cleaner), and [pandoc](https://pandoc.org/) into a single utility.

## Installation

```bash
pip install latex-llm-cleaner

# With PDF support:
pip install latex-llm-cleaner[pdf]
```

Or from source:

```bash
pip install .
# or for development:
pip install -e ".[dev]"
```

## Usage

```bash
latex-llm-cleaner paper.tex                    # output to stdout
latex-llm-cleaner paper.tex -o cleaned.tex     # output to file
latex-llm-cleaner paper.tex --no-bibliography  # skip bib inlining
latex-llm-cleaner thesis.pdf -o thesis.md      # extract text from PDF
latex-llm-cleaner thesis.pdf --ocr -o thesis.md  # OCR with LaTeX equation recovery
```

All features are **on by default**. Disable individual steps with `--no-*` flags:

```
latex-llm-cleaner INPUT_FILE [options]

Options:
  -o, --output FILE          Write to FILE (default: stdout)
  --no-flatten               Disable \input/\include flattening
  --no-comments              Disable comment removal
  --no-bibliography          Disable bibliography inlining
  --no-figures               Disable figure summary substitution
  --figure-summary-suffix S  Suffix for summary files (default: _summary.txt)
  --ocr                      Use Surya vision OCR (recovers LaTeX equations, slower)
  --encoding ENC             File encoding (default: utf-8)
  -v, --verbose              Print processing info to stderr
```

## PDF Input

For compiled PDFs (e.g., theses, published papers), latex-llm-cleaner extracts the text as markdown, preserving table structure and dropping images. This requires the optional `pdf` extra:

```bash
pip install latex-llm-cleaner[pdf]
latex-llm-cleaner thesis.pdf -o thesis.md
```

Tables are output as markdown tables with `|` delimiters. Images are noted as `[picture omitted]` placeholders. The `.tex` pipeline flags (`--no-flatten`, etc.) are ignored for PDF input since they don't apply.

### OCR mode (equation recovery)

The default PDF extraction is fast but loses display equations. For compiled LaTeX PDFs, the `--ocr` flag uses [Surya](https://github.com/VikParuchuri/surya) vision-based OCR to recover equations as LaTeX source:

```bash
pip install latex-llm-cleaner[ocr]
latex-llm-cleaner thesis.pdf --ocr -o thesis.md
```

This reconstructs inline math as `$...$` and display equations as `$$...$$` with full LaTeX notation. It's slower (~30s/page on Apple Silicon) but dramatically more accurate for math-heavy documents. Requires Python ≤ 3.13.

## Processing Pipeline (.tex files)

The four steps run in this order (each operates on the output of the previous step):

1. **Flatten includes** — inline `\input{}`, `\include{}`, and `\subfile{}` recursively, with cycle detection
2. **Remove comments** — strip `%` comments while respecting `\%` escapes and verbatim environments
3. **Inline bibliography** — use a pre-compiled `.bbl` file if available (common in arXiv downloads), otherwise parse `.bib` files; replaces `\bibliography{}` with a `\begin{thebibliography}` block
4. **Figure summary substitution** — replace `\includegraphics` with text descriptions when summary files are available

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
