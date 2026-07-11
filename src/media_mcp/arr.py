"""Read-only queue client for Radarr and Sonarr (v3 API).

The ONLY endpoint used is GET /api/v3/queue — this module contains no writes
and must never grow one; download/library mutations are out of scope for
media-mcp by design. One unreachable *arr degrades to an inline error record
so the merged queue tool still answers for the healthy backend.
"""

import logging
import os

import httpx

logger = logging.getLogger(__name__)


class ArrClient:
    def __init__(
        self,
        name: str,
        base_url: str,
        api_key: str,
        timeout: float = 15.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ):
        self.name = name  # "radarr" | "sonarr" — also selects title shaping
        self._http = httpx.AsyncClient(
            base_url=base_url.rstrip("/"),
            headers={"X-Api-Key": api_key},
            timeout=timeout,
            transport=transport,
        )

    def _title(self, rec: dict) -> str:
        if self.name == "sonarr":
            series = (rec.get("series") or {}).get("title", "?")
            ep = rec.get("episode") or {}
            return f"{series} S{ep.get('seasonNumber', 0):02d}E{ep.get('episodeNumber', 0):02d}"
        return (rec.get("movie") or {}).get("title") or rec.get("title", "?")

    @staticmethod
    def _problems(rec: dict) -> list[str]:
        msgs = [m for sm in rec.get("statusMessages", []) for m in sm.get("messages", [])]
        if rec.get("errorMessage"):
            msgs.append(rec["errorMessage"])
        return msgs

    async def queue(self) -> list[dict]:
        params = {"page": 1, "pageSize": 50}
        # includeMovie / includeSeries+includeEpisode make the queue records
        # carry human titles instead of bare ids.
        params |= {"includeSeries": "true", "includeEpisode": "true"} if self.name == "sonarr" else {"includeMovie": "true"}
        try:
            r = await self._http.get("/api/v3/queue", params=params)
            r.raise_for_status()
            records = r.json().get("records", [])
        except Exception:
            logger.exception("%s queue fetch failed", self.name)
            return [{"title": f"{self.name} unreachable", "percent": 0.0, "time_left": None,
                     "status": "error", "problems": [f"{self.name} did not respond"]}]
        items = []
        for rec in records:
            size, left = rec.get("size") or 0, rec.get("sizeleft") or 0
            items.append({
                "title": self._title(rec),
                "percent": round(100 * (1 - left / size), 1) if size else 0.0,
                "time_left": rec.get("timeleft"),
                "status": rec.get("status", "unknown"),
                "problems": self._problems(rec),
            })
        return items


def radarr_from_env() -> ArrClient:
    return ArrClient("radarr", os.environ["RADARR_URL"], os.environ["RADARR_API_KEY"])


def sonarr_from_env() -> ArrClient:
    return ArrClient("sonarr", os.environ["SONARR_URL"], os.environ["SONARR_API_KEY"])
