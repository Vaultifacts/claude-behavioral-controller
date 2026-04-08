# Quality Gate Measurement System — Exhaustive Audit & Gap Analysis

**Date**: 2026-04-07
**Scope**: Data inventory, dashboard coverage, and gap analysis across all QG layers

---

## A. SYSTEM DATA INVENTORY

### A.1 Log File Data (Local)
**File**: `~/.claude/quality-gate.log`
**Format**: Pipe-delimited, one entry per line
**Entry structure** (line 158 in quality-gate.py):
```
YYYY-MM-DD HH:MM:SS | DECISION | COMPLEXITY | REASON[:80] | tools=TOOL,NAMES | req=USER_REQUEST[:60] | hash=RESPONSE_HASH[:8]
```

**Example** (from tail output):
```
2026-04-07 19:36:12 | BLOCK | subagent:general-purpose | Subagent ran Bash but it doesn't look like a real test. | hash=c5722191
```

**Fields logged**:
| Field | Source | Example | Truncation |
|-------|--------|---------|------------|
| `timestamp` | `datetime.now()` | `2026-04-07 19:15:28` | None |
| `decision` | log_decision() arg | PASS, BLOCK, DEGRADED-PASS | None |
| `complexity` | get_last_complexity() | SIMPLE, MODERATE | Left-padded to 8 chars |
| `reason` | category or LLM reason | "MECHANICAL: Code was edited..." | First 80 chars |
| `tools` | tool_names (first 5 items) | `Bash,Bash,Agent` | Comma-delimited, max 5 items |
| `user_request` | get_user_request() | "Add a countdown timer..." | First 60 chars, newlines stripped |
| `hash` | _response_hash(response)[:8] | `c5722191` | First 8 hex chars, or `--------` if null |

**Additional logged entries**:
- `TRANSCRIPT` entries (lines 919-931): diagnostic logs when transcript path non-empty but tools=0
- `OVERRIDE` entries: written via write_override() in _detect_override() — format not in main logs, stored in separate JSONL

### A.2 Override/Feedback Data (Local)
**File 1**: `~/.claude/quality-gate-overrides.jsonl`
**Purpose**: Track BLOCK→PASS cycles (false positive indicators)
**Record structure** (inferred from _detect_override & write_override):
```json
{
  "ts": "2026-04-07T19:36:12",
  "response_hash": "c5722191",
  "user_request": "The countdown timer and last updated...",
  "block_reason": "Code was edited but no syntax check or test was run...",
  "auto_verdict": "likely_fp or likely_tp"
}
```

**File 2**: `~/.claude/quality-gate-feedback.jsonl`
**Purpose**: User-provided feedback (manual TP/FP/MISS labels)
**Record structure** (from qg-feedback.py lines 102-109):
```json
{
  "ts": "2026-04-07T19:36:12",
  "type": "fp|tp|miss",
  "override_ts": "...",
  "user_request": "...",
  "block_reason": "...",
  "auto_verdict": "...",
  "hash": "...",
  "notes": "..."
}
```

### A.3 Supabase Cloud Data
**Database**: `qkuswxdvidajrqqizwdr.supabase.co`

#### evidence table
**Columns** (from schema lines 7-18):
| Column | Type | Constraints | Source |
|--------|------|-------------|--------|
| `id` | uuid | PK, auto-generated | System |
| `created_at` | timestamptz | default now() | System |
| `session_id` | text | NOT NULL | CLAUDE_SESSION_ID env var (line 43) |
| `block_type` | text | NOT NULL | MECHANICAL / LLM (line 46) |
| `reason` | text | NOT NULL | block reason, first 500 chars (line 47) |
| `response_text` | text | nullable | response text, first 3000 chars (line 48) |
| `tool_names` | jsonb | nullable | JSON array of tool names (line 49) |
| `edited_paths` | jsonb | nullable | JSON array of file paths (line 50) |
| `bash_commands` | jsonb | nullable | JSON array of bash commands (line 51) |
| `user_request` | text | nullable | user request, first 500 chars (line 52) |
| `env_info` | jsonb | nullable | **NOT POPULATED** (see A.5 below) |

**RLS**: anon can INSERT only (no SELECT/UPDATE/DELETE)

#### labels table
**Columns** (from schema lines 29-37):
| Column | Type | Constraints | Source |
|--------|------|-------------|--------|
| `id` | uuid | PK, auto-generated | System |
| `created_at` | timestamptz | default now() | System |
| `evidence_id` | uuid | FK → evidence(id) | Edge function |
| `verdict` | text | NOT NULL, CHECK IN ('TP','FP','SKIP','SPLIT') | 3-model ensemble (Edge function) |
| `method` | text | default 'ENSEMBLE' | Edge function |
| `model_verdicts` | jsonb | nullable | 3 model outputs (Gemini/OpenAI/Grok) |
| `confidence` | float | nullable | majority vote confidence (0.33–1.0) |
| `notes` | text | nullable | error messages or context |

**RLS**: zero anon access (service_role_key only for Edge Function)

#### RPC Functions
| Name | Signature | Behavior | Anon Access |
|------|-----------|----------|------------|
| `get_qg_stats()` | `() → json` | Returns aggregate counts (tp_count, fp_count, skip_count, split_count, evidence_total, labeled_total) | YES — SECURITY DEFINER |
| `get_qg_dashboard` | **(NOT DEFINED IN SCHEMA)** | Called by dashboard but RPC doesn't exist | **BROKEN** |

---

## B. DASHBOARD CURRENT COVERAGE

**File**: `~/.claude/scripts/qg-dashboard.html`
**Load target**: RPC call to `get_qg_dashboard` (line 597)

### B.1 Metrics Shown (Top Cards)
| Card | Source | Calculation | Current Status |
|------|--------|-------------|-----------------|
| **Precision** | `get_qg_stats()` → `tp_count`, `fp_count` | `tp / (tp + fp) * 100%` | Working (lines 610–612) |
| **True Positives (TP)** | `get_qg_stats()` → `tp_count` | Direct count | Working |
| **False Positives (FP)** | `get_qg_stats()` → `fp_count` | Direct count | Working |
| **Skip / Split** | `get_qg_stats()` → `skip_count`, `split_count` | Sum | Working |
| **Evidence Captured** | `get_qg_stats()` → `evidence_total` | Count of rows in evidence table | Working |
| **Labels Written** | `get_qg_stats()` → `labeled_total` | Count of rows in labels table | Working |

### B.2 Audit Bar
**Text** (lines 468–475): "Evidence capture audit: N evidence rows → N labels (all labeled)" or "(N pending)"
**Status**: Working (uses stats from RPC)

### B.3 Recent Verdicts Table
**Columns shown** (lines 201–204):
| Column | Source Field | Data Type | Visible |
|--------|--------------|-----------|---------|
| Time | `created_at` | ISO timestamp | Yes (formatted to "Mar 7, 19:36") |
| Block Type | `block_type` | text | Yes |
| Reason / Request | `reason` + `user_request` | text (truncated to 90+70 chars) | Yes |
| Verdict | `verdict` | badge (TP/FP/SKIP/SPLIT) | Yes |
| Model dots | `gemini_verdict`, `openai_verdict`, `grok_verdict` | 3 dots | Yes |
| Confidence | `confidence` | percentage | Yes |

### B.4 Filter Bar
**Filters available** (lines 182–197):
- Verdict: All, TP, FP, SKIP, SPLIT
- Block Type: All, Mechanical, LLM

### B.5 Modal Detail View
**Shown when row clicked** (lines 297–447):
- Full reason text
- Full user request
- Response snippet
- Model verdicts (Gemini, OpenAI, Grok) with reasons + errors
- Feedback section (localStorage-based, not cloud-synced)

**Data from each row** (lines 364–367):
```json
{
  "gemini_verdict": "TP|FP|SKIP|null",
  "gemini_reason": "string",
  "gemini_error": "string|null",
  "openai_verdict": "...",
  "openai_reason": "...",
  "openai_error": "...",
  "grok_verdict": "...",
  "grok_reason": "...",
  "grok_error": "..."
}
```

---

## C. CRITICAL GAP: `get_qg_dashboard` RPC MISSING

**Status**: 🔴 **BROKEN**

The dashboard calls:
```javascript
fetch(SUPABASE_URL + '/rest/v1/rpc/get_qg_dashboard', {
  body: JSON.stringify({ p_limit: 50 })
})
```

**What the dashboard expects** (inferred from JS code lines 607–621):
```json
{
  "stats": {
    "tp_count": number,
    "fp_count": number,
    "skip_count": number,
    "split_count": number,
    "evidence_total": number,
    "labeled_total": number
  },
  "recent": [
    {
      "id": uuid,
      "created_at": ISO string,
      "block_type": text,
      "reason": text,
      "user_request": text,
      "response_snippet": text,
      "verdict": "TP|FP|SKIP|SPLIT",
      "confidence": float,
      "gemini_verdict": "TP|FP|SKIP|null",
      "gemini_reason": text,
      "gemini_error": text|null,
      "openai_verdict": "...",
      "openai_reason": "...",
      "openai_error": "...",
      "grok_verdict": "...",
      "grok_reason": "...",
      "grok_error": "..."
    }
  ]
}
```

**What actually exists**: Only `get_qg_stats()` which returns counts only.

**Result**: Dashboard loads, shows error bar, and displays no recent verdicts.

---

## D. DATA SOURCES NOT FLOWING TO DASHBOARD

### D.1 Local Log Data (Never Synced)
| Data | Location | Why Missing | Type |
|------|----------|------------|------|
| Complexity level (SIMPLE/MODERATE/etc.) | `quality-gate.log` column 3 | Not in evidence table, not in RPC | LOCAL |
| Decision details | Log lines | Not captured to Supabase at all | LOCAL |
| Bash results | `quality-gate.log` parsing | Never sent to cloud | LOCAL |
| Override records | `quality-gate-overrides.jsonl` | Stored locally, never synced | LOCAL |
| Feedback records | `quality-gate-feedback.jsonl` | Stored locally, never synced | LOCAL |

### D.2 Evidence Table Fields Never Populated
| Field | Definition | Status |
|-------|-----------|--------|
| `env_info` | jsonb | **Declared but never written** |

### D.3 Labels Table Data Not Exposed
| Data | Where It Exists | Why Not Shown |
|------|-----------------|---------------|
| Model verdicts (Gemini/OpenAI/Grok) | `labels.model_verdicts` JSONB | Not in dashboard RPC |
| Confidence scores | `labels.confidence` | Not in dashboard RPC |
| Individual model reasons | `labels.model_verdicts` | Not in dashboard RPC |
| Method (ENSEMBLE, etc.) | `labels.method` | Not in dashboard RPC |

**Current RPC** (`get_qg_stats`) returns only aggregate counts, not detailed row data.

---

## E. COMPLETE GAP LIST

### E.1 Data Gaps (Exists Somewhere, Not on Dashboard)
| Item | Source | Exists? | On Dashboard? | Reason |
|------|--------|---------|---------------|--------|
| **Evidence rows** (recent) | Supabase `evidence` table | ✓ | ✗ | RPC `get_qg_dashboard` missing |
| **Label verdicts** (TP/FP/SKIP/SPLIT) | Supabase `labels.verdict` | ✓ | ✗ | `get_qg_dashboard` missing |
| **Model verdicts** (per model) | Supabase `labels.model_verdicts` JSONB | ✓ | ✗ | RPC doesn't join or unpack |
| **Confidence scores** | Supabase `labels.confidence` | ✓ | ✗ | RPC missing |
| **Complexity level** | Local log line column 3 | ✓ | ✗ | Never sent to Supabase |
| **Tool usage** | Local log `tools=` field | ✓ | ✗ | Sent to Supabase `evidence.tool_names` but RPC doesn't expose |
| **File edits** | Supabase `evidence.edited_paths` | ✓ | ✗ | RPC missing |
| **Bash commands** | Supabase `evidence.bash_commands` | ✓ | ✗ | RPC missing |
| **Response text** | Supabase `evidence.response_text` | ✓ | ✗ | RPC missing |
| **Block type (MECHANICAL/LLM)** | Supabase `evidence.block_type` | ✓ | Partial | Shown in table, not in stats |
| **User feedback** | Local `quality-gate-feedback.jsonl` | ✓ | ✗ | Not synced to cloud |
| **Override history** | Local `quality-gate-overrides.jsonl` | ✓ | ✗ | Not synced to cloud |
| **Category/reason tags** | Local log, Supabase `evidence.reason` | ✓ | Partial | Shown in table, not categorized |
| **Feedback (notes)** | Modal textarea (localStorage only) | ✓ | ✗ | Browser-local only, not persisted to cloud |

### E.2 Computation Gaps (Data Exists, Calculations Missing)
| Metric | Calculation | Status |
|--------|-----------|--------|
| **Precision** | tp / (tp + fp) | ✓ Working |
| **Recall** | tp / (tp + fn) | ✗ No false negatives tracked |
| **F1 Score** | 2 * (precision * recall) / (precision + recall) | ✗ Depends on recall |
| **False Negative Rate** | fn / (tp + fn) | ✗ No miss data in cloud |
| **Block rate trend** | Blocks/hour over time | ✗ No time-series aggregation in RPC |
| **Category distribution** | Counts by block_type | ✗ No aggregation in RPC |
| **Tool usage distribution** | Count by tool type | ✗ tool_names in evidence but not exposed |
| **Model agreement rate** | Cases where all 3 models agree | ✓ `confidence` field captures this, but not exposed in RPC |
| **Confidence distribution** | Histogram of confidence scores | ✗ Scores exist but not aggregated |

---

## F. FEASIBILITY ASSESSMENT

### F.1 Missing RPC: `get_qg_dashboard`

**Implementation needed**:
```sql
CREATE OR REPLACE FUNCTION get_qg_dashboard(p_limit int DEFAULT 50)
RETURNS json
LANGUAGE sql
SECURITY DEFINER
SET search_path = public
AS $$
  SELECT json_build_object(
    'stats', (SELECT json_build_object(
      'evidence_total', (SELECT count(*)::int FROM evidence),
      'labeled_total', (SELECT count(*)::int FROM labels),
      'tp_count', (SELECT count(*)::int FROM labels WHERE verdict = 'TP'),
      'fp_count', (SELECT count(*)::int FROM labels WHERE verdict = 'FP'),
      'skip_count', (SELECT count(*)::int FROM labels WHERE verdict = 'SKIP'),
      'split_count', (SELECT count(*)::int FROM labels WHERE verdict = 'SPLIT')
    )),
    'recent', (SELECT json_agg(row_to_json(t))
      FROM (
        SELECT
          e.id,
          e.created_at,
          e.block_type,
          e.reason,
          e.user_request,
          e.response_text AS response_snippet,
          l.verdict,
          l.confidence,
          l.model_verdicts::json,
          COALESCE((l.model_verdicts -> 'gemini' -> 'verdict'), 'null'::jsonb)::text AS gemini_verdict,
          COALESCE((l.model_verdicts -> 'gemini' -> 'reason'), ''::jsonb)::text AS gemini_reason,
          COALESCE((l.model_verdicts -> 'gemini' -> 'error'), 'null'::jsonb)::text AS gemini_error,
          COALESCE((l.model_verdicts -> 'openai' -> 'verdict'), 'null'::jsonb)::text AS openai_verdict,
          COALESCE((l.model_verdicts -> 'openai' -> 'reason'), ''::jsonb)::text AS openai_reason,
          COALESCE((l.model_verdicts -> 'openai' -> 'error'), 'null'::jsonb)::text AS openai_error,
          COALESCE((l.model_verdicts -> 'grok' -> 'verdict'), 'null'::jsonb)::text AS grok_verdict,
          COALESCE((l.model_verdicts -> 'grok' -> 'reason'), ''::jsonb)::text AS grok_reason,
          COALESCE((l.model_verdicts -> 'grok' -> 'error'), 'null'::jsonb)::text AS grok_error
        FROM evidence e
        LEFT JOIN labels l ON l.evidence_id = e.id
        ORDER BY e.created_at DESC
        LIMIT p_limit
      ) t
    )
  );
$$;

GRANT EXECUTE ON FUNCTION get_qg_dashboard(int) TO anon;
```

**Status**: SUPABASE — can expose via RPC (browser-accessible)

### F.2 Data Sync Gaps

| Gap | Category | Effort | Feasibility |
|-----|----------|--------|-------------|
| Complexity field | LOCAL + SUPABASE | Medium | Add to `evidence.env_info` during `_capture_evidence()`, expose in RPC |
| Override/feedback history | LOCAL + SUPABASE | Medium | Create `feedback` table, sync from CLI tool |
| User feedback persistence | BROWSER → SUPABASE | Low | Move textarea from localStorage to cloud table |
| Block/hour trend | SUPABASE aggregation | Low | Add time-bucket aggregation RPC |
| Category distribution | SUPABASE aggregation | Low | Add GROUP BY block_type RPC |
| Tool usage stats | SUPABASE aggregation | Low | Unnest `tool_names` JSONB, aggregate in RPC |
| Model agreement rate | Already in `confidence` | Very Low | Just expose `confidence` distribution in new RPC |
| False negative tracking | CLI-based tracking | Medium | Create `false_negatives` table, sync from `qg miss` command |

---

## G. DASHBOARD RENDER ISSUES

**Current state**: Dashboard shows error bar because `get_qg_dashboard` RPC doesn't exist.

```javascript
// Line 628: catch block
txt(errBar, 'Error loading data: ' + e.message);
```

**Expected error message** when RPC missing:
```
Error loading data: HTTP 404: ...
```

---

## SUMMARY TABLE: DATA → COVERAGE

| Data Piece | Exists Locally? | Synced to Cloud? | Exposed in RPC? | Shown on Dashboard? |
|------------|-----------------|-----------------|-----------------|-------------------|
| Block decision (PASS/BLOCK) | ✓ log | ✓ evidence.block_type | ✗ | ✗ |
| Complexity (SIMPLE/MODERATE) | ✓ log | ✗ | ✗ | ✗ |
| Tool names used | ✓ log | ✓ evidence.tool_names | ✗ | ✗ |
| Files edited | ✓ log | ✓ evidence.edited_paths | ✗ | ✗ |
| Bash commands | ✓ log | ✓ evidence.bash_commands | ✗ | ✗ |
| Response text | ✗ (not in log) | ✓ evidence.response_text | ✗ | ✗ |
| Verdict (TP/FP/SKIP/SPLIT) | ✗ (computed in cloud) | ✓ labels.verdict | ✗ | ✗ |
| Confidence | ✗ (computed in cloud) | ✓ labels.confidence | ✗ | ✗ |
| Model verdicts (Gemini/OpenAI/Grok) | ✗ (computed in cloud) | ✓ labels.model_verdicts | ✗ | ✗ |
| User feedback | ✓ feedback.jsonl | ✗ | ✗ | ✗ (browser localStorage only) |
| Override history | ✓ overrides.jsonl | ✗ | ✗ | ✗ |
| Aggregate stats (TP/FP counts) | ✓ log + cloud | ✓ derived from labels | ✓ get_qg_stats() | ✓ |

---

## CONCLUSION

**Primary blocker**: `get_qg_dashboard()` RPC function **does not exist** in Supabase schema.

**Secondary gaps**:
1. Complexity levels never sent to cloud
2. Local feedback/override data isolated from dashboard
3. Model-level details (individual verdicts, confidence per model) trapped in JSONB, not exposed
4. No time-series metrics or trend analysis

**Quick fix**: Implement the missing RPC (10–15 line SQL function, SUPABASE category).
**Full solution**: Add feedback sync layer + expose model-level details in RPC.
