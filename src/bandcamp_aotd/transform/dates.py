"""Calendar features for the published date.

Bandcamp prints the date as free text ("March 14, 2024"), so it is parsed
once here and every downstream calendar attribute is derived from the parsed
timestamp. Doing this in the pipeline rather than in the BI tool means
Tableau and the web app read identical values instead of each re-deriving
"week of year" with its own convention.
"""
from __future__ import annotations

import logging

import pandas as pd

logger = logging.getLogger(__name__)

DATE_FEATURE_COLUMNS = [
    "published_date", "year", "quarter", "month", "month_name",
    "iso_week", "day_of_month", "day_of_week_num", "day_of_week",
]


def add_date_features(df: pd.DataFrame, column: str = "published_date") -> pd.DataFrame:
    """Parse ``column`` to a date and add calendar attributes alongside it.

    The order matters: every attribute is extracted while the column is still
    a full datetime, and only then is the column narrowed to a plain date.
    Doing it the other way round throws ``AttributeError`` on ``.dt`` and is a
    classic silent-failure source in notebook code.
    """
    out = df.copy()
    parsed = pd.to_datetime(out[column], errors="coerce", format="mixed")

    unparsed = parsed.isna() & out[column].notna()
    if unparsed.any():
        logger.warning(
            "%d published_date values could not be parsed; examples: %s",
            int(unparsed.sum()), out.loc[unparsed, column].head(3).tolist(),
        )

    out["year"] = parsed.dt.year.astype("Int64")
    out["quarter"] = parsed.dt.quarter.astype("Int64")
    out["month"] = parsed.dt.month.astype("Int64")
    out["month_name"] = parsed.dt.month_name()
    out["iso_week"] = parsed.dt.isocalendar().week.astype("Int64")
    out["day_of_month"] = parsed.dt.day.astype("Int64")
    out["day_of_week_num"] = parsed.dt.dayofweek.astype("Int64")
    out["day_of_week"] = parsed.dt.day_name()

    # Narrow to a date last, once every attribute has been read off.
    out[column] = parsed.dt.date
    return out
