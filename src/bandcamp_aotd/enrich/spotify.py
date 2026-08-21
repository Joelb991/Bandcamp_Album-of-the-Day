"""Spotify Web API client - enrichment for the Album of the Day dataset.

What this adds to the Bandcamp data
-----------------------------------
Cover art, canonical release date, album type, track count, and links back to
Spotify for both the album and the artist. Those are what turn a table of text
into something that looks like a product in the web app and the dashboard.

How matching works
------------------
``GET /search?type=album`` resolves each Bandcamp ``(artist, album)`` pair to a
Spotify album. The search response already carries everything except UPC/EAN
and copyright text, so the default cost is **one API call per row** - pass
``full_details=True`` to spend a second call per row on those extra fields.

Only public catalog data is touched, so this authenticates with the Client
Credentials flow: no user login, no scopes, no redirect URI.

Reliability
-----------
Three things make a 2,300-row run survivable:

* 429 and 5xx responses back off exponentially and honour ``Retry-After``,
  logging each wait so a long pause looks like progress rather than a hang.
* A per-row failure is captured in ``spotify_match_status`` instead of raising,
  so one odd album cannot kill the run.
* Progress is checkpointed to CSV every N rows. Re-running the same command
  resumes: completed rows are skipped and previously-errored rows are retried.

Deliberately omitted: ``Album.genres``, ``Album.label``, ``Album.popularity``
and the artist equivalents are deprecated in Spotify's current API and come
back empty or unreliable. The Bandcamp ``genre_tag`` and ``record_label``
columns are the better source and are already in the dataset.
"""
from __future__ import annotations

import logging
import os
import random
import time
from dataclasses import dataclass

import pandas as pd
import requests
from dotenv import load_dotenv

from .. import config

load_dotenv()

logger = logging.getLogger(__name__)

TOKEN_URL = "https://accounts.spotify.com/api/token"
API_BASE = "https://api.spotify.com/v1"
MAX_RETRIES = 5
MAX_WAIT_SECONDS = 60

# Spotify's limit is a rolling 30-second window whose size it does not publish.
# The original 0.1s pause (~10 requests/second) earned this project a 24-hour
# ban partway through a 2,288-row run. ~3 requests/second is slow enough to
# finish the full dataset in about 13 minutes without tripping it.
DEFAULT_PAUSE_SECONDS = 0.35


class SpotifyAPIError(Exception):
    """Raised when the Spotify API returns an error response."""


class SpotifyAuthError(SpotifyAPIError):
    """Raised when a Client Credentials token can't be obtained."""


class SpotifyRateLimitError(SpotifyAPIError):
    """Raised when Spotify imposes a rate limit longer than we will wait for.

    This is deliberately a *separate* exception from SpotifyAPIError, and it
    is deliberately NOT swallowed by the per-row error handling below.

    The reason is a failure this project actually hit: Spotify answered a bulk
    run with ``Retry-After: 86109`` (a 24-hour cooldown). The per-row handler
    caught it as an ordinary error, wrote "error: rate limited" into that row,
    and moved on - burning through 1,592 remaining rows in seconds, each one
    marked failed, and poisoning the checkpoint with work that was never
    actually attempted.

    A long rate limit is a run-level condition, not a row-level one. It stops
    the whole run so the checkpoint keeps only genuine results and the next
    run resumes from the right place.
    """


@dataclass
class _TokenCache:
    access_token: str | None = None
    expires_at: float = 0.0


class SpotifyClient:
    def __init__(self, client_id: str | None = None, client_secret: str | None = None):
        self.client_id = client_id or config.SPOTIFY.client_id
        self.client_secret = client_secret or config.SPOTIFY.client_secret
        if not self.client_id or not self.client_secret:
            raise SpotifyAuthError(
                "Missing SPOTIFY_CLIENT_ID / SPOTIFY_CLIENT_SECRET. Copy .env.example to "
                ".env and fill in credentials from https://developer.spotify.com/dashboard."
            )
        self._token = _TokenCache()
        self.session = requests.Session()

    # ---- authentication -------------------------------------------------

    def _fetch_token(self) -> None:
        response = self.session.post(
            TOKEN_URL,
            data={"grant_type": "client_credentials"},
            auth=(self.client_id, self.client_secret),
            timeout=30,
        )
        if response.status_code != 200:
            raise SpotifyAuthError(
                f"Failed to obtain access token ({response.status_code}): "
                f"{self._error_message(response)}"
            )
        payload = response.json()
        self._token.access_token = payload["access_token"]
        # Refresh a bit early so we don't race the actual expiry.
        self._token.expires_at = time.time() + payload.get("expires_in", 3600) - 60

    def _get_token(self) -> str:
        if not self._token.access_token or time.time() >= self._token.expires_at:
            self._fetch_token()
        return self._token.access_token

    @staticmethod
    def _error_message(response: requests.Response) -> str:
        try:
            body = response.json()
        except ValueError:
            return response.text[:200] or response.reason
        error = body.get("error")
        if isinstance(error, dict):
            return error.get("message", str(error))
        return str(error) if error else response.text[:200]

    # ---- request plumbing (rate limits + retries) ------------------------

    def _request(self, method: str, path: str, **kwargs) -> requests.Response:
        url = path if path.startswith("http") else f"{API_BASE}{path}"
        base_headers = kwargs.pop("headers", {})
        attempt = 0
        while True:
            headers = {**base_headers, "Authorization": f"Bearer {self._get_token()}"}
            response = self.session.request(method, url, headers=headers, timeout=30, **kwargs)

            if response.status_code == 401 and attempt == 0:
                # Token expired/invalid mid-run: force a refresh and retry once.
                self._token = _TokenCache()
                attempt += 1
                continue

            if response.status_code == 429:
                retry_after = float(response.headers.get("Retry-After", 1))
                if retry_after > MAX_WAIT_SECONDS:
                    raise SpotifyRateLimitError(
                        f"Spotify asked us to wait {retry_after / 3600:.1f}h "
                        f"({retry_after:.0f}s), far above the {MAX_WAIT_SECONDS}s cap. "
                        f"Stopping the run - progress is checkpointed, so re-run this "
                        f"command after the cooldown and it will resume."
                    )
                if attempt >= MAX_RETRIES:
                    raise SpotifyRateLimitError(
                        f"Still rate limited on {method} {url} after {attempt} retries"
                    )
                wait = max(retry_after, 2**attempt) + random.uniform(0, 0.5)
                logger.warning("Rate limited - waiting %.0fs (attempt %d/%d)",
                               wait, attempt + 1, MAX_RETRIES)
                time.sleep(wait)
                attempt += 1
                continue

            if response.status_code in (500, 502, 503):
                if attempt >= MAX_RETRIES:
                    raise SpotifyAPIError(
                        f"Spotify server error {response.status_code} on {method} {url} "
                        f"after {attempt} retries"
                    )
                wait = 2**attempt + random.uniform(0, 0.5)
                logger.warning("Server error %s - waiting %.0fs (attempt %d/%d)",
                               response.status_code, wait, attempt + 1, MAX_RETRIES)
                time.sleep(wait)
                attempt += 1
                continue

            if response.status_code >= 400:
                raise SpotifyAPIError(
                    f"{response.status_code} on {method} {url}: {self._error_message(response)}"
                )

            return response

    # ---- endpoints (see open-api-schema.yaml: search, get-an-album) ------

    def search_album(self, artist: str, album: str, market: str | None = None) -> dict | None:
        """GET /search, type=album. Returns the top SimplifiedAlbumObject hit, or None."""
        safe_artist = artist.replace('"', "")
        safe_album = album.replace('"', "")
        params = {"q": f'album:"{safe_album}" artist:"{safe_artist}"', "type": "album", "limit": 5}
        if market:
            params["market"] = market
        response = self._request("GET", "/search", params=params)
        items = response.json().get("albums", {}).get("items", [])
        return items[0] if items else None

    def get_album(self, album_id: str, market: str | None = None) -> dict:
        """GET /albums/{id}. Returns the full AlbumObject."""
        params = {"market": market} if market else {}
        response = self._request("GET", f"/albums/{album_id}", params=params)
        return response.json()

    def get_artist(self, artist_id: str) -> dict:
        """GET /artists/{id}. Returns the full ArtistObject (has images; SimplifiedArtistObject
        from search/album responses does not)."""
        response = self._request("GET", f"/artists/{artist_id}")
        return response.json()

    def enrich_artist(self, artist_id: str) -> dict:
        """Look up one artist by Spotify ID and return their photo + profile link.

        genres/followers/popularity are deprecated on ArtistObject (empty/unreliable)
        so they're intentionally left out — images and the profile URL are the only
        non-deprecated fields this call adds beyond what search/album already give you.
        """
        result: dict = {
            "spotify_artist_status": "no_id",
            "spotify_artist_image_url": None,
            "spotify_artist_url": None,
        }
        if not artist_id or pd.isna(artist_id):
            return result
        try:
            full = self.get_artist(artist_id)
        except SpotifyRateLimitError:
            raise                       # run-level: let it stop the whole pass
        except SpotifyAPIError as exc:
            result["spotify_artist_status"] = f"error: {exc}"
            return result

        images = full.get("images") or []
        result.update(
            {
                "spotify_artist_status": "matched",
                "spotify_artist_image_url": images[0]["url"] if images else None,
                "spotify_artist_url": (full.get("external_urls") or {}).get("spotify"),
            }
        )
        return result

    def enrich_artists(
        self,
        artist_ids: pd.Series,
        pause: float = DEFAULT_PAUSE_SECONDS,
        progress_every: int = 50,
        checkpoint_path: str | None = None,
        checkpoint_every: int = 50,
    ) -> pd.DataFrame:
        """Look up each unique Spotify artist ID once and return a DataFrame indexed
        by artist id — dedups so an artist featured on multiple rows is only fetched
        once. Merge back onto your main df with:

            df.merge(artist_df, left_on='spotify_artist_id', right_index=True, how='left')

        Same checkpoint/resume behavior as enrich_dataframe: errored lookups are
        retried on re-run, successful ones are skipped.
        """
        unique_ids = sorted(set(artist_ids.dropna()))
        results: dict = {}
        if checkpoint_path and os.path.exists(checkpoint_path):
            loaded = pd.read_csv(checkpoint_path, index_col=0).to_dict(orient="index")
            results = {
                aid: r for aid, r in loaded.items()
                if not str(r.get("spotify_artist_status", "")).startswith("error")
            }
            retrying = len(loaded) - len(results)
            logger.info("Resuming from checkpoint: %d artists done, %d to retry",
                        len(results), retrying)

        total = len(unique_ids)
        for i, artist_id in enumerate(unique_ids):
            try:
                if artist_id not in results:
                    results[artist_id] = self.enrich_artist(artist_id)
                    time.sleep(pause)
            except SpotifyRateLimitError:
                # Flush what we have before unwinding, so the cooldown costs
                # us nothing already paid for.
                if checkpoint_path:
                    pd.DataFrame.from_dict(results, orient="index").to_csv(checkpoint_path)
                    logger.warning("Checkpointed %d artists before stopping", len(results))
                raise

            if progress_every and (i + 1) % progress_every == 0:
                logger.info("Progress: %d / %d", i + 1, total)

            if checkpoint_path and checkpoint_every and (i + 1) % checkpoint_every == 0:
                pd.DataFrame.from_dict(results, orient="index").to_csv(checkpoint_path)

        if checkpoint_path:
            pd.DataFrame.from_dict(results, orient="index").to_csv(checkpoint_path)

        return pd.DataFrame.from_dict(results, orient="index")

    # ---- dataframe enrichment ---------------------------------------------

    def enrich_album(self, artist: str, album: str, full_details: bool = False) -> dict:
        """Look up one (artist, album) pair and return a flat dict of Spotify fields.

        By default this costs a single API call: /search already returns a
        SimplifiedAlbumObject with id/url/release_date/album_type/total_tracks/images —
        everything below except UPC/EAN/copyrights. Pass full_details=True to also call
        /albums/{id} (a second call) for those.

        Never raises for a single bad row — API errors are captured in
        spotify_match_status so a full-dataframe run doesn't die on one row.
        """
        result: dict = {
            "spotify_match_status": "no_match",
            "spotify_id": None,
            "spotify_url": None,
            "spotify_artist_id": None,
            "spotify_match_artist": None,
            "spotify_match_album": None,
            "spotify_release_date": None,
            "spotify_release_date_precision": None,
            "spotify_album_type": None,
            "spotify_total_tracks": None,
            "spotify_image_url": None,
            "spotify_upc": None,
            "spotify_ean": None,
            "spotify_copyright": None,
        }
        if not artist or not album or pd.isna(artist) or pd.isna(album):
            return result
        try:
            hit = self.search_album(artist, album)
            if hit is None:
                return result
            source = self.get_album(hit["id"]) if full_details else hit
        except SpotifyRateLimitError:
            raise                       # run-level: let it stop the whole pass
        except SpotifyAPIError as exc:
            result["spotify_match_status"] = f"error: {exc}"
            return result

        images = source.get("images") or []
        external_ids = source.get("external_ids") or {}
        copyrights = source.get("copyrights") or []
        artists = source.get("artists") or []
        result.update(
            {
                "spotify_match_status": "matched",
                "spotify_id": source.get("id"),
                "spotify_url": (source.get("external_urls") or {}).get("spotify"),
                "spotify_artist_id": artists[0]["id"] if artists else None,
                "spotify_match_artist": ", ".join(a["name"] for a in artists),
                "spotify_match_album": source.get("name"),
                "spotify_release_date": source.get("release_date"),
                "spotify_release_date_precision": source.get("release_date_precision"),
                "spotify_album_type": source.get("album_type"),
                "spotify_total_tracks": source.get("total_tracks"),
                "spotify_image_url": images[0]["url"] if images else None,
                "spotify_upc": external_ids.get("upc"),
                "spotify_ean": external_ids.get("ean"),
                "spotify_copyright": "; ".join(c.get("text", "") for c in copyrights) or None,
            }
        )
        return result

    def enrich_dataframe(
        self,
        df: pd.DataFrame,
        artist_col: str = "artist",
        album_col: str = "album",
        pause: float = DEFAULT_PAUSE_SECONDS,
        progress_every: int = 50,
        full_details: bool = False,
        checkpoint_path: str | None = None,
        checkpoint_every: int = 50,
    ) -> pd.DataFrame:
        """Run enrich_album for every row and return a new DataFrame (same index)
        of spotify_* columns to merge onto the original with pd.concat(axis=1).

        If checkpoint_path is given, progress is saved there every checkpoint_every
        rows. If that file already exists when called, rows already 'matched' or
        confirmed 'no_match' are skipped; rows that previously errored (e.g. hit
        the rate limit) are retried — safe to interrupt and just re-run the same
        cell to resume.
        """
        results: dict = {}
        if checkpoint_path and os.path.exists(checkpoint_path):
            loaded = pd.read_csv(checkpoint_path, index_col=0).to_dict(orient="index")
            results = {
                idx: r for idx, r in loaded.items()
                if not str(r.get("spotify_match_status", "")).startswith("error")
            }
            retrying = len(loaded) - len(results)
            logger.info("Resuming from checkpoint: %d rows done, %d to retry",
                        len(results), retrying)

        total = len(df)
        for i, (idx, row) in enumerate(df.iterrows()):
            try:
                if idx not in results:
                    results[idx] = self.enrich_album(
                        row[artist_col], row[album_col], full_details=full_details
                    )
                    time.sleep(pause)
            except SpotifyRateLimitError:
                # Flush what we have before unwinding, so the cooldown costs
                # us nothing already paid for.
                if checkpoint_path:
                    pd.DataFrame.from_dict(results, orient="index").to_csv(checkpoint_path)
                    logger.warning("Checkpointed %d rows before stopping", len(results))
                raise

            if progress_every and (i + 1) % progress_every == 0:
                logger.info("Progress: %d / %d", i + 1, total)

            if checkpoint_path and checkpoint_every and (i + 1) % checkpoint_every == 0:
                pd.DataFrame.from_dict(results, orient="index").to_csv(checkpoint_path)

        if checkpoint_path:
            pd.DataFrame.from_dict(results, orient="index").to_csv(checkpoint_path)

        out = pd.DataFrame.from_dict(results, orient="index")
        # reindex (not .loc) so a partial run returns empty rows for the
        # indices it never reached instead of raising KeyError.
        return out.reindex(df.index)
