# Plan: Set Up Qdrant + Activate MCP Server

## Current State
- `~/.claude/.env` has `QDRANT_URL=http://localhost:6333` and `QDRANT_API_KEY=YOUR_QDRANT_API_KEY_HERE`
- `settings.json` has qdrant MCP server configured and pointing to those env vars
- Docker is available (Docker MCP server is configured)

## Approach: Local Qdrant via Docker
Simplest path — no cloud account needed, free, works immediately with existing Docker setup.

## Steps

### 1. Start Qdrant container
```bash
docker run -d --name qdrant -p 6333:6333 -p 6334:6334 \
  -v qdrant_storage:/qdrant/storage \
  qdrant/qdrant
```
- Port 6333 = REST API (matches existing `QDRANT_URL` in .env)
- Port 6334 = gRPC
- Named volume `qdrant_storage` persists data across restarts

### 2. Set API key in ~/.claude/.env
Local Qdrant has no auth by default — set a dummy key or leave blank:
```
QDRANT_API_KEY=local
```
(The MCP server requires a value; "local" works fine for an unauthenticated instance)

### 3. Make container auto-start
```bash
docker update --restart unless-stopped qdrant
```

### 4. Restart Claude Code
Both shells already source `~/.claude/.env` on startup — the MCP server will pick up the new value automatically on next Claude Code launch.

## Files Modified
- `C:\Users\Matt1\.claude\.env` — change `QDRANT_API_KEY=YOUR_QDRANT_API_KEY_HERE` → `QDRANT_API_KEY=local`

## No changes to settings.json needed
`QDRANT_URL` is already `http://localhost:6333` — correct for this setup.

## Verification
```bash
curl http://localhost:6333/healthz
```
Should return `{"title":"qdrant - vector search engine","version":"..."}` confirming Qdrant is running and reachable.
