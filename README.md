# EPUB2PDFPrintPerfect

**Production-grade EPUB to PDF converter with pixel-perfect formatting.**

Convert any EPUB ebook into a beautifully formatted, print-ready PDF — with proper chapter breaks, embedded images, page numbers, and a generated table of contents.

---

## Why This Exists

Most EPUB-to-PDF tools produce ugly output: broken layouts, missing images, no page numbers, inconsistent fonts. **EPUB2PDFPrintPerfect** is built to solve that. It parses the EPUB structure properly, sanitizes CSS for print rendering, embeds images as data URIs, and produces PDFs you'd actually want to print or read.

## Features

- **High-quality rendering** — Georgia/serif typography, justified text, proper line height
- **Chapter breaks** — automatic page breaks between chapters
- **Image handling** — embedded images with smart resizing for oversized assets
- **Page numbers** — centered at the bottom of every page (except the first)
- **Table of contents** — optional generated TOC page with chapter links
- **EPUB CSS preservation** — original styles are sanitized and preserved where possible
- **Print-ready** — configurable page size (A4, Letter, A5, B5, Legal) and margins
- **Robust** — handles broken images, encoding issues, corrupt EPUBs, missing TOCs
- **Fast** — converts a 300-page book in ~5 seconds

---

## Quick Start

### Installation

```bash
pip install ebooklib beautifulsoup4 lxml weasyprint Pillow tqdm
```

**System dependency** — WeasyPrint requires some system libraries:

```bash
# Ubuntu/Debian
sudo apt install libpango1.0-dev libcairo2-dev libgdk-pixbuf2.0-dev libffi-dev

# macOS
brew install pango cairo gdk-pixbuf libffi

# Fedora
sudo dnf install pango-devel cairo-devel gdk-pixbuf2-devel libffi-devel
```

### Clone and Install

```bash
git clone https://github.com/vmishra/EPUB2PDFPrintPerfect.git
cd EPUB2PDFPrintPerfect
pip install -e .
```

### Convert Your First Book

```bash
epub2pdf mybook.epub
```

This creates `mybook.pdf` in the same directory.

---

## Usage

```
epub2pdf <input.epub> [OPTIONS]
```

### Options

| Flag | Description | Default |
|------|-------------|---------|
| `-o, --output PATH` | Output PDF path | `<input>.pdf` |
| `--page-size SIZE` | Page size: `A4`, `A5`, `Letter`, `Legal`, `B5` | `A4` |
| `--margin SIZE` | Page margins (CSS units: `2cm`, `1in`, `20mm`) | `2cm` |
| `--font-size SIZE` | Base font size override (`12pt`, `14px`) | browser default |
| `--no-images` | Strip all images from output | — |
| `--toc` | Generate table of contents page | — |
| `-v, --verbose` | Show debug logging | — |
| `-q, --quiet` | Suppress all output except errors | — |
| `--version` | Show version | — |

### Examples

**Basic conversion:**
```bash
epub2pdf book.epub
```

**Custom output path:**
```bash
epub2pdf book.epub --output ~/Documents/book.pdf
```

**Letter size with 1-inch margins:**
```bash
epub2pdf book.epub --page-size Letter --margin 1in
```

**Generate table of contents:**
```bash
epub2pdf book.epub --toc
```

**Larger font for readability:**
```bash
epub2pdf book.epub --font-size 14pt
```

**Text-only (no images, smaller file):**
```bash
epub2pdf book.epub --no-images
```

**Debug mode:**
```bash
epub2pdf book.epub --toc --verbose
```

**As a Python module:**
```bash
python -m epub2pdf book.epub --output book.pdf
```

---

## Architecture

```
src/epub2pdf/
├── __init__.py         # Package version
├── __main__.py         # python -m epub2pdf entry point
├── cli.py              # Argument parsing and pipeline orchestration
├── epub_parser.py      # EPUB loading, validation, chapter/image extraction
├── html_processor.py   # HTML cleaning, CSS sanitization, image embedding, chapter merging
└── pdf_renderer.py     # WeasyPrint rendering with progress tracking
```

### Pipeline

```
EPUB file
  → validate ZIP structure & META-INF/container.xml
  → parse with ebooklib (spine-ordered chapters)
  → extract images and CSS
  → clean HTML (strip scripts, normalize encoding)
  → sanitize CSS (remove float, position:fixed, @font-face)
  → embed images as base64 data URIs (with smart resizing)
  → merge chapters with page-break separators
  → wrap in print-ready HTML with typography CSS
  → render to PDF via WeasyPrint
  → output with page numbers
```

---

## Edge Cases Handled

| Scenario | Behavior |
|----------|----------|
| Missing images | Warning logged, replaced with `[alt text]` |
| Corrupt EPUB (bad ZIP) | Clear error message, exit code 1 |
| Invalid EPUB structure | Validated before parsing |
| Encoding issues | UTF-8 first, falls back to latin-1 |
| Very large images (>1600px) | Automatically resized with Lanczos |
| EPUB CSS with `float` | Stripped to prevent rendering crashes |
| EPUB CSS with `position: fixed/absolute` | Stripped |
| No table of contents in EPUB | Still works; `--toc` generates one from chapters |
| Empty chapters | Skipped silently |
| Multiple HTML files | Merged in spine order |
| XHTML content | Handled transparently |

---

## Dependencies

| Package | Purpose |
|---------|---------|
| `ebooklib` | EPUB parsing and content extraction |
| `beautifulsoup4` | HTML cleaning and manipulation |
| `lxml` | Fast HTML/XML parsing backend |
| `weasyprint` | HTML-to-PDF rendering engine |
| `Pillow` | Image resizing and format conversion |
| `tqdm` | Progress bar during rendering |

---

## API Usage

You can also use EPUB2PDFPrintPerfect as a library:

```python
from pathlib import Path
from epub2pdf.epub_parser import parse_epub
from epub2pdf.html_processor import merge_chapters
from epub2pdf.pdf_renderer import render_pdf

# Parse
epub_data = parse_epub(Path("book.epub"))
print(f"Title: {epub_data.title}")
print(f"Chapters: {len(epub_data.chapters)}")

# Process
html = merge_chapters(epub_data, page_size="A4", margin="2cm")

# Render
render_pdf(html, Path("book.pdf"))
```

---

## License

MIT
