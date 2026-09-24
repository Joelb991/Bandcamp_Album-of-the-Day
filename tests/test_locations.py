"""Tests for location standardisation.

Each case here is a real value that appeared in the scraped data and broke
something. Keeping them as tests means a future refactor of the cleaning
order cannot silently reintroduce a bug that was already fixed once.
"""
import pandas as pd
import pytest

from bandcamp_aotd.transform import locations as loc


class TestCleaningSteps:
    def test_collapses_whitespace_around_commas(self):
        assert loc.fix_whitespace("Osaka ,  Japan") == "Osaka, Japan"
        assert loc.fix_whitespace("  Berlin,   Germany  ") == "Berlin, Germany"

    def test_romanises_cjk_placenames(self):
        assert loc.fix_cjk("東京都, Japan") == "Tokyo, Japan"

    @pytest.mark.parametrize("raw", [
        "Washington, D.C., D.C.",
        "Washington DC, DC",
        "Washington, D.C, D.C",
        "washington, d.c., d.c.",
    ])
    def test_normalises_every_dc_spelling(self, raw):
        assert loc.fix_dc(raw) == "Washington, D.C."

    def test_replaces_turkish_dotted_capital_before_title_casing(self):
        # U+0130 survives .title() as a decomposed sequence, which silently
        # splits Istanbul into two distinct values. Replacing it first is the
        # fix; the alias map then restores the correct Turkish spelling, so
        # both inputs converge on one canonical value.
        assert loc.fix_turkish_dotted_i("İstanbul, Turkey") == "Istanbul, Turkey"
        assert loc.clean_location("İstanbul, Turkey") == loc.clean_location("istanbul, turkey")

    def test_title_artifacts_preserve_allow_listed_words(self):
        assert loc.fix_title_artifacts("Kwazulu-Natal") == "Kwazulu-natal"
        assert loc.fix_title_artifacts("KwaZulu-Natal") == "KwaZulu-Natal"

    def test_expands_uk_abbreviation(self):
        assert loc.expand_uk("London, Uk") == "London, United Kingdom"
        # Must not fire inside another word.
        assert loc.expand_uk("Ukraine") == "Ukraine"

    def test_qualifies_bare_city_names(self):
        assert loc.expand_bare_cities("Chicago") == "Chicago, Illinois"
        assert loc.expand_bare_cities("Nowhere") == "Nowhere"


class TestCleanLocation:
    @pytest.mark.parametrize("raw,expected", [
        ("Osaka , Japan", "Osaka, Japan"),
        ("brooklyn, new york", "Brooklyn, New York"),
        ("LONDON, UK", "London, United Kingdom"),
        ("Chicago", "Chicago, Illinois"),
        ("Washington, D.C., D.C.", "Washington, D.C."),
        ("Bogota, Colombia", "Bogotá, Colombia"),
        ("Kzn, South Africa", "KwaZulu-Natal, South Africa"),
        ("Knosos, Greece", "Knossos, Greece"),
        ("Venezia, Italy", "Venice, Italy"),
    ])
    def test_end_to_end_cleaning(self, raw, expected):
        assert loc.clean_location(raw) == expected

    @pytest.mark.parametrize("empty", [None, "", "   ", float("nan")])
    def test_empty_values_become_none(self, empty):
        assert loc.clean_location(empty) is None

    def test_accent_variants_collapse_to_one_value(self):
        assert loc.clean_location("Montreal, Quebec") == loc.clean_location("Montreal, Québec")


class TestSplitLocation:
    @pytest.mark.parametrize("value,expected", [
        ("Boston, Massachusetts",     ("Boston", "Massachusetts", "United States")),
        ("Berlin, Germany",           ("Berlin", None, "Germany")),
        ("Toronto, Ontario",          ("Toronto", "Ontario", "Canada")),
        ("Japan",                     (None, None, "Japan")),
        ("California",                (None, "California", "United States")),
        ("British Columbia, Canada",  ("British Columbia", None, "Canada")),
    ])
    def test_common_shapes(self, value, expected):
        assert loc.split_location(value) == expected

    def test_uk_constituents_roll_up_to_the_united_kingdom(self):
        # "London, England" and "London, United Kingdom" are the same country
        # for coverage purposes; the constituent survives as the state.
        uk = "United Kingdom"
        assert loc.split_location("England, United Kingdom") == (None, "England", uk)
        assert loc.split_location("Scotland") == (None, "Scotland", uk)
        assert loc.split_location("London, England") == ("London", "England", uk)
        assert loc.split_location("Glasgow, Scotland") == ("Glasgow", "Scotland", uk)

    def test_georgia_is_a_state_for_us_cities_and_a_country_otherwise(self):
        # pycountry knows Georgia the country; it must not win for Atlanta.
        assert loc.split_location("Atlanta, Georgia") == ("Atlanta", "Georgia", "United States")
        assert loc.split_location("Athens, Georgia") == ("Athens", "Georgia", "United States")
        assert loc.split_location("Tbilisi, Georgia") == ("Tbilisi", None, "Georgia")

    @pytest.mark.parametrize(
        "borough", ["Brooklyn", "Queens", "Manhattan", "Bronx", "Staten Island"]
    )
    def test_new_york_boroughs_are_reported_as_new_york(self, borough):
        assert loc.split_location(f"{borough}, New York") == (
            "New York", "New York", "United States"
        )

    def test_dc_is_spelled_out_for_the_geocoder(self):
        assert loc.split_location("Washington, D.C.") == (
            "Washington", "District of Columbia", "United States"
        )

    def test_canonicalisation_is_limited_to_the_united_states(self):
        place = ("Queens", "New York", "Jamaica")
        assert loc.canonicalise_place(*place) == place

    def test_country_containing_a_comma_is_not_split_apart(self):
        assert loc.split_location("São Tomé, São Tomé and Príncipe") == (
            "São Tomé", None, "São Tomé and Príncipe"
        )

    def test_empty_returns_all_none(self):
        assert loc.split_location(None) == (None, None, None)
        assert loc.split_location("") == (None, None, None)


class TestAddLocationFeatures:
    def test_adds_all_four_columns_without_mutating_input(self):
        df = pd.DataFrame({"label_location_raw": ["Osaka , Japan", "Chicago", None]})
        original = df.copy()
        out = loc.add_location_features(df)

        assert list(out.columns) == [
            "label_location_raw", "location_clean", "city", "state", "country"
        ]
        assert out.loc[0, "country"] == "Japan"
        assert out.loc[1, "state"] == "Illinois"
        assert pd.isna(out.loc[2, "location_clean"])
        pd.testing.assert_frame_equal(df, original)   # input untouched

    def test_location_clean_keeps_the_borough_while_city_is_canonical(self):
        # dim_place is keyed on location_clean, so the original text must
        # survive; only the parsed city rolls up.
        df = pd.DataFrame({"label_location_raw": ["brooklyn, new york"]})
        out = loc.add_location_features(df)
        assert out.loc[0, "location_clean"] == "Brooklyn, New York"
        assert out.loc[0, "city"] == "New York"
