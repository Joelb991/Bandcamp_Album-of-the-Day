"""The refresh path, run against a repo that already holds the archive.

Two bugs made `refresh` unsafe there, and neither raised an error:

* The Spotify checkpoint was keyed by row position. The legacy run left
  positions 0..2287 in it, so a fresh scrape (rows 0..n) was treated as
  already enriched and silently given the legacy rows' matches.
* `transform` wrote only the newly scraped rows to the analytics CSV,
  replacing the full archive the notebooks and the Tableau extract read.
"""
import pandas as pd
import pytest

from bandcamp_aotd.cli import build_parser
from bandcamp_aotd.enrich.spotify import SpotifyClient, album_key
from bandcamp_aotd.transform import ANALYTICS_COLUMNS, build_analytics_table, merge_analytics


def _client(lookups: list):
    """A SpotifyClient whose album lookups are recorded, not sent."""
    client = SpotifyClient.__new__(SpotifyClient)   # skip credential checks
    client.call_budget = None
    client.calls_made = 0

    def fake_enrich_album(artist, album, full_details=False):
        lookups.append((artist, album))
        return {"spotify_match_status": "matched", "spotify_id": f"id:{artist}/{album}"}

    client.enrich_album = fake_enrich_album
    return client


def _scrape(*pairs):
    return pd.DataFrame({"artist": [a for a, _ in pairs], "album": [b for _, b in pairs]})


class TestAlbumKey:
    def test_ignores_case_and_whitespace(self):
        assert album_key("  Black Milk ", "CEREMONIAL") == album_key("black milk", "ceremonial")

    def test_distinguishes_artist_from_album(self):
        assert album_key("A B", "C") != album_key("A", "B C")

    def test_missing_values_do_not_crash(self):
        assert album_key(None, float("nan")) == " || "


class TestCheckpoint:
    def test_a_position_keyed_checkpoint_is_not_reused_for_new_rows(self, tmp_path):
        checkpoint = tmp_path / "checkpoint.csv"
        # The old format: row 0 of the legacy run, a completely different album.
        pd.DataFrame(
            {"spotify_match_status": ["matched"], "spotify_id": ["LEGACY"]}, index=[0]
        ).to_csv(checkpoint)

        lookups = []
        out = _client(lookups).enrich_dataframe(
            _scrape(("New Artist", "New Album")), pause=0, checkpoint_path=str(checkpoint)
        )

        assert lookups == [("New Artist", "New Album")]
        assert out.loc[0, "spotify_id"] == "id:New Artist/New Album"

    def test_resume_skips_albums_already_resolved(self, tmp_path):
        checkpoint = str(tmp_path / "checkpoint.csv")
        first = []
        _client(first).enrich_dataframe(_scrape(("A", "One")), pause=0, checkpoint_path=checkpoint)

        # Same album again, now at a different position, plus a new one.
        second = []
        out = _client(second).enrich_dataframe(
            _scrape(("B", "Two"), ("A", "One")), pause=0, checkpoint_path=checkpoint
        )

        assert second == [("B", "Two")]
        assert list(out["spotify_id"]) == ["id:B/Two", "id:A/One"]

    def test_an_album_featured_twice_is_looked_up_once(self):
        lookups = []
        out = _client(lookups).enrich_dataframe(_scrape(("A", "One"), ("a", "ONE ")), pause=0)
        assert len(lookups) == 1
        assert out["spotify_id"].tolist() == ["id:A/One", "id:A/One"]

    def test_output_keeps_the_input_index(self):
        df = _scrape(("A", "One"), ("B", "Two"))
        df.index = [10, 20]
        out = _client([]).enrich_dataframe(df, pause=0)
        assert list(out.index) == [10, 20]


@pytest.fixture
def scraped():
    def rows(*specs):
        return pd.DataFrame([{
            "published_date": date, "title": f"{artist}, {album}", "artist": artist,
            "album": album, "genre_tag": "Jazz", "record_label": "Blue Note",
            "label_location_raw": "Brooklyn, New York", "author": "Jane Doe",
            "article_url": url,
        } for date, artist, album, url in specs])
    return rows


class TestMergeAnalytics:
    def test_new_rows_are_added_and_the_archive_is_kept(self, scraped):
        archive = build_analytics_table(scraped(
            ("March 14, 2024", "Artist One", "Album One", None),
            ("March 15, 2024", "Artist Two", "Album Two", None),
        ))
        new = build_analytics_table(scraped(("June 2, 2026", "Artist Three", "Album Three", "u3")))

        merged = merge_analytics(archive, new)

        assert len(merged) == 3
        assert merged["artist"].tolist() == ["Artist One", "Artist Two", "Artist Three"]
        assert list(merged.columns) == ANALYTICS_COLUMNS

    def test_a_re_scraped_article_replaces_its_old_row(self, scraped):
        archive = build_analytics_table(
            scraped(("March 14, 2024", "Artist One", "Album One", None))
        )
        rescraped = build_analytics_table(
            scraped(("March 14, 2024", "Artist One", "Album One", "https://daily.bandcamp.com/x"))
        )

        merged = merge_analytics(archive, rescraped)

        assert len(merged) == 1
        assert merged.loc[0, "article_url"] == "https://daily.bandcamp.com/x"

    def test_works_on_a_table_read_back_from_csv(self, scraped, tmp_path):
        # The CLI merges into the CSV on disk, where dates are strings, not date objects.
        path = tmp_path / "analytics.csv"
        one = build_analytics_table(scraped(("March 14, 2024", "A", "One", None)))
        one.to_csv(path, index=False)
        new = build_analytics_table(scraped(("January 2, 2024", "B", "Two", None)))

        merged = merge_analytics(pd.read_csv(path), new)

        assert merged["published_date"].tolist() == ["2024-01-02", "2024-03-14"]


class TestTransformCommand:
    def test_merges_into_the_existing_table_by_default(self, scraped, tmp_path, monkeypatch):
        from bandcamp_aotd import cli, config

        table = tmp_path / "analytics.csv"
        build_analytics_table(scraped(
            ("March 14, 2024", "A", "One", None), ("March 15, 2024", "B", "Two", None),
        )).to_csv(table, index=False)
        monkeypatch.setattr(config, "ANALYTICS_CSV", table)

        new_scrape = tmp_path / "scrape.csv"
        scraped(("June 2, 2026", "C", "Three", "u3")).to_csv(new_scrape, index=False)

        args = build_parser().parse_args(["transform", "--input", str(new_scrape)])
        assert cli.cmd_transform(args) == 0
        assert len(pd.read_csv(table)) == 3

    def test_replace_overwrites_on_purpose(self, scraped, tmp_path, monkeypatch):
        from bandcamp_aotd import cli, config

        table = tmp_path / "analytics.csv"
        one = build_analytics_table(scraped(("March 14, 2024", "A", "One", None)))
        one.to_csv(table, index=False)
        monkeypatch.setattr(config, "ANALYTICS_CSV", table)
        new_scrape = tmp_path / "scrape.csv"
        scraped(("June 2, 2026", "C", "Three", "u3")).to_csv(new_scrape, index=False)

        args = build_parser().parse_args(["transform", "--input", str(new_scrape), "--replace"])
        assert cli.cmd_transform(args) == 0
        assert pd.read_csv(table)["artist"].tolist() == ["C"]

    def test_refresh_sets_replace_so_it_can_delegate_to_transform(self):
        assert build_parser().parse_args(["refresh"]).replace is False
