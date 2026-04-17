"""Command-line interface for epub2pdf."""

from __future__ import annotations

import argparse
import logging
import sys
import time
from pathlib import Path

from . import __version__

logger = logging.getLogger("epub2pdf")

VALID_PAGE_SIZES = ("A4", "A5", "Letter", "Legal", "B5")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="epub2pdf",
        description="Convert EPUB files to high-quality PDF with preserved formatting.",
        epilog=(
            "Examples:\n"
            "  epub2pdf book.epub\n"
            "  epub2pdf book.epub --output book.pdf\n"
            "  epub2pdf book.epub --page-size Letter --margin 1in\n"
            "  epub2pdf book.epub --font-size 12pt --no-images\n"
            "  epub2pdf book.epub --toc --verbose\n"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument(
        "input",
        type=str,
        help="Path to the EPUB file to convert",
    )
    parser.add_argument(
        "-o", "--output",
        type=str,
        default=None,
        help="Output PDF path (default: same name as input with .pdf extension)",
    )
    parser.add_argument(
        "--page-size",
        type=str,
        default="A4",
        choices=VALID_PAGE_SIZES,
        help="Page size for the PDF (default: A4)",
    )
    parser.add_argument(
        "--margin",
        type=str,
        default="2cm",
        help="Page margins, e.g. '2cm', '1in', '20mm' (default: 2cm)",
    )
    parser.add_argument(
        "--font-size",
        type=str,
        default=None,
        help="Override base font size, e.g. '12pt', '14px' (default: browser default)",
    )
    parser.add_argument(
        "--no-images",
        action="store_true",
        help="Strip all images from the output PDF",
    )
    parser.add_argument(
        "--toc",
        action="store_true",
        help="Generate a table of contents page at the beginning",
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable verbose/debug logging",
    )
    parser.add_argument(
        "-q", "--quiet",
        action="store_true",
        help="Suppress all output except errors",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )

    return parser


def _setup_logging(verbose: bool, quiet: bool) -> None:
    level = logging.DEBUG if verbose else (logging.ERROR if quiet else logging.INFO)
    root = logging.getLogger("epub2pdf")
    root.setLevel(level)
    # Avoid adding duplicate handlers on repeated calls
    if not root.handlers:
        handler = logging.StreamHandler(sys.stderr)
        handler.setFormatter(logging.Formatter("%(levelname)s: %(message)s"))
        root.addHandler(handler)


def _resolve_output_path(input_path: Path, output_arg: str | None) -> Path:
    if output_arg:
        return Path(output_arg).resolve()
    return input_path.with_suffix(".pdf")


def convert(args: argparse.Namespace) -> int:
    """Run the full EPUB-to-PDF conversion pipeline."""
    from .epub_parser import parse_epub
    from .html_processor import generate_toc_html, merge_chapters
    from .pdf_renderer import render_pdf

    input_path = Path(args.input).resolve()
    output_path = _resolve_output_path(input_path, args.output)

    start_time = time.monotonic()

    # Step 1: Parse EPUB
    logger.info("Parsing EPUB: %s", input_path.name)
    try:
        epub_data = parse_epub(input_path)
    except FileNotFoundError as e:
        logger.error("%s", e)
        return 1
    except ValueError as e:
        logger.error("%s", e)
        return 1

    if not epub_data.chapters:
        logger.error("No content found in EPUB: %s", input_path.name)
        return 1

    logger.info(
        "Found %d chapters, %d images",
        len(epub_data.chapters),
        len(epub_data.images),
    )

    # Step 2: Process and merge HTML
    logger.info("Processing chapters...")
    html_content = merge_chapters(
        epub_data,
        no_images=args.no_images,
        page_size=args.page_size,
        margin=args.margin,
        font_size=args.font_size,
    )

    # Step 2.5: Insert TOC if requested
    if args.toc:
        toc_html = generate_toc_html(epub_data)
        if toc_html:
            html_content = html_content.replace(
                "<body>",
                f"<body>\n{toc_html}",
                1,
            )
            logger.info("Table of contents generated")

    # Step 3: Render PDF
    try:
        render_pdf(html_content, output_path, verbose=args.verbose)
    except RuntimeError as e:
        logger.error("%s", e)
        return 1

    elapsed = time.monotonic() - start_time
    logger.info("Done in %.1fs: %s", elapsed, output_path)

    return 0


def main(argv: list[str] | None = None) -> int:
    """Entry point for the epub2pdf CLI."""
    parser = build_parser()
    args = parser.parse_args(argv)
    _setup_logging(args.verbose, args.quiet)

    try:
        return convert(args)
    except KeyboardInterrupt:
        logger.info("Interrupted")
        return 130
    except Exception as e:
        logger.error("Unexpected error: %s", e)
        if args.verbose:
            import traceback
            traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
