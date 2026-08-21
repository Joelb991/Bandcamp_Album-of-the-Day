"""Tests for the identity key, calendar features and the transform pipeline.

The article_id tests are the important ones: the whole idempotent-load design
rests on that hash being stable, so these pin down exactly what it does and
does not react to.
"""
import pandas as pd
import pytest

from bandcamp_aotd.transform import (
    ANALYTICS_COLUMNS,
    add_date_features,
    build_analytics_table,
    make_article_id,
)
from bandcamp_aotd.transform.text import normalize_text


@pytest.fixture
def raw_rows():
    return pd.DataFrame({
        "published_date": ["March 14, 2024", "March 15, 2024"],
        "title": ["Artist One, Album One", "Artist Two, Album Two"],
        "artist": ["Artist One", "Artist Two"],
        "album": ["Album One", "Album Two"],
        "genre_tag": ["Jazz", "Electronic"],
        "record_label": ["Blue Note", "Independent Artist"],
        "label_location_raw": ["Brooklyn, New York", "Berlin, Germany"],
        "author": ["Jane Doe", "John Roe"],
    })


class TestArticleId:
    def test_is_deterministic(self):
        a = make_article_id("2024-03-14", "Artist", "Album")
        b = make_article_id("2024-03-14", "Artist", "Album")
        assert a == b and a is not None

    def test_ignores_case_punctuation_and_whitespace(self):
        # These are the cosmetic differences between the legacy CSV export and
        # a fresh scrape; they must not mint a second id for the same article.
        assert make_article_id("2024-03-14", "Bjork", "Post") == \
               make_article_id("2024-03-14", " BJORK ", "Post!")

    def test_different_articles_get_different_ids(self):
        assert make_article_id("2024-03-14", "A", "X") != \
               make_article_id("2024-03-15", "A", "X")

    def test_all_empty_input_yields_none(self):
        assert make_article_id(None, None, None) is None


class TestDateFeatures:
    def test_derives_every_calendar_attribute(self):
        df = add_date_features(pd.DataFrame({"published_date": ["March 14, 2024"]}))
        row = df.iloc[0]
        assert row["year"] == 2024
        assert row["quarter"] == 1
        assert row["month"] == 3
        assert row["month_name"] == "March"
        assert row["day_of_week"] == "Thursday"
        assert row["day_of_month"] == 14

    def test_unparseable_dates_become_null_not_an_exception(self):
        df = add_date_features(pd.DataFrame({"published_date": ["not a date"]}))
        assert pd.isna(df.loc[0, "year"])


class TestTextNormalisation:
    def test_unescapes_entities_and_straightens_quotes(self):
        assert normalize_text("Sam&#39;s  Label") == "Sam's Label"
        assert normalize_text("“Album”") == "Album"

    def test_empty_becomes_none(self):
        assert normalize_text("   ") is None
        assert normalize_text(None) is None


class TestBuildAnalyticsTable:
    def test_produces_the_canonical_schema(self, raw_rows):
        out = build_analytics_table(raw_rows)
        assert list(out.columns) == ANALYTICS_COLUMNS
        assert len(out) == 2

    def test_derives_geography_and_the_indie_flag(self, raw_rows):
        out = build_analytics_table(raw_rows).set_index("artist")
        assert out.loc["Artist One", "country"] == "United States"
        assert out.loc["Artist One", "state"] == "New York"
        assert bool(out.loc["Artist One", "is_independent"]) is False
        assert bool(out.loc["Artist Two", "is_independent"]) is True

    def test_is_idempotent_and_deduplicates(self, raw_rows):
        doubled = pd.concat([raw_rows, raw_rows], ignore_index=True)
        assert len(build_analytics_table(doubled)) == 2

    def test_running_twice_gives_identical_output(self, raw_rows):
        first = build_analytics_table(raw_rows)
        second = build_analytics_table(raw_rows)
        pd.testing.assert_frame_equal(first, second)

    def test_output_is_sorted_by_date(self, raw_rows):
        out = build_analytics_table(raw_rows)
        assert out["published_date"].is_monotonic_increasing
