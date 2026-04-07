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
