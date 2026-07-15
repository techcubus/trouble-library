import re
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import Optional

import ebooklib
from ebooklib import epub
from PIL import Image, UnidentifiedImageError

COVER_MAX_DIMENSION = 800
COVER_JPEG_QUALITY = 85


@dataclass
class EpubMetadata:
    title: str = ""
    author: str = ""
    series: str = ""
    series_index: str = ""
    isbn: str = ""
    publisher: str = ""
    pub_date: str = ""
    language: str = ""
    description: str = ""
    cover_bytes: Optional[bytes] = None


def _first(values: list, default: str = "") -> str:
    if not values:
        return default
    return values[0][0] or default


def _prefixed_meta(book: "epub.EpubBook", name: str) -> str:
    """Look up a `<meta name="prefix:tag" content="...">` OPF entry.

    ebooklib splits the name on ':' while parsing and re-buckets the entry
    under a synthetic namespace equal to the prefix (e.g. calibre:series ->
    metadata['calibre']['series']), rather than keeping it under 'OPF'.
    get_metadata() itself does book.metadata[namespace].get(...), which
    raises KeyError when the namespace never appeared in the file at all
    (i.e. any epub never touched by Calibre) — so check first.
    """
    prefix, _, tag = name.partition(":")
    if prefix not in book.metadata:
        return ""
    for _value, attrs in book.get_metadata(prefix, tag):
        content = attrs.get("content")
        if content:
            return content
    return ""


def _clean_isbn(value: str) -> str:
    value = value.strip()
    for prefix in ("urn:isbn:", "isbn:"):
        if value.lower().startswith(prefix):
            return value[len(prefix):]
    return value


_COVER_NAME_RE = re.compile(r"cover|(^|[_-])cvi([_-]|$)")


def _find_cover(book: "epub.EpubBook"):
    """Pick the item that best matches the book's cover.

    Not every epub marks its cover via the EPUB3 cover-image property or
    ebooklib's ITEM_COVER type - many commercially produced epubs (e.g. the
    common Random House/Penguin production pipeline) just embed it as a
    plain image named like "..._msr_cvi_r1.jpg" ("cvi" = cover image, "cvt"
    = cover thumbnail). Falling back to "largest embedded image" isn't safe
    either, since interior illustrations can outweigh the actual cover in
    byte size - so name matching takes priority over that fallback.
    """
    for item in book.get_items_of_type(ebooklib.ITEM_COVER):
        return item

    images = list(book.get_items_of_type(ebooklib.ITEM_IMAGE))
    for item in images:
        if _COVER_NAME_RE.search(item.get_name().lower()):
            return item

    if images:
        return max(images, key=lambda item: len(item.get_content()))

    return None


def parse_epub(path: Path) -> EpubMetadata:
    book = epub.read_epub(str(path))

    title = _first(book.get_metadata("DC", "title"))
    authors = [value for value, _attrs in book.get_metadata("DC", "creator")]
    author = ", ".join(a for a in authors if a)
    language = _first(book.get_metadata("DC", "language"))
    publisher = _first(book.get_metadata("DC", "publisher"))
    description = _first(book.get_metadata("DC", "description"))
    pub_date = _first(book.get_metadata("DC", "date"))

    isbn = ""
    for value, attrs in book.get_metadata("DC", "identifier"):
        scheme = (attrs.get("scheme") or "").lower()
        if value and ("isbn" in scheme or "isbn" in value.lower()):
            isbn = _clean_isbn(value)
            break

    series = _prefixed_meta(book, "calibre:series")
    series_index = _prefixed_meta(book, "calibre:series_index")

    cover_item = _find_cover(book)
    cover_bytes = cover_item.get_content() if cover_item is not None else None

    return EpubMetadata(
        title=title or path.stem,
        author=author,
        series=series,
        series_index=series_index,
        isbn=isbn,
        publisher=publisher,
        pub_date=pub_date,
        language=language,
        description=description,
        cover_bytes=cover_bytes,
    )


def save_cover(covers_dir: Path, media_item_id: int, cover_bytes: bytes) -> str:
    """Normalize a cover image to a size-capped JPEG and write it to disk.

    Covers embedded in epubs vary wildly in size/format; storing them
    unmodified would let a single book bloat the library with multi-MB
    images the UI only ever shows as thumbnails. Returns "" if cover_bytes
    isn't decodable as an image (seen with malformed/placeholder covers).
    """
    try:
        image = Image.open(BytesIO(cover_bytes))
        image.load()
    except (UnidentifiedImageError, OSError):
        return ""

    if image.mode in ("RGBA", "LA") or (image.mode == "P" and "transparency" in image.info):
        rgba = image.convert("RGBA")
        background = Image.new("RGB", rgba.size, (255, 255, 255))
        background.paste(rgba, mask=rgba.split()[-1])
        image = background
    else:
        image = image.convert("RGB")

    image.thumbnail((COVER_MAX_DIMENSION, COVER_MAX_DIMENSION), Image.LANCZOS)

    covers_dir.mkdir(parents=True, exist_ok=True)
    cover_path = covers_dir / f"{media_item_id}.jpg"
    image.save(cover_path, format="JPEG", quality=COVER_JPEG_QUALITY)
    return str(cover_path)
