import json

import pytest

from media_mcp import server
from media_mcp.seerr import SeerrError


class FakeSeerr:
    def __init__(self, get_data=None, post_data=None, post_exc=None):
        self.get_data, self.post_data, self.post_exc = get_data, post_data, post_exc
        self.calls = []

    async def get(self, path, **params):
        self.calls.append(("GET", path, params))
        return self.get_data

    async def post(self, path, payload):
        self.calls.append(("POST", path, payload))
        if self.post_exc:
            raise self.post_exc
        return self.post_data


class FakeArr:
    def __init__(self, items):
        self._items = items

    async def queue(self):
        return self._items


@pytest.fixture(autouse=True)
def reset_clients():
    server._seerr = server._radarr = server._sonarr = None
    yield
    server._seerr = server._radarr = server._sonarr = None


async def test_search_media_returns_compact_results():
    server._seerr = FakeSeerr(get_data={"results": [
        {"mediaType": "movie", "id": 693134, "title": "Dune: Part Two",
         "releaseDate": "2024-02-27", "mediaInfo": {"status": 5}},
        {"mediaType": "person", "id": 1, "name": "Denis Villeneuve"},
    ]})
    out = json.loads(await server.search_media("dune"))
    assert out == [{"title": "Dune: Part Two", "year": "2024", "type": "movie",
                    "tmdb_id": 693134, "status": "available"}]


async def test_request_movie_posts_and_confirms():
    server._seerr = FakeSeerr(post_data={"id": 42, "status": 2})
    out = await server.request_movie(693134)
    assert "approved" in out
    assert server._seerr.calls == [("POST", "/request", {"mediaType": "movie", "mediaId": 693134})]


async def test_request_tv_parses_seasons_string():
    server._seerr = FakeSeerr(post_data={"id": 43, "status": 1})
    await server.request_tv(95396, seasons="1,2")
    assert server._seerr.calls[0][2] == {"mediaType": "tv", "mediaId": 95396, "seasons": [1, 2]}


async def test_request_duplicate_surfaces_backend_message():
    server._seerr = FakeSeerr(post_exc=SeerrError(409, "Request for this media already exists"))
    out = await server.request_movie(693134)
    assert out.startswith("Error:") and "already exists" in out


async def test_get_download_queue_merges_both_arrs():
    server._radarr = FakeArr([{"title": "Dune: Part Two", "percent": 75.0,
                               "time_left": "00:25:00", "status": "downloading", "problems": []}])
    server._sonarr = FakeArr([{"title": "Severance S02E05", "percent": 0.0,
                               "time_left": None, "status": "queued",
                               "problems": ["stalled with no connections"]}])
    out = json.loads(await server.get_download_queue())
    assert [i["title"] for i in out] == ["Dune: Part Two", "Severance S02E05"]


async def test_get_download_queue_missing_config_returns_error_string():
    out = await server.get_download_queue()
    assert out.startswith("Error:")


async def test_discover_media_rejects_unknown_kind():
    out = await server.discover_media("horror")
    assert out.startswith("Error:")


async def test_get_media_status_maps_enum():
    server._seerr = FakeSeerr(get_data={"mediaInfo": {"status": 3}, "title": "Dune: Part Two"})
    out = await server.get_media_status(693134, "movie")
    assert "downloading" in out
