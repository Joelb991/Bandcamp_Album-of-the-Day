"""Step 3 of extraction: turn one article's HTML into one clean record.

Design note
-----------
Each field has a *primary* regex - the expression that has been extracting
this dataset correctly since 2021 - and, where the markup offers one, a
*fallback* that reads the page's Open Graph / article meta tags. If Bandcamp
reskins the site the regex goes quiet and the meta-tag path keeps the pipeline
alive; keeping the regex first means historical output stays byte-identical.

Every extractor returns ``None`` rather than raising, so a single odd article
can never kill a 2,300-page crawl. Parse failures surface as nulls plus a
``parse_status`` value the load step counts and reports.
"""
from __future__ import annotations

import html as html_lib
import logging
import re

logger = logging.getLogger(__name__)

# ── Primary regexes (proven against the full 2016-2026 archive) ─────────────
RE_TITLE = re.compile(r"(<title>\s.*?)\s+(</title>)", re.DOTALL)
RE_DATE = re.compile(r"(middot;\s).*\s(\s.*</article)")
RE_LABEL = re.compile(r'(class="artist-name".*)(?=</a)')
RE_LOCATION = re.compile(r'(?<=location">)(\w.*)(?=</div)')
RE_AUTHOR = re.compile(r"(contributors.*)(\w.+)(?=<)")
RE_TAGS = re.compile(r'article:tag.+(?=">)')

# ── Meta-tag fallbacks ──────────────────────────────────────────────────────
RE_META_TITLE = re.compile(
    r'<meta[^>]+property=["\']og:title["\'][^>]+content=["\'](.*?)["\']', re.IGNORECASE
)
RE_META_PUBLISHED = re.compile(
    r'<meta[^>]+property=["\']article:published_time["\'][^>]+content=["\'](.*?)["\']',
    re.IGNORECASE,
)
RE_META_TAG = re.compile(
    r'<meta[^>]+property=["\']article:tag["\'][^>]+content=["\'](.*?)["\']', re.IGNORECASE
)

# Prefixes Bandcamp puts in front of the "Artist, Album" pair.
TITLE_PREFIXES = (
    "Album of the Day: ",
    "Album of the Day, ",
    "Album of the Week: ",
)

INDEPENDENT_LABEL = "Independent Artist"


def _clean(value) -> str | None:
    """Unescape HTML entities, collapse whitespace, return None if empty."""
    if value is None:
        return None
    text = html_lib.unescape(str(value))
    text = re.sub(r"\s+", " ", text).strip()
    return text or None


def parse_title(page_html: str) -> str | None:
    """The headline, minus site branding and the 'Album of the Day:' prefix."""
    match = RE_TITLE.search(page_html)
    raw = match.group() if match else None
    if raw:
        raw = raw.replace("<title>", "").replace("</title>", "")
    else:
        meta = RE_META_TITLE.search(page_html)
        raw = meta.group(1) if meta else None

    title = _clean(raw)
    if not title:
        return None
    title = re.sub(r"\s*\|\s*Bandcamp Daily\s*$", "", title)
    for prefix in TITLE_PREFIXES:
        if title.startswith(prefix):
            title = title[len(prefix):]
            break
    return _clean(title.replace("“", "").replace("”", ""))


def parse_published_date(page_html: str) -> str | None:
    """Publication date as printed on the article (e.g. 'March 14, 2024')."""
    match = RE_DATE.search(page_html)
    if match:
        raw = match.group().replace("middot;", "")
        raw = raw.split("\n")[0]
        cleaned = _clean(raw)
        if cleaned:
            return cleaned
    meta = RE_META_PUBLISHED.search(page_html)
    return _clean(meta.group(1)) if meta else None


def parse_record_label(page_html: str) -> str | None:
    """The label credited in the album sidebar."""
    match = RE_LABEL.search(page_html)
    if not match:
        return None
    inner = re.search(r"(true.*)", match.group())
    if not inner:
        return None
    return _clean(inner.group().replace('true">', ""))


def parse_label_location(page_html: str) -> str | None:
    """The label's self-reported location - the raw, very messy version."""
    match = RE_LOCATION.search(page_html)
    return _clean(match.group()) if match else None


def parse_author(page_html: str) -> str | None:
    """The Bandcamp Daily contributor who wrote the piece."""
    match = RE_AUTHOR.search(page_html)
    if not match:
        return None
    inner = re.search(r"(>.*)", match.group())
    if not inner:
        return None
    return _clean(inner.group().replace(">", ""))


def parse_tags(page_html: str) -> str | None:
    """The primary genre tag Bandcamp assigns to the article."""
    match = RE_TAGS.search(page_html)
    if match:
        inner = re.search(r"(=.*)", match.group())
        if inner:
            value = inner.group().replace("=", "").replace('"', "").replace("'", "")
            return _clean(value)
    meta = RE_META_TAG.search(page_html)
    return _clean(meta.group(1)) if meta else None


def split_artist_album(title: str | None) -> tuple[str | None, str | None]:
    """Split 'Artist, Album' on the first comma.

    Bandcamp headlines are formatted ``Artist, "Album"``. Some have no comma
    at all (self-titled records, compilations); in that case artist and album
    come back identical and :func:`resolve_label_and_artist` sorts it out.
    """
    if not title:
        return (None, None)
    parts = [part.strip() for part in title.split(",", 1)]
    if len(parts) == 1:
        return (parts[0] or None, parts[0] or None)
    artist, album = parts
    album = album.strip().strip("“”\"")
    return (artist or None, album or artist or None)


def resolve_label_and_artist(
    artist: str | None,
    album: str | None,
    label: str | None,
    headline_had_comma: bool = False,
) -> tuple[str | None, str | None]:
    """Apply the two business rules that disambiguate artist from label.

    1. When the headline had no comma, ``artist == album``; the sidebar's
       label field is actually the artist's name, so promote it. A
       self-titled record *with* a comma ("Lero Lero, Lero Lero") also has
       ``artist == album``, but its artist is already right - promoting the
       label there would credit the record to the label.
    2. When the resulting artist and the label are the same entity, the record
       is self-released - store it as ``Independent Artist``.

    Rule 2 is the origin of the ``is_independent`` dimension, which turns out
    to be the most interesting cut in the whole dataset.
    """
    if artist and album and artist == album and label and not headline_had_comma:
        artist = label
    if artist and label and artist == label:
        label = INDEPENDENT_LABEL
    return artist, label


def parse_article(page_html: str, url: str) -> dict:
    """Parse one article page into the pipeline's canonical record shape."""
    if not page_html:
        return {"article_url": url, "parse_status": "empty_html"}

    title = parse_title(page_html)
    label = parse_record_label(page_html)
    artist, album = split_artist_album(title)
    artist, label = resolve_label_and_artist(
        artist, album, label, headline_had_comma=bool(title) and "," in title
    )

    record = {
        "article_url": url,
        "article_slug": url.rstrip("/").rsplit("/", 1)[-1],
        "published_date": parse_published_date(page_html),
        "title": title,
        "artist": artist,
        "album": album,
        "genre_tag": parse_tags(page_html),
        "record_label": label,
        "label_location_raw": parse_label_location(page_html),
        "author": parse_author(page_html),
    }
    missing = [k for k in ("published_date", "title", "author") if not record.get(k)]
    record["parse_status"] = "ok" if not missing else "missing: " + ",".join(missing)
    return record
