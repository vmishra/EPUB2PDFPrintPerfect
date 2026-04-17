"""PDF rendering module - converts merged HTML to PDF using WeasyPrint."""

from __future__ import annotations

import logging
import sys
import time
from pathlib import Path
from typing import TYPE_CHECKING

from tqdm import tqdm

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


class ProgressTracker:
    """Track and display rendering progress."""

    def __init__(self, verbose: bool = False) -> None:
        self.verbose = verbose
        self._start_time: float = 0
        self._pbar: tqdm | None = None

    def start(self, description: str) -> None:
        self._start_time = time.monotonic()
        if sys.stderr.isatty():
            self._pbar = tqdm(
                total=100,
                desc=description,
                unit="%",
                bar_format="{desc}: {bar} {percentage:.0f}% [{elapsed}<{remaining}]",
                file=sys.stderr,
            )

    def update(self, percentage: int) -> None:
        if self._pbar is not None:
            delta = percentage - self._pbar.n
            if delta > 0:
                self._pbar.update(delta)

    def finish(self) -> None:
        if self._pbar is not None:
            self._pbar.update(100 - self._pbar.n)
            self._pbar.close()
            self._pbar = None
        elapsed = time.monotonic() - self._start_time
        logger.info("Rendering completed in %.1fs", elapsed)


def _suppress_weasyprint_warnings() -> None:
    """Suppress noisy WeasyPrint warnings about missing fonts, etc."""
    for name in ("weasyprint", "fontTools", "weasyprint.css",
                 "weasyprint.css.validation", "weasyprint.html"):
        logging.getLogger(name).setLevel(logging.ERROR)


def render_pdf(
    html_content: str,
    output_path: Path,
    verbose: bool = False,
) -> Path:
    """Render merged HTML content to PDF using WeasyPrint.

    Args:
        html_content: Complete HTML string with embedded images and CSS.
        output_path: Where to write the PDF file.
        verbose: If True, show detailed WeasyPrint logging.

    Returns:
        Path to the generated PDF file.
    """
    # Import here to avoid slow startup when just checking --help
    import weasyprint

    if not verbose:
        _suppress_weasyprint_warnings()

    tracker = ProgressTracker(verbose=verbose)

    output_path = output_path.resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    logger.info("Rendering PDF to: %s", output_path)
    tracker.start("Rendering PDF")

    try:
        # Parse HTML
        tracker.update(10)
        doc = weasyprint.HTML(string=html_content)

        # Render to PDF
        tracker.update(30)
        doc.write_pdf(str(output_path))
        tracker.update(100)

    except Exception as e:
        tracker.finish()
        error_msg = str(e) if str(e) else type(e).__name__
        raise RuntimeError(f"PDF rendering failed: {error_msg}") from e

    tracker.finish()

    file_size = output_path.stat().st_size
    size_mb = file_size / (1024 * 1024)
    logger.info("PDF generated: %s (%.1f MB)", output_path.name, size_mb)

    return output_path
