"""
MCP server: search_code — semantic search over your Qdrant code_snippets collection.
Registered in ~/.claude/settings.json as "code-search" MCP server.
"""

import asyncio
import os
import re
from pathlib import Path

import voyageai
from dotenv import load_dotenv
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool
from qdrant_client import QdrantClient
from qdrant_client.http.models import Prefetch, FusionQuery, Fusion, SparseVector

load_dotenv(Path.home() / ".claude" / ".env")

COLLECTION  = "code_snippets"
EMBED_MODEL = "voyage-code-2"
DENSE_NAME  = "dense"
SPARSE_NAME = "sparse"
SPARSE_DIM  = 65536
_TOKEN_RE   = re.compile(r"[a-zA-Z_][a-zA-Z0-9_]+")

voyage = voyageai.Client(api_key=os.environ["VOYAGE_API_KEY"])
qdrant = QdrantClient(url=os.environ["QDRANT_URL"], api_key=os.environ["QDRANT_API_KEY"])

app = Server("code-search")


def make_sparse(text: str) -> SparseVector:
    from collections import Counter
    tokens = _TOKEN_RE.findall(text.lower())
    if not tokens:
        return SparseVector(indices=[0], values=[0.0])
    counts = Counter(tokens)
    total = sum(counts.values())
    idx_map: dict[int, float] = {}
    for token, count in counts.items():
        idx = abs(hash(token)) % SPARSE_DIM
        idx_map[idx] = idx_map.get(idx, 0.0) + count / total
    indices = list(idx_map.keys())
    return SparseVector(indices=indices, values=[idx_map[i] for i in indices])


def do_search(query: str, limit: int = 5) -> str:
    dense = voyage.embed([query], model=EMBED_MODEL, input_type="query").embeddings[0]
    sparse = make_sparse(query)

    results = qdrant.query_points(
        collection_name=COLLECTION,
        prefetch=[
            Prefetch(query=dense,  using=DENSE_NAME,  limit=limit * 2),
            Prefetch(query=sparse, using=SPARSE_NAME, limit=limit * 2),
        ],
        query=FusionQuery(fusion=Fusion.RRF),
        limit=limit,
        with_payload=True,
    )

    if not results.points:
        return "No results found."

    lines = []
    for i, hit in enumerate(results.points, 1):
        p = hit.payload
        lines.append(f"### {i}. [{p['project']}] {p['filepath']} (chunk {p['chunk']}) — {p['language']}")
        lines.append(f"```{p['language']}")
        lines.append(p["code"][:800])
        lines.append("```")
        lines.append("")
    return "\n".join(lines)


@app.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="search_code",
            description=(
                "Search your codebase by semantic meaning. Returns matching code snippets "
                "from your indexed projects (mnemora, Fallout-Shelter-Auto-Manager-PRO, "
                "swing_strategy_backtest). Use this to find existing implementations before writing new code."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "What you're looking for, e.g. 'jwt token refresh', 'database connection setup', 'file upload handler'",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Number of results to return (default: 5, max: 20)",
                        "default": 5,
                    },
                },
                "required": ["query"],
            },
        )
    ]


@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    if name == "search_code":
        query = arguments["query"]
        limit = min(int(arguments.get("limit", 5)), 20)
        result = await asyncio.get_event_loop().run_in_executor(None, do_search, query, limit)
        return [TextContent(type="text", text=result)]
    raise ValueError(f"Unknown tool: {name}")


async def main():
    async with stdio_server() as (read, write):
        await app.run(read, write, app.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())
