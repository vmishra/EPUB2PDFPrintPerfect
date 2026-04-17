<div align="center">

# EPUB2PDFPrintPerfect

### Convert EPUB ebooks into beautiful, print-ready PDFs.

[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-3776AB.svg?logo=python&logoColor=white)](https://python.org)
[![Code style: ruff](https://img.shields.io/badge/code%20style-ruff-000000.svg)](https://github.com/astral-sh/ruff)

**No more ugly conversions.** Proper chapter breaks. Embedded images. Page numbers. Typography that doesn't hurt your eyes.

[Getting Started](#getting-started) &bull; [Usage](#usage) &bull; [Examples](#examples) &bull; [How It Works](#how-it-works) &bull; [API](#python-api)

</div>

---

## The Problem

Every existing EPUB-to-PDF tool produces the same result: broken layouts, missing images, no page numbers, walls of text with no chapter separation. You end up with a PDF that looks like someone printed a webpage from 2003.

**EPUB2PDFPrintPerfect** exists because converting a book shouldn't mean destroying it.

## What You Get

```
epub2pdf book.epub
```

That's it. One command. Out comes a PDF with:

- **Real typography** &mdash; serif fonts, justified text, 1.6 line height, proper orphan/widow control
- **Chapter separation** &mdash; automatic page breaks between every chapter
- **Embedded images** &mdash; properly scaled, never overflowing the page
- **Page numbers** &mdash; centered at the bottom, hidden on the first page
- **Table of contents** &mdash; auto-generated from chapter titles (with `--toc`)
- **Original styling preserved** &mdash; EPUB CSS is sanitized and kept where it helps

### Performance

| Book | Chapters | Images | PDF Size | Time |
|------|----------|--------|----------|------|
| 300-page non-fiction | 27 | 23 | 5.0 MB | ~5s |
| 400-page finance book | 45 | 222 | 11.2 MB | ~15s |
| 50-chapter tweetstorm | 56 | 2 | 1.4 MB | ~3s |

---

## Getting Started

### Prerequisites

WeasyPrint needs a few system libraries for font/image rendering:

```bash
# Ubuntu / Debian
sudo apt install libpango1.0-dev libcairo2-dev libgdk-pixbuf2.0-dev libffi-dev

# macOS
brew install pango cairo gdk-pixbuf libffi

# Fedora / RHEL
sudo dnf install pango-devel cairo-devel gdk-pixbuf2-devel libffi-devel

# Arch
sudo pacman -S pango cairo gdk-pixbuf2 libffi
```

### Install

```bash
git clone https://github.com/vmishra/EPUB2PDFPrintPerfect.git
cd EPUB2PDFPrintPerfect
pip install -e .
```

Or without cloning:

```bash
pip install ebooklib beautifulsoup4 lxml weasyprint Pillow tqdm
# then run directly with: python -m epub2pdf
```

### Verify

```bash
epub2pdf --version
```

---

## Usage

```
epub2pdf <input.epub> [options]
```

### Options

| Flag | Description | Default |
|:-----|:------------|:--------|
| `-o, --output <path>` | Output PDF file path | Same as input, with `.pdf` |
| `--page-size <size>` | `A4` `A5` `Letter` `Legal` `B5` | `A4` |
| `--margin <size>` | CSS margin value (`2cm`, `1in`, `20mm`) | `2cm` |
| `--font-size <size>` | Base font size (`12pt`, `14px`) | Browser default |
| `--toc` | Prepend a generated table of contents | Off |
| `--no-images` | Strip all images (smaller output) | Off |
| `-v, --verbose` | Debug-level logging | Off |
| `-q, --quiet` | Errors only | Off |

---

## Examples

**Basic &mdash; just convert it:**
```bash
epub2pdf book.epub
# => book.pdf in the same directory
```

**Custom output path:**
```bash
epub2pdf book.epub -o ~/Documents/book.pdf
```

**US Letter, 1-inch margins, with TOC:**
```bash
epub2pdf book.epub --page-size Letter --margin 1in --toc
```

**Large print edition:**
```bash
epub2pdf book.epub --font-size 16pt --page-size A4
```

**Text-only (no images, minimal file size):**
```bash
epub2pdf book.epub --no-images -o book-text.pdf
```

**Debug a problematic EPUB:**
```bash
epub2pdf book.epub --verbose 2>&1 | head -50
```

**Batch convert a directory:**
```bash
for f in ~/Books/*.epub; do
  epub2pdf "$f" --toc --quiet
done
```

**Use as a Python module:**
```bash
python -m epub2pdf book.epub --output book.pdf
```

---

## How It Works

```
                    EPUB2PDFPrintPerfect Pipeline
                    ============================

    .epub file
        |
        v
   +-----------+     Validate ZIP structure, check META-INF/container.xml
   | Validate  |     Catch corrupt files early with clear error messages
   +-----------+
        |
        v
   +-----------+     ebooklib parses OPF manifest + spine ordering
   |   Parse   |     Extract chapters, images (incl. covers), CSS, metadata
   +-----------+
        |
        v
   +-----------+     Strip scripts, forms, iframes, comments
   |   Clean   |     Sanitize inline styles (float, position:fixed)
   +-----------+     Handle UTF-8 / latin-1 encoding gracefully
        |
        v
   +-----------+     Resize images >1600px (Lanczos downsampling)
   |  Process  |     Convert to base64 data URIs for self-contained HTML
   +-----------+     Resolve relative paths, URL-decoded filenames
        |
        v
   +-----------+     Merge chapters in spine order with page-break separators
   |   Merge   |     Apply print CSS: typography, margins, page counters
   +-----------+     Sanitize EPUB CSS: strip @font-face, float, overflow
        |
        v
   +-----------+     WeasyPrint renders the merged HTML document
   |  Render   |     Outputs PDF 1.7 with embedded fonts + images
   +-----------+     Progress bar on stderr for large books
        |
        v
     .pdf file
```

### Project Structure

```
src/epub2pdf/
├── cli.py              # CLI argument parsing, pipeline orchestration
├── epub_parser.py      # EPUB validation, chapter/image/CSS extraction
├── html_processor.py   # HTML cleaning, CSS sanitization, image embedding
├── pdf_renderer.py     # WeasyPrint rendering with progress tracking
├── __init__.py         # Package version
└── __main__.py         # python -m entry point
```

---

## Edge Cases

This isn't a toy converter. It handles real-world EPUBs:

| Scenario | What happens |
|:---------|:-------------|
| Missing or broken images | Warning logged, replaced with `[alt text]` placeholder |
| Corrupt EPUB (bad ZIP) | Clear error message, exits with code 1 |
| Invalid EPUB structure | Validated before parsing begins |
| Encoding issues | Tries UTF-8, falls back to latin-1 |
| Oversized images (>1600px) | Downscaled with Lanczos resampling |
| URL-encoded image paths | Decoded automatically (`%20` etc.) |
| EPUB CSS with `float` | Stripped (prevents WeasyPrint crashes) |
| CSS `position: fixed/absolute` | Stripped from both stylesheets and inline styles |
| `@font-face` declarations | Removed (fonts aren't bundled in EPUB extraction) |
| No table of contents | Works fine; `--toc` generates one from chapter titles |
| Empty chapters | Skipped silently |
| Multiple HTML files | Merged in spine order |
| XHTML content | Handled transparently |
| SVG `<image>` tags | Resolved via `xlink:href` |
| Cover image stored as ITEM_COVER | Extracted alongside regular images |

---

## Python API

Use it as a library in your own projects:

```python
from pathlib import Path
from epub2pdf.epub_parser import parse_epub
from epub2pdf.html_processor import merge_chapters, generate_toc_html
from epub2pdf.pdf_renderer import render_pdf

# 1. Parse the EPUB
epub_data = parse_epub(Path("book.epub"))
print(f"{epub_data.title} by {epub_data.author}")
print(f"{len(epub_data.chapters)} chapters, {len(epub_data.images)} images")

# 2. Merge chapters into print-ready HTML
html = merge_chapters(
    epub_data,
    page_size="A4",
    margin="2cm",
    font_size="12pt",
)

# 3. Optionally prepend a table of contents
toc = generate_toc_html(epub_data)
html = html.replace("<body>", f"<body>\n{toc}", 1)

# 4. Render to PDF
render_pdf(html, Path("book.pdf"))
```

### Key Data Structures

```python
@dataclass
class EpubData:
    title: str                    # Book title from DC metadata
    author: str                   # Author from DC metadata
    language: str                 # Language code (e.g. "en-US")
    chapters: list[Chapter]       # Ordered chapter content
    images: list[EpubImage]       # All images including cover
    css_files: list[str]          # Original EPUB stylesheets
    spine_order: list[str]        # Reading order from OPF spine

@dataclass
class Chapter:
    title: str                    # Chapter title
    html_content: bytes           # Raw HTML/XHTML bytes
    file_name: str                # Path within EPUB archive
    order: int                    # Position in reading order
```

---

## Dependencies

| Package | What it does |
|:--------|:-------------|
| [`ebooklib`](https://github.com/aerkalov/ebooklib) | Parse EPUB structure, extract content by spine order |
| [`beautifulsoup4`](https://www.crummy.com/software/BeautifulSoup/) | Clean and manipulate HTML from each chapter |
| [`lxml`](https://lxml.de/) | Fast HTML/XML parsing backend |
| [`WeasyPrint`](https://weasyprint.org/) | Render HTML+CSS to PDF with print layout support |
| [`Pillow`](https://python-pillow.org/) | Resize oversized images, convert color modes |
| [`tqdm`](https://github.com/tqdm/tqdm) | Progress bar for rendering |

---

## Alternatives Compared

| Tool | Images | Chapter breaks | Page numbers | CSS handling | Speed |
|:-----|:-------|:---------------|:-------------|:-------------|:------|
| **EPUB2PDFPrintPerfect** | Embedded + resized | Automatic | Yes | Sanitized | ~5s |
| Calibre CLI | Sometimes broken | Manual | Plugin needed | Often breaks | ~10s |
| Pandoc | Dropped frequently | No | No | Ignored | ~3s |
| Online converters | Low quality | No | No | Stripped | Varies |

---

## Contributing

Contributions are welcome. Please keep changes focused and include test cases for edge cases.

```bash
# Clone and install in dev mode
git clone https://github.com/vmishra/EPUB2PDFPrintPerfect.git
cd EPUB2PDFPrintPerfect
pip install -e ".[dev]"

# Run on a test EPUB
epub2pdf test.epub --toc --verbose
```

---

## License

[MIT](LICENSE) &mdash; use it however you want.
