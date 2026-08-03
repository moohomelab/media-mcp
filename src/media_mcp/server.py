"""Media request MCP server (Hollywood's tool plane).

Seven tools. The ONLY mutations are request_movie/request_tv (creating a
Seerr request — the product's purpose). Deletes, config writes, quality/
indexer management are NOT implemented anywhere in this package; that
absence is the security boundary (synology-mcp precedent).
"""

import json
import logging

from dotenv import load_dotenv
from mcp.server import MCPServer

from .arr import ArrClient, radarr_from_env, sonarr_from_env
from .seerr import SeerrClient, SeerrError

load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

mcp = MCPServer("media-mcp")

_seerr: SeerrClient | None = None
_radarr: ArrClient | None = None
_sonarr: ArrClient | None = None

# Overseerr/Seerr media status enum -> plain words a chat model can relay.
MEDIA_STATUS = {1: "not in library", 2: "pending approval", 3: "downloading",
                4: "partially available", 5: "available"}
REQUEST_STATUS = {1: "pending approval", 2: "approved", 3: "declined"}
DISCOVER_PATHS = {"trending": "/discover/trending", "popular": "/discover/movies",
                  "upcoming": "/discover/movies/upcoming"}


def get_seerr() -> SeerrClient:
    global _seerr
    if _seerr is None:
        _seerr = SeerrClient.from_env()
    return _seerr


def get_radarr() -> ArrClient:
    global _radarr
    if _radarr is None:
        _radarr = radarr_from_env()
    return _radarr


def get_sonarr() -> ArrClient:
    global _sonarr
    if _sonarr is None:
        _sonarr = sonarr_from_env()
    return _sonarr


def _shape_result(r: dict) -> dict:
    date = r.get("releaseDate") or r.get("firstAirDate") or ""
    status_code = (r.get("mediaInfo") or {}).get("status", 1)
    return {
        "title": r.get("title") or r.get("name") or "?",
        "year": date[:4],
        "type": r["mediaType"],
        "tmdb_id": r["id"],
        "status": MEDIA_STATUS.get(status_code, "not in library"),
    }


@mcp.tool()
async def search_media(query: str) -> str:
    """Search movies and TV shows by name. Returns title, year, type
    (movie/tv), tmdb_id (needed to request), and library status."""
    try:
        data = await get_seerr().get("/search", query=query, page=1)
        results = [_shape_result(r) for r in data.get("results", [])
                   if r.get("mediaType") in ("movie", "tv")][:10]
        return json.dumps(results, indent=2)
    except SeerrError as err:
        return f"Error: {err}"
    except Exception as err:
        logger.exception("search failed")
        return f"Error: Seerr unreachable: {err}"


@mcp.tool()
async def request_movie(tmdb_id: int) -> str:
    """Request a movie for download by its tmdb_id (from search_media).
    Only call this when the user explicitly asked to download it."""
    try:
        data = await get_seerr().post("/request", {"mediaType": "movie", "mediaId": tmdb_id})
        return f"Requested. Status: {REQUEST_STATUS.get(data.get('status'), 'submitted')}."
    except SeerrError as err:
        return f"Error: {err}"
    except Exception as err:
        logger.exception("request_movie failed")
        return f"Error: Seerr unreachable: {err}"


@mcp.tool()
async def request_tv(tmdb_id: int, seasons: str = "all") -> str:
    """Request a TV show by tmdb_id. seasons is "all" or a comma-separated
    list like "1,2". Only call when the user explicitly asked to download."""
    try:
        wanted = "all" if seasons.strip().lower() == "all" else [int(s) for s in seasons.split(",")]
    except ValueError:
        return f'Error: seasons must be "all" or like "1,2", got {seasons!r}'
    try:
        data = await get_seerr().post("/request", {"mediaType": "tv", "mediaId": tmdb_id, "seasons": wanted})
        return f"Requested. Status: {REQUEST_STATUS.get(data.get('status'), 'submitted')}."
    except SeerrError as err:
        return f"Error: {err}"
    except Exception as err:
        logger.exception("request_tv failed")
        return f"Error: Seerr unreachable: {err}"


@mcp.tool()
async def list_requests() -> str:
    """Recent download requests with their approval and availability status."""
    try:
        data = await get_seerr().get("/request", take=20, sort="added")
        items = []
        for req in data.get("results", []):
            media = req.get("media") or {}
            items.append({
                "title": media.get("title") or media.get("name") or f"tmdb:{media.get('tmdbId')}",
                "type": media.get("mediaType"),
                "requested": REQUEST_STATUS.get(req.get("status"), "unknown"),
                "availability": MEDIA_STATUS.get(media.get("status"), "unknown"),
            })
        return json.dumps(items, indent=2)
    except SeerrError as err:
        return f"Error: {err}"
    except Exception as err:
        logger.exception("list_requests failed")
        return f"Error: Seerr unreachable: {err}"


@mcp.tool()
async def discover_media(kind: str = "trending") -> str:
    """What's hot: kind is "trending", "popular", or "upcoming"."""
    path = DISCOVER_PATHS.get(kind.strip().lower())
    if not path:
        return f"Error: kind must be one of {sorted(DISCOVER_PATHS)}, got {kind!r}"
    try:
        data = await get_seerr().get(path, page=1)
        results = [_shape_result(r) for r in data.get("results", [])
                   if r.get("mediaType") in ("movie", "tv")][:10]
        return json.dumps(results, indent=2)
    except SeerrError as err:
        return f"Error: {err}"
    except Exception as err:
        logger.exception("discover failed")
        return f"Error: Seerr unreachable: {err}"


@mcp.tool()
async def get_download_queue() -> str:
    """Everything currently downloading (movies and TV): percent done,
    time left, and any problems (stalled, import blocked, errors)."""
    try:
        items = await get_radarr().queue() + await get_sonarr().queue()
    except Exception as err:
        logger.exception("queue fetch failed")
        return f"Error: download queue unavailable: {err}"
    return json.dumps(items, indent=2) if items else "The download queue is empty."


@mcp.tool()
async def get_media_status(tmdb_id: int, media_type: str) -> str:
    """Is one title available yet? media_type is "movie" or "tv"."""
    if media_type not in ("movie", "tv"):
        return f'Error: media_type must be "movie" or "tv", got {media_type!r}'
    try:
        data = await get_seerr().get(f"/{media_type}/{tmdb_id}")
        status = MEDIA_STATUS.get((data.get("mediaInfo") or {}).get("status", 1), "not in library")
        title = data.get("title") or data.get("name") or f"tmdb:{tmdb_id}"
        return f"{title}: {status}"
    except SeerrError as err:
        return f"Error: {err}"
    except Exception as err:
        logger.exception("get_media_status failed")
        return f"Error: Seerr unreachable: {err}"


def main() -> None:
    # v2 moved transport params from the constructor to run()
    mcp.run(transport="streamable-http", host="0.0.0.0", port=8000)


if __name__ == "__main__":
    main()
