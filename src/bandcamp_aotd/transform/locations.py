"""Location standardisation — the hardest cleaning problem in the dataset.

``label_location_raw`` is free text a label owner typed into their own Bandcamp
profile. Across ~2,300 articles that produces every failure mode you would
expect and several you would not: stray whitespace before commas, CJK
placenames, six spellings of Washington D.C., the Turkish dotted capital I
(U+0130, which ``str.title()`` silently mangles), bare city names with no
country, and accent-only duplicates such as ``Bogota`` vs ``Bogota``.

The cleaner runs as an explicit, ordered pipeline. Order is load-bearing:
casing has to be normalised *before* the lookup tables are applied so their
keys match exactly, and the Turkish dotted capital has to be replaced *before*
casing so title-casing doesn't corrupt it. Each step is a separate named
function so the sequence reads as documentation and each rule can be
unit-tested on its own.

The second half of the module parses the standardised string into
``(city, state, country)`` for choropleth mapping.
"""
from __future__ import annotations

import logging
import re
import unicodedata

import pandas as pd

logger = logging.getLogger(__name__)

# ==========================================================================
# PART 1 - Standardise the free-text location string
# ==========================================================================

# Step 2 reference: CJK placenames that appear in the source data.
CJK_MAP = {"東京都": "Tokyo"}

# Step 6 reference: words whose casing str.title() would destroy.
KEEP_WORDS = {"D.C.", "KwaZulu-Natal", "São", "Québec", "Réunion", "Príncipe"}

# Step 8 reference: bare city names, expanded to fully-qualified locations.
CITY_EXPANSIONS = {
    "Chicago":       "Chicago, Illinois",
    "Detroit":       "Detroit, Michigan",
    "Denton":        "Denton, Texas",
    "Pittsburgh":    "Pittsburgh, Pennsylvania",
    "San Francisco": "San Francisco, California",
    "Los Angeles":   "Los Angeles, California",
    "Toronto":       "Toronto, Ontario",
    "Vancouver":     "Vancouver, British Columbia",
    "Grand Rapids":  "Grand Rapids, Michigan",
    "Barcelona":     "Barcelona, Spain",
    # Country-level entries that are really cities
    "Belize":        "Belize City, Belize",
}

# Step 9 reference: hand-built alias map covering de-duplication, typo fixes,
# translations, and geocoder-friendly rewrites.
ALIASES = {
    # Accent de-duplication
    "Bogota, Colombia":                 "Bogotá, Colombia",
    "Montreal, Quebec":                 "Montréal, Québec",
    "Montreal, Québec":            "Montréal, Québec",
    "Istanbul, Turkey":                 "İstanbul, Turkey",
    "İstanbul, Turkey":            "İstanbul, Turkey",
    # Compound / malformed entries
    "Sao Tome, São Tomé And Príncipe":  "São Tomé, São Tomé and Príncipe",
    "São Tomé, São Tomé And Príncipe": "São Tomé, São Tomé and Príncipe",
    "Kwazulu-Natal, South Africa":      "KwaZulu-Natal, South Africa",
    "Kzn, South Africa":                "KwaZulu-Natal, South Africa",
    # Typos
    "Knosos, Greece":                   "Knossos, Greece",
    # Language normalisation
    "Sizilien, Italy":                  "Sicily, Italy",
    "Venezia, Italy":                   "Venice, Italy",
    # Geocoder-friendlier country forms
    "Syrian Arab Republic":             "Syria",
    "Democratic Republic Of The Congo": "Democratic Republic of the Congo",
    # Bare province -> add country
    "British Columbia":                 "British Columbia, Canada",
    # Ambiguous regional codes
    "Cn, Spain":                        "Castellón, Spain",
    "Ga, Spain":                        "Galicia, Spain",
    "Ib, Spain":                        "Ibiza, Spain",
    "Go, Brazil":                       "Goiás, Brazil",
    "Dl, Ireland":                      "County Donegal, Ireland",
    # Unusable entry -> fall back to the country
    "Straße, Egypt":               "Egypt",
}


def fix_whitespace(s: str) -> str:
    """Step 1 - collapse runs of whitespace and normalise comma spacing.

    ``"Osaka ,  Japan"`` -> ``"Osaka, Japan"``
    """
    s = re.sub(r"\s+", " ", s)
    s = re.sub(r"\s+,", ",", s)
    s = re.sub(r",\s{2,}", ", ", s)
    return s.strip()


def fix_cjk(s: str) -> str:
    """Step 2 - romanise CJK placenames. ``"<Tokyo in kanji>, Japan"`` -> ``"Tokyo, Japan"``"""
    for cjk, english in CJK_MAP.items():
        s = s.replace(cjk, english)
    return s.strip(", ").strip()


def fix_dc(s: str) -> str:
    """Step 3 - collapse every Washington D.C. spelling into one.

    Runs before title-casing, which would otherwise produce ``D.c.``
    """
    return re.sub(
        r"Washington,?\s*D\.?\s*C\.?,?\s*D\.?\s*C\.?",
        "Washington, D.C.", s, flags=re.IGNORECASE,
    )


def fix_turkish_dotted_i(s: str) -> str:
    """Step 4 - replace the Turkish dotted capital I (U+0130) with plain I.

    ``str.title()`` decomposes U+0130 into ``I`` plus a combining dot, which
    then survives every later comparison and silently splits Istanbul into two
    distinct values. Normalising first is the only reliable fix.
    """
    return s.replace("İ", "I")


def fix_case(s: str) -> str:
    """Step 5 - title-case, so lookup-table keys match exactly."""
    return s.title()


def fix_title_artifacts(s: str) -> str:
    """Step 6 - repair casing that ``str.title()`` breaks.

    ``.title()`` capitalises the letter after every non-alphabetic character,
    which mangles hyphenated regions and abbreviations. Words on the
    allow-list are restored verbatim; everything else keeps only its first
    letter capitalised.
    """
    fixed = []
    for word in s.split():
        if word in KEEP_WORDS:
            fixed.append(word)
        else:
            fixed.append(word[0] + word[1:].lower() if len(word) > 1 else word)
    return " ".join(fixed)


def expand_uk(s: str) -> str:
    """Step 7 - ``"Uk"`` -> ``"United Kingdom"`` (post-title-case spelling)."""
    return re.sub(r"\bUk\b", "United Kingdom", s)


def expand_bare_cities(s: str) -> str:
    """Step 8 - qualify bare city names so they geocode unambiguously."""
    return CITY_EXPANSIONS.get(s, s)


def apply_aliases(s: str) -> str:
    """Step 9 - apply the manual alias map, Unicode-normalising the lookup.

    Accented names can arrive as either NFC (a single codepoint) or NFD (a
    base letter plus a combining accent). Comparing normalised forms means
    both spellings hit the same key.
    """
    if s in ALIASES:
        return ALIASES[s]
    normalised = unicodedata.normalize("NFC", s)
    for key, value in ALIASES.items():
        if unicodedata.normalize("NFC", key) == normalised:
            return value
    return s


# The ordered pipeline. Order is load-bearing - see the module docstring.
CLEANING_STEPS = (
    fix_whitespace,
    fix_cjk,
    fix_dc,
    fix_turkish_dotted_i,
    fix_case,
    fix_title_artifacts,
    expand_uk,
    expand_bare_cities,
    apply_aliases,
)


def clean_location(raw) -> str | None:
    """Run the full standardisation pipeline over one raw location string."""
    if raw is None or str(raw).strip() == "" or (isinstance(raw, float) and pd.isna(raw)):
        return None
    value = str(raw).strip()
    for step in CLEANING_STEPS:
        value = step(value)
    return value or None


# ==========================================================================
# PART 2 - Parse the standardised string into city / state / country
# ==========================================================================

US_STATES = {
    "Alabama", "Alaska", "Arizona", "Arkansas", "California", "Colorado",
    "Connecticut", "Delaware", "Florida", "Georgia", "Hawaii", "Idaho",
    "Illinois", "Indiana", "Iowa", "Kansas", "Kentucky", "Louisiana", "Maine",
    "Maryland", "Massachusetts", "Michigan", "Minnesota", "Mississippi",
    "Missouri", "Montana", "Nebraska", "Nevada", "New Hampshire", "New Jersey",
    "New Mexico", "New York", "North Carolina", "North Dakota", "Ohio",
    "Oklahoma", "Oregon", "Pennsylvania", "Rhode Island", "South Carolina",
    "South Dakota", "Tennessee", "Texas", "Utah", "Vermont", "Virginia",
    "Washington", "West Virginia", "Wisconsin", "Wyoming", "D.C.",
}

CANADA_PROVINCES = {
    "Alberta", "British Columbia", "Manitoba", "New Brunswick",
    "Newfoundland and Labrador", "Nova Scotia", "Ontario",
    "Prince Edward Island", "Québec", "Quebec", "Saskatchewan",
    "Northwest Territories", "Nunavut", "Yukon",
}

# Resolved to country "United Kingdom" with the constituent kept as ``state``,
# so "London, England" and "London, United Kingdom" count as one country in
# the dashboard while the finer detail survives for anyone who wants it.
UK_CONSTITUENTS = {"England", "Scotland", "Wales", "Northern Ireland"}

# "Georgia" is both a US state and a country, and the country lookup wins -
# which quietly filed Atlanta under the Caucasus. A city on this list resolves
# to the state; anything else ("Tbilisi, Georgia") keeps the country.
GEORGIA_US_CITIES = {
    "Atlanta", "Athens", "Savannah", "Augusta", "Macon", "Columbus",
    "Decatur", "Perry", "Marietta", "Alpharetta",
}

# Values that parse correctly but should be *reported* under a canonical name.
# ``location_clean`` keeps the original text - it is the dim_place key and the
# audit trail - only the parsed city / state change.
#
# New York's boroughs are one city for coverage purposes: split apart, Brooklyn
# looks like a mid-sized city and New York falls behind Los Angeles. And
# Tableau geocodes "District of Columbia" but not the "D.C." spelling the
# source data uses.
BOROUGH_CANONICAL = {
    ("Brooklyn", "New York"):      "New York",
    ("Queens", "New York"):        "New York",
    ("Manhattan", "New York"):     "New York",
    ("Bronx", "New York"):         "New York",
    ("The Bronx", "New York"):     "New York",
    ("Staten Island", "New York"): "New York",
}
STATE_CANONICAL = {"D.C.": "District of Columbia"}

# Country names that contain a comma, which would otherwise be split apart.
MULTI_WORD_COUNTRY_WITH_COMMA = {"São Tomé and Príncipe"}

# Everyday names that ISO 3166 (and therefore pycountry) stores differently,
# plus territories the dataset treats as their own country. Keeping this
# explicit means an upstream pycountry release cannot silently change how a
# country is labelled in the dashboard.
COUNTRY_ALIASES = {
    "Uk": "United Kingdom", "United Kingdom": "United Kingdom",
    "Usa": "United States", "United States": "United States",
    "South Korea": "South Korea", "The Netherlands": "Netherlands",
    "Netherlands": "Netherlands", "Russia": "Russia", "Iran": "Iran",
    "Syria": "Syria",
    "Democratic Republic of the Congo": "Democratic Republic of the Congo",
    "Vietnam": "Vietnam", "Taiwan": "Taiwan", "Bolivia": "Bolivia",
    "Venezuela": "Venezuela", "Palestine": "Palestine",
    "Hong Kong": "Hong Kong", "Faroe Islands": "Faroe Islands",
    "Puerto Rico": "Puerto Rico", "Guadeloupe": "Guadeloupe",
    "Réunion": "Réunion", "Zanzibar": "Tanzania",
    "Guyana": "Guyana", "Jamaica": "Jamaica", "Singapore": "Singapore",
    "Israel": "Israel", "Lebanon": "Lebanon", "Ghana": "Ghana",
    "Nigeria": "Nigeria", "Niger": "Niger",
    # Common names pycountry now stores only under their official form
    "Turkey": "Turkey",                 # pycountry: "Türkiye"
    "Czech Republic": "Czech Republic",  # pycountry: "Czechia"
    "Ivory Coast": "Ivory Coast",        # pycountry: "Côte d'Ivoire"
    "Cape Verde": "Cape Verde",          # pycountry: "Cabo Verde"
    "Swaziland": "Swaziland",            # pycountry: "Eswatini"
    "Macedonia": "North Macedonia",
    "Burma": "Myanmar",
    "East Timor": "Timor-Leste",
}


def _build_country_names() -> set:
    """Every ISO 3166 country name, plus the aliases above.

    pycountry is the source of truth for the long tail; if it isn't installed
    the module still works against the alias map alone, just with less
    coverage. That keeps the import optional rather than fatal.
    """
    names = set(COUNTRY_ALIASES) | set(COUNTRY_ALIASES.values())
    try:
        import pycountry
    except ImportError:  # pragma: no cover - optional dependency
        logger.warning(
            "pycountry is not installed - country matching falls back to the "
            "built-in alias map. Install it with: pip install pycountry"
        )
        return names
    for country in pycountry.countries:
        names.add(country.name)
        for attr in ("common_name", "official_name"):
            value = getattr(country, attr, None)
            if value:
                names.add(value)
    return names


COUNTRY_NAMES = _build_country_names()


def is_country(name: str) -> bool:
    return name in COUNTRY_NAMES


def normalize_country(name: str) -> str:
    return COUNTRY_ALIASES.get(name, name)


def _parse_location(location) -> tuple[str | None, str | None, str | None]:
    """Split a standardised location into ``(city, state, country)``.

    Rules, in the order they are tried:

    * Countries whose own name contains a comma are matched first, before any
      comma splitting can tear them apart.
    * A single token is resolved by lookup: country, US state, Canadian
      province, or - failing all three - an unqualified city.
    * Two tokens are the common case: ``City, Country``, ``City, State``, or
      ``Region, Country``.
    * UK constituent countries resolve to country "United Kingdom" with the
      constituent (England, Scotland, ...) kept as the state, so the country
      count isn't inflated by "London, England" vs "London, United Kingdom".
    * "Georgia" is the US state when the city is a known Georgia city
      (Atlanta, Athens, Savannah) and the country otherwise (Tbilisi).
    """
    if location is None or str(location).strip() == "" or (
        isinstance(location, float) and pd.isna(location)
    ):
        return (None, None, None)

    raw = str(location).strip()

    for special in MULTI_WORD_COUNTRY_WITH_COMMA:
        if raw.endswith(special):
            city = raw[: -len(special)].rstrip(", ").strip()
            return (city or None, None, special)

    parts = [part.strip() for part in raw.split(",")]

    # -- One token -------------------------------------------------------
    if len(parts) == 1:
        value = parts[0]
        if value in UK_CONSTITUENTS:
            return (None, value, "United Kingdom")
        if is_country(value):
            return (None, None, normalize_country(value))
        if value in US_STATES:
            return (None, value, "United States")
        if value in CANADA_PROVINCES:
            return (None, value, "Canada")
        return (value, None, None)

    # -- Two tokens ------------------------------------------------------
    if len(parts) == 2:
        first, second = parts
        if first in UK_CONSTITUENTS and second == "United Kingdom":
            return (None, first, "United Kingdom")
        if first in US_STATES and second in ("United States", "Usa"):
            return (None, first, "United States")
        if second == "Georgia" and first in GEORGIA_US_CITIES:
            return (first, "Georgia", "United States")
        if is_country(second):
            return (first, None, normalize_country(second))
        if second in US_STATES:
            return (first, second, "United States")
        if second in CANADA_PROVINCES:
            return (first, second, "Canada")
        if second in UK_CONSTITUENTS:
            return (first, second, "United Kingdom")
        return (first, second, None)

    # -- Three or more tokens --------------------------------------------
    if is_country(parts[-1]):
        return (", ".join(parts[:-1]), None, normalize_country(parts[-1]))
    return (", ".join(parts[:-1]), parts[-1], None)


def canonicalise_place(city, state, country):
    """Apply :data:`BOROUGH_CANONICAL` and :data:`STATE_CANONICAL`.

    Only fires for the United States - the maps are US-specific, and keeping
    the guard explicit means a "Queens, New York" in some other country's data
    can never be swallowed by accident.
    """
    if country == "United States":
        city = BOROUGH_CANONICAL.get((city, state), city)
        state = STATE_CANONICAL.get(state, state)
    return (city, state, country)


def split_location(location) -> tuple[str | None, str | None, str | None]:
    """Parse a standardised location, then apply the canonical-name maps.

    This is the public entry point; :func:`_parse_location` documents the
    parsing rules and :func:`canonicalise_place` the renames that follow.
    """
    return canonicalise_place(*_parse_location(location))


def add_location_features(
    df: pd.DataFrame, source_column: str = "label_location_raw"
) -> pd.DataFrame:
    """Add ``location_clean``, ``city``, ``state`` and ``country`` to ``df``.

    Returns a copy; the caller's frame is never mutated.
    """
    out = df.copy()
    out["location_clean"] = out[source_column].apply(clean_location)
    parsed = out["location_clean"].apply(split_location)
    out[["city", "state", "country"]] = pd.DataFrame(parsed.tolist(), index=out.index)

    unresolved = out["location_clean"].notna() & out["country"].isna()
    if unresolved.any():
        examples = sorted(out.loc[unresolved, "location_clean"].dropna().unique())[:10]
        logger.warning(
            "%d rows have a cleaned location but no country. Add them to "
            "ALIASES or CITY_EXPANSIONS. Examples: %s",
            int(unresolved.sum()), examples,
        )
    return out
