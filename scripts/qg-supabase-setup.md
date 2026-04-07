# Quality Gate Measurement System — Supabase Setup Guide

## Prerequisites
- Supabase account (free tier works)
- Supabase CLI (`npm install -g supabase`)
- API keys for: Google Gemini, OpenAI, Mistral AI

---

## Step 1 — Create a Supabase project

1. Go to [supabase.com](https://supabase.com) → New project
2. Name it `qg-measurement` (or anything)
3. Save the **Project URL** and **anon public key** (Settings → API)

---

## Step 2 — Run the schema

1. Open **SQL Editor** in the Supabase dashboard
2. Paste the contents of `~/.claude/scripts/qg-supabase-schema.sql`
3. Click **Run**

Verify tables exist: Database → Tables → `evidence` and `labels`
Verify function exists: Database → Functions → `get_qg_stats`

---

## Step 3 — Add API keys to Supabase Vault

In the Supabase dashboard → Edge Functions → Manage Secrets, add:

| Secret Name      | Value                        |
|------------------|------------------------------|
| `GEMINI_API_KEY`  | Your Google AI Studio key    |
| `OPENAI_API_KEY`  | Your OpenAI key              |
| `MISTRAL_API_KEY` | Your Mistral AI key          |

> Note: `SUPABASE_SERVICE_ROLE_KEY` is auto-injected — do NOT add it manually.

---

## Step 4 — Deploy the Edge Function

```bash
cd ~/.claude/scripts
supabase login
supabase link --project-ref <your-project-ref>
supabase functions deploy qg-reviewer
```

The project ref is the string in your project URL:
`https://<project-ref>.supabase.co`

Verify deployment: Edge Functions → `qg-reviewer` → should show "Active"

---

## Step 5 — Configure the trigger

### Option A: DB Webhook (preferred)
1. Dashboard → Database → Webhooks → Create new webhook
2. Name: `qg-evidence-webhook`
3. Table: `evidence`, Event: `INSERT`
4. URL: `https://<project-ref>.supabase.co/functions/v1/qg-reviewer`
5. HTTP method: `POST`
6. Headers: `Authorization: Bearer <service-role-key>`

### Option B: Cron fallback (works on all tiers)
1. Dashboard → Database → Extensions → enable `pg_cron`
2. SQL Editor → run:

```sql
SELECT cron.schedule(
  'qg-reviewer-cron',
  '*/15 * * * *',  -- every 15 minutes
  $$
    SELECT net.http_post(
      url := 'https://<project-ref>.supabase.co/functions/v1/qg-reviewer',
      headers := '{"Authorization": "Bearer <service-role-key>", "Content-Type": "application/json"}'::jsonb,
      body := '{}'::jsonb
    );
  $$
);
```

> Use Option A if available (real-time). Fall back to Option B if webhooks aren't available on your tier.

---

## Step 6 — Add env vars to Claude Code settings

Edit `~/.claude/settings.json` → add to the `env` block:

```json
"SUPABASE_QG_URL": "https://<project-ref>.supabase.co",
"SUPABASE_QG_ANON_KEY": "<your-anon-public-key>"
```

These are safe on disk — the anon key only allows INSERT to `evidence` (RLS enforced).

---

## Step 7 — Verify end-to-end

1. **Trigger a BLOCK** — provoke the quality gate (e.g., make an unverified claim)
2. **Check evidence table** — Dashboard → Table Editor → `evidence` → new row should appear
3. **Check labels table** — within 15s (webhook) or 15min (cron), a label row should appear
4. **Run `qg precision-cloud`** — should show counts and P/R/F1

```bash
qg precision-cloud
```

Expected output:
```
=== Quality Gate Precision (Cloud) ===
Evidence inserts:  N
Log BLOCK count:   N  [tamper audit: OK / DIVERGENCE DETECTED]
Labeled:           N  (N%)

TP: N  FP: N  SKIP: N  SPLIT: N
Precision:  XX.X%  (TP / (TP+FP))
```

---

## Cost estimate

Based on 129 BLOCKs/day observed (≈3,782/month):
- Gemini 2.0 Flash: ~$0.00 (free tier covers this volume)
- GPT-4o-mini: ~$0.150/1M input tokens
- Mistral Large: ~$0.002/1K tokens

**Total: ~$9.72/month** at observed block rate (within $2–10 budget).

---

## Tamper audit

`qg precision-cloud` compares:
- **Evidence inserts** (rows in Supabase `evidence` table)
- **Log BLOCK count** (lines matching `| BLOCK |` in `~/.claude/quality-gate.log`)

If Claude suppressed a capture call (e.g., by modifying `_capture_evidence()`), the
counts diverge and the audit reports `DIVERGENCE DETECTED`. The capture function
is ~25 lines and easy to review on every quality-gate.py change.
