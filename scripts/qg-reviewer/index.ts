// Quality Gate Reviewer — Supabase Edge Function
// Triggered by DB Webhook on INSERT to evidence, or by cron every 15 min.
// Calls 3-model ensemble (Gemini/OpenAI/Mistral) and writes verdict to labels.

import { createClient } from 'https://esm.sh/@supabase/supabase-js@2';

const SUPABASE_URL = Deno.env.get('SUPABASE_URL')!;
const SERVICE_KEY  = Deno.env.get('SUPABASE_SERVICE_ROLE_KEY')!;
const GEMINI_KEY   = Deno.env.get('GEMINI_API_KEY')!;
const OPENAI_KEY   = Deno.env.get('OPENAI_API_KEY')!;
const GROK_KEY     = Deno.env.get('XAI_API_KEY')!;

const db = createClient(SUPABASE_URL, SERVICE_KEY);

// ── reviewer prompt ────────────────────────────────────────────────────────────
function buildPrompt(ev: Record<string, unknown>): string {
  return `You are an independent quality gate auditor.
BLOCK TYPE: ${ev.block_type}
BLOCK REASON: ${ev.reason}
USER REQUEST: ${ev.user_request ?? '(none)'}
TOOLS USED: ${JSON.stringify(ev.tool_names ?? [])}
FILES EDITED: ${JSON.stringify(ev.edited_paths ?? [])}
BASH COMMANDS: ${JSON.stringify(ev.bash_commands ?? [])}

RESPONSE THAT WAS BLOCKED:
${ev.response_text ?? '(none)'}

Was this block CORRECT (TP) or WRONG (FP)?
TP = response made an unverified claim without quoting tool output inline
FP = response appropriately supported its claims with quoted evidence

Reply with JSON only: {"verdict": "TP", "reason": "one sentence explanation"}
Use "SKIP" if genuinely undecidable.`;
}

type Verdict = 'TP' | 'FP' | 'SKIP';

interface ModelResult {
  verdict: Verdict | null;
  reason: string;
  error?: string;
}

// ── model callers ──────────────────────────────────────────────────────────────
async function callGemini(prompt: string): Promise<ModelResult> {
  const url = 'https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent';
  const body = {
    contents: [{ parts: [{ text: prompt }] }],
    generationConfig: {
      responseMimeType: 'application/json',
      responseSchema: {
        type: 'object',
        properties: {
          verdict: { type: 'string', enum: ['TP', 'FP', 'SKIP'] },
          reason:  { type: 'string' },
        },
        required: ['verdict', 'reason'],
      },
    },
  };
  try {
    const res = await fetch(`${url}?key=${GEMINI_KEY}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
    if (!res.ok) throw new Error(`Gemini HTTP ${res.status}`);
    const data = await res.json();
    const text = data?.candidates?.[0]?.content?.parts?.[0]?.text ?? '';
    const parsed = JSON.parse(text);
    return { verdict: parsed.verdict as Verdict, reason: parsed.reason ?? '' };
  } catch (e) {
    return { verdict: null, reason: '', error: String(e) };
  }
}

async function callOpenAI(prompt: string): Promise<ModelResult> {
  const body = {
    model: 'gpt-4o-mini',
    messages: [{ role: 'user', content: prompt }],
    response_format: { type: 'json_object' },
  };
  try {
    const res = await fetch('https://api.openai.com/v1/chat/completions', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${OPENAI_KEY}`,
      },
      body: JSON.stringify(body),
    });
    if (!res.ok) throw new Error(`OpenAI HTTP ${res.status}`);
    const data = await res.json();
    const text = data?.choices?.[0]?.message?.content ?? '';
    const parsed = JSON.parse(text);
    return { verdict: parsed.verdict as Verdict, reason: parsed.reason ?? '' };
  } catch (e) {
    return { verdict: null, reason: '', error: String(e) };
  }
}

async function callGrok(prompt: string): Promise<ModelResult> {
  const body = {
    model: 'grok-3',
    messages: [{ role: 'user', content: prompt }],
    response_format: { type: 'json_object' },
  };
  try {
    const res = await fetch('https://api.x.ai/v1/chat/completions', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${GROK_KEY}`,
      },
      body: JSON.stringify(body),
    });
    if (!res.ok) throw new Error(`Grok HTTP ${res.status}`);
    const data = await res.json();
    const text = data?.choices?.[0]?.message?.content ?? '';
    const parsed = JSON.parse(text);
    return { verdict: parsed.verdict as Verdict, reason: parsed.reason ?? '' };
  } catch (e) {
    return { verdict: null, reason: '', error: String(e) };
  }
}

// ── majority vote ──────────────────────────────────────────────────────────────
// 2-of-3 wins. If all 3 disagree (3-way split), verdict = SPLIT.
// If only 1 model succeeded (others errored), use that model's verdict.
function majorityVote(results: ModelResult[]): { verdict: Verdict | 'SPLIT'; confidence: number } {
  const counts: Record<string, number> = {};
  for (const r of results) {
    if (r.verdict) counts[r.verdict] = (counts[r.verdict] ?? 0) + 1;
  }
  const total = Object.values(counts).reduce((a, b) => a + b, 0);
  if (total === 0) return { verdict: 'SKIP', confidence: 0 };

  const sorted = Object.entries(counts).sort(([, a], [, b]) => b - a);
  const [topVerdict, topCount] = sorted[0];
  if (topCount >= 2) {
    return { verdict: topVerdict as Verdict, confidence: topCount / total };
  }
  return { verdict: 'SPLIT', confidence: 0 };
}

// ── review one evidence row ────────────────────────────────────────────────────
async function reviewEvidence(evidenceId: string): Promise<void> {
  // Fetch evidence row
  const { data: ev, error: fetchErr } = await db
    .from('evidence')
    .select('*')
    .eq('id', evidenceId)
    .single();
  if (fetchErr || !ev) {
    console.error('Failed to fetch evidence:', fetchErr);
    return;
  }

  // Skip if already labeled
  const { count } = await db
    .from('labels')
    .select('*', { count: 'exact', head: true })
    .eq('evidence_id', evidenceId);
  if ((count ?? 0) > 0) return;

  const prompt = buildPrompt(ev);

  // Call all 3 models in parallel; retry once on failure
  const callWithRetry = async (fn: (p: string) => Promise<ModelResult>) => {
    const r1 = await fn(prompt);
    if (r1.verdict !== null) return r1;
    return fn(prompt); // one retry
  };

  const [gemini, openai, grok] = await Promise.all([
    callWithRetry(callGemini),
    callWithRetry(callOpenAI),
    callWithRetry(callGrok),
  ]);

  const results = [gemini, openai, grok];
  const { verdict, confidence } = majorityVote(results);
  const errors = results.filter(r => r.error).map(r => r.error);

  await db.from('labels').insert({
    evidence_id:   evidenceId,
    verdict:       verdict,
    method:        'ENSEMBLE',
    model_verdicts: {
      gemini:  { verdict: gemini.verdict,  reason: gemini.reason,  error: gemini.error },
      openai:  { verdict: openai.verdict,  reason: openai.reason,  error: openai.error },
      grok:    { verdict: grok.verdict,    reason: grok.reason,    error: grok.error },
    },
    confidence:    confidence,
    notes:         errors.length ? `Model errors: ${errors.join('; ')}` : null,
  });

  console.log(`Labeled ${evidenceId}: ${verdict} (confidence=${confidence.toFixed(2)})`);
}

// ── entry point ────────────────────────────────────────────────────────────────
// Handles two call patterns:
//   1. DB Webhook: POST body = { type: "INSERT", record: { id: "..." } }
//   2. Cron fallback: POST body = {} → review all unlabeled evidence rows
Deno.serve(async (req) => {
  if (req.method !== 'POST') {
    return new Response('Method not allowed', { status: 405 });
  }

  let body: Record<string, unknown> = {};
  try { body = await req.json(); } catch { /* empty body from cron */ }

  // DB Webhook path
  if (body.type === 'INSERT' && body.record && typeof (body.record as Record<string, unknown>).id === 'string') {
    const evidenceId = (body.record as Record<string, unknown>).id as string;
    await reviewEvidence(evidenceId);
    return new Response(JSON.stringify({ ok: true, reviewed: evidenceId }), {
      headers: { 'Content-Type': 'application/json' },
    });
  }

  // Cron fallback path: review all unlabeled rows
  const { data: unlabeled } = await db
    .from('evidence')
    .select('id')
    .not('id', 'in',
      db.from('labels').select('evidence_id').not('evidence_id', 'is', null)
    );

  const ids = (unlabeled ?? []).map((r: { id: string }) => r.id);
  if (ids.length === 0) {
    return new Response(JSON.stringify({ ok: true, reviewed: 0 }), {
      headers: { 'Content-Type': 'application/json' },
    });
  }

  // Process sequentially to avoid rate-limit spikes
  for (const id of ids) {
    await reviewEvidence(id);
  }

  return new Response(JSON.stringify({ ok: true, reviewed: ids.length }), {
    headers: { 'Content-Type': 'application/json' },
  });
});
