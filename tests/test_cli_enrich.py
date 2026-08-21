"""Guardrails for the enrich command's two input shapes.

The project has data in two column conventions: freshly scraped rows use
snake_case, the original exports use Title_Case. Getting this wrong used to
fail deep inside the Spotify client with a bare KeyError after the run had
already started making API calls. These tests pin the check to the front.
"""
import pandas as pd
import pytest

from bandcamp_aotd.cli import build_parser

LEGACY_COLUMNS = ["Date", "Album", "Artist", "Tags",
                  "Record_Label", "Record_Label_Loc", "Author"]


@pytest.fixture
def legacy_csv(tmp_path):
    path = tmp_path / "legacy.csv"
    pd.DataFrame([{
        "Date": "March 14, 2024", "Album": "Album One", "Artist": "Artist One",
        "Tags": "Jazz", "Record_Label": "Blue Note",
        "Record_Label_Loc": "Brooklyn, New York", "Author": "Jane Doe",
    }])[LEGACY_COLUMNS].to_csv(path, index=False)
    return path


class TestEnrichArguments:
    def test_legacy_and_output_flags_exist(self):
        args = build_parser().parse_args(
            ["enrich", "--input", "x.csv", "--output", "y.csv", "--legacy"]
        )
        assert args.legacy is True
        assert args.output == "y.csv"

    def test_legacy_defaults_to_false(self):
        assert build_parser().parse_args(["enrich"]).legacy is False

    def test_refresh_sets_legacy_so_it_can_delegate_to_enrich(self):
        # refresh calls cmd_enrich directly; without this default that call
        # dies with AttributeError instead of running.
        assert build_parser().parse_args(["refresh"]).legacy is False


class TestEnrichInputValidation:
    def test_legacy_csv_without_the_flag_fails_fast_with_guidance(
        self, legacy_csv, monkeypatch, caplog
    ):
        from bandcamp_aotd import cli, config

        monkeypatch.setattr(
            config, "SPOTIFY",
            config.SpotifyConfig(client_id="x", client_secret="y"),
        )
        args = build_parser().parse_args(["enrich", "--input", str(legacy_csv)])

        assert cli.cmd_enrich(args) == 1          # refused, not crashed
        assert "--legacy" in caplog.text           # and told the user why

    def test_missing_input_file_is_reported(self, tmp_path):
        from bandcamp_aotd import cli

        args = build_parser().parse_args(
            ["enrich", "--input", str(tmp_path / "nope.csv")]
        )
        assert cli.cmd_enrich(args) == 1


class TestNetworkResilience:
    """A read timeout used to kill a 40-minute enrichment run outright.

    `_request` called `session.request` with no exception handling, so a
    `requests.ReadTimeout` sailed past the per-row handler (it isn't a
    SpotifyAPIError), past the checkpoint flush, and out to the CLI.
    """

    def _client(self):
        import requests

        from bandcamp_aotd.enrich.spotify import SpotifyClient

        client = SpotifyClient.__new__(SpotifyClient)   # skip credential checks
        client._token = type("T", (), {"access_token": "tok", "expires_at": 1e12})()
        client.client_id = client.client_secret = "x"
        client.session = requests.Session()
        return client

    def test_a_transient_timeout_is_retried_not_fatal(self, monkeypatch):
        import requests

        from bandcamp_aotd.enrich import spotify

        calls = {"n": 0}

        def flaky(*args, **kwargs):
            calls["n"] += 1
            if calls["n"] == 1:
                raise requests.exceptions.ReadTimeout("read timed out")
            return type("R", (), {"status_code": 200, "json": lambda self: {"ok": True}})()

        client = self._client()
        monkeypatch.setattr(client.session, "request", flaky)
        monkeypatch.setattr(spotify.time, "sleep", lambda *a: None)

        response = client._request("GET", "/search")
        assert response.status_code == 200
        assert calls["n"] == 2                    # failed once, then succeeded

    def test_persistent_network_failure_aborts_the_run(self, monkeypatch):
        import requests

        from bandcamp_aotd.enrich import spotify

        def always_fails(*args, **kwargs):
            raise requests.exceptions.ConnectionError("network is down")

        client = self._client()
        monkeypatch.setattr(client.session, "request", always_fails)
        monkeypatch.setattr(spotify.time, "sleep", lambda *a: None)

        with pytest.raises(spotify.SpotifyNetworkError):
            client._request("GET", "/search")

    def test_run_level_aborts_are_not_swallowed_by_the_per_row_handler(self, monkeypatch):
        # The whole point of SpotifyRunAborted: enrich_album records ordinary
        # failures in the status column, but must let these through.
        from bandcamp_aotd.enrich import spotify

        client = self._client()

        def boom(*args, **kwargs):
            raise spotify.SpotifyNetworkError("down")

        monkeypatch.setattr(client, "search_album", boom)
        with pytest.raises(spotify.SpotifyNetworkError):
            client.enrich_album("Artist", "Album")

    def test_ordinary_api_errors_are_still_recorded_per_row(self, monkeypatch):
        from bandcamp_aotd.enrich import spotify

        client = self._client()

        def boom(*args, **kwargs):
            raise spotify.SpotifyAPIError("400 bad request")

        monkeypatch.setattr(client, "search_album", boom)
        result = client.enrich_album("Artist", "Album")
        assert result["spotify_match_status"].startswith("error")


class TestCallBudget:
    """Spotify's Development Mode quota is undocumented and enforced with
    ~24h cooldowns. A budget lets a run stop voluntarily with its checkpoint
    intact rather than walking into the ban every time.
    """

    def _client(self, monkeypatch):
        import requests

        from bandcamp_aotd.enrich import spotify

        client = spotify.SpotifyClient.__new__(spotify.SpotifyClient)
        client._token = type("T", (), {"access_token": "t", "expires_at": 1e12})()
        client.client_id = client.client_secret = "x"
        client.session = requests.Session()
        client.call_budget = None
        client.calls_made = 0
        monkeypatch.setattr(spotify.time, "sleep", lambda *a: None)
        return client

    def test_album_pass_stops_at_the_budget(self, monkeypatch, tmp_path):
        client = self._client(monkeypatch)
        client.call_budget = 10

        monkeypatch.setattr(
            type(client), "enrich_album",
            lambda self, a, b, full_details=False: {"spotify_match_status": "matched",
                                                    "spotify_artist_id": None},
        )
        df = pd.DataFrame({"artist": [f"A{i}" for i in range(50)],
                           "album": [f"B{i}" for i in range(50)]})

        out = client.enrich_dataframe(df, checkpoint_path=str(tmp_path / "cp.csv"))

        assert client.calls_made == 10          # stopped exactly at the budget
        assert len(out) == 50                    # unreached rows come back empty
        assert out["spotify_match_status"].notna().sum() == 10

    def test_progress_is_checkpointed_when_the_budget_runs_out(self, monkeypatch, tmp_path):
        client = self._client(monkeypatch)
        client.call_budget = 10
        checkpoint = tmp_path / "cp.csv"

        monkeypatch.setattr(
            type(client), "enrich_album",
            lambda self, a, b, full_details=False: {"spotify_match_status": "matched",
                                                    "spotify_artist_id": None},
        )
        df = pd.DataFrame({"artist": [f"A{i}" for i in range(50)],
                           "album": [f"B{i}" for i in range(50)]})
        client.enrich_dataframe(df, checkpoint_path=str(checkpoint), checkpoint_every=5)

        # A second run must resume rather than redo the paid-for work.
        resumed = self._client(monkeypatch)
        resumed.call_budget = 10
        monkeypatch.setattr(
            type(resumed), "enrich_album",
            lambda self, a, b, full_details=False: {"spotify_match_status": "matched",
                                                    "spotify_artist_id": None},
        )
        resumed.enrich_dataframe(df, checkpoint_path=str(checkpoint))
        assert resumed.calls_made == 10          # 10 more, not 10 repeats
        assert len(pd.read_csv(checkpoint, index_col=0)) == 20

    def test_no_budget_means_unlimited(self, monkeypatch):
        client = self._client(monkeypatch)
        assert client.budget_exhausted is False
        client.calls_made = 10_000
        assert client.budget_exhausted is False
