# LaTeX LLM Cleaner

A CLI tool that converts LaTeX `.tex`, compiled `.pdf`, PowerPoint `.pptx`, and Word `.docx` files into clean text for feeding to language models.

## Why this matters

Documents weren't designed to be read by language models. Each format loses information in its own way when you extract text from it:

- **PDF** is the worst case. It's a *display* format — it stores glyph positions, not semantic content. Math fonts often use character codes that don't match their visual appearance. Tables have no structure; extractors guess cell boundaries from character positions. Figures are typically ignored entirely.
- **PPTX/DOCX** store equations as Office MathML — verbose XML that models struggle to interpret correctly.
- **LaTeX** source may be split across dozens of `\input` files, full of custom macros, with figures as opaque file paths.

In all cases, the model receives something different from what the author wrote, and neither the model nor the user can tell.

Here's what a standard text extractor produces from a page of a compiled paper (PDF):

```
qA =ω+(ε → ω)x , qB =ω(1 → x )
 1          1   1       1

Pg = 1/2 for all i, g
 i

dϖ   1  dPA       1  dPB
 1 =   1 (ε → ω)+   1 ( → ω)
dx   2 · dqA ·     2 · dqB ·
 1        1             1
```

Minus signs become arrows. Subscripts and superscripts scatter across lines. Greek letters map to wrong Unicode points. The model reads this confidently and reasons from it.

The same page with `latex-llm-cleaner --ocr`:

```
$q_1^A = \beta + (\alpha - \beta)x_1, \qquad q_1^B = \beta(1 - x_1)$

$P_i^g = 1/2$ for all $i, g$

$$\frac{d\pi_1}{dx_1}\bigg|_{x_1=x_2=0} = \frac{1}{2} \cdot \frac{dP_1^A}{dq_1^A} \cdot (\alpha - \beta) + \frac{1}{2} \cdot \frac{dP_1^B}{dq_1^B} \cdot (-\beta)$$
```

None of these formats were built for the document-to-model pipeline. Until one is, this tool bridges the gap: OCR for math, vision-based summarization for figures and tables, OMML-to-LaTeX conversion, and structured markdown output.

## Installation

```bash
pip install latex-llm-cleaner
```

For OCR-based equation recovery from PDFs (requires Python ≤ 3.13):

```bash
pip install 'latex-llm-cleaner[ocr]'
```

### Global install

```bash
# Recommended:
uv tool install --prerelease=allow latex-llm-cleaner
uv tool install --prerelease=allow 'latex-llm-cleaner[ocr]'

# Alternative (pipx):
pipx install latex-llm-cleaner
pipx inject latex-llm-cleaner surya-ocr 'transformers<5'   # for OCR
```

> **Note:** `--prerelease=allow` is needed because bibtexparser v2 is still in beta. `pip install` handles this automatically.

> **Note:** OCR requires `libjpeg` headers. On macOS: `brew install jpeg`

### From source

```bash
pip install -e ".[dev]"
```

## Usage

```bash
latex-llm-cleaner paper.tex                       # output to stdout
latex-llm-cleaner paper.tex -o cleaned.tex        # output to file
latex-llm-cleaner paper.tex --no-bibliography     # skip bib inlining
latex-llm-cleaner thesis.pdf -o thesis.md          # extract text from PDF
latex-llm-cleaner thesis.pdf --ocr -o thesis.md   # OCR with LaTeX equation recovery
latex-llm-cleaner slides.pptx -o slides.md         # extract slides from PPTX
latex-llm-cleaner slides.pptx --notes -o slides.md # include speaker notes
latex-llm-cleaner report.docx -o report.md         # extract text from Word doc
latex-llm-cleaner report.docx --notes -o report.md # include Word comments
latex-llm-cleaner paper.tex --auto-summarize       # generate figure summaries via Gemini
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
  --notes                    Include speaker notes (PPTX) or comments (DOCX)
  --ocr                      Use Surya vision OCR for PDFs (recovers LaTeX equations, slower)
  --auto-summarize           Generate figure summaries via Gemini vision API
  --google-api-key KEY       API key for --auto-summarize (default: GOOGLE_API_KEY env var)
  --encoding ENC             File encoding (default: utf-8)
  -v, --verbose              Print processing info to stderr
```

## PDF Input

Extracts text as markdown, preserving table structure. Tables become markdown pipe-tables. Images become `[picture omitted]` placeholders (or text summaries if summary files exist).

The `.tex` pipeline flags (`--no-flatten`, etc.) are ignored for PDF input.

### OCR mode

The default extraction is fast but loses display equations. The `--ocr` flag uses [Surya](https://github.com/VikParuchuri/surya) vision OCR to recover them as LaTeX (`$...$` and `$$...$$`). Slower (~30s/page on Apple Silicon). Requires Python ≤ 3.13.

```bash
pip install 'latex-llm-cleaner[ocr]'
latex-llm-cleaner thesis.pdf --ocr -o thesis.md
```

## PPTX Input

Each slide becomes a markdown section (`# Slide N: Title`), separated by `---`. Tables are output as pipe-tables. Images become `[Image]` placeholders unless a summary file exists.

Speaker notes are excluded by default; use `--notes` to include them.

OMML equations in the presentation are converted to LaTeX.

### Image summaries for PPTX

Place summary files next to the `.pptx` using this naming convention:

```
slides.pptx
slides_slide1_image1_summary.txt
slides_slide3_image2_summary.txt
```

## DOCX Input

Extracts headings, tables (as pipe-tables), bold/italic formatting, and images (with summaries or `[Image]` placeholders). OMML equations are converted to LaTeX.

Use `--notes` to include Word comments (rendered as blockquotes with author attribution).

## Auto-Summarize

The `--auto-summarize` flag generates text descriptions of figures using the Gemini vision API, so you don't have to write summary files by hand. Works with PDF, PPTX, DOCX, and LaTeX input.

Requires a Google API key:

```bash
export GOOGLE_API_KEY=your-key
latex-llm-cleaner paper.tex --auto-summarize -o cleaned.tex
```

Summaries are written as `_summary.txt` files next to each figure. On subsequent runs, existing summaries are reused. The goal is data-equivalent descriptions: what you'd learn from looking at the figure, nothing more.

## Processing Pipeline (.tex files)

Five steps, in order (each operates on the output of the previous):

1. **Flatten includes** — inline `\input{}`, `\include{}`, and `\subfile{}` recursively, with cycle detection
2. **Remove comments** — strip `%` comments while respecting `\%` escapes and verbatim environments
3. **Expand macros** — substitute `\newcommand`, `\renewcommand`, `\def`, `\DeclareMathOperator` inline. Handles 0–9 arguments, optional arguments with defaults, and nested macros via multi-pass expansion. Also strips `\usepackage` lines (use `--keep-usepackage` to retain).
4. **Inline bibliography** — use a `.bbl` file if available, otherwise parse `.bib`; replaces `\bibliography{}` with a `\begin{thebibliography}` block
5. **Figure summary substitution** — replace `\includegraphics` with text descriptions from summary files

## Figure Summaries

For each image (e.g., `figs/plot.png`), place a summary file alongside it:

```
figs/plot.png              ← the image
figs/plot_summary.txt      ← the text summary
```

A summary should be **data-equivalent** to the figure: the same information a reader would get from looking at it, nothing more.

Good example:
> Bar chart with four groups (A, B, C, D). Method X scores 0.92, 0.87, 0.76, 0.81. Method Y scores 0.85, 0.91, 0.80, 0.74. Error bars show standard deviation across 5 runs.

Bad example:
> This figure clearly demonstrates the superiority of Method X, which aligns with our hypothesis.

## Development

```bash
pip install -e ".[dev]"
pytest
```
