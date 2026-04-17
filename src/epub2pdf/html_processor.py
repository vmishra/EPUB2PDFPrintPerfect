"""HTML processing module - cleans, normalizes, and merges EPUB HTML content."""

from __future__ import annotations

import base64
import io
import logging
import re
from pathlib import PurePosixPath
from typing import TYPE_CHECKING
from urllib.parse import unquote

from bs4 import BeautifulSoup, Comment
from PIL import Image

if TYPE_CHECKING:
    from .epub_parser import EpubData

logger = logging.getLogger(__name__)

# Maximum image dimension (pixels) before resizing
MAX_IMAGE_DIMENSION = 1600
# JPEG quality for resized images
JPEG_QUALITY = 85

# Pre-compiled regexes for inline style sanitization
_RE_FLOAT = re.compile(r"float\s*:\s*[^;]+;?")
_RE_POSITION = re.compile(r"position\s*:\s*(absolute|fixed)\s*;?")
_RE_OVERFLOW_X = re.compile(r"overflow-x\s*:\s*[^;]+;?")

# Tags to strip from EPUB HTML (not relevant to PDF output)
_STRIP_TAGS_SELECTOR = (
    "script, noscript, form, input, button, iframe, "
    "video, audio, canvas, map, object, embed"
)


def clean_html(html_content: bytes, file_name: str) -> BeautifulSoup:
    """Parse and clean a single HTML document from the EPUB.

    Handles encoding issues, strips scripts/interactive elements,
    and normalizes the HTML structure.
    """
    # Try UTF-8 first, fall back to latin-1
    try:
        html_str = html_content.decode("utf-8")
    except UnicodeDecodeError:
        logger.debug("UTF-8 decode failed for %s, trying latin-1", file_name)
        html_str = html_content.decode("latin-1", errors="replace")

    soup = BeautifulSoup(html_str, "html.parser")

    # Remove elements that don't belong in PDF output (single DOM pass)
    for tag in soup.select(_STRIP_TAGS_SELECTOR):
        tag.decompose()

    # Remove HTML comments
    for comment in soup.find_all(string=lambda text: isinstance(text, Comment)):
        comment.extract()

    # Strip float and position:absolute/fixed from inline styles
    # (these cause WeasyPrint assertion errors)
    for tag in soup.find_all(style=True):
        style = tag["style"]
        style = _RE_FLOAT.sub("", style)
        style = _RE_POSITION.sub("", style)
        style = _RE_OVERFLOW_X.sub("overflow:hidden;", style)
        if style.strip():
            tag["style"] = style
        else:
            del tag["style"]

    return soup


def _resolve_image_path(src: str, chapter_file: str) -> str:
    """Resolve a relative image path against the chapter's location in the EPUB."""
    if src.startswith(("http://", "https://", "data:")):
        return src
    # Decode URL-encoded paths (e.g. %20 -> space)
    src = unquote(src)
    # Strip any fragment identifier (e.g. image.jpg#page=1)
    src = src.split("#")[0]
    chapter_dir = str(PurePosixPath(chapter_file).parent)
    resolved = str(PurePosixPath(chapter_dir) / src)
    # Normalize ../ segments
    parts: list[str] = []
    for part in resolved.split("/"):
        if part == "..":
            if parts:
                parts.pop()
        elif part and part != ".":
            parts.append(part)
    return "/".join(parts)


def _resize_image_if_needed(image_data: bytes, media_type: str) -> tuple[bytes, str]:
    """Resize an image if it exceeds MAX_IMAGE_DIMENSION. Returns (data, media_type)."""
    try:
        img = Image.open(io.BytesIO(image_data))
    except (OSError, ValueError):
        return image_data, media_type

    try:
        w, h = img.size
        if w <= MAX_IMAGE_DIMENSION and h <= MAX_IMAGE_DIMENSION:
            return image_data, media_type

        ratio = min(MAX_IMAGE_DIMENSION / w, MAX_IMAGE_DIMENSION / h)
        new_w = int(w * ratio)
        new_h = int(h * ratio)
        logger.debug("Resizing image from %dx%d to %dx%d", w, h, new_w, new_h)

        resized = img.resize((new_w, new_h), Image.Resampling.LANCZOS)
        # Convert any mode with alpha or palette to RGB for JPEG
        if resized.mode not in ("RGB", "L"):
            resized = resized.convert("RGB")
        buf = io.BytesIO()
        resized.save(buf, format="JPEG", quality=JPEG_QUALITY, optimize=True)
        return buf.getvalue(), "image/jpeg"
    finally:
        img.close()


def embed_images(
    soup: BeautifulSoup,
    chapter_file: str,
    image_map: dict[str, tuple[bytes, str]],
    basename_map: dict[str, str],
    no_images: bool = False,
) -> None:
    """Replace image src attributes with base64 data URIs.

    This embeds images directly into the HTML so WeasyPrint can render
    them without needing file system access to the EPUB contents.
    """
    # Handle both <img> and SVG <image> tags (xlink:href)
    for img_tag in soup.find_all(["img", "image"]):
        if no_images:
            img_tag.decompose()
            continue

        # Get src from either 'src', 'xlink:href', or 'href' attributes
        src = img_tag.get("src") or img_tag.get("xlink:href") or img_tag.get("href", "")
        if not src or src.startswith("data:"):
            continue

        resolved = _resolve_image_path(src, chapter_file)

        if resolved not in image_map:
            # O(1) fallback: try basename match (some EPUBs use flat structure)
            basename = PurePosixPath(resolved).name
            if basename in basename_map:
                resolved = basename_map[basename]
            else:
                logger.warning("Image not found in EPUB: %s (from %s)", src, chapter_file)
                alt = img_tag.get("alt") or PurePosixPath(src).name
                img_tag.replace_with(f"[{alt}]")
                continue

        img_data, img_media_type = image_map[resolved]
        img_data, img_media_type = _resize_image_if_needed(img_data, img_media_type)

        b64 = base64.b64encode(img_data).decode("ascii")
        data_uri = f"data:{img_media_type};base64,{b64}"
        # Set the appropriate attribute based on tag type
        if img_tag.name == "image":
            img_tag["xlink:href"] = data_uri
        else:
            img_tag["src"] = data_uri
        # Ensure images scale within page
        existing_style = img_tag.get("style", "")
        if "max-width" not in existing_style:
            img_tag["style"] = f"max-width:100%;height:auto;{existing_style}"


def build_image_map(
    epub_data: EpubData,
) -> tuple[dict[str, tuple[bytes, str]], dict[str, str]]:
    """Build lookup dicts for image resolution.

    Returns:
        image_map: full path -> (bytes, media_type)
        basename_map: filename only -> full path (for fallback lookups)
    """
    image_map = {img.file_name: (img.content, img.media_type) for img in epub_data.images}
    basename_map = {PurePosixPath(k).name: k for k in image_map}
    return image_map, basename_map


def merge_chapters(
    epub_data: EpubData,
    no_images: bool = False,
    page_size: str = "A4",
    margin: str = "2cm",
    font_size: str | None = None,
) -> str:
    """Merge all EPUB chapters into a single HTML document for PDF rendering.

    This is the main HTML pipeline:
    1. Clean each chapter's HTML
    2. Embed images as data URIs
    3. Merge all chapters with page-break separators
    4. Wrap in a complete HTML document with CSS for print layout
    """
    image_map, basename_map = build_image_map(epub_data)

    # Collect original EPUB CSS
    epub_css = "\n".join(epub_data.css_files)

    # Build merged body
    body_parts: list[str] = []
    skipped_empty = 0

    for i, chapter in enumerate(epub_data.chapters):
        logger.debug("Processing chapter %d/%d: %s", i + 1, len(epub_data.chapters), chapter.title)

        soup = clean_html(chapter.html_content, chapter.file_name)
        embed_images(soup, chapter.file_name, image_map, basename_map, no_images=no_images)

        # Extract body content
        body = soup.find("body")
        if body:
            inner_html = body.decode_contents()
        else:
            inner_html = soup.decode_contents()

        if not inner_html.strip():
            skipped_empty += 1
            continue

        # Wrap each chapter in a section with page-break
        chapter_class = "chapter-first" if i == 0 else "chapter"
        body_parts.append(
            f'<section class="{chapter_class}" id="chapter-{i}">'
            f"{inner_html}"
            f"</section>"
        )

    if skipped_empty:
        logger.debug("Skipped %d empty chapters", skipped_empty)

    merged_body = "\n".join(body_parts)

    # Build the print CSS
    font_size_css = f"font-size: {font_size};" if font_size else ""

    print_css = f"""
    @page {{
        size: {page_size};
        margin: {margin};

        @bottom-center {{
            content: counter(page);
            font-size: 10pt;
            color: #666;
        }}
    }}

    @page :first {{
        @bottom-center {{
            content: none;
        }}
    }}

    body {{
        font-family: "Georgia", "Times New Roman", "DejaVu Serif", serif;
        line-height: 1.6;
        color: #1a1a1a;
        {font_size_css}
    }}

    h1, h2, h3, h4, h5, h6 {{
        page-break-after: avoid;
        break-after: avoid;
        margin-top: 1.2em;
        margin-bottom: 0.6em;
        line-height: 1.3;
    }}

    h1 {{ font-size: 1.8em; }}
    h2 {{ font-size: 1.5em; }}
    h3 {{ font-size: 1.3em; }}

    p {{
        text-align: justify;
        margin-bottom: 0.8em;
        orphans: 3;
        widows: 3;
    }}

    img {{
        max-width: 100%;
        height: auto;
        display: block;
        margin: 1em auto;
        page-break-inside: avoid;
        break-inside: avoid;
    }}

    table {{
        page-break-inside: avoid;
        break-inside: avoid;
        border-collapse: collapse;
        width: 100%;
        margin: 1em 0;
    }}

    th, td {{
        border: 1px solid #ccc;
        padding: 0.4em 0.6em;
        text-align: left;
    }}

    pre, code {{
        font-family: "DejaVu Sans Mono", "Courier New", monospace;
        font-size: 0.9em;
        background: #f5f5f5;
        padding: 0.2em 0.4em;
        border-radius: 3px;
    }}

    pre {{
        padding: 1em;
        overflow: hidden;
        white-space: pre-wrap;
        word-wrap: break-word;
        page-break-inside: avoid;
    }}

    blockquote {{
        border-left: 3px solid #ccc;
        margin: 1em 0;
        padding: 0.5em 1em;
        color: #555;
        font-style: italic;
    }}

    a {{
        color: #1a1a1a;
        text-decoration: none;
    }}

    section.chapter {{
        page-break-before: always;
        break-before: page;
    }}

    section.chapter-first {{
        page-break-before: auto;
    }}

    /* Table of contents styles */
    .toc {{
        page-break-after: always;
        break-after: page;
    }}

    .toc h1 {{
        text-align: center;
        margin-bottom: 1.5em;
    }}

    .toc ul {{
        list-style: none;
        padding-left: 0;
    }}

    .toc li {{
        margin-bottom: 0.5em;
        padding: 0.2em 0;
        border-bottom: 1px dotted #ccc;
    }}

    .toc a {{
        text-decoration: none;
        color: #1a1a1a;
    }}
    """

    # Sanitize EPUB CSS to avoid conflicts with our print layout
    epub_css_sanitized = _sanitize_epub_css(epub_css)

    html = f"""<!DOCTYPE html>
<html lang="{epub_data.language}">
<head>
<meta charset="utf-8">
<title>{_escape_html(epub_data.title)}</title>
<style>
{print_css}
</style>
<style>
/* Original EPUB styles (sanitized) */
{epub_css_sanitized}
</style>
</head>
<body>
{merged_body}
</body>
</html>"""

    return html


def _escape_html(text: str) -> str:
    """Escape HTML special characters in text."""
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


_RE_CSS_PAGE = re.compile(r"@page\s*\{[^}]*\}")
_RE_CSS_FONT_FACE = re.compile(r"@font-face\s*\{[^}]*\}", re.DOTALL)
_RE_CSS_BODY_POS = re.compile(
    r"body\s*\{[^}]*position\s*:\s*(fixed|absolute)[^}]*\}"
)
_RE_CSS_ROOT_BLOCK = re.compile(r"(html|body)\s*\{[^}]*\}")
_RE_CSS_FLOAT = re.compile(r"float\s*:\s*[^;]+;")
_RE_CSS_OVERFLOW_X = re.compile(r"overflow-x\s*:\s*[^;]+;")
_RE_CSS_ABS_FIXED = re.compile(r"position\s*:\s*(absolute|fixed)\s*;")


def _sanitize_epub_css(css: str) -> str:
    """Sanitize EPUB CSS to avoid breaking the print layout.

    Removes @page rules, fixed positioning, float properties, and other
    problematic properties that conflict with WeasyPrint's print rendering.
    """
    css = _RE_CSS_PAGE.sub("", css)
    css = _RE_CSS_FONT_FACE.sub("", css)
    css = _RE_CSS_BODY_POS.sub("", css)
    css = _RE_CSS_ROOT_BLOCK.sub(_strip_dimension_props, css)
    css = _RE_CSS_FLOAT.sub("", css)
    css = _RE_CSS_OVERFLOW_X.sub("overflow: hidden;", css)
    css = _RE_CSS_ABS_FIXED.sub("", css)
    return css


def _strip_dimension_props(match: re.Match) -> str:
    """Remove width/height/margin properties from html/body rules."""
    block = match.group(0)
    block = re.sub(r"(width|height|margin|padding)\s*:[^;]+;", "", block)
    return block


def generate_toc_html(epub_data: EpubData) -> str:
    """Generate a table of contents HTML section from chapter titles."""
    items: list[str] = []
    for i, chapter in enumerate(epub_data.chapters):
        title = _escape_html(chapter.title)
        items.append(f'<li><a href="#chapter-{i}">{title}</a></li>')

    if not items:
        return ""

    toc_list = "\n".join(items)
    return f"""<section class="toc">
<h1>Table of Contents</h1>
<ul>
{toc_list}
</ul>
</section>
"""
