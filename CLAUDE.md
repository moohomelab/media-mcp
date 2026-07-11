# media-mcp

MCP server for media requests (the Hollywood assistant's tool plane): search/request/discover via Seerr, read-only download queue via Radarr/Sonarr.

- **Contract:** exactly 7 tools — `search_media`, `request_movie`, `request_tv`, `list_requests`, `discover_media`, `get_download_queue`, `get_media_status`. The only mutation is Seerr `POST /request`; no other mutating endpoint may ever be added.
- Tests: `uv run pytest`
- Deploy: moolab `homelab/openshift-cluster/apps/ai-platform/media-mcp/` (image auto-built to ghcr.io on push to main).
