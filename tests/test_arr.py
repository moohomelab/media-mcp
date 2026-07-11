import httpx

from media_mcp.arr import ArrClient

RADARR_QUEUE = {
    "records": [
        {
            "title": "Dune.Part.Two.2024.2160p.x265-GRP",
            "movie": {"title": "Dune: Part Two"},
            "size": 1000.0,
            "sizeleft": 250.0,
            "timeleft": "00:25:00",
            "status": "downloading",
            "trackedDownloadState": "downloading",
            "statusMessages": [],
        },
        {
            "title": "Stalled.Movie.1080p",
            "movie": {"title": "Stalled Movie"},
            "size": 500.0,
            "sizeleft": 500.0,
            "timeleft": None,
            "status": "queued",
            "trackedDownloadState": "downloading",
            "statusMessages": [{"title": "x", "messages": ["The download is stalled with no connections"]}],
            "errorMessage": "",
        },
    ]
}

SONARR_QUEUE = {
    "records": [
        {
            "title": "Severance.S02E05.1080p",
            "series": {"title": "Severance"},
            "episode": {"seasonNumber": 2, "episodeNumber": 5},
            "size": 100.0,
            "sizeleft": 0.0,
            "timeleft": None,
            "status": "completed",
            "trackedDownloadState": "importBlocked",
            "statusMessages": [],
            "errorMessage": "Import blocked: no matching series path",
        }
    ]
}


def make(name: str, payload: dict) -> ArrClient:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["X-Api-Key"] == "k"
        assert request.url.path == "/api/v3/queue"
        return httpx.Response(200, json=payload)

    return ArrClient(name, "http://arr.test", "k", transport=httpx.MockTransport(handler))


async def test_radarr_queue_maps_to_movie_language():
    items = await make("radarr", RADARR_QUEUE).queue()
    assert items[0]["title"] == "Dune: Part Two"
    assert items[0]["percent"] == 75.0
    assert items[0]["time_left"] == "00:25:00"
    assert items[0]["problems"] == []
    assert items[1]["percent"] == 0.0
    assert "stalled" in items[1]["problems"][0].lower()


async def test_sonarr_queue_maps_to_episode_language_and_error():
    items = await make("sonarr", SONARR_QUEUE).queue()
    assert items[0]["title"] == "Severance S02E05"
    assert items[0]["status"] == "completed"
    assert "Import blocked" in items[0]["problems"][0]


async def test_backend_down_returns_error_marker_not_raise():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("boom")

    items = await ArrClient("radarr", "http://arr.test", "k", transport=httpx.MockTransport(handler)).queue()
    assert items == [{"title": "radarr unreachable", "percent": 0.0, "time_left": None, "status": "error", "problems": ["radarr did not respond"]}]
