"""EPUB parsing module - handles loading and extracting content from EPUB files."""

from __future__ import annotations

import logging
import zipfile
from dataclasses import dataclass, field
from pathlib import Path

import ebooklib
from ebooklib import epub

logger = logging.getLogger(__name__)


@dataclass
class Chapter:
    """A single chapter extracted from an EPUB."""

    title: str
    html_content: bytes
    file_name: str
    order: int


@dataclass
class EpubImage:
    """An image extracted from an EPUB."""

    file_name: str
    content: bytes
    media_type: str


@dataclass
class EpubData:
    """All content extracted from an EPUB file."""

    title: str
    author: str
    language: str
    chapters: list[Chapter] = field(default_factory=list)
    images: list[EpubImage] = field(default_factory=list)
    css_files: list[str] = field(default_factory=list)
    spine_order: list[str] = field(default_factory=list)


def validate_epub(epub_path: Path) -> None:
    """Validate that the file is a valid EPUB (ZIP with correct structure)."""
    if not epub_path.exists():
        raise FileNotFoundError(f"EPUB file not found: {epub_path}")
    if not epub_path.is_file():
        raise ValueError(f"Path is not a file: {epub_path}")
    if epub_path.stat().st_size == 0:
        raise ValueError(f"EPUB file is empty: {epub_path}")

    # EPUB is a ZIP file - verify basic structure
    if not zipfile.is_zipfile(epub_path):
        raise ValueError(
            f"File is not a valid EPUB (not a ZIP archive): {epub_path}"
        )

    try:
        with zipfile.ZipFile(epub_path, "r") as zf:
            names = zf.namelist()
            # Every EPUB must have a META-INF/container.xml
            if "META-INF/container.xml" not in names:
                raise ValueError(
                    f"Invalid EPUB structure: missing META-INF/container.xml in {epub_path}"
                )
    except zipfile.BadZipFile as e:
        raise ValueError(f"Corrupt EPUB file: {epub_path}: {e}") from e


def load_epub(epub_path: Path) -> epub.EpubBook:
    """Load and return an EpubBook object.

    Validates the file before loading and provides clear error messages.
    """
    validate_epub(epub_path)
    logger.info("Loading EPUB: %s", epub_path)
    try:
        book = epub.read_epub(str(epub_path), options={"ignore_ncx": False})
    except Exception as e:
        raise ValueError(f"Failed to parse EPUB: {epub_path}: {e}") from e
    logger.info("EPUB loaded successfully: %s", epub_path.name)
    return book


def _get_metadata_field(book: epub.EpubBook, field_name: str) -> str:
    """Safely extract a metadata field from the EPUB."""
    try:
        values = book.get_metadata("DC", field_name)
        if values:
            return str(values[0][0])
    except (IndexError, KeyError, TypeError):
        logger.debug("Metadata field '%s' not found", field_name)
    return "Unknown"


def _build_spine_order(book: epub.EpubBook) -> list[str]:
    """Build ordered list of content file names from the EPUB spine."""
    spine_ids = []
    for item in book.spine:
        # spine items are (id, linear) tuples
        item_id = item[0] if isinstance(item, (list, tuple)) else item
        spine_ids.append(item_id)

    ordered_names = []
    for spine_id in spine_ids:
        item = book.get_item_with_id(spine_id)
        if item is not None:
            ordered_names.append(item.get_name())
    return ordered_names


def extract_chapters(book: epub.EpubBook) -> list[Chapter]:
    """Extract all document chapters from the EPUB, ordered by spine."""
    spine_order = _build_spine_order(book)
    logger.debug("Spine order: %s", spine_order)

    # Collect all HTML documents
    doc_items: dict[str, epub.EpubItem] = {}
    for item in book.get_items_of_type(ebooklib.ITEM_DOCUMENT):
        doc_items[item.get_name()] = item

    chapters: list[Chapter] = []
    order = 0

    # First add items in spine order
    for name in spine_order:
        if name in doc_items:
            item = doc_items.pop(name)
            content = item.get_content()
            if not content or not content.strip():
                logger.debug("Skipping empty chapter: %s", name)
                continue
            title = _extract_chapter_title(item, order)
            chapters.append(
                Chapter(
                    title=title,
                    html_content=content,
                    file_name=name,
                    order=order,
                )
            )
            order += 1

    # Then add any remaining documents not in spine (some EPUBs have these)
    for name, item in doc_items.items():
        content = item.get_content()
        if not content or not content.strip():
            continue
        title = _extract_chapter_title(item, order)
        chapters.append(
            Chapter(
                title=title,
                html_content=content,
                file_name=name,
                order=order,
            )
        )
        order += 1

    logger.info("Extracted %d chapters", len(chapters))
    return chapters


def _extract_chapter_title(item: epub.EpubItem, fallback_order: int) -> str:
    """Try to extract a chapter title from the item or its HTML content."""
    # Try the item's own title attribute
    title = getattr(item, "title", None)
    if title:
        return str(title)
    # Fallback to filename-based title
    name = Path(item.get_name()).stem
    return name if name else f"Chapter {fallback_order + 1}"


def extract_images(book: epub.EpubBook) -> list[EpubImage]:
    """Extract all images from the EPUB, including cover images."""
    images: list[EpubImage] = []
    seen: set[str] = set()
    # ITEM_IMAGE (1) is regular images, ITEM_COVER (10) is cover image
    for item_type in (ebooklib.ITEM_IMAGE, ebooklib.ITEM_COVER):
        for item in book.get_items_of_type(item_type):
            name = item.get_name()
            if name in seen:
                continue
            seen.add(name)
            try:
                content = item.get_content()
                if content:
                    images.append(
                        EpubImage(
                            file_name=name,
                            content=content,
                            media_type=item.media_type,
                        )
                    )
            except (KeyError, OSError, AttributeError) as e:
                logger.warning("Failed to extract image: %s (%s)", name, e)
    logger.info("Extracted %d images", len(images))
    return images


def extract_css(book: epub.EpubBook) -> list[str]:
    """Extract all CSS stylesheets from the EPUB."""
    css_files: list[str] = []
    for item in book.get_items_of_type(ebooklib.ITEM_STYLE):
        try:
            content = item.get_content()
            if content:
                css_text = content.decode("utf-8", errors="replace")
                css_files.append(css_text)
        except (KeyError, OSError, UnicodeDecodeError) as e:
            logger.warning("Failed to extract CSS: %s (%s)", item.get_name(), e)
    logger.debug("Extracted %d CSS files", len(css_files))
    return css_files


def parse_epub(epub_path: Path) -> EpubData:
    """Main entry point: load EPUB and extract all content into EpubData."""
    book = load_epub(epub_path)

    title = _get_metadata_field(book, "title")
    author = _get_metadata_field(book, "creator")
    language = _get_metadata_field(book, "language")

    logger.info("Book: '%s' by %s (%s)", title, author, language)

    chapters = extract_chapters(book)
    images = extract_images(book)
    css_files = extract_css(book)
    spine_order = _build_spine_order(book)

    return EpubData(
        title=title,
        author=author,
        language=language,
        chapters=chapters,
        images=images,
        css_files=css_files,
        spine_order=spine_order,
    )
