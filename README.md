# media-mcp

Media request MCP server for searching and requesting movies and TV shows. Provides 7 tools to query media, check request status, and submit new requests through Seerr (Overseerr-compatible), with Radarr/Sonarr integration for status tracking. All operations are read-only or request-only; deletions are not supported by design. API credentials are configured server-side via environment variables.

Deployed in moolab at `apps/ai-platform/media-mcp/` via GitOps.
