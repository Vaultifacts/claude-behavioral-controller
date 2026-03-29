# Plan: Checklist Round 1 — Bot tasks/pause/resume, Dashboard Forecast tab, API tests, README sync

## Context
CHECKLIST.md was created at v2.1.49 tracking ~51 remaining items. This plan addresses the
highest-ROI items: closing 4 feature-parity gaps (bot commands, dashboard tab), adding 3
missing API tests, and syncing the outdated README.

## Files to modify
- `discord_bot/bot.py`
- `api/dashboard.html`
- `api/test_app.py`
- `README.md`
- `CHECKLIST.md` (update checkboxes on completion)

---

## Item 1 — Bot: `tasks`, `/pause`, `/resume` commands (`discord_bot/bot.py`)

### 1a — `_format_tasks(state)` helper
Add after `_format_stats` (or near it). Returns a compact per-task summary table:
```python
def _format_tasks(state: dict) -> str:
    dag = state.get("dag", {})
    if not dag:
        return "No tasks."
    lines = ["**Tasks**", "```"]
    for t_name, t_data in dag.items():
        branches = t_data.get("branches", {})
        total = sum(len(b.get("subtasks", {})) for b in branches.values())
        verified = sum(
            1 for b in branches.values()
            for st in b.get("subtasks", {}).values()
            if st.get("status") == "Verified"
        )
        pct = int(verified / total * 100) if total else 0
        status = t_data.get("status", "Pending")
        lines.append(f"{t_name:<8} {verified:>2}/{total:<2} {pct:>3}%  [{status}]")
    lines.append("```")
    return "\n".join(lines)
```

### 1b — Plain-text `tasks` command
In `handle_text_command`, add (near other read-only commands like `stats`, `forecast`):
```python
elif cmd == "tasks":
    state = _load_state()
    await message.channel.send(_format_tasks(state))
```

### 1c — Slash `/tasks` command
```python
@bot.tree.command(name="tasks", description="Per-task summary table")
async def slash_tasks(interaction: discord.Interaction):
    if not _check_channel(interaction): return
    state = _load_state()
    await interaction.response.send_message(_format_tasks(state))
```

### 1d — Plain-text `pause` and `resume` already exist — add slash commands
```python
@bot.tree.command(name="pause", description="Pause the auto-run")
async def slash_pause(interaction: discord.Interaction):
    if not _check_channel(interaction): return
    _ROOT.joinpath("state", "pause_trigger").touch()
    await interaction.response.send_message("⏸ Pause trigger sent.")

@bot.tree.command(name="resume", description="Resume a paused auto-run")
async def slash_resume(interaction: discord.Interaction):
    if not _check_channel(interaction): return
    _ROOT.joinpath("state", "resume_trigger").touch()
    await interaction.response.send_message("▶ Resume trigger sent.")
```

### 1e — Add `tasks` to slash `/help` text and plain-text `_HELP_TEXT`
- `/help` entries: add `tasks — per-task summary table` and `pause/resume — pause/resume auto-run`
- `_HELP_TEXT`: add `tasks` row

---

## Item 2 — Dashboard: Forecast tab (`api/dashboard.html`)

### 2a — Add sidebar tab button (after Agents tab button)
```html
<button class="tab-btn" data-tab="forecast" onclick="switchTab('forecast')">Forecast</button>
```

### 2b — Add tab panel (after agents panel)
```html
<div id="tab-forecast" class="tab-panel" style="display:none">
  <h3>Completion Forecast</h3>
  <div id="forecast-content"><em>Loading…</em></div>
</div>
```

### 2c — `pollForecast()` function
```javascript
async function pollForecast() {
  try {
    const r = await fetch('/forecast');
    const d = await r.json();
    const el = document.getElementById('forecast-content');
    if (!el) return;
    const eta = d.eta_steps != null ? `${d.eta_steps} steps` : 'N/A';
    const rate = d.verified_per_step != null ? d.verified_per_step.toFixed(2) : '—';
    const pct  = d.percent_complete != null ? d.percent_complete.toFixed(1) : '—';
    el.innerHTML = `
      <table class="info-table">
        <tr><td>Completion</td><td><strong>${pct}%</strong></td></tr>
        <tr><td>Rate</td><td>${rate} verified/step</td></tr>
        <tr><td>ETA</td><td>${eta}</td></tr>
        <tr><td>Verified</td><td>${d.verified ?? '—'} / ${d.total ?? '—'}</td></tr>
        <tr><td>Stalled</td><td>${d.stalled_count ?? 0}</td></tr>
      </table>`;
  } catch(e) { /* ignore */ }
}
```

### 2d — Wire into tick loop
In the existing `tick()` function, add `pollForecast()` alongside the other pollers.
Only poll when the forecast tab is active (check `currentTab === 'forecast'`) — or poll always
since it's lightweight (single small JSON).

---

## Item 3 — API: 3 missing tests (`api/test_app.py`)

### 3a — `TestGetRoot` (1 test)
```python
class TestGetRoot(unittest.TestCase):
    def test_get_root_returns_html(self):
        rv = client.get('/')
        self.assertEqual(rv.status_code, 200)
        self.assertIn(b'<!DOCTYPE html>', rv.data)
```

### 3b — `TestPostExport` (2 tests)
```python
class TestPostExport(unittest.TestCase):
    def test_post_export_creates_file(self):
        rv = client.post('/export')
        self.assertEqual(rv.status_code, 200)
        self.assertIn('path', rv.get_json())

    def test_post_export_returns_json(self):
        rv = client.post('/export')
        data = rv.get_json()
        self.assertIn('status', data)
```

### 3c — `TestPostTaskTrigger` (2 tests)
```python
class TestPostTaskTrigger(unittest.TestCase):
    def test_post_task_trigger_valid(self):
        rv = client.post('/tasks/0/trigger', json={"action": "verify", "subtask": "A1"})
        self.assertIn(rv.status_code, [200, 404])

    def test_post_task_trigger_invalid_task(self):
        rv = client.post('/tasks/999/trigger', json={"action": "verify"})
        self.assertIn(rv.status_code, [404, 400])
```

---

## Item 4 — README sync (`README.md`)

Update the following outdated sections:
- Test count: change "21 bot tests" → "194 bot tests, 71 API tests (265 total)"
- CI badge description: note all 15 CI steps
- Commands section: add newer commands (tasks, heal, stalled, agents, forecast, filter, search, log, branches, rename, diff, pause, resume, prioritize_branch, depends, undepends, timeline, history, stats, output, config, priority, undo)
- Architecture section: note all 4 surfaces (CLI, API, Dashboard, Discord Bot), 17 trigger files, 4-tier execution

---

## CHECKLIST.md updates (on completion)
Mark these items [x]:
- `- [ ] tasks (not in bot yet — CLI only)`
- `- [ ] /tasks (not in bot yet)`
- `- [ ] /pause, /resume (plain-text only, no slash)`
- `- [ ] Forecast — dedicated forecast tab with progress/rates/ETA display`
- `- [ ] Test for GET / (root endpoint) — not tested`
- `- [ ] Test for POST /tasks/<id>/trigger — not tested`
- `- [ ] Test for POST /export — not tested`
- `- [ ] README test count outdated (says "21 tests" for bot, actually 194)`
- `- [ ] README command list outdated (missing newer commands)`
- `- [ ] README architecture section outdated (missing newer endpoints/tabs)`
Update summary table counts accordingly.

---

## Verification
1. Bot tests: `python -m pytest discord_bot/test_bot.py -q` — should pass (add tests for new commands)
2. API tests: `python -m pytest api/test_app.py -q` — now 74→76 tests, all pass
3. Dashboard: open `http://127.0.0.1:5000` → Forecast tab visible, shows ETA/rate/pct
4. Bot: `tasks` in Discord → table of 7 tasks with verified counts
5. Bot: `/tasks` slash → same output
6. Bot: `/pause` slash → "⏸ Pause trigger sent."
7. README: `grep -i "194"` confirms updated test count
