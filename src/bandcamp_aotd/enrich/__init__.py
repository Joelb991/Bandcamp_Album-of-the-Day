"""Enrichment: third-party catalog metadata layered onto the Bandcamp data."""
from .spotify import (
    SpotifyAPIError,
    SpotifyAuthError,
    SpotifyClient,
    SpotifyNetworkError,
    SpotifyRateLimitError,
    SpotifyRunAborted,
)

__all__ = [
    "SpotifyClient",
    "SpotifyAPIError",
    "SpotifyAuthError",
    "SpotifyRunAborted",
    "SpotifyRateLimitError",
    "SpotifyNetworkError",
]
