# Plan: Code Snippets Auto-Ingest Script

## Context
Matt has a Qdrant cloud instance (us-west-2) with a freshly created `code_snippets` collection
configured for hybrid search (dense 1536-dim Cosine + sparse BM25 with IDF). He has multiple
active projects (Python, TypeScript/React, Node.js) with no existing embedding pipeline.
Goal: a single Python script that walks his project directories, embeds each code file, and
upserts it into Qdrant so the collection is immediately searchable.

## Prerequisites (user must add to ~/.claude/.env)
- `OPENAI_API_KEY` — needed for text-embedding-3-small (1536 dims, matches collection)
- `QDRANT_URL` and `QDRANT_API_KEY` — already set

## Output File
`C:\Users\Matt1\ingest_code.py`

## Dependencies to install
```
pip install qdrant-client openai python-dotenv
```

## Script Design

### Config (top of file, easy to edit)
```python
PROJECTS_ROOT = r"C:\Users\Matt1"
PROJECT_DIRS  = ["mnemora", "Fallout-Shelter-Auto-Manager-PRO", "swing_strategy_backtest"]
EXTENSIONS    = {".py", ".ts", ".tsx", ".js", ".jsx", ".md"}
CHUNK_LINES   = 100          # files larger than this get split
OVERLAP_LINES = 10           # overlap between chunks
COLLECTION    = "code_snippets"
EMBED_MODEL   = "text-embedding-3-small"  # 1536 dims
BATCH_SIZE    = 50           # upsert batch size
```

### Flow
1. **Walk** each project dir, collect files matching EXTENSIONS (skip node_modules, .git, __pycache__, venv, dist, build)
2. **Chunk** each file:
   - Files ≤ CHUNK_LINES → one chunk (whole file)
   - Files > CHUNK_LINES → sliding window chunks with OVERLAP_LINES overlap
3. **Embed** chunks in batches via OpenAI `text-embedding-3-small`
4. **Sparse vector** computed client-side using qdrant-client's built-in BM25 tokenizer
   (`qdrant_client.http.models.SparseVector` with term frequencies)
5. **Upsert** to Qdrant in batches of BATCH_SIZE

### Payload per point
```json
{
  "project":   "mnemora",
  "language":  "python",
  "filepath":  "backend/app/services/card_generator.py",
  "filename":  "card_generator.py",
  "chunk":     0,
  "code":      "<raw source text>",
  "tags":      ["python", "fastapi"]
}
```

### Point ID
`uuid5(namespace, filepath + ":" + str(chunk_index))` — deterministic, so re-running updates existing points rather than duplicating.

## Usage after creation
```bash
# first run — indexes everything
PYTHONIOENCODING=utf-8 python ingest_code.py

# re-run any time to update (upsert is idempotent)
PYTHONIOENCODING=utf-8 python ingest_code.py --project mnemora
```

## Verification
1. Run script, confirm "Upserted N points" output with no errors
2. Check Qdrant dashboard → code_snippets → points count > 0
3. Run a quick search via curl:
```bash
source ~/.claude/.env
curl -s -X POST "$QDRANT_URL/collections/code_snippets/points/query" \
  -H "api-key: $QDRANT_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"query": [0.1, 0.2, ...], "limit": 3}'
```
Or add a `--search "your query"` flag to the script for a quick test.
