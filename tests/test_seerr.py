import httpx
import pytest

from media_mcp.seerr import SeerrClient, SeerrError


def make_client(handler) -> SeerrClient:
    return SeerrClient(
        base_url="http://seerr.test:5055",
        api_key="k",
        transport=httpx.MockTransport(handler),
    )


async def test_get_sends_api_key_and_returns_json():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["X-Api-Key"] == "k"
        assert request.url.path == "/api/v1/search"
        assert request.url.params["query"] == "dune"
        return httpx.Response(200, json={"results": []})

    client = make_client(handler)
    assert await client.get("/search", query="dune") == {"results": []}


async def test_post_sends_json_body():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert b'"mediaId": 693134' in request.content or b'"mediaId":693134' in request.content
        return httpx.Response(201, json={"id": 1, "status": 2})

    client = make_client(handler)
    assert (await client.post("/request", {"mediaType": "movie", "mediaId": 693134}))["status"] == 2


async def test_http_error_raises_seerr_error_with_backend_message():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(409, json={"message": "Request for this media already exists"})

    client = make_client(handler)
    with pytest.raises(SeerrError) as err:
        await client.post("/request", {"mediaType": "movie", "mediaId": 1})
    assert err.value.status == 409
    assert "already exists" in str(err.value)
