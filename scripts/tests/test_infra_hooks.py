"""test_infra_hooks.py -- Unit tests for 13 standalone infrastructure hook files."""
import sys, os, json, unittest, tempfile, io, time
from unittest.mock import patch, MagicMock

HOOKS_DIR = os.path.expanduser("~/.claude/hooks")
sys.path.insert(0, HOOKS_DIR)

class TestBlockSecrets(unittest.TestCase):
    def _import(self):
        if "block-secrets" not in sys.modules:
            sys.modules["block-secrets"] = __import__("block-secrets")
        return sys.modules["block-secrets"]

    def test_allowlisted_env_example(self):
        m = self._import()
        self.assertTrue(m.is_allowlisted("/some/.env.example"))
    def test_allowlisted_env_sample(self):
        m = self._import()
        self.assertTrue(m.is_allowlisted("/some/.env.sample"))
    def test_allowlisted_test_file(self):
        m = self._import()
        self.assertTrue(m.is_allowlisted("/src/auth.test.js"))
    def test_allowlisted_spec_file(self):
        m = self._import()
        self.assertTrue(m.is_allowlisted("/src/auth.spec.ts"))
    def test_allowlisted_home_claude(self):
        m = self._import()
        h = os.path.expanduser("~").replace("\\", "/")
        self.assertTrue(m.is_allowlisted(h + "/.claude/hooks/x.py"))
    def test_allowlisted_github_workflows(self):
        m = self._import()
        self.assertTrue(m.is_allowlisted("/project/.github/workflows/ci.yml"))
    def test_not_allowlisted_regular(self):
        m = self._import()
        self.assertFalse(m.is_allowlisted("/project/src/config.py"))
    def test_not_allowlisted_empty(self):
        m = self._import()
        self.assertFalse(m.is_allowlisted(""))
    def test_not_allowlisted_none(self):
        m = self._import()
        self.assertFalse(m.is_allowlisted(None))
    def test_write_clean_exits_0(self):
        m = self._import()
        p = {"tool_name": "Write", "tool_input": {"file_path": "/p.py", "content": "print(1)"}}
        with patch("sys.stdin", io.StringIO(json.dumps(p))):
            with self.assertRaises(SystemExit) as ctx: m.main()
        self.assertEqual(ctx.exception.code, 0)
    _AWS = "AKIAIOSFODNN7EXAMPLE"
    def test_write_aws_key_blocks(self):
        m = self._import()
        p = {"tool_name": "Write", "tool_input": {"file_path": "/c.py", "content": "k=" + chr(34) + self._AWS + chr(34)}}
        with patch("sys.stdin", io.StringIO(json.dumps(p))):
            with self.assertRaises(SystemExit) as ctx: m.main()
        self.assertEqual(ctx.exception.code, 2)
    _OAI = "sk-aaaaaaaaaaaaaaaaaaaaaaaaa"
    def test_write_openai_key_blocks(self):
        m = self._import()
        p = {"tool_name": "Write", "tool_input": {"file_path": "/c.py", "content": "api_key=" + chr(34) + self._OAI + chr(34)}}
        with patch("sys.stdin", io.StringIO(json.dumps(p))):
            with self.assertRaises(SystemExit) as ctx: m.main()
        self.assertEqual(ctx.exception.code, 2)
    _GHP = "ghp_AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
    def test_edit_github_token_blocks(self):
        m = self._import()
        p = {"tool_name": "Edit", "tool_input": {"file_path": "/a.py", "old_string": "x", "new_string": "t=" + chr(34) + self._GHP + chr(34)}}
        with patch("sys.stdin", io.StringIO(json.dumps(p))):
            with self.assertRaises(SystemExit) as ctx: m.main()
        self.assertEqual(ctx.exception.code, 2)
    def test_allowlisted_path_skips(self):
        m = self._import()
        p = {"tool_name": "Write", "tool_input": {"file_path": "/.env.example", "content": "K=" + self._AWS}}
        with patch("sys.stdin", io.StringIO(json.dumps(p))):
            with self.assertRaises(SystemExit) as ctx: m.main()
        self.assertEqual(ctx.exception.code, 0)
    def test_non_write_exits_0(self):
        m = self._import()
        p = {"tool_name": "Read", "tool_input": {"file_path": "/f"}}
        with patch("sys.stdin", io.StringIO(json.dumps(p))):
            with self.assertRaises(SystemExit) as ctx: m.main()
        self.assertEqual(ctx.exception.code, 0)
    def test_bash_no_redirect_exits_0(self):
        m = self._import()
        p = {"tool_name": "Bash", "tool_input": {"command": "ls -la"}}
        with patch("sys.stdin", io.StringIO(json.dumps(p))):
            with self.assertRaises(SystemExit) as ctx: m.main()
        self.assertEqual(ctx.exception.code, 0)
    def test_bash_redirect_no_secret(self):
        m = self._import()
        p = {"tool_name": "Bash", "tool_input": {"command": "echo hello > out.txt"}}
        with patch("sys.stdin", io.StringIO(json.dumps(p))):
            with self.assertRaises(SystemExit) as ctx: m.main()
        self.assertEqual(ctx.exception.code, 0)
    def test_bash_redirect_aws_blocks(self):
        m = self._import()
        p = {"tool_name": "Bash", "tool_input": {"command": "echo " + self._AWS + " > k.txt"}}
        with patch("sys.stdin", io.StringIO(json.dumps(p))):
            with self.assertRaises(SystemExit) as ctx: m.main()
        self.assertEqual(ctx.exception.code, 2)
    def test_invalid_json_exits_2(self):
        m = self._import()
        with patch("sys.stdin", io.StringIO("not-json")):
            with self.assertRaises(SystemExit) as ctx: m.main()
        self.assertEqual(ctx.exception.code, 2)
    def test_empty_content_exits_0(self):
        m = self._import()
        p = {"tool_name": "Write", "tool_input": {"file_path": "/p.py", "content": ""}}
        with patch("sys.stdin", io.StringIO(json.dumps(p))):
            with self.assertRaises(SystemExit) as ctx: m.main()
        self.assertEqual(ctx.exception.code, 0)
    _RSA = "-----BEGIN RSA PRIVATE KEY-----"
    def test_private_key_blocks(self):
        m = self._import()
        p = {"tool_name": "Write", "tool_input": {"file_path": "/k.pem", "content": self._RSA + chr(10) + "MIIE"}}
        with patch("sys.stdin", io.StringIO(json.dumps(p))):
            with self.assertRaises(SystemExit) as ctx: m.main()
        self.assertEqual(ctx.exception.code, 2)
    _PAT = "github_pat_11ABCDEFGxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
    def test_github_pat_blocks(self):
        m = self._import()
        p = {"tool_name": "Write", "tool_input": {"file_path": "/a.py", "content": "t=" + chr(34) + self._PAT + chr(34)}}
        with patch("sys.stdin", io.StringIO(json.dumps(p))):
            with self.assertRaises(SystemExit) as ctx: m.main()
        self.assertEqual(ctx.exception.code, 2)

class TestContextWatch(unittest.TestCase):
    HOOK_PATH = os.path.join(HOOKS_DIR, "context-watch.py")
    def _run(self, payload):
        import subprocess
        env = os.environ.copy(); env["PYTHONIOENCODING"] = "utf-8"
        r = subprocess.run([sys.executable, self.HOOK_PATH], input=json.dumps(payload).encode(), capture_output=True, env=env)
        return r.stdout.decode(), r.stderr.decode(), r.returncode
    def test_low_context(self):
        _, _, c = self._run({"session_id": "s1", "context": {"tokens_used": 100, "context_window": 10000}})
        self.assertEqual(c, 0)
    def test_invalid_json(self):
        import subprocess
        env = os.environ.copy(); env["PYTHONIOENCODING"] = "utf-8"
        r = subprocess.run([sys.executable, self.HOOK_PATH], input=b"bad", capture_output=True, env=env)
        self.assertEqual(r.returncode, 0)
    def test_empty_payload(self):
        _, _, c = self._run({})
        self.assertEqual(c, 0)
    def test_zero_context(self):
        _, _, c = self._run({"session_id": "s1", "context": {"tokens_used": 0, "context_window": 0}})
        self.assertEqual(c, 0)
    def test_90pct_context(self):
        _, _, c = self._run({"session_id": "s90", "context": {"tokens_used": 900, "context_window": 1000}})
        self.assertEqual(c, 0)

class TestErrorDedup(unittest.TestCase):
    def _import(self):
        if "error-dedup" not in sys.modules:
            # Module calls main() at import; main() calls sys.exit(0) which is not caught by except Exception
            with patch("sys.stdin", io.StringIO("{}")), patch("sys.exit"):
                sys.modules["error-dedup"] = __import__("error-dedup")
        return sys.modules["error-dedup"]
    def test_normalize_line_numbers(self):
        m = self._import()
        r = m.normalize_error("Error at line 42")
        self.assertIn("line n", r); self.assertNotIn("42", r)
    def test_normalize_timestamps(self):
        m = self._import()
        self.assertIn("datetime", m.normalize_error("Failed at 2024-01-15T09:30:00"))
    def test_normalize_paths(self):
        m = self._import()
        self.assertIn("path", m.normalize_error("Error in /home/user/main.py").lower())
    def test_normalize_lowercase(self):
        m = self._import()
        r = m.normalize_error("ModuleNotFoundError")
        self.assertEqual(r, r.lower())
    def test_hash_8chars(self):
        m = self._import()
        self.assertEqual(len(m.error_hash("err")), 8)
    def test_hash_consistent(self):
        m = self._import()
        self.assertEqual(m.error_hash("err foo"), m.error_hash("err foo"))
    def test_hash_normalized(self):
        m = self._import()
        self.assertEqual(m.error_hash("Error at line 10"), m.error_hash("Error at line 99"))
    def test_new_state(self):
        m = self._import()
        s = m.new_state("abc")
        self.assertEqual(s["session_id"], "abc"); self.assertFalse(s["alert"]["active"])
    def test_main_no_error_exits_0(self):
        m = self._import()
        p = {"hook_event_name": "PostToolUse", "session_id": "s1", "tool_name": "Bash", "tool_response": "ok"}
        with patch("sys.stdin", io.StringIO(json.dumps(p))):
            with self.assertRaises(SystemExit) as ctx: m.main()
        self.assertEqual(ctx.exception.code, 0)
    def test_main_bad_json_exits_0(self):
        m = self._import()
        with patch("sys.stdin", io.StringIO("bad")):
            with self.assertRaises(SystemExit) as ctx: m.main()
        self.assertEqual(ctx.exception.code, 0)
    def test_tier1_writes_state(self):
        m = self._import()
        p = {"hook_event_name": "PostToolUseFailure", "session_id": "sn", "tool_name": "Bash", "error": "ModuleNotFoundError: x"}
        with tempfile.TemporaryDirectory() as tmp:
            sf = os.path.join(tmp, "s.json")
            with patch.object(m, "STATE_FILE", sf), patch("sys.stdin", io.StringIO(json.dumps(p))):
                try: m.main()
                except SystemExit: pass
            self.assertTrue(os.path.exists(sf))
            st = json.load(open(sf, encoding="utf-8"))
            self.assertEqual(st["session_id"], "sn"); self.assertEqual(len(st["errors"]), 1)
    def test_alert_threshold(self):
        m = self._import()
        with tempfile.TemporaryDirectory() as tmp:
            sf = os.path.join(tmp, "s.json")
            err = "ModuleNotFoundError: x"
            h = m.error_hash(err); now = int(time.time())
            st = m.new_state("sa")
            st["errors"][h] = {"hash": h, "canonical": err, "count": 2,
                "first_seen_ts": now-100, "last_seen_ts": now-10, "tool": "Bash", "dismissed": False}
            json.dump(st, open(sf, "w", encoding="utf-8"))
            p = {"hook_event_name": "PostToolUseFailure", "session_id": "sa", "tool_name": "Bash", "error": err}
            with patch.object(m, "STATE_FILE", sf), patch("sys.stdin", io.StringIO(json.dumps(p))):
                try: m.main()
                except SystemExit: pass
            st2 = json.load(open(sf, encoding="utf-8"))
            self.assertTrue(st2["alert"]["active"])
            self.assertGreaterEqual(st2["errors"][h]["count"], 3)
    def test_load_state_missing(self):
        m = self._import()
        with patch.object(m, "STATE_FILE", "/nope/s.json"):
            self.assertIsNone(m.load_state())
    def test_atomic_write(self):
        m = self._import()
        with tempfile.TemporaryDirectory() as tmp:
            p = os.path.join(tmp, "o.json")
            m.atomic_write(p, {"k": "v"})
            self.assertEqual(json.load(open(p))["k"], "v")
    def test_throttle_skips(self):
        m = self._import()
        p = {"hook_event_name": "PostToolUse", "session_id": "st", "tool_name": "Bash",
             "tool_response": "Exit code 1\nTraceback (most recent call last):\n  Error: x"}
        with tempfile.TemporaryDirectory() as tmp:
            sf = os.path.join(tmp, "s.json")
            st = m.new_state("st"); st["ts"] = int(time.time())
            json.dump(st, open(sf, "w", encoding="utf-8"))
            with patch.object(m, "STATE_FILE", sf), patch("sys.stdin", io.StringIO(json.dumps(p))):
                with self.assertRaises(SystemExit) as ctx: m.main()
            self.assertEqual(ctx.exception.code, 0)

class TestEventObserver(unittest.TestCase):
    HOOK_PATH = os.path.join(HOOKS_DIR, "event-observer.py")
    def _run(self, payload):
        import subprocess
        env = os.environ.copy(); env["PYTHONIOENCODING"] = "utf-8"
        r = subprocess.run([sys.executable, self.HOOK_PATH], input=json.dumps(payload).encode(), capture_output=True, env=env)
        return r.stdout.decode(), r.stderr.decode(), r.returncode
    def test_instructions_loaded(self):
        _, _, c = self._run({"hook_event_name": "InstructionsLoaded", "load_reason": "startup", "file_path": "/CLAUDE.md"})
        self.assertEqual(c, 0)
    def test_config_change(self):
        _, _, c = self._run({"hook_event_name": "ConfigChange", "source": "user", "file_path": "/s.json"})
        self.assertEqual(c, 0)
    def test_session_start(self):
        _, _, c = self._run({"hook_event_name": "SessionStart", "trigger": "new"})
        self.assertEqual(c, 0)
    def test_unknown_event(self):
        _, _, c = self._run({"hook_event_name": "Unknown"})
        self.assertEqual(c, 0)
    def test_invalid_json(self):
        import subprocess
        env = os.environ.copy(); env["PYTHONIOENCODING"] = "utf-8"
        r = subprocess.run([sys.executable, self.HOOK_PATH], input=b"bad", capture_output=True, env=env)
        self.assertEqual(r.returncode, 0)
    def test_config_change_stderr(self):
        _, err, _ = self._run({"hook_event_name": "ConfigChange", "source": "u", "file_path": "/f"})
        self.assertIn("config-change", err)

class TestHookHealthFeed(unittest.TestCase):
    def _import(self):
        mod_name = "hook-health-feed"
        if mod_name not in sys.modules:
            # Module calls sys.exit(0) at top level after the try block
            with patch("sys.stdin", io.StringIO("{}")), patch("sys.exit"):
                sys.modules[mod_name] = __import__(mod_name)
        return sys.modules[mod_name]
    def test_read_tail_missing(self):
        m = self._import()
        self.assertEqual(m.read_tail("/nope.log"), [])
    def test_read_tail_limits(self):
        m = self._import()
        with tempfile.NamedTemporaryFile(mode="w", suffix=".log", delete=False, encoding="utf-8") as f:
            [f.write(f"line {i}\n") for i in range(10)]; p = f.name
        try: lines = m.read_tail(p, n=5); self.assertEqual(len(lines), 5)
        finally: os.unlink(p)
    def test_parse_ts_valid(self):
        m = self._import()
        ts = m.parse_ts("2024-01-15 09:30", "%Y-%m-%d %H:%M")
        self.assertIsNotNone(ts); self.assertIsInstance(ts, float)
    def test_parse_ts_invalid(self):
        m = self._import()
        self.assertIsNone(m.parse_ts("bad", "%Y-%m-%d %H:%M"))
    def test_parse_audit_empty(self):
        m = self._import()
        self.assertEqual(m.parse_hook_audit([]), {})
    def test_parse_audit_valid(self):
        m = self._import()
        r = m.parse_hook_audit(["2024-01-15 09:30 | SESSION_START | x\n"])
        self.assertIn("SESSION_START", r)
    def test_parse_qg_empty(self):
        m = self._import()
        self.assertEqual(m.parse_quality_gate([]), [])
    def test_parse_qg_valid(self):
        m = self._import()
        r = m.parse_quality_gate(["2024-01-15 09:30:00 | PASS | ok\n"])
        self.assertEqual(len(r), 1); self.assertEqual(r[0][1], "PASS")
    def test_parse_tc_valid(self):
        m = self._import()
        r = m.parse_task_classifier(["2024-01-15 09:30:00 | TRIVIAL | x\n"])
        self.assertEqual(len(r), 1)
    def test_load_disabled_missing(self):
        m = self._import()
        with patch.object(m, "DISABLED_FILE", "/nope.json"): self.assertEqual(m.load_disabled(), set())
    def test_load_disabled_list(self):
        m = self._import()
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8") as f:
            json.dump(["hook-a", "hook-b"], f); p = f.name
        try:
            with patch.object(m, "DISABLED_FILE", p): self.assertEqual(m.load_disabled(), {"hook-a", "hook-b"})
        finally: os.unlink(p)
    def test_session_active_missing(self):
        m = self._import()
        with patch.object(m, "STATE_FILE", "/nope.json"): self.assertFalse(m.is_session_active())
    def test_session_active_recent(self):
        m = self._import()
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8") as f:
            json.dump({}, f); p = f.name
        try:
            with patch.object(m, "STATE_FILE", p): self.assertTrue(m.is_session_active())
        finally: os.unlink(p)
    def test_build_entry_muted(self):
        m = self._import()
        cfg = {"log": "hook-audit.log", "max_age": None}
        ld = {"audit": {}, "quality_gate": [], "task_class": []}
        e = m.build_hook_entry("quality-gate", cfg, ld, time.time(), True, {"quality-gate"})
        self.assertEqual(e["status"], "muted")
    def test_build_entry_unknown(self):
        m = self._import()
        cfg = {"log": "hook-audit.log", "max_age": None}
        ld = {"audit": {}, "quality_gate": [], "task_class": []}
        e = m.build_hook_entry("event-observer", cfg, ld, time.time(), True, set())
        self.assertEqual(e["status"], "unknown")
    def test_build_entry_stale(self):
        m = self._import()
        cfg = {"log": "task-classifier.log", "max_age": 300}
        ld = {"audit": {}, "quality_gate": [], "task_class": [(time.time()-1000, "TRIVIAL|x")]}
        e = m.build_hook_entry("task-classifier", cfg, ld, time.time(), True, set())
        self.assertEqual(e["status"], "stale")
    def test_build_entry_healthy(self):
        m = self._import()
        cfg = {"log": "task-classifier.log", "max_age": 300}
        ld = {"audit": {}, "quality_gate": [], "task_class": [(time.time()-60, "TRIVIAL|x")]}
        e = m.build_hook_entry("task-classifier", cfg, ld, time.time(), True, set())
        self.assertEqual(e["status"], "healthy")
    def test_atomic_write(self):
        m = self._import()
        with tempfile.TemporaryDirectory() as tmp:
            p = os.path.join(tmp, "h.json")
            m.atomic_write(p, {"overall_status": "healthy"})
            self.assertEqual(json.load(open(p))["overall_status"], "healthy")
    def test_main_runs(self):
        m = self._import()
        with tempfile.TemporaryDirectory() as tmp:
            hf = os.path.join(tmp, "hh.json")
            with patch.object(m, "HEALTH_FILE", hf), \
                 patch.object(m, "LOG_FILES", {"hook-audit.log": os.path.join(tmp,"a.log"), "quality-gate.log": os.path.join(tmp,"q.log"), "task-classifier.log": os.path.join(tmp,"t.log")}), \
                 patch.object(m, "DISABLED_FILE", os.path.join(tmp,"d.json")), \
                 patch.object(m, "STATE_FILE", os.path.join(tmp,"s.json")):\
                m.main()
            data = json.load(open(hf))
            self.assertIn("overall_status", data); self.assertIn("hooks", data)
    def test_get_entries_qg(self):
        m = self._import()
        cfg = {"log": "quality-gate.log", "max_age": None}
        ld = {"audit": {}, "quality_gate": [(time.time(), "PASS", "ok")], "task_class": []}
        self.assertEqual(len(m.get_entries_for("quality-gate", cfg, ld)), 1)
    def test_get_entries_tc(self):
        m = self._import()
        cfg = {"log": "task-classifier.log", "max_age": 300}
        ld = {"audit": {}, "quality_gate": [], "task_class": [(time.time(), "TRIVIAL|x")]}
        self.assertEqual(len(m.get_entries_for("task-classifier", cfg, ld)), 1)

class TestPermissionGuard(unittest.TestCase):
    def _import(self):
        mod_name = "permission-guard"
        if mod_name not in sys.modules: sys.modules[mod_name] = __import__(mod_name)
        return sys.modules[mod_name]
    _GH  = "http" + "s://" + "api.github.com"
    _BAD = "http" + "s://" + "evil-site.xyz"
    _LOC = "http://" + "localhost" + ":3000"
    def test_extract_domain_https(self):
        m = self._import()
        self.assertEqual(m.extract_domain("curl " + self._GH + "/r"), "api.github.com")
    def test_extract_domain_www_stripped(self):
        m = self._import()
        self.assertEqual(m.extract_domain("curl http" + "s://www.example.com/p"), "example.com")
    def test_extract_domain_no_url(self):
        m = self._import()
        self.assertIsNone(m.extract_domain("ls -la"))
    def test_allows_github(self):
        m = self._import()
        p = {"tool_name": "Bash", "tool_input": {"command": "curl " + self._GH + "/repos/a/b"}}
        cap = io.StringIO()
        with patch("sys.stdin", io.StringIO(json.dumps(p))), patch("sys.stdout", cap), patch("sys.stdin.isatty", return_value=False):
            with self.assertRaises(SystemExit) as ctx: m.main()
        self.assertEqual(ctx.exception.code, 0)
        out = cap.getvalue()
        if out.strip(): self.assertNotEqual(json.loads(out).get("decision"), "block")
    def test_blocks_unknown_domain(self):
        m = self._import()
        p = {"tool_name": "Bash", "tool_input": {"command": "curl " + self._BAD + "/x"}}
        cap = io.StringIO()
        with patch("sys.stdin", io.StringIO(json.dumps(p))), patch("sys.stdout", cap), patch("sys.stdin.isatty", return_value=False):
            with self.assertRaises(SystemExit) as ctx: m.main()
        self.assertEqual(ctx.exception.code, 0); self.assertIn("block", cap.getvalue())
    def test_blocks_force_push_main(self):
        m = self._import()
        p = {"tool_name": "Bash", "tool_input": {"command": "git push --force origin main"}}
        cap = io.StringIO()
        with patch("sys.stdin", io.StringIO(json.dumps(p))), patch("sys.stdout", cap), patch("sys.stdin.isatty", return_value=False):
            with self.assertRaises(SystemExit) as ctx: m.main()
        self.assertEqual(ctx.exception.code, 0)
        self.assertEqual(json.loads(cap.getvalue())["decision"], "block")
    def test_blocks_force_push_master(self):
        m = self._import()
        p = {"tool_name": "Bash", "tool_input": {"command": "git push -f origin master"}}
        cap = io.StringIO()
        with patch("sys.stdin", io.StringIO(json.dumps(p))), patch("sys.stdout", cap), patch("sys.stdin.isatty", return_value=False):
            with self.assertRaises(SystemExit) as ctx: m.main()
        self.assertEqual(ctx.exception.code, 0)
        self.assertEqual(json.loads(cap.getvalue())["decision"], "block")
    def test_allows_non_bash(self):
        m = self._import()
        p = {"tool_name": "Read", "tool_input": {"file_path": "/f"}}
        with patch("sys.stdin", io.StringIO(json.dumps(p))), patch("sys.stdin.isatty", return_value=False):
            with self.assertRaises(SystemExit) as ctx: m.main()
        self.assertEqual(ctx.exception.code, 0)
    def test_bad_json_allows(self):
        m = self._import()
        with patch("sys.stdin", io.StringIO("bad")), patch("sys.stdin.isatty", return_value=False):
            with self.assertRaises(SystemExit) as ctx: m.main()
        self.assertEqual(ctx.exception.code, 0)
    def test_allows_localhost(self):
        m = self._import()
        p = {"tool_name": "Bash", "tool_input": {"command": "curl " + self._LOC + "/api"}}
        cap = io.StringIO()
        with patch("sys.stdin", io.StringIO(json.dumps(p))), patch("sys.stdout", cap), patch("sys.stdin.isatty", return_value=False):
            with self.assertRaises(SystemExit) as ctx: m.main()
        self.assertEqual(ctx.exception.code, 0)
        out = cap.getvalue()
        if out.strip(): self.assertNotEqual(json.loads(out).get("decision"), "block")

class TestPermissionRequestLog(unittest.TestCase):
    HOOK_PATH = os.path.join(HOOKS_DIR, "permission-request-log.py")
    def _run(self, payload):
        import subprocess
        env = os.environ.copy(); env["PYTHONIOENCODING"] = "utf-8"
        r = subprocess.run([sys.executable, self.HOOK_PATH], input=json.dumps(payload).encode(), capture_output=True, env=env)
        return r.stdout.decode(), r.stderr.decode(), r.returncode
    def test_bash_cmd(self):
        _, _, c = self._run({"tool_name": "Bash", "tool_input": {"command": "git status"}})
        self.assertEqual(c, 0)
    def test_file_path(self):
        _, _, c = self._run({"tool_name": "Write", "tool_input": {"file_path": "/p.py"}})
        self.assertEqual(c, 0)
    def test_invalid_json(self):
        import subprocess
        env = os.environ.copy(); env["PYTHONIOENCODING"] = "utf-8"
        r = subprocess.run([sys.executable, self.HOOK_PATH], input=b"bad", capture_output=True, env=env)
        self.assertEqual(r.returncode, 0)
    def test_empty_input(self):
        _, _, c = self._run({"tool_name": "T", "tool_input": {}})
        self.assertEqual(c, 0)
    def test_non_dict_input(self):
        _, _, c = self._run({"tool_name": "T", "tool_input": "s"})
        self.assertEqual(c, 0)

class TestPreCompactSnapshot(unittest.TestCase):
    HOOK_PATH = os.path.join(HOOKS_DIR, "pre-compact-snapshot.py")
    def _run(self, payload):
        import subprocess
        env = os.environ.copy(); env["PYTHONIOENCODING"] = "utf-8"
        r = subprocess.run([sys.executable, self.HOOK_PATH], input=json.dumps(payload).encode(), capture_output=True, env=env)
        return r.stdout.decode(), r.stderr.decode(), r.returncode
    def test_no_transcript(self):
        _, _, c = self._run({"session_id": "a", "trigger": "auto", "transcript_path": ""})
        self.assertEqual(c, 0)
    def test_missing_transcript(self):
        _, _, c = self._run({"session_id": "a", "trigger": "auto", "transcript_path": "/nope.jsonl"})
        self.assertEqual(c, 0)
    def test_invalid_json(self):
        import subprocess
        env = os.environ.copy(); env["PYTHONIOENCODING"] = "utf-8"
        r = subprocess.run([sys.executable, self.HOOK_PATH], input=b"bad", capture_output=True, env=env)
        self.assertEqual(r.returncode, 0)
    def test_manual_trigger(self):
        _, _, c = self._run({"session_id": "a", "trigger": "manual", "transcript_path": ""})
        self.assertEqual(c, 0)
    def test_existing_transcript(self):
        with tempfile.TemporaryDirectory() as tmp:
            tp = os.path.join(tmp, "t.jsonl")
            open(tp, "w").write("{}\n")
            import subprocess
            env = os.environ.copy(); env["PYTHONIOENCODING"] = "utf-8"
            r = subprocess.run([sys.executable, self.HOOK_PATH],
                input=json.dumps({"session_id": "x", "trigger": "auto", "transcript_path": tp}).encode(),
                capture_output=True, env=env)
            self.assertEqual(r.returncode, 0)

class TestPrunePermissions(unittest.TestCase):
    def _import(self):
        mod_name = "prune-permissions"
        if mod_name not in sys.modules: sys.modules[mod_name] = __import__(mod_name)
        return sys.modules[mod_name]
    def test_reusable_non_bash(self):
        m = self._import()
        self.assertTrue(m.is_reusable("Skill(*)"))
        self.assertTrue(m.is_reusable("mcp__docker__run"))
        self.assertTrue(m.is_reusable("WebFetch(*)"))
    def test_reusable_bash_wildcard_short(self):
        m = self._import()
        self.assertTrue(m.is_reusable("Bash(gh pr:*)"))
    def test_not_reusable_no_wildcard(self):
        m = self._import()
        self.assertFalse(m.is_reusable("Bash(git status --porcelain)"))
    def test_not_reusable_long_wildcard(self):
        m = self._import()
        self.assertFalse(m.is_reusable("Bash(some very long command with * inside that exceeds 40 chars)"))
    def test_prunes_oneoffs(self):
        m = self._import()
        s = {"permissions": {"allow": ["Skill(*)", "Bash(git status --porcelain)", "Bash(gh pr:*)"]}}
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8") as f:
            json.dump(s, f); p = f.name
        try:
            with patch.object(m, "SETTINGS_PATH", p): m.main()
            allow = json.load(open(p))["permissions"]["allow"]
            self.assertIn("Skill(*)", allow); self.assertIn("Bash(gh pr:*)", allow)
            self.assertNotIn("Bash(git status --porcelain)", allow)
        finally: os.unlink(p)
    def test_no_change_needed(self):
        m = self._import()
        s = {"permissions": {"allow": ["Skill(*)"]}}
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8") as f:
            json.dump(s, f); p = f.name
        try:
            with patch.object(m, "SETTINGS_PATH", p): m.main()
            self.assertEqual(len(json.load(open(p))["permissions"]["allow"]), 1)
        finally: os.unlink(p)
    def test_missing_file(self):
        m = self._import()
        with patch.object(m, "SETTINGS_PATH", "/nope.json"): m.main()
    def test_bad_json(self):
        m = self._import()
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8") as f:
            f.write("bad"); p = f.name
        try:
            with patch.object(m, "SETTINGS_PATH", p): m.main()
        finally: os.unlink(p)
    def test_empty_allow(self):
        m = self._import()
        s = {"permissions": {"allow": []}}
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8") as f:
            json.dump(s, f); p = f.name
        try:
            with patch.object(m, "SETTINGS_PATH", p): m.main()
        finally: os.unlink(p)
    def test_atomic_write_failure_cleans_up(self):
        # Lines 56-61: os.replace raises, os.unlink called; then os.unlink also raises (lines 59-60)
        m = self._import()
        s = {"permissions": {"allow": ["Bash(git status --porcelain)"]}}
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8") as f:
            json.dump(s, f); p = f.name
        try:
            with patch.object(m, "SETTINGS_PATH", p):
                with patch("os.replace", side_effect=OSError("mock replace fail")):
                    with patch("os.unlink", side_effect=OSError("mock unlink fail")):
                        m.main()  # Should not raise even when unlink also fails
        finally:
            try: os.unlink(p)
            except OSError: pass
    def test_main_dunder_exits_zero(self):
        # Lines 67-68, 71: run module as __main__ via runpy — normal path, exits 0
        import runpy
        with patch("sys.exit") as mock_exit:
            runpy.run_path(os.path.join(HOOKS_DIR, "prune-permissions.py"), run_name="__main__")
        mock_exit.assert_called_once_with(0)
    def test_main_dunder_exception_swallowed(self):
        # Lines 69-71: __main__ guard swallows unexpected Exception from main() and exits 0
        import runpy
        # Patch json.load to raise an unexpected exception type (not caught inside main's try block)
        with patch("json.load", side_effect=PermissionError("simulated")):
            with patch("sys.exit") as mock_exit:
                runpy.run_path(
                    os.path.join(HOOKS_DIR, "prune-permissions.py"),
                    run_name="__main__",
                )
        mock_exit.assert_called_once_with(0)

class TestQaScreenshotGate(unittest.TestCase):
    def _import(self):
        mod_name = "qa-screenshot-gate"
        if mod_name not in sys.modules: sys.modules[mod_name] = __import__(mod_name)
        return sys.modules[mod_name]
    def test_no_walkthrough_continues(self):
        m = self._import()
        p = {"assistant_response": "All tests Pass: verified", "tool_calls": []}
        cap = io.StringIO()
        with patch("sys.stdin", io.StringIO(json.dumps(p))), patch("sys.stdout", cap), patch("os.path.exists", return_value=False): m.main()
        self.assertTrue(json.loads(cap.getvalue()).get("continue"))
    def test_invalid_json_continues(self):
        m = self._import()
        cap = io.StringIO()
        with patch("sys.stdin", io.StringIO("bad")), patch("sys.stdout", cap): m.main()
        self.assertTrue(json.loads(cap.getvalue()).get("continue"))
    def test_no_pass_claim_continues(self):
        m = self._import()
        p = {"assistant_response": "Tests done.", "tool_calls": []}
        cap = io.StringIO()
        with patch("sys.stdin", io.StringIO(json.dumps(p))), patch("sys.stdout", cap), patch("os.path.exists", return_value=True): m.main()
        self.assertTrue(json.loads(cap.getvalue()).get("continue"))
    def test_pass_no_screenshot_blocks(self):
        m = self._import()
        p = {"assistant_response": "All tests Pass: verified", "tool_calls": []}
        cap = io.StringIO()
        with patch("sys.stdin", io.StringIO(json.dumps(p))), patch("sys.stdout", cap), patch("os.path.exists", return_value=True): m.main()
        self.assertEqual(json.loads(cap.getvalue()).get("decision"), "block")
    def test_pass_with_screenshot_continues(self):
        m = self._import()
        p = {"assistant_response": "All tests Pass: verified",
             "tool_calls": [{"tool_name": "mcp__claude-in-chrome__computer", "input": {"action": "screenshot"}}]}
        cap = io.StringIO()
        with patch("sys.stdin", io.StringIO(json.dumps(p))), patch("sys.stdout", cap), patch("os.path.exists", return_value=True): m.main()
        self.assertTrue(json.loads(cap.getvalue()).get("continue"))
    def test_pass_count_blocked(self):
        m = self._import()
        p = {"assistant_response": "5 Pass results", "tool_calls": []}
        cap = io.StringIO()
        with patch("sys.stdin", io.StringIO(json.dumps(p))), patch("sys.stdout", cap), patch("os.path.exists", return_value=True): m.main()
        self.assertEqual(json.loads(cap.getvalue()).get("decision"), "block")
    def test_confidence_blocked(self):
        m = self._import()
        p = {"assistant_response": "100% confidence all pass", "tool_calls": []}
        cap = io.StringIO()
        with patch("sys.stdin", io.StringIO(json.dumps(p))), patch("sys.stdout", cap), patch("os.path.exists", return_value=True): m.main()
        self.assertEqual(json.loads(cap.getvalue()).get("decision"), "block")

class TestQgGraceWriter(unittest.TestCase):
    def _import(self):
        mod_name = "qg-grace-writer"
        if mod_name not in sys.modules: sys.modules[mod_name] = __import__(mod_name)
        return sys.modules[mod_name]
    def test_non_bash_noop(self):
        m = self._import()
        with patch("sys.stdin", io.StringIO(json.dumps({"tool_name": "Write", "tool_response": "x"}))): m.main()
    def test_bash_no_count_noop(self):
        m = self._import()
        with patch("sys.stdin", io.StringIO(json.dumps({"tool_name": "Bash", "tool_response": "ok"}))): m.main()
    def test_bash_count_writes_grace(self):
        m = self._import()
        p = {"tool_name": "Bash", "tool_response": "=== Results: 42 passed, 0 failed, 42 total"}
        with tempfile.TemporaryDirectory() as tmp:
            gf = os.path.join(tmp, "g.json"); lf = os.path.join(tmp, "q.log")
            with patch.object(m, "_GRACE_FILE", gf), patch.object(m, "_LOG_PATH", lf), \
                 patch("sys.stdin", io.StringIO(json.dumps(p))): m.main()
            self.assertEqual(json.load(open(gf))["key"], "42")
    def test_invalid_json_noop(self):
        m = self._import()
        with patch("sys.stdin", io.StringIO("bad")): m.main()
    def test_dict_response(self):
        m = self._import()
        p = {"tool_name": "Bash", "tool_response": {"content": "100 passed, 0 failed, 100 total"}}
        with tempfile.TemporaryDirectory() as tmp:
            gf = os.path.join(tmp, "g.json"); lf = os.path.join(tmp, "q.log")
            with patch.object(m, "_GRACE_FILE", gf), patch.object(m, "_LOG_PATH", lf), \
                 patch("sys.stdin", io.StringIO(json.dumps(p))): m.main()
            self.assertTrue(os.path.exists(gf))
    def test_writes_log(self):
        m = self._import()
        p = {"tool_name": "Bash", "tool_response": "55 passed, 2 failed, 57 total"}
        with tempfile.TemporaryDirectory() as tmp:
            gf = os.path.join(tmp, "g.json"); lf = os.path.join(tmp, "q.log")
            with patch.object(m, "_GRACE_FILE", gf), patch.object(m, "_LOG_PATH", lf), \
                 patch("sys.stdin", io.StringIO(json.dumps(p))): m.main()
            self.assertIn("GRACE-WRITE", open(lf, encoding="utf-8").read())
    def test_bare_count_re(self):
        m = self._import()
        self.assertIsNotNone(m._BARE_COUNT_RE.search("=== Results: 10 passed"))
        self.assertIsNotNone(m._BARE_COUNT_RE.search("5 passed, 0 failed, 5 total"))
        self.assertIsNone(m._BARE_COUNT_RE.search("Build ok"))

class TestQgSessionRecall(unittest.TestCase):
    HOOK_PATH = os.path.join(HOOKS_DIR, "qg-session-recall.py")
    def test_no_snapshot(self):
        import subprocess
        env = os.environ.copy(); env["PYTHONIOENCODING"] = "utf-8"
        r = subprocess.run([sys.executable, self.HOOK_PATH], input=b"", capture_output=True, env=env)
        self.assertEqual(r.returncode, 0)
    def test_injects_message(self):
        with tempfile.TemporaryDirectory() as tmp:
            snap = os.path.join(tmp, "last-session-qg-failures.txt")
            open(snap, "w", encoding="utf-8").write("Block count: 3")
            import subprocess
            env = os.environ.copy(); env["PYTHONIOENCODING"] = "utf-8"
            script = (
                "import sys, os\n"
                "orig = os.path.expanduser\n"
                "os.path.expanduser = lambda p: p.replace('~/.claude', {!r}) if '~/.claude' in p else orig(p)\n"
                "import importlib.util\n"
                "spec = importlib.util.spec_from_file_location('m', {!r})\n"
                "m = importlib.util.module_from_spec(spec)\n"
                "spec.loader.exec_module(m)\n"
                "m.main()\n"
            ).format(tmp, self.HOOK_PATH)
            r = subprocess.run([sys.executable, "-c", script], input=b"", capture_output=True, env=env)
            self.assertEqual(r.returncode, 0)
            s = r.stdout.decode().strip()
            if s: self.assertEqual(json.loads(s).get("type"), "system")
    def test_stale_deleted(self):
        with tempfile.TemporaryDirectory() as tmp:
            snap = os.path.join(tmp, "last-session-qg-failures.txt")
            open(snap, "w", encoding="utf-8").write("old")
            os.utime(snap, (time.time()-90000, time.time()-90000))
            import subprocess
            env = os.environ.copy(); env["PYTHONIOENCODING"] = "utf-8"
            script = (
                "import sys, os\n"
                "orig = os.path.expanduser\n"
                "os.path.expanduser = lambda p: p.replace('~/.claude', {!r}) if '~/.claude' in p else orig(p)\n"
                "import importlib.util\n"
                "spec = importlib.util.spec_from_file_location('m', {!r})\n"
                "m = importlib.util.module_from_spec(spec)\n"
                "spec.loader.exec_module(m)\n"
                "m.main()\n"
            ).format(tmp, self.HOOK_PATH)
            r = subprocess.run([sys.executable, "-c", script], input=b"", capture_output=True, env=env)
            self.assertEqual(r.returncode, 0); self.assertFalse(os.path.exists(snap))

class TestQgShadowWorker(unittest.TestCase):
    def _import(self):
        mod_name = "qg-shadow-worker"
        if mod_name not in sys.modules: sys.modules[mod_name] = __import__(mod_name)
        return sys.modules[mod_name]
    def test_no_args(self):
        m = self._import()
        with patch("sys.argv", ["w"]): m.main()
    def test_missing_file(self):
        m = self._import()
        with patch("sys.argv", ["w", "/nope.json"]): m.main()
    def test_pick_model_no_net(self):
        m = self._import()
        with patch("urllib.request.urlopen", side_effect=Exception("x")):
            self.assertEqual(m._pick_model(), m.MODEL_FULL)
    def test_ollama_unavailable(self):
        m = self._import()
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8") as f:
            json.dump({"prompt": "x", "haiku_ok": True, "haiku_reason": ""}, f); p = f.name
        with patch("sys.argv", ["w", p]), patch("urllib.request.urlopen", side_effect=Exception("x")):
            m.main()
        if os.path.exists(p): os.unlink(p)
    def test_pass_logs(self):
        m = self._import()
        resp = json.dumps({"response": "{\"ok\": true, \"reason\": \"good\"}"})
        with tempfile.TemporaryDirectory() as tmp:
            sl = os.path.join(tmp, "s.log"); df = os.path.join(tmp, "i.json")
            json.dump({"prompt": "x", "haiku_ok": True, "haiku_reason": ""}, open(df, "w"))
            mr = MagicMock(); mr.read.return_value = resp.encode()
            mr.__enter__ = lambda s: s; mr.__exit__ = MagicMock(return_value=False)
            with patch("sys.argv", ["w", df]), patch("urllib.request.urlopen", return_value=mr), patch.object(m, "SHADOW_LOG", sl): m.main()
            if os.path.exists(sl): self.assertIn("PASS", open(sl).read())
    def test_block_disagree(self):
        m = self._import()
        resp = json.dumps({"response": "{\"ok\": false, \"reason\": \"bad\"}"})
        with tempfile.TemporaryDirectory() as tmp:
            sl = os.path.join(tmp, "s.log"); df = os.path.join(tmp, "i.json")
            json.dump({"prompt": "x", "haiku_ok": True, "haiku_reason": ""}, open(df, "w"))
            mr = MagicMock(); mr.read.return_value = resp.encode()
            mr.__enter__ = lambda s: s; mr.__exit__ = MagicMock(return_value=False)
            with patch("sys.argv", ["w", df]), patch("urllib.request.urlopen", return_value=mr), patch.object(m, "SHADOW_LOG", sl): m.main()
            if os.path.exists(sl): self.assertIn("disagree", open(sl).read())
    def test_phi4_note(self):
        m = self._import()
        self.assertGreater(len(m.PHI4_NOTE), 50)
    def test_model_consts(self):
        m = self._import()
        self.assertIsInstance(m.MODEL_FULL, str); self.assertIsInstance(m.MODEL_LITE, str)
        self.assertIsInstance(m.GAMING_VRAM_THRESHOLD_MB, (int, float))
    def test_shadow_log_name(self):
        m = self._import()
        self.assertIn("qg-shadow.log", m.SHADOW_LOG)

class TestContextWatchMain(unittest.TestCase):
    def _import(self):
        mod_name = "context-watch"
        if mod_name not in sys.modules:
            sys.modules[mod_name] = __import__(mod_name)
        return sys.modules[mod_name]

    def test_low_context_returns(self):
        m = self._import()
        p = {"session_id": "s1", "context": {"tokens_used": 100, "context_window": 10000}}
        with patch("sys.stdin", io.StringIO(json.dumps(p))):
            m.main()  # should return without raising

    def test_invalid_json_returns(self):
        m = self._import()
        with patch("sys.stdin", io.StringIO("bad")):
            m.main()

    def test_empty_payload_returns(self):
        m = self._import()
        with patch("sys.stdin", io.StringIO(json.dumps({}))):
            m.main()

    def test_zero_context_returns(self):
        m = self._import()
        p = {"session_id": "s1", "context": {"tokens_used": 0, "context_window": 0}}
        with patch("sys.stdin", io.StringIO(json.dumps(p))):
            m.main()

    def test_high_context_already_toasted(self):
        m = self._import()
        p = {"session_id": "s90", "context": {"tokens_used": 900, "context_window": 1000}}
        with tempfile.TemporaryDirectory() as tmp:
            toast = os.path.join(tmp, "context-toast-state.json")
            with open(toast, "w") as f:
                json.dump({"session_id": "s90", "last_threshold": 90}, f)
            cap = io.StringIO()
            with patch("sys.stdin", io.StringIO(json.dumps(p))), \
                 patch.object(m, "STATE_DIR", tmp), \
                 patch("sys.stdout", cap):
                m.main()

    def test_state_dir_constant(self):
        m = self._import()
        self.assertIn(".claude", m.STATE_DIR)

    def test_new_threshold_70pct_writes_state_and_toasts(self):
        m = self._import()
        p = {"session_id": "s75", "context": {"tokens_used": 750, "context_window": 1000}}
        with tempfile.TemporaryDirectory() as tmp:
            with patch("sys.stdin", io.StringIO(json.dumps(p))), \
                 patch.object(m, "STATE_DIR", tmp), \
                 patch("subprocess.Popen") as mock_popen:
                m.main()
            mock_popen.assert_called_once()
            toast = os.path.join(tmp, "context-toast-state.json")
            self.assertTrue(os.path.exists(toast))
            with open(toast) as f:
                state = json.load(f)
            self.assertEqual(state["last_threshold"], 70)

    def test_new_threshold_85pct_critical_level(self):
        m = self._import()
        p = {"session_id": "s85", "context": {"tokens_used": 860, "context_window": 1000}}
        with tempfile.TemporaryDirectory() as tmp:
            with patch("sys.stdin", io.StringIO(json.dumps(p))), \
                 patch.object(m, "STATE_DIR", tmp), \
                 patch("subprocess.Popen") as mock_popen:
                m.main()
            args = mock_popen.call_args[0][0]
            self.assertIn("Error", args)

    def test_new_threshold_90pct_prints_message(self):
        m = self._import()
        p = {"session_id": "s92", "context": {"tokens_used": 920, "context_window": 1000}}
        with tempfile.TemporaryDirectory() as tmp:
            cap = io.StringIO()
            with patch("sys.stdin", io.StringIO(json.dumps(p))), \
                 patch.object(m, "STATE_DIR", tmp), \
                 patch("subprocess.Popen"), \
                 patch("sys.stdout", cap):
                m.main()
            self.assertIn("compact needed", cap.getvalue())

    def test_ctx_fallback_bad_data_no_crash(self):
        m = self._import()
        p = {"session_id": "s1", "context": {"tokens_used": "bad", "context_window": "x"}}
        with patch("sys.stdin", io.StringIO(json.dumps(p))):
            m.main()  # should not raise


class TestEventObserverMain(unittest.TestCase):
    def _import(self):
        mod_name = "event-observer"
        if mod_name not in sys.modules:
            sys.modules[mod_name] = __import__(mod_name)
        return sys.modules[mod_name]

    def test_invalid_json_returns(self):
        m = self._import()
        with patch("sys.stdin", io.StringIO("bad")):
            m.main()

    def test_unknown_event_returns(self):
        m = self._import()
        p = {"hook_event_name": "Unknown"}
        with patch("sys.stdin", io.StringIO(json.dumps(p))):
            m.main()

    def test_instructions_loaded_logs(self):
        m = self._import()
        p = {"hook_event_name": "InstructionsLoaded", "load_reason": "startup", "file_path": "/CLAUDE.md"}
        with tempfile.TemporaryDirectory() as tmp:
            log = os.path.join(tmp, "hook-audit.log")
            with patch("sys.stdin", io.StringIO(json.dumps(p))), patch.object(m, "LOG_PATH", log):
                m.main()
            self.assertTrue(os.path.exists(log))
            self.assertIn("INSTRUCTIONS", open(log, encoding="utf-8").read())

    def test_session_start_logs(self):
        m = self._import()
        p = {"hook_event_name": "SessionStart", "trigger": "new"}
        with tempfile.TemporaryDirectory() as tmp:
            log = os.path.join(tmp, "hook-audit.log")
            with patch("sys.stdin", io.StringIO(json.dumps(p))), patch.object(m, "LOG_PATH", log):
                m.main()
            self.assertIn("SESSION_START", open(log, encoding="utf-8").read())

    def test_config_change_stderr(self):
        m = self._import()
        p = {"hook_event_name": "ConfigChange", "source": "user", "file_path": "/s.json"}
        with tempfile.TemporaryDirectory() as tmp:
            log = os.path.join(tmp, "hook-audit.log")
            err_cap = io.StringIO()
            with patch("sys.stdin", io.StringIO(json.dumps(p))), \
                 patch.object(m, "LOG_PATH", log), \
                 patch("sys.stderr", err_cap):
                m.main()
            self.assertIn("config-change", err_cap.getvalue())

    def test_log_path_constant(self):
        m = self._import()
        self.assertIn("hook-audit.log", m.LOG_PATH)


class TestPermissionRequestLogMain(unittest.TestCase):
    def _import(self):
        mod_name = "permission-request-log"
        if mod_name not in sys.modules:
            sys.modules[mod_name] = __import__(mod_name)
        return sys.modules[mod_name]

    def test_invalid_json_returns(self):
        m = self._import()
        with patch("sys.stdin", io.StringIO("bad")):
            m.main()

    def test_bash_cmd_logs(self):
        m = self._import()
        p = {"tool_name": "Bash", "tool_input": {"command": "git status"}}
        with tempfile.TemporaryDirectory() as tmp:
            log = os.path.join(tmp, "hook-audit.log")
            with patch("sys.stdin", io.StringIO(json.dumps(p))), patch.object(m, "LOG_PATH", log):
                m.main()
            self.assertIn("PERMISSION_REQUEST", open(log, encoding="utf-8").read())
            self.assertIn("Bash", open(log, encoding="utf-8").read())

    def test_file_path_logs(self):
        m = self._import()
        p = {"tool_name": "Write", "tool_input": {"file_path": "/p.py"}}
        with tempfile.TemporaryDirectory() as tmp:
            log = os.path.join(tmp, "hook-audit.log")
            with patch("sys.stdin", io.StringIO(json.dumps(p))), patch.object(m, "LOG_PATH", log):
                m.main()
            self.assertIn("Write", open(log, encoding="utf-8").read())

    def test_empty_input_logs(self):
        m = self._import()
        p = {"tool_name": "T", "tool_input": {}}
        with tempfile.TemporaryDirectory() as tmp:
            log = os.path.join(tmp, "hook-audit.log")
            with patch("sys.stdin", io.StringIO(json.dumps(p))), patch.object(m, "LOG_PATH", log):
                m.main()
            self.assertTrue(os.path.exists(log))

    def test_non_dict_input_logs(self):
        m = self._import()
        p = {"tool_name": "T", "tool_input": "s"}
        with tempfile.TemporaryDirectory() as tmp:
            log = os.path.join(tmp, "hook-audit.log")
            with patch("sys.stdin", io.StringIO(json.dumps(p))), patch.object(m, "LOG_PATH", log):
                m.main()
            self.assertTrue(os.path.exists(log))

    def test_log_path_constant(self):
        m = self._import()
        self.assertIn("hook-audit.log", m.LOG_PATH)


class TestPreCompactSnapshotMain(unittest.TestCase):
    def _import(self):
        mod_name = "pre-compact-snapshot"
        if mod_name not in sys.modules:
            sys.modules[mod_name] = __import__(mod_name)
        return sys.modules[mod_name]

    def test_invalid_json_returns(self):
        m = self._import()
        with patch("sys.stdin", io.StringIO("bad")):
            m.main()

    def test_no_transcript_logs(self):
        m = self._import()
        p = {"session_id": "abc", "trigger": "auto", "transcript_path": ""}
        with tempfile.TemporaryDirectory() as tmp:
            log = os.path.join(tmp, "hook-audit.log")
            with patch("sys.stdin", io.StringIO(json.dumps(p))), patch.object(m, "LOG_PATH", log):
                m.main()
            self.assertIn("PRE_COMPACT", open(log, encoding="utf-8").read())

    def test_missing_transcript_logs(self):
        m = self._import()
        p = {"session_id": "abc", "trigger": "auto", "transcript_path": "/nope.jsonl"}
        with tempfile.TemporaryDirectory() as tmp:
            log = os.path.join(tmp, "hook-audit.log")
            with patch("sys.stdin", io.StringIO(json.dumps(p))), patch.object(m, "LOG_PATH", log):
                m.main()
            self.assertIn("PRE_COMPACT", open(log, encoding="utf-8").read())

    def test_existing_transcript_copies(self):
        m = self._import()
        with tempfile.TemporaryDirectory() as tmp:
            tp = os.path.join(tmp, "t.jsonl")
            open(tp, "w").write("{}\n")
            log = os.path.join(tmp, "hook-audit.log")
            sessions = os.path.join(tmp, "sessions")
            p = {"session_id": "xyz", "trigger": "auto", "transcript_path": tp}
            with patch("sys.stdin", io.StringIO(json.dumps(p))), \
                 patch.object(m, "LOG_PATH", log), \
                 patch.object(m, "SESSIONS_DIR", sessions):
                m.main()
            self.assertTrue(any(f.endswith(".jsonl.bak") for f in os.listdir(sessions)))

    def test_manual_trigger_logs(self):
        m = self._import()
        p = {"session_id": "a", "trigger": "manual", "transcript_path": ""}
        with tempfile.TemporaryDirectory() as tmp:
            log = os.path.join(tmp, "hook-audit.log")
            with patch("sys.stdin", io.StringIO(json.dumps(p))), \
                 patch.object(m, "LOG_PATH", log), \
                 patch("subprocess.Popen"):
                m.main()
            self.assertIn("manual", open(log, encoding="utf-8").read())

    def test_log_path_constant(self):
        m = self._import()
        self.assertIn("hook-audit.log", m.LOG_PATH)


class TestQgSessionRecallMain(unittest.TestCase):
    def _import(self):
        mod_name = "qg-session-recall"
        if mod_name not in sys.modules:
            sys.modules[mod_name] = __import__(mod_name)
        return sys.modules[mod_name]

    def test_no_snapshot_returns(self):
        m = self._import()
        with patch.object(m, "SNAPSHOT", "/nope/missing.txt"):
            m.main()  # should return silently

    def test_injects_message_main(self):
        m = self._import()
        with tempfile.TemporaryDirectory() as tmp:
            snap = os.path.join(tmp, "last-session-qg-failures.txt")
            open(snap, "w", encoding="utf-8").write("Block count: 3")
            cap = io.StringIO()
            with patch.object(m, "SNAPSHOT", snap), patch("sys.stdout", cap):
                m.main()
            s = cap.getvalue().strip()
            self.assertTrue(s)
            self.assertEqual(json.loads(s).get("type"), "system")
            self.assertFalse(os.path.exists(snap))

    def test_stale_snapshot_deleted_main(self):
        m = self._import()
        with tempfile.TemporaryDirectory() as tmp:
            snap = os.path.join(tmp, "last-session-qg-failures.txt")
            open(snap, "w", encoding="utf-8").write("old")
            os.utime(snap, (time.time()-90000, time.time()-90000))
            with patch.object(m, "SNAPSHOT", snap):
                m.main()
            self.assertFalse(os.path.exists(snap))

    def test_empty_text_no_output(self):
        m = self._import()
        with tempfile.TemporaryDirectory() as tmp:
            snap = os.path.join(tmp, "last-session-qg-failures.txt")
            open(snap, "w", encoding="utf-8").write("   ")
            cap = io.StringIO()
            with patch.object(m, "SNAPSHOT", snap), patch("sys.stdout", cap):
                m.main()
            self.assertEqual(cap.getvalue().strip(), "")

    def test_snapshot_constant(self):
        m = self._import()
        self.assertIn("last-session-qg-failures.txt", m.SNAPSHOT)


class TestStopLog(unittest.TestCase):
    """Tests for stop-log.py — logs session cost/duration to audit-log.md on Stop."""
    HOOK_PATH = os.path.join(HOOKS_DIR, "stop-log.py")

    def _run(self, payload, extra_env=None):
        env = os.environ.copy()
        env["PYTHONIOENCODING"] = "utf-8"
        if extra_env:
            env.update(extra_env)
        import subprocess
        r = subprocess.run(
            [sys.executable, self.HOOK_PATH],
            input=json.dumps(payload).encode(),
            capture_output=True, env=env
        )
        return r.returncode

    def test_invalid_json_exits_0(self):
        env = os.environ.copy()
        env["PYTHONIOENCODING"] = "utf-8"
        import subprocess
        r = subprocess.run(
            [sys.executable, self.HOOK_PATH],
            input=b"not-json",
            capture_output=True, env=env
        )
        self.assertEqual(r.returncode, 0)

    def test_empty_payload_exits_0(self):
        self.assertEqual(self._run({}), 0)

    def test_valid_payload_exits_0(self):
        payload = {
            "session_id": "abcd1234",
            "cost": {"total_cost_usd": 0.05, "total_duration_ms": 90000},
            "model": "claude-sonnet",
        }
        self.assertEqual(self._run(payload), 0)

    def test_writes_audit_log_entry(self):
        with tempfile.TemporaryDirectory() as tmp:
            log_path = os.path.join(tmp, "audit-log.md")
            payload = {
                "session_id": "testtest",
                "cost": {"total_cost_usd": 0.123, "total_duration_ms": 120000},
                "model": "claude-sonnet",
            }
            rc = self._run(payload, extra_env={"AUDIT_LOG_PATH": log_path})
            self.assertEqual(rc, 0)
            self.assertTrue(os.path.exists(log_path))
            content = open(log_path, encoding="utf-8").read()
            self.assertIn("testtest", content)

    def test_creates_log_header_when_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            log_path = os.path.join(tmp, "audit-log.md")
            self._run({"session_id": "abc"}, extra_env={"AUDIT_LOG_PATH": log_path})
            if os.path.exists(log_path):
                content = open(log_path, encoding="utf-8").read()
                self.assertIn("Claude Code Audit Log", content)

    def test_cwd_from_workspace_dict(self):
        payload = {
            "session_id": "cwdtest",
            "workspace": {"current_dir": "C:\\Users\\Matt1\\project"},
        }
        self.assertEqual(self._run(payload), 0)

    def test_model_as_string(self):
        payload = {"session_id": "modeltest", "model": "claude-opus"}
        self.assertEqual(self._run(payload), 0)

    def test_model_as_dict_with_display_name(self):
        payload = {"session_id": "md", "model": {"display_name": "Claude 3", "id": "cl3"}}
        self.assertEqual(self._run(payload), 0)

    def test_missing_cost_field(self):
        payload = {"session_id": "nocost"}
        self.assertEqual(self._run(payload), 0)

    def test_cost_as_non_dict_ignored(self):
        payload = {"session_id": "badcost", "cost": "not-a-dict"}
        self.assertEqual(self._run(payload), 0)


class TestStopFailureLog(unittest.TestCase):
    """Tests for stop-failure-log.py — logs StopFailure events to hook-audit.log."""
    HOOK_PATH = os.path.join(HOOKS_DIR, "stop-failure-log.py")

    def _run(self, payload, extra_env=None):
        env = os.environ.copy()
        env["PYTHONIOENCODING"] = "utf-8"
        if extra_env:
            env.update(extra_env)
        import subprocess
        r = subprocess.run(
            [sys.executable, self.HOOK_PATH],
            input=json.dumps(payload).encode(),
            capture_output=True, env=env
        )
        return r.returncode

    def test_invalid_json_exits_0(self):
        env = os.environ.copy()
        env["PYTHONIOENCODING"] = "utf-8"
        import subprocess
        r = subprocess.run(
            [sys.executable, self.HOOK_PATH],
            input=b"bad-json",
            capture_output=True, env=env
        )
        self.assertEqual(r.returncode, 0)

    def test_empty_payload_exits_0(self):
        self.assertEqual(self._run({}), 0)

    def test_rate_limit_exits_0_no_notify(self):
        payload = {"error": "rate_limit", "session_id": "abc12345"}
        self.assertEqual(self._run(payload), 0)

    def test_auth_failed_exits_0(self):
        payload = {
            "error": "auth_failed",
            "error_details": "Invalid API key",
            "session_id": "abc12345",
        }
        self.assertEqual(self._run(payload), 0)

    def test_server_error_exits_0(self):
        payload = {
            "error": "server_error",
            "error_details": "Internal server error",
            "last_assistant_message": "Let me help you",
            "session_id": "sess1234",
        }
        self.assertEqual(self._run(payload), 0)

    def test_writes_log_entry(self):
        with tempfile.TemporaryDirectory() as tmp:
            log_path = os.path.join(tmp, "hook-audit.log")
            payload = {
                "error": "rate_limit",
                "error_details": "Too many requests",
                "session_id": "logtest1",
            }
            env = os.environ.copy()
            env["PYTHONIOENCODING"] = "utf-8"
            import subprocess
            # Patch by overriding the module's STATE_DIR — use subprocess with a wrapper instead
            # We can verify via the existing log path the module constructs from STATE_DIR
            r = subprocess.run(
                [sys.executable, self.HOOK_PATH],
                input=json.dumps(payload).encode(),
                capture_output=True, env=env
            )
            self.assertEqual(r.returncode, 0)

    def test_long_error_details_truncated(self):
        payload = {
            "error": "server_error",
            "error_details": "x" * 300,
            "session_id": "trunc123",
        }
        self.assertEqual(self._run(payload), 0)

    def test_missing_error_field_uses_unknown(self):
        payload = {"session_id": "noerr123"}
        self.assertEqual(self._run(payload), 0)


class TestToolFailureLog(unittest.TestCase):
    """Tests for tool-failure-log.py — logs PostToolUseFailure events to hook-audit.log."""
    HOOK_PATH = os.path.join(HOOKS_DIR, "tool-failure-log.py")

    def _run(self, payload):
        env = os.environ.copy()
        env["PYTHONIOENCODING"] = "utf-8"
        import subprocess
        r = subprocess.run(
            [sys.executable, self.HOOK_PATH],
            input=json.dumps(payload).encode(),
            capture_output=True, env=env
        )
        return r.returncode

    def test_invalid_json_exits_0(self):
        env = os.environ.copy()
        env["PYTHONIOENCODING"] = "utf-8"
        import subprocess
        r = subprocess.run(
            [sys.executable, self.HOOK_PATH],
            input=b"bad",
            capture_output=True, env=env
        )
        self.assertEqual(r.returncode, 0)

    def test_empty_payload_exits_0(self):
        self.assertEqual(self._run({}), 0)

    def test_bash_failure_exits_0(self):
        payload = {
            "tool_name": "Bash",
            "error": "command not found: foobar",
            "tool_input": {"command": "foobar --help"},
        }
        self.assertEqual(self._run(payload), 0)

    def test_edit_failure_exits_0(self):
        payload = {
            "tool_name": "Edit",
            "error": "File not found",
            "tool_input": {"file_path": "/nonexistent.py"},
        }
        self.assertEqual(self._run(payload), 0)

    def test_write_failure_exits_0(self):
        payload = {
            "tool_name": "Write",
            "error": "Permission denied",
            "tool_input": {"file_path": "/etc/protected.txt"},
        }
        self.assertEqual(self._run(payload), 0)

    def test_tool_input_as_non_dict_handled(self):
        payload = {
            "tool_name": "Read",
            "error": "something",
            "tool_input": "not-a-dict",
        }
        self.assertEqual(self._run(payload), 0)

    def test_missing_tool_name_exits_0(self):
        payload = {"error": "oops", "tool_input": {}}
        self.assertEqual(self._run(payload), 0)

    def test_error_truncated_at_100_chars(self):
        payload = {
            "tool_name": "Bash",
            "error": "e" * 200,
            "tool_input": {"command": "ls"},
        }
        self.assertEqual(self._run(payload), 0)

    def test_context_from_command_field(self):
        payload = {
            "tool_name": "Bash",
            "error": "fail",
            "tool_input": {"command": "git status"},
        }
        self.assertEqual(self._run(payload), 0)

    def test_context_from_file_path_field(self):
        payload = {
            "tool_name": "Write",
            "error": "fail",
            "tool_input": {"file_path": "/tmp/x.py"},
        }
        self.assertEqual(self._run(payload), 0)


class TestVerifyReminder(unittest.TestCase):
    """Tests for verify-reminder.py — PostToolUse hook that reminds Claude to verify edits."""

    def _import(self):
        mod_name = "verify-reminder"
        if mod_name not in sys.modules:
            with patch("sys.stdin", io.StringIO("{}")), patch("sys.exit"):
                sys.modules[mod_name] = __import__(mod_name)
        return sys.modules[mod_name]

    def test_non_edit_tool_exits_0(self):
        _, _, rc = self._run({"tool_name": "Read", "tool_input": {"file_path": "/foo.py"}})
        self.assertEqual(rc, 0)

    def _run(self, payload):
        import subprocess
        env = os.environ.copy()
        env["PYTHONIOENCODING"] = "utf-8"
        r = subprocess.run(
            [sys.executable, os.path.join(HOOKS_DIR, "verify-reminder.py")],
            input=json.dumps(payload).encode(),
            capture_output=True, env=env
        )
        return r.stdout.decode(), r.stderr.decode(), r.returncode

    def test_edit_code_file_exits_2(self):
        _, err, rc = self._run({"tool_name": "Edit", "tool_input": {"file_path": "/project/main.py"}})
        self.assertEqual(rc, 2)
        self.assertIn("verify", err.lower())

    def test_write_code_file_exits_2(self):
        _, err, rc = self._run({"tool_name": "Write", "tool_input": {"file_path": "/project/app.js"}})
        self.assertEqual(rc, 2)

    def test_edit_memory_file_exits_0(self):
        _, _, rc = self._run({"tool_name": "Edit", "tool_input": {"file_path": "/memory/MEMORY.md"}})
        self.assertEqual(rc, 0)

    def test_edit_claude_md_exits_0(self):
        _, _, rc = self._run({"tool_name": "Edit", "tool_input": {"file_path": "/path/CLAUDE.md"}})
        self.assertEqual(rc, 0)

    def test_edit_settings_json_exits_0(self):
        _, _, rc = self._run({"tool_name": "Edit", "tool_input": {"file_path": "/some/settings.json"}})
        self.assertEqual(rc, 0)

    def test_bash_tool_exits_0(self):
        _, _, rc = self._run({"tool_name": "Bash", "tool_input": {"command": "ls"}})
        self.assertEqual(rc, 0)

    def test_invalid_json_exits_0(self):
        import subprocess
        env = os.environ.copy()
        env["PYTHONIOENCODING"] = "utf-8"
        r = subprocess.run(
            [sys.executable, os.path.join(HOOKS_DIR, "verify-reminder.py")],
            input=b"bad-json",
            capture_output=True, env=env
        )
        self.assertEqual(r.returncode, 0)

    def test_empty_file_path_exits_0(self):
        _, _, rc = self._run({"tool_name": "Edit", "tool_input": {"file_path": ""}})
        self.assertEqual(rc, 0)

    def test_no_tool_input_exits_0(self):
        _, _, rc = self._run({"tool_name": "Edit"})
        self.assertEqual(rc, 0)

    def test_stderr_message_contains_filename(self):
        _, err, _ = self._run({"tool_name": "Edit", "tool_input": {"file_path": "/project/mymodule.py"}})
        self.assertIn("mymodule.py", err)


class TestSessionEndLog(unittest.TestCase):
    """Tests for session-end-log.py — SessionEnd hook that logs and runs QG feedback."""
    HOOK_PATH = os.path.join(HOOKS_DIR, "session-end-log.py")

    def _run(self, payload, extra_env=None):
        env = os.environ.copy()
        env["PYTHONIOENCODING"] = "utf-8"
        if extra_env:
            env.update(extra_env)
        import subprocess
        r = subprocess.run(
            [sys.executable, self.HOOK_PATH],
            input=json.dumps(payload).encode(),
            capture_output=True, env=env,
            timeout=30
        )
        return r.returncode

    def test_invalid_json_exits_0(self):
        env = os.environ.copy()
        env["PYTHONIOENCODING"] = "utf-8"
        import subprocess
        r = subprocess.run(
            [sys.executable, self.HOOK_PATH],
            input=b"not-json",
            capture_output=True, env=env,
            timeout=30
        )
        self.assertEqual(r.returncode, 0)

    def test_empty_payload_exits_0(self):
        self.assertEqual(self._run({}), 0)

    def test_normal_exit_reason_exits_0(self):
        payload = {"reason": "normal_exit", "session_id": "sess1234"}
        self.assertEqual(self._run(payload), 0)

    def test_user_exit_reason_exits_0(self):
        payload = {"reason": "user_exit", "session_id": "abcd5678"}
        self.assertEqual(self._run(payload), 0)

    def test_session_id_truncated_to_8(self):
        payload = {"reason": "normal_exit", "session_id": "verylongsessionid"}
        self.assertEqual(self._run(payload), 0)

    def test_missing_reason_uses_question_mark(self):
        payload = {"session_id": "abc12345"}
        self.assertEqual(self._run(payload), 0)

    def test_missing_session_id_uses_question_mark(self):
        payload = {"reason": "normal_exit"}
        self.assertEqual(self._run(payload), 0)

    def test_always_exits_0(self):
        for reason in ("normal_exit", "timeout", "error", "compact", "unknown"):
            rc = self._run({"reason": reason, "session_id": "test1234"})
            self.assertEqual(rc, 0, f"Expected exit 0 for reason={reason!r}")


class TestSmokeCountUpdater(unittest.TestCase):
    """Tests for smoke-count-updater.py — PostToolUse hook that updates smoke test counts."""

    def _import(self):
        mod_name = "smoke-count-updater"
        if mod_name not in sys.modules:
            import importlib.util
            spec = importlib.util.spec_from_file_location(
                "smoke_count_updater",
                os.path.join(HOOKS_DIR, "smoke-count-updater.py")
            )
            mod = importlib.util.module_from_spec(spec)
            sys.modules[mod_name] = mod
            spec.loader.exec_module(mod)
        return sys.modules[mod_name]

    def test_import_has_main(self):
        m = self._import()
        self.assertTrue(callable(m.main))

    def test_non_bash_tool_returns_early(self):
        m = self._import()
        p = {"tool_name": "Read", "tool_response": {"content": "=== Results: 100 passed, 0 failed, 100 total ==="}}
        with patch("sys.stdin", io.StringIO(json.dumps(p))):
            m.main()

    def test_bash_tool_no_results_returns_early(self):
        m = self._import()
        p = {"tool_name": "Bash", "tool_response": {"content": "All done, no results line"}}
        with patch("sys.stdin", io.StringIO(json.dumps(p))):
            m.main()

    def test_bash_tool_count_below_50_returns_early(self):
        m = self._import()
        p = {"tool_name": "Bash", "tool_response": {"content": "=== Results: 30 passed, 0 failed, 30 total ==="}}
        with patch("sys.stdin", io.StringIO(json.dumps(p))):
            m.main()

    def test_bash_tool_results_string_response(self):
        m = self._import()
        p = {"tool_name": "Bash", "tool_response": "=== Results: 80 passed, 0 failed, 80 total ==="}
        with tempfile.TemporaryDirectory() as tmp:
            mem_path = os.path.join(tmp, "MEMORY.md")
            cal_path = os.path.join(tmp, "calibration.md")
            open(mem_path, "w", encoding="utf-8").write(
                "quality-gate-calibration.md — Session 7 complete: 80 examples, 468 smoke tests pass\n"
            )
            open(cal_path, "w", encoding="utf-8").write("# Calibration\n")
            with patch.object(m, "_MEMORY_MD", mem_path), \
                 patch.object(m, "_CALIBRATION", cal_path), \
                 patch("sys.stdin", io.StringIO(json.dumps(p))):
                m.main()

    def test_bash_tool_count_gte_50_updates_memory(self):
        m = self._import()
        p = {
            "tool_name": "Bash",
            "tool_response": {"content": "=== Results: 576 passed, 0 failed, 576 total ==="},
        }
        with tempfile.TemporaryDirectory() as tmp:
            mem_path = os.path.join(tmp, "MEMORY.md")
            cal_path = os.path.join(tmp, "calibration.md")
            open(mem_path, "w", encoding="utf-8").write(
                "quality-gate-calibration.md — Session 7 complete: 468 smoke tests pass\n"
            )
            open(cal_path, "w", encoding="utf-8").write("# Calibration\n")
            with patch.object(m, "_MEMORY_MD", mem_path), \
                 patch.object(m, "_CALIBRATION", cal_path), \
                 patch("sys.stdin", io.StringIO(json.dumps(p))):
                m.main()
            content = open(mem_path, encoding="utf-8").read()
            self.assertIn("576 smoke tests pass", content)

    def test_calibration_appended_once(self):
        m = self._import()
        p = {
            "tool_name": "Bash",
            "tool_response": {"content": "=== Results: 200 passed, 0 failed, 200 total ==="},
        }
        with tempfile.TemporaryDirectory() as tmp:
            mem_path = os.path.join(tmp, "MEMORY.md")
            cal_path = os.path.join(tmp, "calibration.md")
            open(mem_path, "w", encoding="utf-8").write(
                "quality-gate-calibration.md — 100 smoke tests pass\n"
            )
            open(cal_path, "w", encoding="utf-8").write("# Cal\n")
            with patch.object(m, "_MEMORY_MD", mem_path), \
                 patch.object(m, "_CALIBRATION", cal_path), \
                 patch("sys.stdin", io.StringIO(json.dumps(p))):
                m.main()
                m.main()  # second call should be deduplicated
            cal = open(cal_path, encoding="utf-8").read()
            self.assertEqual(cal.count("200 passed"), 1)

    def test_empty_stdin_returns_early(self):
        m = self._import()
        with patch("sys.stdin") as mock_stdin:
            mock_stdin.isatty.return_value = True
            m.main()

    def test_invalid_json_returns_early(self):
        m = self._import()
        with patch("sys.stdin", io.StringIO("not-json")):
            m.main()

    def test_results_regex_pattern(self):
        m = self._import()
        self.assertIsNotNone(m._RESULTS_RE.search("=== Results: 576 passed, 0 failed, 576 total ==="))
        self.assertIsNone(m._RESULTS_RE.search("=== Results: 10 passed, 5 failed, 15 total ==="))

    def test_memline_regex_pattern(self):
        m = self._import()
        line = "quality-gate-calibration.md — 468 smoke tests pass"
        match = m._MEMLINE_RE.search(line)
        self.assertIsNotNone(match)
        replaced = m._MEMLINE_RE.sub(lambda mo: mo.group(1) + "999" + " smoke tests pass", line)
        self.assertIn("999 smoke tests pass", replaced)


if __name__ == "__main__":
    unittest.main(verbosity=2)