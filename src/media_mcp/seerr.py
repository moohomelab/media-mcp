"""Async client for the Seerr (Overseerr-compatible) v1 API.

Owns the base URL, the X-Api-Key header, and error shaping. The ONLY write
this client is ever used for is POST /request (creating a media request);
the server layer contains no other mutating calls by design.
"""

import os
from urllib.parse import quote, urlencode

import httpx

_API = "/api/v1"


class SeerrError(Exception):
    """Seerr returned a non-2xx; carries the backend's own message."""

    def __init__(self, status: int, detail: str):
        self.status = status
        super().__init__(f"Seerr error {status}: {detail}")


class SeerrClient:
    def __init__(
        self,
        base_url: str,
        api_key: str,
        timeout: float = 15.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ):
        self._http = httpx.AsyncClient(
            base_url=f"{base_url.rstrip('/')}{_API}",
            headers={"X-Api-Key": api_key},
            timeout=timeout,
            transport=transport,
        )

    @classmethod
    def from_env(cls) -> "SeerrClient":
        return cls(base_url=os.environ["SEERR_URL"], api_key=os.environ["SEERR_API_KEY"])

    @staticmethod
    def _check(r: httpx.Response) -> dict:
        if r.is_success:
            return r.json()
        try:
            detail = r.json().get("message", r.text[:200])
        except Exception:
            detail = r.text[:200]
        raise SeerrError(r.status_code, detail)

    async def get(self, path: str, **params) -> dict:
        # Seerr's /search rejects '+'-encoded spaces (400 "must be url encoded");
        # it only accepts %20. httpx defaults to quote_plus for query params, so
        # encode the query string ourselves with quote (space -> %20).
        qs = urlencode(params, quote_via=quote)
        return self._check(await self._http.get(f"{path}?{qs}" if qs else path))

    async def post(self, path: str, payload: dict) -> dict:
        return self._check(await self._http.post(path, json=payload))
