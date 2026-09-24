"""Tests for article parsing and the artist/label business rules.

The HTML fixtures are trimmed to just the fragments each extractor targets -
enough to prove the regex and the meta-tag fallback both work, without
committing a 200KB page to the repo.
"""

from bandcamp_aotd.extract import parse

ARTICLE_HTML = """
<html><head>
<title>
Album of the Day: Kelly Lee Owens, &#8220;Inner Song&#8221; | Bandcamp Daily
</title>
<meta property="article:tag" content="Electronic">
<meta property="article:published_time" content="2020-08-28">
</head><body>
<article>
<div class="byline">contributors"><a href="/contributor/x">Jane Doe</a></div>
&middot; August 28, 2020
</article>
<a class="artist-name" data-label="true">Smalltown Supersound</a>
<div class="location">Oslo, Norway</div>
</body></html>
"""


class TestFieldExtraction:
    def test_title_strips_branding_and_prefix(self):
        # Typographic quotes are stripped here so the album title matches
        # across sources; the plain-text form is what the warehouse stores.
        assert parse.parse_title(ARTICLE_HTML) == "Kelly Lee Owens, Inner Song"

    def test_tags(self):
        assert parse.parse_tags(ARTICLE_HTML) == "Electronic"

    def test_meta_fallback_used_when_regex_finds_nothing(self):
        # Simulates Bandcamp changing its markup: no <title>, only meta tags.
        html = ('<meta property="og:title" content="Album of the Day: A, B">'
                '<meta property="article:tag" content="Jazz">')
        assert parse.parse_title(html) == "A, B"
        assert parse.parse_tags(html) == "Jazz"

    def test_missing_fields_return_none_rather_than_raising(self):
        assert parse.parse_title("<html></html>") is None
        assert parse.parse_author("<html></html>") is None
        assert parse.parse_label_location("<html></html>") is None


class TestSplitArtistAlbum:
    def test_splits_on_the_first_comma_only(self):
        assert parse.split_artist_album('Sufjan Stevens, "Illinois, The Album"') == (
            "Sufjan Stevens", "Illinois, The Album"
        )

    def test_strips_typographic_quotes_from_the_album(self):
        assert parse.split_artist_album("Kelly Lee Owens, “Inner Song”") == (
            "Kelly Lee Owens", "Inner Song"
        )

    def test_no_comma_yields_identical_artist_and_album(self):
        assert parse.split_artist_album("Untitled") == ("Untitled", "Untitled")

    def test_none_in_none_out(self):
        assert parse.split_artist_album(None) == (None, None)


class TestBusinessRules:
    def test_headline_without_a_comma_promotes_the_label_to_artist(self):
        artist, label = parse.resolve_label_and_artist("Untitled", "Untitled", "Boomkat")
        assert artist == "Boomkat"

    def test_artist_equal_to_label_means_self_released(self):
        artist, label = parse.resolve_label_and_artist("Aphex Twin", "Syro", "Aphex Twin")
        assert (artist, label) == ("Aphex Twin", parse.INDEPENDENT_LABEL)

    def test_self_titled_headline_with_a_comma_keeps_its_artist(self):
        # "Celestial Power, Celestial Power" on Feeding Tube Records was being
        # credited to the label, and marked self-released.
        artist, label = parse.resolve_label_and_artist(
            "Celestial Power", "Celestial Power", "Feeding Tube Records",
            headline_had_comma=True,
        )
        assert (artist, label) == ("Celestial Power", "Feeding Tube Records")

    def test_self_titled_and_self_released_is_still_independent(self):
        artist, label = parse.resolve_label_and_artist(
            "Hannah Lew", "Hannah Lew", "Hannah Lew", headline_had_comma=True
        )
        assert (artist, label) == ("Hannah Lew", parse.INDEPENDENT_LABEL)

    def test_normal_signed_release_is_left_alone(self):
        artist, label = parse.resolve_label_and_artist(
            "Kelly Lee Owens", "Inner Song", "Smalltown Supersound"
        )
        assert (artist, label) == ("Kelly Lee Owens", "Smalltown Supersound")


class TestParseArticle:
    def test_returns_the_canonical_record_shape(self):
        record = parse.parse_article(ARTICLE_HTML, "https://daily.bandcamp.com/album-of-the-day/x")
        assert record["article_slug"] == "x"
        assert record["artist"] == "Kelly Lee Owens"
        assert record["album"] == "Inner Song"
        assert record["genre_tag"] == "Electronic"
        assert record["label_location_raw"] == "Oslo, Norway"

    def test_empty_html_is_reported_not_raised(self):
        record = parse.parse_article("", "https://daily.bandcamp.com/album-of-the-day/x")
        assert record["parse_status"] == "empty_html"
