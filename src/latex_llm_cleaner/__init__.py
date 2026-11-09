"""LaTeX LLM Cleaner — flatten and clean LaTeX (and PPTX) for LLM consumption."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("latex-llm-cleaner")
except PackageNotFoundError:  # running from a source tree without install
    __version__ = "unknown"
