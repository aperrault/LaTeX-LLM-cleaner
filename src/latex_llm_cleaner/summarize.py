"""Auto-generate figure summaries using the Gemini vision API."""

import mimetypes
import sys
import time
from functools import wraps
from pathlib import Path

from .figures import _INCLUDEGRAPHICS_RE, _IMAGE_EXTENSIONS, _find_summary

_PROMPT = (
    "Describe this figure so that someone who cannot see it has all the same "
    "information. For charts and plots, extract the data into tables. For "
    "diagrams, describe the structure and relationships. For photographs, "
    "describe what is shown. Do not editorialize or interpret beyond what "
    "the figure itself conveys."
)

_MODEL = "gemini-3.1-flash-lite-preview"


def _retry_with_backoff(max_retries=3, base_delay=10, max_delay=60):
    """Retry decorator with exponential backoff for transient API errors."""

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    error_str = str(e).lower()
                    retryable = any(
                        x in error_str
                        for x in [
                            "timeout",
                            "503",
                            "502",
                            "504",
                            "429",
                            "unavailable",
                            "cancelled",
                            "overloaded",
                            "rate limit",
                            "connection",
                        ]
                    )
                    if not retryable or attempt == max_retries - 1:
                        raise
                    delay = min(base_delay * (2**attempt), max_delay)
                    print(
                        f"  Retrying in {delay}s (attempt {attempt + 1}/{max_retries})...",
                        file=sys.stderr,
                    )
                    time.sleep(delay)
            raise last_exception  # type: ignore[misc]

        return wrapper

    return decorator


def _resolve_image_path(base_dir: Path, img_path_str: str) -> Path | None:
    """Find the actual image file on disk, probing extensions if needed."""
    img_path = base_dir / img_path_str

    if img_path.is_file():
        return img_path

    # If no extension, try common image extensions
    if img_path.suffix.lower() not in _IMAGE_EXTENSIONS:
        for ext in _IMAGE_EXTENSIONS:
            candidate = base_dir / (img_path_str + ext)
            if candidate.is_file():
                return candidate

    return None


def _get_mime_type(image_path: Path) -> str:
    """Detect MIME type from file extension."""
    mime, _ = mimetypes.guess_type(str(image_path))
    return mime or "application/octet-stream"


@_retry_with_backoff()
def _call_gemini(client, image_path: Path, prompt: str) -> str:
    """Send image + prompt to Gemini, return generated text."""
    from google.genai import types  # noqa: E402

    image_bytes = image_path.read_bytes()
    mime_type = _get_mime_type(image_path)

    response = client.models.generate_content(
        model=_MODEL,
        contents=[
            types.Content(
                parts=[
                    types.Part.from_bytes(data=image_bytes, mime_type=mime_type),
                    types.Part.from_text(text=prompt),
                ]
            )
        ],
    )
    return response.text


def auto_summarize_figures(content: str, base_dir: Path, options: dict) -> str:
    """Generate summary files for figures that lack them.

    This function has side effects (writes _summary.txt files) but returns
    the content string unchanged.  The subsequent substitute_figures step
    will pick up the newly created summaries.
    """
    try:
        from google import genai  # noqa: E402
    except ImportError:
        print(
            "Error: google-genai is required for --auto-summarize.\n"
            "Install it with: pip install 'latex-llm-cleaner[summarize]'",
            file=sys.stderr,
        )
        sys.exit(1)

    api_key = options.get("google_api_key")
    if not api_key:
        print(
            "Error: No Google API key found. Set GOOGLE_API_KEY or use --google-api-key.",
            file=sys.stderr,
        )
        sys.exit(1)

    verbose = options.get("verbose", False)
    suffix = options.get("figure_summary_suffix", "_summary.txt")
    encoding = options.get("encoding", "utf-8")

    # Collect unique image paths
    seen: set[str] = set()
    image_paths: list[str] = []
    for m in _INCLUDEGRAPHICS_RE.finditer(content):
        img_path_str = m.group(1).strip()
        if img_path_str not in seen:
            seen.add(img_path_str)
            image_paths.append(img_path_str)

    if not image_paths:
        if verbose:
            print("  No figures found to summarize.", file=sys.stderr)
        return content

    client = genai.Client(api_key=api_key)
    generated = 0

    for img_path_str in image_paths:
        # Skip if summary already exists
        existing = _find_summary(base_dir, img_path_str, suffix, encoding)
        if existing is not None:
            if verbose:
                print(f"  Skipping {img_path_str} (summary exists)", file=sys.stderr)
            continue

        # Resolve actual image file
        image_path = _resolve_image_path(base_dir, img_path_str)
        if image_path is None:
            if verbose:
                print(
                    f"  Warning: image file not found for {img_path_str}",
                    file=sys.stderr,
                )
            continue

        # Generate summary
        if verbose:
            print(f"  Generating summary for {img_path_str}...", file=sys.stderr)

        try:
            summary_text = _call_gemini(client, image_path, _PROMPT)
        except Exception as e:
            print(
                f"  Warning: API error for {img_path_str}: {e}",
                file=sys.stderr,
            )
            continue

        # Write summary file
        if image_path.suffix.lower() in _IMAGE_EXTENSIONS:
            stem_path = image_path.with_suffix("")
        else:
            stem_path = image_path
        summary_path = Path(str(stem_path) + suffix)
        summary_path.write_text(summary_text, encoding=encoding)
        generated += 1

        if verbose:
            print(f"  Wrote {summary_path}", file=sys.stderr)

    if verbose:
        print(
            f"  Generated {generated} summary file(s) "
            f"({len(image_paths) - generated} skipped).",
            file=sys.stderr,
        )

    return content
