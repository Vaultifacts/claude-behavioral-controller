-- Quality Gate Measurement System — Supabase Schema
-- Run this in Supabase SQL Editor after creating a new project.

-- ── evidence table ────────────────────────────────────────────────────────────
-- Claude inserts rows here at every BLOCK. Anon INSERT-only via RLS.
-- Claude cannot update/delete its own evidence.
CREATE TABLE IF NOT EXISTS evidence (
  id           uuid        DEFAULT gen_random_uuid() PRIMARY KEY,
  created_at   timestamptz DEFAULT now(),
  session_id   text        NOT NULL,
  block_type   text        NOT NULL,   -- MECHANICAL | OVERCONFIDENCE | ASSUMPTION
  reason       text        NOT NULL,
  response_text text,
  tool_names   jsonb,
  edited_paths jsonb,
  bash_commands jsonb,
  user_request text,
  env_info     jsonb
);

ALTER TABLE evidence ENABLE ROW LEVEL SECURITY;
CREATE POLICY "anon_insert_evidence" ON evidence
  FOR INSERT TO anon WITH CHECK (true);
-- No SELECT/UPDATE/DELETE policy for anon → Claude cannot read or modify evidence rows

-- ── labels table ──────────────────────────────────────────────────────────────
-- Written exclusively by the Edge Function using service role key.
-- No anon policy = zero anon access.
CREATE TABLE IF NOT EXISTS labels (
  id           uuid        DEFAULT gen_random_uuid() PRIMARY KEY,
  created_at   timestamptz DEFAULT now(),
  evidence_id  uuid        REFERENCES evidence(id),
  verdict      text        NOT NULL CHECK (verdict IN ('TP','FP','SKIP','SPLIT')),
  method       text        NOT NULL DEFAULT 'ENSEMBLE',
  model_verdicts jsonb,
  confidence   float,
  notes        text
);

ALTER TABLE labels ENABLE ROW LEVEL SECURITY;
-- No anon policy = zero anon INSERT/UPDATE/DELETE/SELECT on labels

-- ── get_qg_stats() RPC ────────────────────────────────────────────────────────
-- SECURITY DEFINER: runs as postgres (has BYPASSRLS), so it can SELECT from
-- labels even though anon has no SELECT policy.
-- Anon receives aggregate counts only — never individual verdict rows.
CREATE OR REPLACE FUNCTION get_qg_stats()
RETURNS json
LANGUAGE sql
SECURITY DEFINER
SET search_path = public
AS $$
  SELECT json_build_object(
    'evidence_total', (SELECT count(*)::int FROM evidence),
    'labeled_total',  (SELECT count(*)::int FROM labels),
    'tp_count',       (SELECT count(*)::int FROM labels WHERE verdict = 'TP'),
    'fp_count',       (SELECT count(*)::int FROM labels WHERE verdict = 'FP'),
    'skip_count',     (SELECT count(*)::int FROM labels WHERE verdict = 'SKIP'),
    'split_count',    (SELECT count(*)::int FROM labels WHERE verdict = 'SPLIT')
  );
$$;

GRANT EXECUTE ON FUNCTION get_qg_stats() TO anon;
-- Callable via: POST {SUPABASE_URL}/rest/v1/rpc/get_qg_stats
--   Headers: apikey: <anon_key>, Content-Type: application/json
--   Body: {}

-- ── get_qg_dashboard(p_limit) RPC ─────────────────────────────────────────────
-- Returns full dashboard payload: stats, recent labeled verdicts, model stats,
-- confidence distribution, and daily trend for the last 7 days.
-- SECURITY DEFINER: runs as postgres (BYPASSRLS) to SELECT from labels.
CREATE OR REPLACE FUNCTION get_qg_dashboard(p_limit int DEFAULT 50)
RETURNS json
LANGUAGE sql
SECURITY DEFINER
SET search_path = public
AS $$
  SELECT json_build_object(
    'stats', json_build_object(
      'evidence_total', (SELECT count(*)::int FROM evidence),
      'labeled_total',  (SELECT count(*)::int FROM labels),
      'tp_count',       (SELECT count(*)::int FROM labels WHERE verdict = 'TP'),
      'fp_count',       (SELECT count(*)::int FROM labels WHERE verdict = 'FP'),
      'skip_count',     (SELECT count(*)::int FROM labels WHERE verdict = 'SKIP'),
      'split_count',    (SELECT count(*)::int FROM labels WHERE verdict = 'SPLIT')
    ),
    'recent', (
      SELECT json_agg(row_to_json(t))
      FROM (
        SELECT
          e.id,
          e.created_at,
          e.block_type,
          e.reason,
          e.user_request,
          left(e.response_text, 500) AS response_snippet,
          e.tool_names,
          e.edited_paths,
          e.bash_commands,
          l.verdict,
          l.confidence,
          l.notes,
          (l.model_verdicts->'gemini'->>'verdict')  AS gemini_verdict,
          (l.model_verdicts->'gemini'->>'reason')   AS gemini_reason,
          (l.model_verdicts->'gemini'->>'error')    AS gemini_error,
          (l.model_verdicts->'openai'->>'verdict')  AS openai_verdict,
          (l.model_verdicts->'openai'->>'reason')   AS openai_reason,
          (l.model_verdicts->'grok'->>'verdict')    AS grok_verdict,
          (l.model_verdicts->'grok'->>'reason')     AS grok_reason
        FROM evidence e
        JOIN labels l ON l.evidence_id = e.id
        ORDER BY l.created_at DESC
        LIMIT p_limit
      ) t
    ),
    'model_stats', (
      SELECT json_build_object(
        'gemini_tp',    count(*) FILTER (WHERE (model_verdicts->'gemini'->>'verdict') = 'TP'),
        'gemini_fp',    count(*) FILTER (WHERE (model_verdicts->'gemini'->>'verdict') = 'FP'),
        'gemini_skip',  count(*) FILTER (WHERE (model_verdicts->'gemini'->>'verdict') = 'SKIP'),
        'gemini_error', count(*) FILTER (WHERE model_verdicts->'gemini'->>'error' IS NOT NULL AND model_verdicts->'gemini'->>'error' != ''),
        'openai_tp',    count(*) FILTER (WHERE (model_verdicts->'openai'->>'verdict') = 'TP'),
        'openai_fp',    count(*) FILTER (WHERE (model_verdicts->'openai'->>'verdict') = 'FP'),
        'openai_skip',  count(*) FILTER (WHERE (model_verdicts->'openai'->>'verdict') = 'SKIP'),
        'grok_tp',      count(*) FILTER (WHERE (model_verdicts->'grok'->>'verdict') = 'TP'),
        'grok_fp',      count(*) FILTER (WHERE (model_verdicts->'grok'->>'verdict') = 'FP'),
        'grok_skip',    count(*) FILTER (WHERE (model_verdicts->'grok'->>'verdict') = 'SKIP'),
        'total',        count(*)::int
      )
      FROM labels
    ),
    'confidence_dist', (
      SELECT json_build_object(
        'high',      count(*) FILTER (WHERE confidence >= 0.90)::int,
        'medium',    count(*) FILTER (WHERE confidence >= 0.67 AND confidence < 0.90)::int,
        'low',       count(*) FILTER (WHERE confidence >= 0.34 AND confidence < 0.67)::int,
        'very_low',  count(*) FILTER (WHERE confidence < 0.34)::int,
        'total',     count(*)::int
      )
      FROM labels
      WHERE confidence IS NOT NULL
    ),
    'daily_trend', (
      SELECT json_agg(row_to_json(t) ORDER BY t.day)
      FROM (
        SELECT
          date_trunc('day', l.created_at)::date AS day,
          count(*)::int AS total,
          count(*) FILTER (WHERE l.verdict = 'TP')::int AS tp,
          count(*) FILTER (WHERE l.verdict = 'FP')::int AS fp
        FROM labels l
        WHERE l.created_at >= now() - interval '7 days'
        GROUP BY date_trunc('day', l.created_at)
        ORDER BY 1
      ) t
    )
  );
$$;

GRANT EXECUTE ON FUNCTION get_qg_dashboard(int) TO anon;
-- Callable via: POST {SUPABASE_URL}/rest/v1/rpc/get_qg_dashboard
--   Headers: apikey: <anon_key>, Content-Type: application/json
--   Body: {"p_limit": 50}
