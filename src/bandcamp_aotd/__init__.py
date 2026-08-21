"""Bandcamp *Album of the Day* analytics pipeline.

An ELT pipeline that turns Bandcamp Daily's editorial archive into a modelled
Postgres warehouse feeding a Tableau dashboard and a web app.

Stages
------
``extract``   discover, fetch and parse Bandcamp Daily article pages
``enrich``    attach Spotify catalog metadata (cover art, release date, links)
``transform`` clean locations, derive geography and calendar features
``load``      upsert into Postgres, idempotently

Run the whole thing with ``python -m bandcamp_aotd refresh``.
"""

__version__ = "2.0.0"
__all__ = ["config", "extract", "enrich", "transform", "load", "legacy"]
