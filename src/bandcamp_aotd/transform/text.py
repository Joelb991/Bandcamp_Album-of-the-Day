"""Text normalisation shared across artist, album, label and author fields.

Two problems recur in scraped editorial copy:

* HTML entities survive extraction, so ``Sam &#39;s Label`` and
  ``Sam's Label`` become two different labels in a ``GROUP BY``.
* Typographic quotes and stray punctuation cling to album titles pulled out
  of headlines.

Normalising once, here, is what makes label and artist counts trustworthy in
the dashboard.
"""
from __future__ import annotations

import html as html_lib
import re

import pandas as pd

SMART_QUOTES = str.maketrans({
    "“": '"', "”": '"',      # curly double quotes
    "‘": "'", "’": "'",      # curly single quotes
    "–": "-", "—": "-",      # en / em dash
})

TEXT_COLUMNS = ("artist", "album", "record_label", "author", "genre_tag", "title")


def normalize_text(value) -> str | None:
    """Unescape entities, straighten quotes, collapse whitespace."""
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    text = html_lib.unescape(str(value))
    text = text.translate(SMART_QUOTES)
    text = re.sub(r"\s+", " ", text).strip()
    text = text.strip('"').strip()
    return text or None


def normalize_text_columns(df: pd.DataFrame, columns=TEXT_COLUMNS) -> pd.DataFrame:
    """Apply :func:`normalize_text` to every column present in ``df``."""
    out = df.copy()
    for column in columns:
        if column in out.columns:
            out[column] = out[column].apply(normalize_text)
    return out


def add_label_features(df: pd.DataFrame) -> pd.DataFrame:
    """Derive the independent-vs-signed flag used throughout the analysis.

    "Independent Artist" is written by the extract step when the credited
    label and the artist are the same entity — i.e. the record is
    self-released. It is the single most useful derived dimension in the
    dataset, so it becomes a real boolean column rather than a string
    comparison repeated in every query.
    """
    out = df.copy()
    out["is_independent"] = out["record_label"].eq("Independent Artist")
    return out
