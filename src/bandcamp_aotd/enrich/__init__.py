"""Enrichment: third-party catalog metadata layered onto the Bandcamp data."""
from .spotify import (
    SpotifyAPIError,
    SpotifyAuthError,
    SpotifyClient,
    SpotifyRateLimitError,
)

__all__ = [
    "SpotifyClient",
    "SpotifyAPIError",
    "SpotifyAuthError",
    "SpotifyRateLimitError",
]
