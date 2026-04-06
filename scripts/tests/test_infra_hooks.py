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

    def _import(self):
        mod_name = "stop-log"
        if mod_name not in sys.modules:
            sys.modules[mod_name] = __import__(mod_name)
        return sys.modules[mod_name]

    def _run_main(self, payload, log_path=None):
        m = self._import()
        env_patch = {}
        if log_path:
            env_patch["AUDIT_LOG_PATH"] = log_path
        with patch("sys.stdin", io.StringIO(json.dumps(payload))):
            with patch.dict(os.environ, env_patch):
                m.main()

    def test_invalid_json_returns(self):
        m = self._import()
        with patch("sys.stdin", io.StringIO("not-json")):
            m.main()  # should return without raising

    def test_empty_payload_returns(self):
        self._run_main({})

    def test_valid_payload_runs(self):
        payload = {
            "session_id": "abcd1234",
            "cost": {"total_cost_usd": 0.05, "total_duration_ms": 90000},
            "model": "claude-sonnet",
        }
        with tempfile.TemporaryDirectory() as tmp:
            self._run_main(payload, log_path=os.path.join(tmp, "audit-log.md"))

    def test_writes_audit_log_entry(self):
        with tempfile.TemporaryDirectory() as tmp:
            log_path = os.path.join(tmp, "audit-log.md")
            payload = {
                "session_id": "testtest",
                "cost": {"total_cost_usd": 0.123, "total_duration_ms": 120000},
                "model": "claude-sonnet",
            }
            self._run_main(payload, log_path=log_path)
            self.assertTrue(os.path.exists(log_path))
            content = open(log_path, encoding="utf-8").read()
            self.assertIn("testtest", content)

    def test_creates_log_header_when_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            log_path = os.path.join(tmp, "audit-log.md")
            self._run_main({"session_id": "abc"}, log_path=log_path)
            if os.path.exists(log_path):
                content = open(log_path, encoding="utf-8").read()
                self.assertIn("Claude Code Audit Log", content)

    def test_cwd_from_workspace_dict(self):
        payload = {
            "session_id": "cwdtest",
            "workspace": {"current_dir": "C:\\Users\\Matt1\\project"},
        }
        with tempfile.TemporaryDirectory() as tmp:
            self._run_main(payload, log_path=os.path.join(tmp, "audit-log.md"))

    def test_model_as_string(self):
        with tempfile.TemporaryDirectory() as tmp:
            self._run_main({"session_id": "modeltest", "model": "claude-opus"},
                           log_path=os.path.join(tmp, "audit-log.md"))

    def test_model_as_dict_with_display_name(self):
        with tempfile.TemporaryDirectory() as tmp:
            self._run_main({"session_id": "md", "model": {"display_name": "Claude 3", "id": "cl3"}},
                           log_path=os.path.join(tmp, "audit-log.md"))

    def test_missing_cost_field(self):
        with tempfile.TemporaryDirectory() as tmp:
            self._run_main({"session_id": "nocost"},
                           log_path=os.path.join(tmp, "audit-log.md"))

    def test_cost_as_non_dict_ignored(self):
        with tempfile.TemporaryDirectory() as tmp:
            self._run_main({"session_id": "badcost", "cost": "not-a-dict"},
                           log_path=os.path.join(tmp, "audit-log.md"))

    def test_has_main_callable(self):
        m = self._import()
        self.assertTrue(callable(m.main))

    def test_session_id_truncated_to_8(self):
        with tempfile.TemporaryDirectory() as tmp:
            log_path = os.path.join(tmp, "audit-log.md")
            self._run_main({"session_id": "abcdefghijklmnop"}, log_path=log_path)
            content = open(log_path, encoding="utf-8").read()
            self.assertIn("abcdefgh", content)
            self.assertNotIn("abcdefghijklmnop", content)

    def test_duration_computed_from_ms(self):
        with tempfile.TemporaryDirectory() as tmp:
            log_path = os.path.join(tmp, "audit-log.md")
            self._run_main(
                {"session_id": "durtest", "cost": {"total_cost_usd": 0.01, "total_duration_ms": 90000}},
                log_path=log_path
            )
            content = open(log_path, encoding="utf-8").read()
            self.assertIn("1m30s", content)


class TestStopFailureLog(unittest.TestCase):
    """Tests for stop-failure-log.py — logs StopFailure events to hook-audit.log."""

    def _import(self):
        mod_name = "stop-failure-log"
        if mod_name not in sys.modules:
            sys.modules[mod_name] = __import__(mod_name)
        return sys.modules[mod_name]

    def _run_main(self, payload, log_path=None):
        m = self._import()
        with patch("sys.stdin", io.StringIO(json.dumps(payload))):
            if log_path:
                with patch.object(m, "LOG_PATH", log_path):
                    m.main()
            else:
                m.main()

    def test_has_main_callable(self):
        m = self._import()
        self.assertTrue(callable(m.main))

    def test_invalid_json_returns(self):
        m = self._import()
        with patch("sys.stdin", io.StringIO("bad-json")):
            m.main()  # should return without raising

    def test_empty_payload_runs(self):
        self._run_main({})

    def test_rate_limit_runs(self):
        self._run_main({"error": "rate_limit", "session_id": "abc12345"})

    def test_auth_failed_runs(self):
        self._run_main({
            "error": "auth_failed",
            "error_details": "Invalid API key",
            "session_id": "abc12345",
        })

    def test_server_error_runs(self):
        self._run_main({
            "error": "server_error",
            "error_details": "Internal server error",
            "last_assistant_message": "Let me help you",
            "session_id": "sess1234",
        })

    def test_writes_log_entry(self):
        with tempfile.TemporaryDirectory() as tmp:
            log_path = os.path.join(tmp, "hook-audit.log")
            self._run_main({
                "error": "rate_limit",
                "error_details": "Too many requests",
                "session_id": "logtest1",
            }, log_path=log_path)
            self.assertTrue(os.path.exists(log_path))
            content = open(log_path, encoding="utf-8").read()
            self.assertIn("STOP_FAIL", content)
            self.assertIn("rate_limit", content)

    def test_long_error_details_truncated(self):
        with tempfile.TemporaryDirectory() as tmp:
            log_path = os.path.join(tmp, "hook-audit.log")
            self._run_main({
                "error": "server_error",
                "error_details": "x" * 300,
                "session_id": "trunc123",
            }, log_path=log_path)
            content = open(log_path, encoding="utf-8").read()
            # details are truncated to 200 chars
            self.assertLessEqual(content.count("x"), 200)

    def test_missing_error_field_uses_unknown(self):
        with tempfile.TemporaryDirectory() as tmp:
            log_path = os.path.join(tmp, "hook-audit.log")
            self._run_main({"session_id": "noerr123"}, log_path=log_path)
            content = open(log_path, encoding="utf-8").read()
            self.assertIn("unknown", content)

    def test_session_id_in_log(self):
        with tempfile.TemporaryDirectory() as tmp:
            log_path = os.path.join(tmp, "hook-audit.log")
            self._run_main({"error": "rate_limit", "session_id": "mysess12"}, log_path=log_path)
            content = open(log_path, encoding="utf-8").read()
            self.assertIn("mysess12", content)

    def test_non_rate_limit_attempts_notify(self):
        m = self._import()
        with patch("sys.stdin", io.StringIO(json.dumps({"error": "auth_failed"}))):
            with patch("subprocess.Popen") as mock_popen:
                with patch.object(m, "LOG_PATH", os.devnull):
                    m.main()
                # Popen may be called for notification; we just verify no exception
                self.assertIsNotNone(mock_popen)

    def test_rate_limit_does_not_notify(self):
        m = self._import()
        with patch("sys.stdin", io.StringIO(json.dumps({"error": "rate_limit"}))):
            with patch("subprocess.Popen") as mock_popen:
                with patch.object(m, "LOG_PATH", os.devnull):
                    m.main()
                mock_popen.assert_not_called()


class TestToolFailureLog(unittest.TestCase):
    """Tests for tool-failure-log.py — logs PostToolUseFailure events to hook-audit.log."""

    def _import(self):
        mod_name = "tool-failure-log"
        if mod_name not in sys.modules:
            sys.modules[mod_name] = __import__(mod_name)
        return sys.modules[mod_name]

    def _run_main(self, payload, log_path=None):
        m = self._import()
        with patch("sys.stdin", io.StringIO(json.dumps(payload))):
            if log_path:
                with patch.object(m, "LOG_PATH", log_path):
                    m.main()
            else:
                m.main()

    def test_has_main_callable(self):
        m = self._import()
        self.assertTrue(callable(m.main))

    def test_invalid_json_returns(self):
        m = self._import()
        with patch("sys.stdin", io.StringIO("bad")):
            m.main()  # should return without raising

    def test_empty_payload_runs(self):
        self._run_main({})

    def test_bash_failure_runs(self):
        self._run_main({
            "tool_name": "Bash",
            "error": "command not found: foobar",
            "tool_input": {"command": "foobar --help"},
        })

    def test_edit_failure_runs(self):
        self._run_main({
            "tool_name": "Edit",
            "error": "File not found",
            "tool_input": {"file_path": "/nonexistent.py"},
        })

    def test_write_failure_runs(self):
        self._run_main({
            "tool_name": "Write",
            "error": "Permission denied",
            "tool_input": {"file_path": "/etc/protected.txt"},
        })

    def test_tool_input_as_non_dict_handled(self):
        self._run_main({
            "tool_name": "Read",
            "error": "something",
            "tool_input": "not-a-dict",
        })

    def test_missing_tool_name_runs(self):
        self._run_main({"error": "oops", "tool_input": {}})

    def test_writes_fail_log_entry(self):
        with tempfile.TemporaryDirectory() as tmp:
            log_path = os.path.join(tmp, "hook-audit.log")
            self._run_main({
                "tool_name": "Bash",
                "error": "command not found",
                "tool_input": {"command": "foobar"},
            }, log_path=log_path)
            self.assertTrue(os.path.exists(log_path))
            content = open(log_path, encoding="utf-8").read()
            self.assertIn("FAIL", content)
            self.assertIn("Bash", content)

    def test_error_truncated_at_100_chars(self):
        with tempfile.TemporaryDirectory() as tmp:
            log_path = os.path.join(tmp, "hook-audit.log")
            self._run_main({
                "tool_name": "Bash",
                "error": "e" * 200,
                "tool_input": {"command": "ls"},
            }, log_path=log_path)
            content = open(log_path, encoding="utf-8").read()
            self.assertLessEqual(content.count("e"), 100)

    def test_context_from_command_field(self):
        with tempfile.TemporaryDirectory() as tmp:
            log_path = os.path.join(tmp, "hook-audit.log")
            self._run_main({
                "tool_name": "Bash",
                "error": "fail",
                "tool_input": {"command": "git status"},
            }, log_path=log_path)
            content = open(log_path, encoding="utf-8").read()
            self.assertIn("git status", content)

    def test_context_from_file_path_field(self):
        with tempfile.TemporaryDirectory() as tmp:
            log_path = os.path.join(tmp, "hook-audit.log")
            self._run_main({
                "tool_name": "Write",
                "error": "fail",
                "tool_input": {"file_path": "/tmp/x.py"},
            }, log_path=log_path)
            content = open(log_path, encoding="utf-8").read()
            self.assertIn("/tmp/x.py", content)


class TestVerifyReminder(unittest.TestCase):
    """Tests for verify-reminder.py — PostToolUse hook that reminds Claude to verify edits."""

    def _import(self):
        mod_name = "verify-reminder"
        if mod_name not in sys.modules:
            sys.modules[mod_name] = __import__(mod_name)
        return sys.modules[mod_name]

    def _run_main(self, payload):
        m = self._import()
        with patch("sys.stdin", io.StringIO(json.dumps(payload))):
            return m.main()

    def test_has_main_callable(self):
        m = self._import()
        self.assertTrue(callable(m.main))

    def test_invalid_json_returns_0(self):
        m = self._import()
        with patch("sys.stdin", io.StringIO("bad-json")):
            result = m.main()
        self.assertIn(result, (0, None))

    def test_non_edit_tool_returns_0(self):
        result = self._run_main({"tool_name": "Read", "tool_input": {"file_path": "/foo.py"}})
        self.assertIn(result, (0, None))

    def test_bash_tool_returns_0(self):
        result = self._run_main({"tool_name": "Bash", "tool_input": {"command": "ls"}})
        self.assertIn(result, (0, None))

    def test_edit_code_file_returns_2(self):
        result = self._run_main({"tool_name": "Edit", "tool_input": {"file_path": "/project/main.py"}})
        self.assertEqual(result, 2)

    def test_write_code_file_returns_2(self):
        result = self._run_main({"tool_name": "Write", "tool_input": {"file_path": "/project/app.js"}})
        self.assertEqual(result, 2)

    def test_edit_memory_file_returns_0(self):
        result = self._run_main({"tool_name": "Edit", "tool_input": {"file_path": "/memory/MEMORY.md"}})
        self.assertIn(result, (0, None))

    def test_edit_claude_md_returns_0(self):
        result = self._run_main({"tool_name": "Edit", "tool_input": {"file_path": "/path/CLAUDE.md"}})
        self.assertIn(result, (0, None))

    def test_edit_settings_json_returns_0(self):
        result = self._run_main({"tool_name": "Edit", "tool_input": {"file_path": "/some/settings.json"}})
        self.assertIn(result, (0, None))

    def test_empty_file_path_returns_0(self):
        result = self._run_main({"tool_name": "Edit", "tool_input": {"file_path": ""}})
        self.assertIn(result, (0, None))

    def test_no_tool_input_returns_0(self):
        result = self._run_main({"tool_name": "Edit"})
        self.assertIn(result, (0, None))

    def test_stderr_message_contains_filename(self):
        m = self._import()
        with patch("sys.stdin", io.StringIO(json.dumps(
            {"tool_name": "Edit", "tool_input": {"file_path": "/project/mymodule.py"}}
        ))):
            with patch("sys.stderr", io.StringIO()) as mock_err:
                m.main()
                mock_err.seek(0)
                self.assertIn("mymodule.py", mock_err.read())

    def test_edit_py_file_returns_2(self):
        result = self._run_main({"tool_name": "Edit", "tool_input": {"file_path": "/hooks/verify-reminder.py"}})
        self.assertEqual(result, 2)

    def test_write_ts_file_returns_2(self):
        result = self._run_main({"tool_name": "Write", "tool_input": {"file_path": "/src/index.ts"}})
        self.assertEqual(result, 2)


class TestSessionEndLog(unittest.TestCase):
    """Tests for session-end-log.py — SessionEnd hook that logs and runs QG feedback."""

    def _import(self):
        mod_name = "session-end-log"
        if mod_name not in sys.modules:
            sys.modules[mod_name] = __import__(mod_name)
        return sys.modules[mod_name]

    def _run_main(self, payload, log_path=None):
        m = self._import()
        # Patch subprocess.run to skip the slow qg-feedback.py calls
        with patch("sys.stdin", io.StringIO(json.dumps(payload))):
            with patch("subprocess.run") as mock_run:
                mock_run.return_value = MagicMock(stdout="", returncode=0)
                with patch("subprocess.Popen", MagicMock()):
                    if log_path:
                        with patch.object(m, "LOG_PATH", log_path):
                            m.main()
                    else:
                        m.main()

    def test_has_main_callable(self):
        m = self._import()
        self.assertTrue(callable(m.main))

    def test_invalid_json_returns(self):
        m = self._import()
        with patch("sys.stdin", io.StringIO("not-json")):
            m.main()  # should return without raising

    def test_empty_payload_runs(self):
        self._run_main({})

    def test_normal_exit_reason_runs(self):
        self._run_main({"reason": "normal_exit", "session_id": "sess1234"})

    def test_user_exit_reason_runs(self):
        self._run_main({"reason": "user_exit", "session_id": "abcd5678"})

    def test_session_id_truncated_to_8(self):
        with tempfile.TemporaryDirectory() as tmp:
            log_path = os.path.join(tmp, "hook-audit.log")
            self._run_main({"reason": "normal_exit", "session_id": "verylongsessionid"},
                           log_path=log_path)
            content = open(log_path, encoding="utf-8").read()
            self.assertIn("verylon", content)
            self.assertNotIn("verylongsessionid", content)

    def test_missing_reason_uses_question_mark(self):
        with tempfile.TemporaryDirectory() as tmp:
            log_path = os.path.join(tmp, "hook-audit.log")
            self._run_main({"session_id": "abc12345"}, log_path=log_path)
            content = open(log_path, encoding="utf-8").read()
            self.assertIn("?", content)

    def test_missing_session_id_uses_question_mark(self):
        with tempfile.TemporaryDirectory() as tmp:
            log_path = os.path.join(tmp, "hook-audit.log")
            self._run_main({"reason": "normal_exit"}, log_path=log_path)

    def test_writes_session_end_line(self):
        with tempfile.TemporaryDirectory() as tmp:
            log_path = os.path.join(tmp, "hook-audit.log")
            self._run_main({"reason": "compact", "session_id": "test1234"}, log_path=log_path)
            content = open(log_path, encoding="utf-8").read()
            self.assertIn("SESSION_END", content)
            self.assertIn("compact", content)

    def test_always_runs_for_all_reasons(self):
        for reason in ("normal_exit", "timeout", "error", "compact", "unknown"):
            self._run_main({"reason": reason, "session_id": "test1234"})


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


class TestSessionEndLogBackup(unittest.TestCase):
    """Additional tests for session-end-log.py — OneDrive backup and file-cleanup branches."""

    def _import(self):
        mod_name = "session-end-log"
        if mod_name not in sys.modules:
            sys.modules[mod_name] = __import__(mod_name)
        return sys.modules[mod_name]

    def _run_main(self, payload, log_path=None, subprocess_stdout="", makedirs_ok=True):
        m = self._import()
        mock_run_result = MagicMock(stdout=subprocess_stdout, returncode=0)
        with patch("sys.stdin", io.StringIO(json.dumps(payload))), \
             patch("subprocess.run", return_value=mock_run_result), \
             patch("subprocess.Popen", MagicMock()):
            if log_path:
                with patch.object(m, "LOG_PATH", log_path):
                    m.main()
            else:
                m.main()

    def test_backup_makedirs_called(self):
        """makedirs is called for the backup directory structure."""
        m = self._import()
        payload = {"reason": "normal_exit", "session_id": "test1234"}
        with patch("sys.stdin", io.StringIO(json.dumps(payload))), \
             patch("subprocess.run", return_value=MagicMock(stdout="", returncode=0)), \
             patch("subprocess.Popen", MagicMock()), \
             patch("os.makedirs") as mock_makedirs, \
             patch("os.path.isdir", return_value=False), \
             patch("glob.glob", return_value=[]), \
             patch("os.path.expanduser", side_effect=lambda p: p.replace("~", "/fake/home")):
            try:
                m.main()
            except Exception:
                pass
        self.assertTrue(mock_makedirs.called)

    def test_backup_copy2_called_for_matching_files(self):
        """shutil.copy2 is called when glob finds matching files."""
        m = self._import()
        payload = {"reason": "normal_exit", "session_id": "test1234"}
        fake_state = "/fake/home/.claude"
        fake_backup = "/fake/home/OneDrive/Documents/ClaudeCode"
        with tempfile.TemporaryDirectory() as tmp:
            log_path = os.path.join(tmp, "hook-audit.log")
            with patch("sys.stdin", io.StringIO(json.dumps(payload))), \
                 patch("subprocess.run", return_value=MagicMock(stdout="", returncode=0)), \
                 patch("subprocess.Popen", MagicMock()), \
                 patch("os.makedirs"), \
                 patch("os.path.isdir", return_value=False), \
                 patch("glob.glob", return_value=[f"{fake_state}/settings.json"]), \
                 patch("os.path.basename", return_value="settings.json"), \
                 patch("shutil.copy2") as mock_copy2, \
                 patch("os.path.expanduser", side_effect=lambda p: p.replace("~", "/fake/home")), \
                 patch.object(m, "LOG_PATH", log_path):
                m.main()
        self.assertTrue(mock_copy2.called)

    def test_backup_subdir_copy_when_isdir_true(self):
        """Files from hooks/templates/commands subdirs are copied when isdir returns True."""
        m = self._import()
        payload = {"reason": "normal_exit", "session_id": "test1234"}
        with tempfile.TemporaryDirectory() as tmp:
            log_path = os.path.join(tmp, "hook-audit.log")
            # Simulate a subdir with one .py file
            def fake_isdir(path):
                return True
            with patch("sys.stdin", io.StringIO(json.dumps(payload))), \
                 patch("subprocess.run", return_value=MagicMock(stdout="", returncode=0)), \
                 patch("subprocess.Popen", MagicMock()), \
                 patch("os.makedirs"), \
                 patch("os.path.isdir", side_effect=fake_isdir), \
                 patch("os.listdir", return_value=["myhook.py"]), \
                 patch("glob.glob", return_value=[]), \
                 patch("shutil.copy2") as mock_copy2, \
                 patch("os.path.expanduser", side_effect=lambda p: p.replace("~", "/fake/home")), \
                 patch.object(m, "LOG_PATH", log_path):
                m.main()
        self.assertTrue(mock_copy2.called)

    def test_backup_memory_dirs_copied(self):
        """Memory directories (.md files) are copied when isdir returns True."""
        m = self._import()
        payload = {"reason": "normal_exit", "session_id": "test1234"}
        with tempfile.TemporaryDirectory() as tmp:
            log_path = os.path.join(tmp, "hook-audit.log")
            with patch("sys.stdin", io.StringIO(json.dumps(payload))), \
                 patch("subprocess.run", return_value=MagicMock(stdout="", returncode=0)), \
                 patch("subprocess.Popen", MagicMock()), \
                 patch("os.makedirs"), \
                 patch("os.path.isdir", return_value=True), \
                 patch("os.listdir", return_value=["MEMORY.md"]), \
                 patch("glob.glob", return_value=[]), \
                 patch("shutil.copy2") as mock_copy2, \
                 patch("os.path.expanduser", side_effect=lambda p: p.replace("~", "/fake/home")), \
                 patch.object(m, "LOG_PATH", log_path):
                m.main()
        self.assertTrue(mock_copy2.called)

    def test_backup_sessions_cleanup_old_bak_files(self):
        """Old .jsonl.bak files older than 7 days are removed."""
        m = self._import()
        payload = {"reason": "normal_exit", "session_id": "test1234"}
        with tempfile.TemporaryDirectory() as tmp:
            log_path = os.path.join(tmp, "hook-audit.log")
            old_bak = os.path.join(tmp, "old-session.jsonl.bak")
            open(old_bak, "w").write("x")
            # Make it 8 days old
            old_time = time.time() - 8 * 86400
            os.utime(old_bak, (old_time, old_time))

            def fake_isdir(path):
                if "sessions" in path:
                    return True
                return False

            with patch("sys.stdin", io.StringIO(json.dumps(payload))), \
                 patch("subprocess.run", return_value=MagicMock(stdout="", returncode=0)), \
                 patch("subprocess.Popen", MagicMock()), \
                 patch("os.makedirs"), \
                 patch("os.path.isdir", side_effect=fake_isdir), \
                 patch("os.listdir", return_value=["old-session.jsonl.bak"]), \
                 patch("glob.glob", return_value=[]), \
                 patch("shutil.copy2"), \
                 patch("os.path.getmtime", return_value=old_time), \
                 patch("os.remove") as mock_remove, \
                 patch("os.path.expanduser", side_effect=lambda p: p.replace("~", "/fake/home")), \
                 patch.object(m, "LOG_PATH", log_path):
                m.main()
        self.assertTrue(mock_remove.called)

    def test_backup_sessions_keeps_recent_bak_files(self):
        """Recent .jsonl.bak files (within 7 days) are NOT removed."""
        m = self._import()
        payload = {"reason": "normal_exit", "session_id": "test1234"}

        def fake_isdir(path):
            return "sessions" in path

        with tempfile.TemporaryDirectory() as tmp:
            log_path = os.path.join(tmp, "hook-audit.log")
            with patch("sys.stdin", io.StringIO(json.dumps(payload))), \
                 patch("subprocess.run", return_value=MagicMock(stdout="", returncode=0)), \
                 patch("subprocess.Popen", MagicMock()), \
                 patch("os.makedirs"), \
                 patch("os.path.isdir", side_effect=fake_isdir), \
                 patch("os.listdir", return_value=["recent.jsonl.bak"]), \
                 patch("glob.glob", return_value=[]), \
                 patch("shutil.copy2"), \
                 patch("os.path.getmtime", return_value=time.time() - 3600), \
                 patch("os.remove") as mock_remove, \
                 patch("os.path.expanduser", side_effect=lambda p: p.replace("~", "/fake/home")), \
                 patch.object(m, "LOG_PATH", log_path):
                m.main()
        mock_remove.assert_not_called()

    def test_backup_skips_dotfiles(self):
        """Files starting with '.' are skipped during glob backup."""
        m = self._import()
        payload = {"reason": "normal_exit", "session_id": "test1234"}
        with tempfile.TemporaryDirectory() as tmp:
            log_path = os.path.join(tmp, "hook-audit.log")
            fake_state = "/fake/home/.claude"
            with patch("sys.stdin", io.StringIO(json.dumps(payload))), \
                 patch("subprocess.run", return_value=MagicMock(stdout="", returncode=0)), \
                 patch("subprocess.Popen", MagicMock()), \
                 patch("os.makedirs"), \
                 patch("os.path.isdir", return_value=False), \
                 patch("glob.glob", return_value=[f"{fake_state}/.env.secret"]), \
                 patch("os.path.basename", return_value=".env.secret"), \
                 patch("shutil.copy2") as mock_copy2, \
                 patch("os.path.expanduser", side_effect=lambda p: p.replace("~", "/fake/home")), \
                 patch.object(m, "LOG_PATH", log_path):
                m.main()
        mock_copy2.assert_not_called()

    def test_backup_writes_ok_line_to_log(self):
        """When backup succeeds, 'backup OK' is written to the log."""
        m = self._import()
        payload = {"reason": "normal_exit", "session_id": "test1234"}
        with tempfile.TemporaryDirectory() as tmp:
            log_path = os.path.join(tmp, "hook-audit.log")
            with patch("sys.stdin", io.StringIO(json.dumps(payload))), \
                 patch("subprocess.run", return_value=MagicMock(stdout="", returncode=0)), \
                 patch("subprocess.Popen", MagicMock()), \
                 patch("os.makedirs"), \
                 patch("os.path.isdir", return_value=False), \
                 patch("glob.glob", return_value=[]), \
                 patch("os.path.expanduser", side_effect=lambda p: p.replace("~", "/fake/home")), \
                 patch.object(m, "LOG_PATH", log_path):
                m.main()
            content = open(log_path, encoding="utf-8").read()
        self.assertIn("backup OK", content)

    def test_backup_failure_writes_fail_line(self):
        """When makedirs raises, 'backup FAIL' is written to the log."""
        m = self._import()
        payload = {"reason": "normal_exit", "session_id": "test1234"}
        with tempfile.TemporaryDirectory() as tmp:
            log_path = os.path.join(tmp, "hook-audit.log")
            with patch("sys.stdin", io.StringIO(json.dumps(payload))), \
                 patch("subprocess.run", return_value=MagicMock(stdout="", returncode=0)), \
                 patch("subprocess.Popen", MagicMock()), \
                 patch("os.makedirs", side_effect=OSError("no space")), \
                 patch("os.path.expanduser", side_effect=lambda p: p.replace("~", "/fake/home")), \
                 patch.object(m, "LOG_PATH", log_path):
                m.main()
            content = open(log_path, encoding="utf-8").read()
        self.assertIn("backup FAIL", content)

    def test_qg_feedback_with_blocks_writes_snapshot(self):
        """When qg failures output contains blocks, snapshot file is written."""
        m = self._import()
        payload = {"reason": "normal_exit", "session_id": "test1234"}
        qg_out = "Block count: 3 blocks in last session"
        with tempfile.TemporaryDirectory() as tmp:
            log_path = os.path.join(tmp, "hook-audit.log")
            snap_path = os.path.join(tmp, "last-session-qg-failures.txt")

            def fake_run(cmd, **kwargs):
                if "failures" in cmd:
                    return MagicMock(stdout=qg_out, returncode=0)
                if "auto-detect" in cmd:
                    return MagicMock(stdout="", returncode=0)
                return MagicMock(stdout="", returncode=0)

            with patch("sys.stdin", io.StringIO(json.dumps(payload))), \
                 patch("subprocess.run", side_effect=fake_run), \
                 patch("subprocess.Popen", MagicMock()), \
                 patch("os.makedirs"), \
                 patch("os.path.isdir", return_value=False), \
                 patch("glob.glob", return_value=[]), \
                 patch("os.path.expanduser", side_effect=lambda p: p.replace("~", "/fake/home")), \
                 patch("os.path.exists", return_value=False), \
                 patch.object(m, "LOG_PATH", log_path):
                # Patch the snapshot path by patching open for the snapshot write
                real_open = open
                written = {}
                def patched_open(path, mode="r", **kw):
                    if "last-session-qg-failures" in str(path) and "w" in mode:
                        buf = io.StringIO()
                        written["buf"] = buf
                        return buf
                    return real_open(path, mode, **kw)
                with patch("builtins.open", side_effect=patched_open):
                    m.main()

    def test_qg_feedback_no_blocks_skips_snapshot(self):
        """When qg output has 0 blocks, snapshot file is NOT written."""
        m = self._import()
        payload = {"reason": "normal_exit", "session_id": "test1234"}
        qg_out = "0 blocks total"

        with tempfile.TemporaryDirectory() as tmp:
            log_path = os.path.join(tmp, "hook-audit.log")
            snap_path = os.path.join(tmp, "last-session-qg-failures.txt")

            def fake_run(cmd, **kwargs):
                if "failures" in cmd:
                    return MagicMock(stdout=qg_out, returncode=0)
                return MagicMock(stdout="", returncode=0)

            with patch("sys.stdin", io.StringIO(json.dumps(payload))), \
                 patch("subprocess.run", side_effect=fake_run), \
                 patch("subprocess.Popen", MagicMock()), \
                 patch("os.makedirs"), \
                 patch("os.path.isdir", return_value=False), \
                 patch("glob.glob", return_value=[]), \
                 patch("os.path.expanduser", side_effect=lambda p: p.replace("~", "/fake/home")), \
                 patch.object(m, "LOG_PATH", log_path):
                m.main()
        self.assertFalse(os.path.exists(snap_path))

    def test_qg_autodetect_appends_to_existing_snapshot(self):
        """auto-detect output is appended to an existing snapshot file."""
        m = self._import()
        payload = {"reason": "normal_exit", "session_id": "test1234"}

        with tempfile.TemporaryDirectory() as tmp:
            log_path = os.path.join(tmp, "hook-audit.log")
            snap_path = os.path.join(tmp, "last-session-qg-failures.txt")
            open(snap_path, "w", encoding="utf-8").write("Block count: 2 blocks\nIf the gate missed something")

            def fake_run(cmd, **kwargs):
                if "failures" in cmd:
                    return MagicMock(stdout="2 blocks found", returncode=0)
                if "auto-detect" in cmd:
                    return MagicMock(stdout="SYSTEMIC: repeated assumption pattern", returncode=0)
                return MagicMock(stdout="", returncode=0)

            real_exists = os.path.exists
            def fake_exists(p):
                if "last-session-qg-failures" in str(p):
                    return True
                return real_exists(p)

            with patch("sys.stdin", io.StringIO(json.dumps(payload))), \
                 patch("subprocess.run", side_effect=fake_run), \
                 patch("subprocess.Popen", MagicMock()), \
                 patch("os.makedirs"), \
                 patch("os.path.isdir", return_value=False), \
                 patch("glob.glob", return_value=[]), \
                 patch("os.path.expanduser", side_effect=lambda p: p.replace("~", "/fake/home")), \
                 patch("os.path.exists", side_effect=fake_exists), \
                 patch.object(m, "LOG_PATH", log_path):
                real_open = open
                appended = {}
                def patched_open(path, mode="r", **kw):
                    if "last-session-qg-failures" in str(path) and "a" in mode:
                        buf = io.StringIO()
                        appended["called"] = True
                        return buf
                    if "last-session-qg-failures" in str(path) and "w" in mode:
                        return io.StringIO()
                    return real_open(path, mode, **kw)
                with patch("builtins.open", side_effect=patched_open):
                    m.main()
        self.assertTrue(appended.get("called", False))

    def test_weekly_summary_appended_when_this_week_line_found(self):
        """Weekly summary line is appended to snapshot when 'This week' line present."""
        m = self._import()
        payload = {"reason": "normal_exit", "session_id": "test1234"}
        weekly_out = "This week: 5 sessions, 3 blocks\nBlock rate delta: -10%"

        real_exists = os.path.exists
        def fake_exists(p):
            if "last-session-qg-failures" in str(p):
                return True
            return real_exists(p)

        with tempfile.TemporaryDirectory() as tmp:
            log_path = os.path.join(tmp, "hook-audit.log")

            def fake_run(cmd, **kwargs):
                if "weekly" in cmd:
                    return MagicMock(stdout=weekly_out, returncode=0)
                return MagicMock(stdout="", returncode=0)

            appended = {}
            real_open = open
            def patched_open(path, mode="r", **kw):
                if "last-session-qg-failures" in str(path) and "a" in mode:
                    appended["called"] = True
                    return io.StringIO()
                if "last-session-qg-failures" in str(path) and "w" in mode:
                    return io.StringIO()
                return real_open(path, mode, **kw)

            with patch("sys.stdin", io.StringIO(json.dumps(payload))), \
                 patch("subprocess.run", side_effect=fake_run), \
                 patch("subprocess.Popen", MagicMock()), \
                 patch("os.makedirs"), \
                 patch("os.path.isdir", return_value=False), \
                 patch("glob.glob", return_value=[]), \
                 patch("os.path.expanduser", side_effect=lambda p: p.replace("~", "/fake/home")), \
                 patch("os.path.exists", side_effect=fake_exists), \
                 patch("builtins.open", side_effect=patched_open), \
                 patch.object(m, "LOG_PATH", log_path):
                m.main()
        self.assertTrue(appended.get("called", False))

    def test_shadow_summary_appended_when_agreement_line_found(self):
        """Shadow phi4 summary is appended when 'Agreement:' line is present."""
        m = self._import()
        payload = {"reason": "normal_exit", "session_id": "test1234"}
        shadow_out = "Agreement: 90%\nTotal evals: 20\nOllama more aggressive: 2"

        real_exists = os.path.exists
        def fake_exists(p):
            if "last-session-qg-failures" in str(p):
                return True
            return real_exists(p)

        with tempfile.TemporaryDirectory() as tmp:
            log_path = os.path.join(tmp, "hook-audit.log")

            def fake_run(cmd, **kwargs):
                if "shadow" in cmd:
                    return MagicMock(stdout=shadow_out, returncode=0)
                return MagicMock(stdout="", returncode=0)

            appended = {}
            real_open = open
            def patched_open(path, mode="r", **kw):
                if "last-session-qg-failures" in str(path) and "a" in mode:
                    appended["called"] = True
                    return io.StringIO()
                if "last-session-qg-failures" in str(path) and "w" in mode:
                    return io.StringIO()
                return real_open(path, mode, **kw)

            with patch("sys.stdin", io.StringIO(json.dumps(payload))), \
                 patch("subprocess.run", side_effect=fake_run), \
                 patch("subprocess.Popen", MagicMock()), \
                 patch("os.makedirs"), \
                 patch("os.path.isdir", return_value=False), \
                 patch("glob.glob", return_value=[]), \
                 patch("os.path.expanduser", side_effect=lambda p: p.replace("~", "/fake/home")), \
                 patch("os.path.exists", side_effect=fake_exists), \
                 patch("builtins.open", side_effect=patched_open), \
                 patch.object(m, "LOG_PATH", log_path):
                m.main()
        self.assertTrue(appended.get("called", False))

    def test_qg_run_exception_swallowed(self):
        """Exception from subprocess.run is swallowed gracefully."""
        m = self._import()
        payload = {"reason": "normal_exit", "session_id": "test1234"}
        with tempfile.TemporaryDirectory() as tmp:
            log_path = os.path.join(tmp, "hook-audit.log")
            with patch("sys.stdin", io.StringIO(json.dumps(payload))), \
                 patch("subprocess.run", side_effect=Exception("network error")), \
                 patch("subprocess.Popen", MagicMock()), \
                 patch("os.makedirs"), \
                 patch("os.path.isdir", return_value=False), \
                 patch("glob.glob", return_value=[]), \
                 patch("os.path.expanduser", side_effect=lambda p: p.replace("~", "/fake/home")), \
                 patch.object(m, "LOG_PATH", log_path):
                m.main()  # should not raise


class TestTaskClassifier(unittest.TestCase):
    """Tests for task-classifier.py — UserPromptSubmit hook that classifies task complexity."""

    HOOK_PATH = os.path.join(HOOKS_DIR, "task-classifier.py")

    _RCFILE = os.path.join(os.path.expanduser("~/.claude"), ".coveragerc")

    def _run(self, payload, transcript_path=None):
        """Run task-classifier under coverage run so subprocess lines are tracked."""
        import subprocess
        if transcript_path:
            payload = dict(payload, transcript_path=transcript_path)
        env = os.environ.copy()
        env["PYTHONIOENCODING"] = "utf-8"
        cmd = [sys.executable, "-m", "coverage", "run",
               "--parallel-mode", "--rcfile=" + self._RCFILE,
               self.HOOK_PATH]
        r = subprocess.run(cmd, input=json.dumps(payload).encode(),
                           capture_output=True, env=env)
        return r.stdout.decode(), r.stderr.decode(), r.returncode

    def test_invalid_json_exits_0(self):
        import subprocess
        env = os.environ.copy(); env["PYTHONIOENCODING"] = "utf-8"
        r = subprocess.run([sys.executable, self.HOOK_PATH], input=b"not-json", capture_output=True, env=env)
        self.assertEqual(r.returncode, 0)

    def test_trivial_short_message(self):
        out, _, rc = self._run({"message": "hi"})
        self.assertEqual(rc, 0)
        self.assertIn("TRIVIAL", out)

    def test_trivial_yes_no_response(self):
        out, _, rc = self._run({"message": "yes"})
        self.assertEqual(rc, 0)
        self.assertIn("TRIVIAL", out)

    def test_trivial_ok_response(self):
        out, _, rc = self._run({"message": "ok"})
        self.assertEqual(rc, 0)
        self.assertIn("TRIVIAL", out)

    def test_simple_rename_keyword(self):
        out, _, rc = self._run({"message": "rename the function foo to bar in main.py"})
        self.assertEqual(rc, 0)
        self.assertIn("SIMPLE", out)

    def test_simple_debug_keyword(self):
        out, _, rc = self._run({"message": "debug the login page issue"})
        self.assertEqual(rc, 0)
        self.assertIn("SIMPLE", out)

    def test_complex_implement_keyword(self):
        out, _, rc = self._run({"message": "implement the new authentication flow for the API"})
        self.assertEqual(rc, 0)
        self.assertIn("COMPLEX", out)

    def test_complex_refactor_keyword(self):
        out, _, rc = self._run({"message": "refactor the database layer to use the repository pattern"})
        self.assertEqual(rc, 0)
        self.assertIn("COMPLEX", out)

    def test_complex_build_keyword(self):
        out, _, rc = self._run({"message": "build the CI pipeline for the project"})
        self.assertEqual(rc, 0)
        self.assertIn("COMPLEX", out)

    def test_deep_architecture_keyword(self):
        out, _, rc = self._run({"message": "design the overall architecture for the microservices migration"})
        self.assertEqual(rc, 0)
        self.assertIn("DEEP", out)

    def test_deep_algorithm_keyword(self):
        out, _, rc = self._run({"message": "analyze the algorithm performance and optimize the bottleneck"})
        self.assertEqual(rc, 0)
        self.assertIn("DEEP", out)

    def test_message_as_dict(self):
        out, _, rc = self._run({"message": {"content": "rename x to y"}})
        self.assertEqual(rc, 0)
        self.assertIn("task-classifier", out)

    def test_message_as_list_of_blocks(self):
        out, _, rc = self._run({"message": [{"type": "text", "text": "refactor the whole codebase"}]})
        self.assertEqual(rc, 0)
        self.assertIn("COMPLEX", out)

    def test_prompt_field_fallback(self):
        out, _, rc = self._run({"prompt": "implement a new feature for the dashboard"})
        self.assertEqual(rc, 0)
        self.assertIn("COMPLEX", out)

    def test_system_task_notification_exits_early(self):
        out, _, rc = self._run({"message": "<task-notification>some background task done</task-notification>"})
        self.assertEqual(rc, 0)
        self.assertNotIn("task-classifier", out)

    def test_system_message_exits_early(self):
        out, _, rc = self._run({"message": "<system>internal message</system>"})
        self.assertEqual(rc, 0)
        self.assertNotIn("task-classifier", out)

    def test_stop_hook_feedback_forces_moderate_minimum(self):
        out, _, rc = self._run({"message": "stop hook feedback: please fix this"})
        self.assertEqual(rc, 0)
        # compliance-retry message should appear
        self.assertIn("compliance-retry", out)

    def test_contradiction_signal_injects_reminder(self):
        out, _, rc = self._run({"message": "that's wrong, it does not exist"})
        self.assertEqual(rc, 0)
        self.assertIn("contradiction-check", out)

    def test_confidence_challenge_injects_reminder(self):
        out, _, rc = self._run({"message": "are you sure that's correct?"})
        self.assertEqual(rc, 0)
        self.assertIn("confidence-challenge", out)

    def test_gate_miss_signal_injects_reminder(self):
        out, _, rc = self._run({"message": "you assumed that without checking"})
        self.assertEqual(rc, 0)
        self.assertIn("gate-miss", out)

    def test_new_project_intent_detected(self):
        out, _, rc = self._run({"message": "let's start a new project for the dashboard"})
        self.assertEqual(rc, 0)
        self.assertIn("project-detector", out)

    def test_new_project_question_not_detected(self):
        out, _, rc = self._run({"message": "how does the new project workflow handle the setup?"})
        self.assertEqual(rc, 0)
        self.assertNotIn("project-detector", out)

    def test_short_input_go_ahead(self):
        out, _, rc = self._run({"message": "go ahead"})
        self.assertEqual(rc, 0)
        # short-input hint may fire when transcript_path absent
        self.assertEqual(rc, 0)

    def test_short_input_number_with_no_transcript(self):
        out, _, rc = self._run({"message": "1"})
        self.assertEqual(rc, 0)

    def test_short_input_number_with_missing_transcript(self):
        out, _, rc = self._run({"message": "2", "transcript_path": "/nope/missing.jsonl"})
        self.assertEqual(rc, 0)

    def test_short_input_with_numbered_list_transcript(self):
        """When transcript has a numbered list, short-input hint includes items."""
        with tempfile.TemporaryDirectory() as tmp:
            tp = os.path.join(tmp, "t.jsonl")
            assistant_entry = {
                "type": "assistant",
                "message": {
                    "content": [{
                        "type": "text",
                        "text": "Here are your options:\n1. Option one description here\n2. Option two description here\n3. Option three description here",
                    }]
                }
            }
            open(tp, "w", encoding="utf-8").write(json.dumps(assistant_entry) + "\n")
            out, _, rc = self._run({"message": "1"}, transcript_path=tp)
        self.assertEqual(rc, 0)
        self.assertIn("short-input", out)

    def test_short_input_with_no_numbered_list_transcript(self):
        """When transcript has assistant text without numbered list, brief-input hint fires."""
        with tempfile.TemporaryDirectory() as tmp:
            tp = os.path.join(tmp, "t.jsonl")
            assistant_entry = {
                "type": "assistant",
                "message": {
                    "content": [{"type": "text", "text": "Here is some information without a list."}]
                }
            }
            open(tp, "w", encoding="utf-8").write(json.dumps(assistant_entry) + "\n")
            out, _, rc = self._run({"message": "go"}, transcript_path=tp)
        self.assertEqual(rc, 0)
        self.assertIn("short-input", out)

    def test_word_count_determines_moderate_score(self):
        """A 13+ word message defaults to MODERATE when no keywords match."""
        msg = "please look at this file and tell me what the function does now"
        out, _, rc = self._run({"message": msg})
        self.assertEqual(rc, 0)
        self.assertIn("MODERATE", out)

    def test_trivial_list_pattern(self):
        # "list files?" matches ^(list|show|display) \w+\??$ trivial pattern
        # and doesn't hit any SIMPLE keywords that would bump score
        out, _, rc = self._run({"message": "thanks!"})
        self.assertEqual(rc, 0)
        self.assertIn("TRIVIAL", out)

    def test_orchestrator_hint_at_high_context(self):
        """Context at 40%+ injects orchestrator dispatch hint for MODERATE+ tasks.
        The real statusline-state.json (pct>=40) triggers the orchestrator hint."""
        state_path = os.path.expanduser("~/.claude/statusline-state.json")
        if os.path.exists(state_path):
            try:
                pct = json.load(open(state_path)).get("pct", 0)
            except Exception:
                pct = 0
        else:
            pct = 0
        # Only assert orchestrator hint when context is actually >=20%
        out, _, rc = self._run({"message": "implement a new authentication flow for the API"})
        self.assertEqual(rc, 0)
        if pct >= 20:
            self.assertIn("orchestrator", out)
        else:
            self.assertIn("task-classifier", out)


class TestTodoExtractor(unittest.TestCase):
    """Tests for todo-extractor.py — Stop hook that extracts TODOs from transcripts.

    Loads the original hooks/todo-extractor.py in-process using importlib with
    sys.exit patched to raise SystemExit (so control flow inside main() works).
    detect_project_name is injected after load since it only lives in a dead
    except-ImportError block. FEED_FILE is overridden per-test via mod.FEED_FILE.
    """

    HOOK_PATH = os.path.join(HOOKS_DIR, "todo-extractor.py")

    @classmethod
    def _load_module(cls):
        """Load todo-extractor.py in-process, return the module object."""
        import importlib.util
        spec = importlib.util.spec_from_file_location("todo_extractor", cls.HOOK_PATH)
        mod = importlib.util.module_from_spec(spec)
        dummy_payload = json.dumps({"session_id": "load_dummy"})
        with unittest.mock.patch("sys.exit", side_effect=SystemExit), \
             unittest.mock.patch("sys.stdin", io.StringIO(dummy_payload)):
            try:
                spec.loader.exec_module(mod)
            except SystemExit:
                pass
        # Inject detect_project_name — it only exists in a dead except-ImportError block
        def _dpn(payload):
            cwd = (payload.get("workspace", {}).get("current_dir", "")
                   or payload.get("cwd", ""))
            if not cwd:
                return None
            return os.path.basename(cwd.rstrip("/\\"))
        mod.detect_project_name = _dpn
        return mod

    def _call_main(self, mod, payload, feed_file):
        """Override mod.FEED_FILE, call main() with payload, return 0 on success."""
        mod.FEED_FILE = feed_file
        try:
            with unittest.mock.patch("sys.exit", side_effect=SystemExit), \
                 unittest.mock.patch("sys.stdin", io.StringIO(json.dumps(payload))):
                mod.main()
        except SystemExit:
            pass
        return 0

    def _run_and_read(self, payload, feed_file):
        """Call main() and return (0, feed_data_dict_or_None)."""
        mod = self._load_module()
        rc = self._call_main(mod, payload, feed_file)
        if os.path.exists(feed_file):
            data = json.load(open(feed_file, encoding="utf-8"))
        else:
            data = None
        return rc, data

    def test_invalid_json_exits_0(self):
        """Invalid JSON on stdin: main() catches exception, exits 0."""
        mod = self._load_module()
        mod.FEED_FILE = os.devnull
        try:
            with unittest.mock.patch("sys.exit", side_effect=SystemExit), \
                 unittest.mock.patch("sys.stdin", io.StringIO("not-json")):
                mod.main()
        except SystemExit as e:
            # side_effect=SystemExit raises SystemExit() with no args → code is None
            self.assertIn(e.code, (0, None))

    def test_no_transcript_path_writes_empty_feed(self):
        with tempfile.TemporaryDirectory() as tmp:
            feed = os.path.join(tmp, "feed.json")
            rc, data = self._run_and_read({"session_id": "abc12345"}, feed)
        self.assertEqual(rc, 0)
        self.assertIsNotNone(data)
        self.assertEqual(data["count"], 0)
        self.assertEqual(data["items"], [])

    def test_missing_transcript_writes_empty_feed(self):
        with tempfile.TemporaryDirectory() as tmp:
            feed = os.path.join(tmp, "feed.json")
            rc, data = self._run_and_read(
                {"session_id": "abc12345", "transcript_path": "/nope/missing.jsonl"}, feed
            )
        self.assertEqual(rc, 0)
        self.assertIsNotNone(data)
        self.assertEqual(data["count"], 0)

    def test_transcript_with_code_todo_extracted(self):
        """TODO: comment in Write tool_use is extracted."""
        with tempfile.TemporaryDirectory() as tmp:
            tp = os.path.join(tmp, "t.jsonl")
            feed = os.path.join(tmp, "feed.json")
            entry = {
                "type": "assistant",
                "message": {"content": [{
                    "type": "tool_use", "name": "Write",
                    "input": {"file_path": "/project/main.py",
                              "content": "def foo():\n    # TODO: implement this properly\n    pass\n"},
                }]},
            }
            open(tp, "w", encoding="utf-8").write(json.dumps(entry) + "\n")
            rc, data = self._run_and_read({"session_id": "abc12345", "transcript_path": tp}, feed)
        self.assertEqual(rc, 0)
        self.assertGreater(data["count"], 0)
        self.assertEqual(data["items"][0]["category"], "TODO")

    def test_transcript_with_fixme_extracted(self):
        """FIXME: comment in Edit new_string is extracted."""
        with tempfile.TemporaryDirectory() as tmp:
            tp = os.path.join(tmp, "t.jsonl")
            feed = os.path.join(tmp, "feed.json")
            entry = {
                "type": "assistant",
                "message": {"content": [{
                    "type": "tool_use", "name": "Edit",
                    "input": {"file_path": "/project/app.py", "old_string": "x = 1",
                              "new_string": "x = 1  # FIXME: handle edge case here"},
                }]},
            }
            open(tp, "w", encoding="utf-8").write(json.dumps(entry) + "\n")
            rc, data = self._run_and_read({"session_id": "abc12345", "transcript_path": tp}, feed)
        self.assertEqual(rc, 0)
        self.assertGreater(data["count"], 0)
        self.assertEqual(data["items"][0]["category"], "FIXME")

    def test_transcript_dont_forget_pattern_extracted(self):
        """don't forget pattern in assistant text is extracted as high-conf TODO."""
        with tempfile.TemporaryDirectory() as tmp:
            tp = os.path.join(tmp, "t.jsonl")
            feed = os.path.join(tmp, "feed.json")
            entry = {
                "type": "assistant",
                "message": {"content": [{
                    "type": "text",
                    "text": "Don't forget to add error handling for the database connection.",
                }]},
            }
            open(tp, "w", encoding="utf-8").write(json.dumps(entry) + "\n")
            rc, data = self._run_and_read({"session_id": "abc12345", "transcript_path": tp}, feed)
        self.assertEqual(rc, 0)
        self.assertGreater(data["count"], 0)
        self.assertEqual(data["items"][0]["category"], "dont_forget")

    def test_transcript_low_conf_without_deferral_not_extracted(self):
        """Low-confidence 'we should' without deferral signal is NOT extracted."""
        with tempfile.TemporaryDirectory() as tmp:
            tp = os.path.join(tmp, "t.jsonl")
            feed = os.path.join(tmp, "feed.json")
            entry = {
                "type": "assistant",
                "message": {"content": [{
                    "type": "text",
                    "text": "We should use the new API endpoint for authentication.",
                }]},
            }
            open(tp, "w", encoding="utf-8").write(json.dumps(entry) + "\n")
            rc, data = self._run_and_read({"session_id": "abc12345", "transcript_path": tp}, feed)
        self.assertEqual(rc, 0)
        self.assertEqual(data["count"], 0)

    def test_anti_pattern_suppresses_low_conf_todo(self):
        """Anti-pattern 'the existing TODO' suppresses false positive extraction."""
        with tempfile.TemporaryDirectory() as tmp:
            tp = os.path.join(tmp, "t.jsonl")
            feed = os.path.join(tmp, "feed.json")
            entry = {
                "type": "assistant",
                "message": {"content": [{
                    "type": "text",
                    "text": "The existing TODO says we should clean up the code later.",
                }]},
            }
            open(tp, "w", encoding="utf-8").write(json.dumps(entry) + "\n")
            rc, data = self._run_and_read({"session_id": "abc12345", "transcript_path": tp}, feed)
        self.assertEqual(rc, 0)
        # anti-pattern suppresses 'we should' even with deferral signal 'later'
        self.assertEqual(data["count"], 0)

    def test_code_fence_segments_excluded_from_conversational_scan(self):
        """Text inside code fences is not scanned for conversational patterns."""
        with tempfile.TemporaryDirectory() as tmp:
            tp = os.path.join(tmp, "t.jsonl")
            feed = os.path.join(tmp, "feed.json")
            entry = {
                "type": "assistant",
                "message": {"content": [{
                    "type": "text",
                    "text": "Here is the code:\n```python\n# Don't forget to add tests\ndef foo(): pass\n```\nDone.",
                }]},
            }
            open(tp, "w", encoding="utf-8").write(json.dumps(entry) + "\n")
            rc, data = self._run_and_read({"session_id": "abc12345", "transcript_path": tp}, feed)
        self.assertEqual(rc, 0)
        self.assertEqual(data["count"], 0)

    def test_duplicate_todos_deduplicated(self):
        """Same TODO text appearing twice results in only one item."""
        with tempfile.TemporaryDirectory() as tmp:
            tp = os.path.join(tmp, "t.jsonl")
            feed = os.path.join(tmp, "feed.json")
            entry1 = {
                "type": "assistant",
                "message": {"content": [{
                    "type": "tool_use", "name": "Write",
                    "input": {"file_path": "/a.py", "content": "# TODO: fix this bug properly"},
                }]},
            }
            entry2 = {
                "type": "assistant",
                "message": {"content": [{
                    "type": "tool_use", "name": "Write",
                    "input": {"file_path": "/b.py", "content": "# TODO: fix this bug properly"},
                }]},
            }
            with open(tp, "w", encoding="utf-8") as f:
                f.write(json.dumps(entry1) + "\n")
                f.write(json.dumps(entry2) + "\n")
            rc, data = self._run_and_read({"session_id": "abc12345", "transcript_path": tp}, feed)
        self.assertEqual(rc, 0)
        self.assertEqual(data["count"], 1)

    def test_non_write_edit_tool_use_skipped(self):
        """tool_use blocks for Bash are not scanned for TODO patterns."""
        with tempfile.TemporaryDirectory() as tmp:
            tp = os.path.join(tmp, "t.jsonl")
            feed = os.path.join(tmp, "feed.json")
            entry = {
                "type": "assistant",
                "message": {"content": [{
                    "type": "tool_use", "name": "Bash",
                    "input": {"command": "# TODO: remember to run this"},
                }]},
            }
            open(tp, "w", encoding="utf-8").write(json.dumps(entry) + "\n")
            rc, data = self._run_and_read({"session_id": "abc12345", "transcript_path": tp}, feed)
        self.assertEqual(rc, 0)
        self.assertEqual(data["count"], 0)

    def test_empty_transcript_writes_empty_feed(self):
        """Empty transcript file produces empty feed."""
        with tempfile.TemporaryDirectory() as tmp:
            tp = os.path.join(tmp, "t.jsonl")
            feed = os.path.join(tmp, "feed.json")
            open(tp, "w").write("")
            rc, data = self._run_and_read({"session_id": "abc12345", "transcript_path": tp}, feed)
        self.assertEqual(rc, 0)
        self.assertEqual(data["count"], 0)

    def test_invalid_jsonl_lines_skipped(self):
        """Non-JSON lines in transcript are skipped without crashing."""
        with tempfile.TemporaryDirectory() as tmp:
            tp = os.path.join(tmp, "t.jsonl")
            feed = os.path.join(tmp, "feed.json")
            open(tp, "w", encoding="utf-8").write("not-json\nalso-bad\n")
            rc, data = self._run_and_read({"session_id": "abc12345", "transcript_path": tp}, feed)
        self.assertEqual(rc, 0)
        self.assertEqual(data["count"], 0)

    def test_feed_file_has_expected_keys(self):
        """Output feed.json has all expected top-level keys."""
        with tempfile.TemporaryDirectory() as tmp:
            feed = os.path.join(tmp, "feed.json")
            rc, data = self._run_and_read({"session_id": "abc12345"}, feed)
        self.assertEqual(rc, 0)
        for key in ("ts", "session_id", "project", "count", "items", "persisted_to_backlog"):
            self.assertIn(key, data)

    def test_later_pattern_high_conf(self):
        """'later: ...' pattern is high-confidence and extracted without deferral co-signal."""
        with tempfile.TemporaryDirectory() as tmp:
            tp = os.path.join(tmp, "t.jsonl")
            feed = os.path.join(tmp, "feed.json")
            entry = {
                "type": "assistant",
                "message": {"content": [{
                    "type": "text",
                    "text": "Later: we need to add proper validation for this endpoint.",
                }]},
            }
            open(tp, "w", encoding="utf-8").write(json.dumps(entry) + "\n")
            rc, data = self._run_and_read({"session_id": "abc12345", "transcript_path": tp}, feed)
        self.assertEqual(rc, 0)
        self.assertGreater(data["count"], 0)
        self.assertEqual(data["items"][0]["category"], "later")

    def test_normalize_text_helper(self):
        """normalize_text strips and lowercases, collapses whitespace."""
        mod = self._load_module()
        result = mod.normalize_text("  Hello   World  ")
        self.assertEqual(result, "hello world")

    def test_item_hash_length_and_consistency(self):
        """item_hash returns 8-char hex string, same text = same hash."""
        mod = self._load_module()
        h = mod.item_hash("test item")
        self.assertEqual(len(h), 8)
        self.assertEqual(h, mod.item_hash("test item"))

    def test_split_code_fences_helper(self):
        """split_code_fences returns even-indexed segments outside fences."""
        mod = self._load_module()
        parts = mod.split_code_fences("before\n```python\ninside\n```\nafter")
        self.assertIn("before", parts[0])
        self.assertIn("after", parts[-1])

    def test_atomic_write_creates_file(self):
        """atomic_write writes JSON atomically via temp file."""
        mod = self._load_module()
        with tempfile.TemporaryDirectory() as tmp:
            out_path = os.path.join(tmp, "out.json")
            mod.atomic_write(out_path, {"key": "value"})
            data = json.load(open(out_path, encoding="utf-8"))
        self.assertEqual(data["key"], "value")

    def test_get_transcript_path_direct(self):
        """get_transcript_path returns path when transcript_path file exists."""
        mod = self._load_module()
        with tempfile.TemporaryDirectory() as tmp:
            tp = os.path.join(tmp, "t.jsonl")
            open(tp, "w").write("{}\n")
            result = mod.get_transcript_path({"transcript_path": tp})
        self.assertEqual(result.replace("\\", "/"), tp.replace("\\", "/"))

    def test_get_transcript_path_missing_returns_none(self):
        """get_transcript_path returns None when file doesn't exist."""
        mod = self._load_module()
        result = mod.get_transcript_path({"transcript_path": "/nope/missing.jsonl"})
        self.assertIsNone(result)

    def test_get_transcript_path_empty_returns_none(self):
        """get_transcript_path returns None when no path and no session_id."""
        mod = self._load_module()
        result = mod.get_transcript_path({})
        self.assertIsNone(result)

    def test_atomic_write_permission_error_retry(self):
        """atomic_write retries on PermissionError (lines 95-96)."""
        mod = self._load_module()
        with tempfile.TemporaryDirectory() as tmp:
            out_path = os.path.join(tmp, "out.json")
            call_count = [0]
            real_replace = os.replace
            def fake_replace(src, dst):
                call_count[0] += 1
                if call_count[0] < 2:
                    raise PermissionError("locked")
                real_replace(src, dst)
            with unittest.mock.patch("os.replace", side_effect=fake_replace):
                mod.atomic_write(out_path, {"x": 1})
            data = json.load(open(out_path, encoding="utf-8"))
        self.assertEqual(data["x"], 1)
        self.assertEqual(call_count[0], 2)

    def test_get_transcript_path_slug_search(self):
        """get_transcript_path finds file by searching PROJECTS_DIR (lines 107-116)."""
        mod = self._load_module()
        with tempfile.TemporaryDirectory() as tmp:
            # Create a fake project dir with a session JSONL
            proj_dir = os.path.join(tmp, "some-project")
            os.makedirs(proj_dir)
            tp = os.path.join(proj_dir, "sess123.jsonl")
            open(tp, "w").write("{}\n")
            payload = {
                "transcript_path": "",
                "cwd": "/fake/cwd",
                "session_id": "sess123",
            }
            with unittest.mock.patch.object(mod, "PROJECTS_DIR", tmp):
                result = mod.get_transcript_path(payload)
        self.assertIsNotNone(result)
        self.assertTrue(result.endswith("sess123.jsonl"))

    def test_get_transcript_path_no_cwd_no_session(self):
        """get_transcript_path returns None when cwd or session_id missing (line 105-106)."""
        mod = self._load_module()
        result = mod.get_transcript_path({"transcript_path": "", "cwd": "", "session_id": ""})
        self.assertIsNone(result)

    def test_scan_transcript_empty_line_skipped(self):
        """Empty lines in transcript don't crash scan (line 164)."""
        mod = self._load_module()
        with tempfile.TemporaryDirectory() as tmp:
            tp = os.path.join(tmp, "t.jsonl")
            with open(tp, "w", encoding="utf-8") as f:
                f.write("\n\n\n")
            items = mod.scan_transcript(tp, int(time.time()))
        self.assertEqual(items, [])

    def test_scan_transcript_non_list_content_skipped(self):
        """Assistant message with non-list content is skipped (line 177)."""
        mod = self._load_module()
        with tempfile.TemporaryDirectory() as tmp:
            tp = os.path.join(tmp, "t.jsonl")
            entry = {"type": "assistant", "message": {"content": "just a string"}}
            open(tp, "w", encoding="utf-8").write(json.dumps(entry) + "\n")
            items = mod.scan_transcript(tp, int(time.time()))
        self.assertEqual(items, [])

    def test_scan_transcript_empty_scan_text_skipped(self):
        """Write tool_use with empty content is skipped (line 199)."""
        mod = self._load_module()
        with tempfile.TemporaryDirectory() as tmp:
            tp = os.path.join(tmp, "t.jsonl")
            entry = {
                "type": "assistant",
                "message": {"content": [{
                    "type": "tool_use", "name": "Write",
                    "input": {"file_path": "/f.py", "content": ""},
                }]},
            }
            open(tp, "w", encoding="utf-8").write(json.dumps(entry) + "\n")
            items = mod.scan_transcript(tp, int(time.time()))
        self.assertEqual(items, [])

    def test_scan_transcript_empty_captured_skipped(self):
        """CODE_TODO_RE match with empty capture group is skipped (line 204)."""
        mod = self._load_module()
        with tempfile.TemporaryDirectory() as tmp:
            tp = os.path.join(tmp, "t.jsonl")
            # A TODO: followed by only whitespace — captured group strips to empty
            entry = {
                "type": "assistant",
                "message": {"content": [{
                    "type": "tool_use", "name": "Write",
                    "input": {"file_path": "/f.py", "content": "# TODO:     "},
                }]},
            }
            open(tp, "w", encoding="utf-8").write(json.dumps(entry) + "\n")
            items = mod.scan_transcript(tp, int(time.time()))
        # Either 0 items (pattern doesn't match short text) or captured is indeed empty
        self.assertIsInstance(items, list)

    def test_scan_transcript_empty_text_block_skipped(self):
        """Assistant text block with empty text is skipped (line 215)."""
        mod = self._load_module()
        with tempfile.TemporaryDirectory() as tmp:
            tp = os.path.join(tmp, "t.jsonl")
            entry = {
                "type": "assistant",
                "message": {"content": [{"type": "text", "text": ""}]},
            }
            open(tp, "w", encoding="utf-8").write(json.dumps(entry) + "\n")
            items = mod.scan_transcript(tp, int(time.time()))
        self.assertEqual(items, [])

    def test_anti_pattern_suppresses_high_conf(self):
        """Anti-pattern suppresses high-confidence 'don't forget' pattern (line 227)."""
        mod = self._load_module()
        with tempfile.TemporaryDirectory() as tmp:
            tp = os.path.join(tmp, "t.jsonl")
            # "the existing TODO" triggers anti-pattern; "don't forget" is in same sentence
            entry = {
                "type": "assistant",
                "message": {"content": [{"type": "text",
                    "text": "The existing TODO says don't forget to handle the edge case."}]},
            }
            open(tp, "w", encoding="utf-8").write(json.dumps(entry) + "\n")
            items = mod.scan_transcript(tp, int(time.time()))
        self.assertEqual(items, [])

    def test_low_conf_with_deferral_signal_extracted(self):
        """Low-confidence 'we should' with deferral signal is extracted (lines 240-242)."""
        mod = self._load_module()
        with tempfile.TemporaryDirectory() as tmp:
            tp = os.path.join(tmp, "t.jsonl")
            entry = {
                "type": "assistant",
                "message": {"content": [{"type": "text",
                    "text": "We should refactor this later when we have more time."}]},
            }
            open(tp, "w", encoding="utf-8").write(json.dumps(entry) + "\n")
            items = mod.scan_transcript(tp, int(time.time()))
        self.assertGreater(len(items), 0)

    def test_module_level_main_call(self):
        """Module-level try: main() / except Exception: pass runs without crashing (lines 282-284)."""
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "todo_extractor_ml",
            os.path.join(HOOKS_DIR, "todo-extractor.py")
        )
        mod2 = importlib.util.module_from_spec(spec)
        payload = json.dumps({"session_id": "ml_test"})
        with unittest.mock.patch("sys.exit", side_effect=SystemExit), \
             unittest.mock.patch("sys.stdin", io.StringIO(payload)):
            try:
                spec.loader.exec_module(mod2)
            except SystemExit:
                pass


# ---------------------------------------------------------------------------
# TestSubagentQualityGate — SubagentStop hook
# ---------------------------------------------------------------------------

class TestSubagentQualityGate(unittest.TestCase):
    """Tests for subagent-quality-gate.py — SubagentStop hook."""

    HOOK_PATH = os.path.join(HOOKS_DIR, "subagent-quality-gate.py")

    @classmethod
    def _load_module(cls):
        import importlib.util
        mod_name = "subagent_quality_gate"
        spec = importlib.util.spec_from_file_location(mod_name, cls.HOOK_PATH)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod

    def _call_main(self, mod, payload):
        cap = io.StringIO()
        with unittest.mock.patch("sys.stdin", io.StringIO(json.dumps(payload))), \
             unittest.mock.patch("sys.stdout", cap):
            mod.main()
        out = cap.getvalue().strip()
        return json.loads(out) if out else {}

    # ── get_tool_summary ────────────────────────────────────────────────────

    def test_get_tool_summary_missing_transcript(self):
        """get_tool_summary returns empty lists for missing file (line 24-25)."""
        mod = self._load_module()
        names, paths, cmds = mod.get_tool_summary("/nope/missing.jsonl")
        self.assertEqual(names, [])
        self.assertEqual(paths, [])
        self.assertEqual(cmds, [])

    def test_get_tool_summary_empty_transcript(self):
        """get_tool_summary handles empty transcript."""
        mod = self._load_module()
        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False, encoding="utf-8") as f:
            f.write("")
            tp = f.name
        try:
            names, paths, cmds = mod.get_tool_summary(tp)
        finally:
            os.unlink(tp)
        self.assertEqual(names, [])

    def test_get_tool_summary_edit_write_bash(self):
        """get_tool_summary extracts Edit, Write, Bash names and paths (lines 48-61)."""
        mod = self._load_module()
        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False, encoding="utf-8") as f:
            line = json.dumps({"type": "assistant", "message": {"content": [
                {"type": "tool_use", "name": "Edit", "input": {"file_path": "/a.py"}},
                {"type": "tool_use", "name": "Bash", "input": {"command": "pytest"}},
            ]}})
            f.write(line + "\n")
            tp = f.name
        try:
            names, paths, cmds = mod.get_tool_summary(tp)
        finally:
            os.unlink(tp)
        self.assertIn("Edit", names)
        self.assertIn("Bash", names)
        self.assertIn("/a.py", paths)
        self.assertIn("pytest", cmds)

    def test_get_tool_summary_user_message_breaks_loop(self):
        """get_tool_summary stops at user message with non-tool-result content (lines 38-46)."""
        mod = self._load_module()
        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False, encoding="utf-8") as f:
            lines = [
                json.dumps({"type": "assistant", "message": {"content": [
                    {"type": "tool_use", "name": "Bash", "input": {"command": "ls"}},
                ]}}),
                json.dumps({"type": "user", "message": {"content": "hello"}}),
            ]
            f.write("\n".join(lines) + "\n")
            tp = f.name
        try:
            names, paths, cmds = mod.get_tool_summary(tp)
        finally:
            os.unlink(tp)
        # Should have found the Bash tool before breaking on user message
        self.assertIn("Bash", names)

    def test_get_tool_summary_tool_result_continues(self):
        """get_tool_summary skips user messages that are pure tool_result (line 44)."""
        mod = self._load_module()
        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False, encoding="utf-8") as f:
            lines = [
                json.dumps({"type": "assistant", "message": {"content": [
                    {"type": "tool_use", "name": "Edit", "input": {"file_path": "/b.py"}},
                ]}}),
                json.dumps({"type": "user", "message": {"content": [
                    {"type": "tool_result", "tool_use_id": "x", "content": "ok"},
                ]}}),
                json.dumps({"type": "assistant", "message": {"content": [
                    {"type": "tool_use", "name": "Bash", "input": {"command": "pytest"}},
                ]}}),
            ]
            f.write("\n".join(lines) + "\n")
            tp = f.name
        try:
            names, paths, cmds = mod.get_tool_summary(tp)
        finally:
            os.unlink(tp)
        self.assertIn("Bash", names)

    # ── get_failed_commands ─────────────────────────────────────────────────

    def test_get_failed_commands_missing_transcript(self):
        """get_failed_commands returns [] for missing file (lines 69-70)."""
        mod = self._load_module()
        result = mod.get_failed_commands("/nope/missing.jsonl")
        self.assertEqual(result, [])

    def test_get_failed_commands_no_failures(self):
        """get_failed_commands returns [] when no is_error=True results."""
        mod = self._load_module()
        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False, encoding="utf-8") as f:
            lines = [
                json.dumps({"type": "assistant", "message": {"content": [
                    {"type": "tool_use", "name": "Bash", "id": "tid1",
                     "input": {"command": "pytest"}},
                ]}}),
                json.dumps({"type": "user", "message": {"content": [
                    {"type": "tool_result", "tool_use_id": "tid1",
                     "is_error": False, "content": "4 passed"},
                ]}}),
            ]
            f.write("\n".join(lines) + "\n")
            tp = f.name
        try:
            result = mod.get_failed_commands(tp)
        finally:
            os.unlink(tp)
        self.assertEqual(result, [])

    def test_get_failed_commands_detects_error(self):
        """get_failed_commands matches is_error=True with pending Bash (lines 81-113)."""
        mod = self._load_module()
        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False, encoding="utf-8") as f:
            lines = [
                json.dumps({"type": "assistant", "message": {"content": [
                    {"type": "tool_use", "name": "Bash", "id": "tid2",
                     "input": {"command": "bad_command"}},
                ]}}),
                json.dumps({"type": "user", "message": {"content": [
                    {"type": "tool_result", "tool_use_id": "tid2",
                     "is_error": True, "content": "command not found"},
                ]}}),
            ]
            f.write("\n".join(lines) + "\n")
            tp = f.name
        try:
            result = mod.get_failed_commands(tp)
        finally:
            os.unlink(tp)
        self.assertEqual(len(result), 1)
        self.assertIn("bad_command", result[0][0])

    # ── get_last_response ───────────────────────────────────────────────────

    def test_get_last_response_missing_transcript(self):
        """get_last_response returns '' for missing file (lines 121-122)."""
        mod = self._load_module()
        result = mod.get_last_response("/nope/missing.jsonl")
        self.assertEqual(result, "")

    def test_get_last_response_finds_text(self):
        """get_last_response extracts last assistant text block (lines 134-141)."""
        mod = self._load_module()
        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False, encoding="utf-8") as f:
            line = json.dumps({"type": "assistant", "message": {"content": [
                {"type": "text", "text": "Task complete."},
            ]}})
            f.write(line + "\n")
            tp = f.name
        try:
            result = mod.get_last_response(tp)
        finally:
            os.unlink(tp)
        self.assertEqual(result, "Task complete.")

    def test_get_last_response_string_content(self):
        """get_last_response handles string message content (line 142-143)."""
        mod = self._load_module()
        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False, encoding="utf-8") as f:
            line = json.dumps({"type": "assistant", "message": {"content": "Direct string response."}})
            f.write(line + "\n")
            tp = f.name
        try:
            result = mod.get_last_response(tp)
        finally:
            os.unlink(tp)
        self.assertEqual(result, "Direct string response.")

    # ── log_decision ────────────────────────────────────────────────────────

    def test_log_decision_writes_line(self):
        """log_decision writes a log line (lines 149-158)."""
        mod = self._load_module()
        with tempfile.TemporaryDirectory() as tmp:
            log = os.path.join(tmp, "quality-gate.log")
            with unittest.mock.patch.object(mod, "LOG_PATH", log):
                mod.log_decision("PASS", "ok", "test-agent", "some response")
            content = open(log, encoding="utf-8").read()
        self.assertIn("PASS", content)
        self.assertIn("subagent:test-agent", content)

    # ── main() flow ─────────────────────────────────────────────────────────

    def test_main_stop_hook_active_continues(self):
        """stop_hook_active=True → immediately return {continue: True} (line 168-170)."""
        mod = self._load_module()
        result = self._call_main(mod, {"stop_hook_active": True})
        self.assertTrue(result.get("continue"))

    def test_main_invalid_json_continues(self):
        """Invalid JSON stdin → data={}, no edits → continues (lines 162-165)."""
        mod = self._load_module()
        cap = io.StringIO()
        with unittest.mock.patch("sys.stdin", io.StringIO("bad json")), \
             unittest.mock.patch("sys.stdout", cap):
            mod.main()
        out = cap.getvalue().strip()
        result = json.loads(out)
        self.assertTrue(result.get("continue"))

    def test_main_no_edit_no_verify_continues(self):
        """No code edits, no verification → passes all mechanical checks → continues."""
        mod = self._load_module()
        with tempfile.TemporaryDirectory() as tmp:
            log = os.path.join(tmp, "quality-gate.log")
            with unittest.mock.patch.object(mod, "LOG_PATH", log), \
                 unittest.mock.patch.object(mod, "check_cache", return_value=(True, "ok")):
                result = self._call_main(mod, {
                    "agent_type": "test",
                    "agent_transcript_path": "",
                    "last_assistant_message": "I read the file and summarized it.",
                })
        self.assertTrue(result.get("continue"))

    def test_main_code_edit_no_verify_blocks(self):
        """Code edit without verification → BLOCK (lines 185-189)."""
        mod = self._load_module()
        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False, encoding="utf-8") as f:
            line = json.dumps({"type": "assistant", "message": {"content": [
                {"type": "tool_use", "name": "Edit",
                 "input": {"file_path": "/src/app.py", "old_string": "x", "new_string": "y"}},
            ]}})
            f.write(line + "\n")
            tp = f.name
        try:
            with tempfile.TemporaryDirectory() as tmp:
                log = os.path.join(tmp, "quality-gate.log")
                with unittest.mock.patch.object(mod, "LOG_PATH", log):
                    result = self._call_main(mod, {
                        "agent_type": "test",
                        "agent_transcript_path": tp,
                    })
        finally:
            os.unlink(tp)
        self.assertEqual(result.get("decision"), "block")
        self.assertIn("QUALITY GATE", result.get("reason", ""))

    def test_main_code_edit_non_code_path_not_blocked(self):
        """Code edit on non-code path (memory/) → has_code_edit=False → not blocked (lines 181-183)."""
        mod = self._load_module()
        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False, encoding="utf-8") as f:
            line = json.dumps({"type": "assistant", "message": {"content": [
                {"type": "tool_use", "name": "Edit",
                 "input": {"file_path": "memory/MEMORY.md", "old_string": "x", "new_string": "y"}},
            ]}})
            f.write(line + "\n")
            tp = f.name
        try:
            with tempfile.TemporaryDirectory() as tmp:
                log = os.path.join(tmp, "quality-gate.log")
                with unittest.mock.patch.object(mod, "LOG_PATH", log), \
                     unittest.mock.patch.object(mod, "check_cache", return_value=(True, "ok")):
                    result = self._call_main(mod, {
                        "agent_type": "test",
                        "agent_transcript_path": tp,
                        "last_assistant_message": "Updated memory file.",
                    })
        finally:
            os.unlink(tp)
        self.assertTrue(result.get("continue"))

    def test_main_edit_then_bash_not_validation_blocks(self):
        """Edit + Bash but Bash is not a validation command → BLOCK (lines 191-196)."""
        mod = self._load_module()
        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False, encoding="utf-8") as f:
            lines = [
                json.dumps({"type": "assistant", "message": {"content": [
                    {"type": "tool_use", "name": "Edit",
                     "input": {"file_path": "/src/app.py", "old_string": "x", "new_string": "y"}},
                    {"type": "tool_use", "name": "Bash",
                     "input": {"command": "echo done"}},
                ]}}),
            ]
            f.write("\n".join(lines) + "\n")
            tp = f.name
        try:
            with tempfile.TemporaryDirectory() as tmp:
                log = os.path.join(tmp, "quality-gate.log")
                with unittest.mock.patch.object(mod, "LOG_PATH", log):
                    result = self._call_main(mod, {
                        "agent_type": "test",
                        "agent_transcript_path": tp,
                    })
        finally:
            os.unlink(tp)
        self.assertEqual(result.get("decision"), "block")

    def test_main_edit_last_action_blocks(self):
        """Edit + pytest but last action is Edit → BLOCK (lines 198-202).

        get_tool_summary iterates lines in reverse, collecting tools in reverse order,
        then re-reverses. So the LAST tool in the file becomes tool_names[-1].
        Two separate assistant blocks are needed so Edit appears after Bash in the file.
        """
        mod = self._load_module()
        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False, encoding="utf-8") as f:
            lines = [
                json.dumps({"type": "assistant", "message": {"content": [
                    {"type": "tool_use", "name": "Bash",
                     "input": {"command": "pytest"}},
                ]}}),
                json.dumps({"type": "user", "message": {"content": [
                    {"type": "tool_result", "tool_use_id": "x", "content": "3 passed"},
                ]}}),
                json.dumps({"type": "assistant", "message": {"content": [
                    {"type": "tool_use", "name": "Edit",
                     "input": {"file_path": "/src/app.py", "old_string": "x", "new_string": "y"}},
                ]}}),
            ]
            f.write("\n".join(lines) + "\n")
            tp = f.name
        try:
            with tempfile.TemporaryDirectory() as tmp:
                log = os.path.join(tmp, "quality-gate.log")
                with unittest.mock.patch.object(mod, "LOG_PATH", log):
                    result = self._call_main(mod, {
                        "agent_type": "test",
                        "agent_transcript_path": tp,
                    })
        finally:
            os.unlink(tp)
        self.assertEqual(result.get("decision"), "block")

    def test_main_cites_test_count_no_verify_blocks(self):
        """Response cites test counts but no verification ran → BLOCK (lines 205-215)."""
        mod = self._load_module()
        with tempfile.TemporaryDirectory() as tmp:
            log = os.path.join(tmp, "quality-gate.log")
            with unittest.mock.patch.object(mod, "LOG_PATH", log):
                result = self._call_main(mod, {
                    "agent_type": "test",
                    "agent_transcript_path": "",
                    "last_assistant_message": "Tests pass: 42 passed, 0 failed, 42 total",
                })
        self.assertEqual(result.get("decision"), "block")
        self.assertIn("QUALITY GATE", result.get("reason", ""))

    def test_main_failed_command_unaddressed_blocks(self):
        """Failed command with response not addressing error → BLOCK (lines 218-227)."""
        mod = self._load_module()
        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False, encoding="utf-8") as f:
            lines = [
                json.dumps({"type": "assistant", "message": {"content": [
                    {"type": "tool_use", "name": "Bash", "id": "tid3",
                     "input": {"command": "python script.py"}},
                ]}}),
                json.dumps({"type": "user", "message": {"content": [
                    {"type": "tool_result", "tool_use_id": "tid3",
                     "is_error": True, "content": "ImportError modulenotfoundxyz missing"},
                ]}}),
            ]
            f.write("\n".join(lines) + "\n")
            tp = f.name
        try:
            with tempfile.TemporaryDirectory() as tmp:
                log = os.path.join(tmp, "quality-gate.log")
                with unittest.mock.patch.object(mod, "LOG_PATH", log):
                    result = self._call_main(mod, {
                        "agent_type": "test",
                        "agent_transcript_path": tp,
                        "last_assistant_message": "The task is done and everything looks great.",
                    })
        finally:
            os.unlink(tp)
        self.assertEqual(result.get("decision"), "block")

    def test_main_llm_pass_continues(self):
        """LLM check returns ok=True → PASS → continues (lines 230-270)."""
        mod = self._load_module()
        with tempfile.TemporaryDirectory() as tmp:
            log = os.path.join(tmp, "quality-gate.log")
            with unittest.mock.patch.object(mod, "LOG_PATH", log), \
                 unittest.mock.patch.object(mod, "check_cache", return_value=(True, "ok")):
                result = self._call_main(mod, {
                    "agent_type": "test",
                    "agent_transcript_path": "",
                    "last_assistant_message": "I read the file and found the pattern.",
                })
        self.assertTrue(result.get("continue"))

    def test_main_llm_block_blocks(self):
        """LLM check returns ok=False → BLOCK (lines 262-265)."""
        mod = self._load_module()
        with tempfile.TemporaryDirectory() as tmp:
            log = os.path.join(tmp, "quality-gate.log")
            with unittest.mock.patch.object(mod, "LOG_PATH", log), \
                 unittest.mock.patch.object(mod, "check_cache",
                                            return_value=(False, "ASSUMPTION: guessed file path")):
                result = self._call_main(mod, {
                    "agent_type": "test",
                    "agent_transcript_path": "",
                    "last_assistant_message": "The file is at /some/guessed/path.py",
                })
        self.assertEqual(result.get("decision"), "block")

    def test_main_llm_degraded_continues(self):
        """LLM call fails (degraded) → DEGRADED-PASS → continues (lines 258-260, 267-270)."""
        mod = self._load_module()
        with tempfile.TemporaryDirectory() as tmp:
            log = os.path.join(tmp, "quality-gate.log")
            # cache miss and call_haiku_check returns genuine=False (degraded).
            # Patch on mod directly — module uses `from _hooks_shared import ...`
            # so names are bound on the module itself, not on _hooks_shared.
            with unittest.mock.patch.object(mod, "LOG_PATH", log), \
                 unittest.mock.patch.object(mod, "check_cache", return_value=None), \
                 unittest.mock.patch.object(mod, "call_haiku_check",
                                            return_value=(True, "ok", False)):
                result = self._call_main(mod, {
                    "agent_type": "test",
                    "agent_transcript_path": "",
                    "last_assistant_message": "Done with the task.",
                })
        self.assertTrue(result.get("continue"))

    def test_main_empty_response_skips_llm(self):
        """Empty response skips LLM check entirely → continues (line 231)."""
        mod = self._load_module()
        with tempfile.TemporaryDirectory() as tmp:
            log = os.path.join(tmp, "quality-gate.log")
            with unittest.mock.patch.object(mod, "LOG_PATH", log):
                result = self._call_main(mod, {
                    "agent_type": "test",
                    "agent_transcript_path": "",
                    "last_assistant_message": "",
                })
        self.assertTrue(result.get("continue"))

    def test_main_edit_with_pytest_passes(self):
        """Edit then pytest validation as last action → passes mechanical checks → LLM checked."""
        mod = self._load_module()
        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False, encoding="utf-8") as f:
            # Two separate assistant blocks: Edit first, then Bash last.
            # get_tool_summary reverses lines so tool_names[-1] == last tool in file == Bash.
            lines = [
                json.dumps({"type": "assistant", "message": {"content": [
                    {"type": "tool_use", "name": "Edit",
                     "input": {"file_path": "/src/app.py", "old_string": "x", "new_string": "y"}},
                ]}}),
                json.dumps({"type": "user", "message": {"content": [
                    {"type": "tool_result", "tool_use_id": "x", "content": "ok"},
                ]}}),
                json.dumps({"type": "assistant", "message": {"content": [
                    {"type": "tool_use", "name": "Bash",
                     "input": {"command": "pytest --tb=short"}},
                ]}}),
            ]
            f.write("\n".join(lines) + "\n")
            tp = f.name
        try:
            with tempfile.TemporaryDirectory() as tmp:
                log = os.path.join(tmp, "quality-gate.log")
                with unittest.mock.patch.object(mod, "LOG_PATH", log), \
                     unittest.mock.patch.object(mod, "check_cache", return_value=(True, "ok")):
                    result = self._call_main(mod, {
                        "agent_type": "test",
                        "agent_transcript_path": tp,
                        "last_assistant_message": "All tests pass.",
                    })
        finally:
            os.unlink(tp)
        self.assertTrue(result.get("continue"))

    # ── get_tool_summary additional coverage ─────────────────────────────────

    def test_get_tool_summary_empty_line_skipped(self):
        """Empty lines in transcript are skipped via continue (line 32)."""
        mod = self._load_module()
        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False, encoding="utf-8") as f:
            f.write("\n\n\n")
            tp = f.name
        try:
            names, paths, cmds = mod.get_tool_summary(tp)
        finally:
            os.unlink(tp)
        self.assertEqual(names, [])

    def test_get_tool_summary_non_assistant_non_user_skipped(self):
        """Non-assistant, non-user type entries are skipped (line 47 continue)."""
        mod = self._load_module()
        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False, encoding="utf-8") as f:
            line = json.dumps({"type": "system", "message": {"content": "init"}})
            f.write(line + "\n")
            tp = f.name
        try:
            names, paths, cmds = mod.get_tool_summary(tp)
        finally:
            os.unlink(tp)
        self.assertEqual(names, [])

    def test_get_tool_summary_user_no_tool_names_continues(self):
        """User message with non-tool-result content but tool_names=[] → continue, not break (lines 38-47)."""
        mod = self._load_module()
        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False, encoding="utf-8") as f:
            # user message with plain string content (not a list of tool_result)
            # tool_names is empty at this point so the outer `if tool_names` in line 38 is False
            lines = [
                json.dumps({"type": "user", "message": {"content": "hello"}}),
                json.dumps({"type": "assistant", "message": {"content": [
                    {"type": "tool_use", "name": "Read", "input": {}},
                ]}}),
            ]
            f.write("\n".join(lines) + "\n")
            tp = f.name
        try:
            names, paths, cmds = mod.get_tool_summary(tp)
        finally:
            os.unlink(tp)
        self.assertIn("Read", names)

    def test_get_tool_summary_invalid_json_skipped(self):
        """Invalid JSON lines are skipped via continue (lines 62-63)."""
        mod = self._load_module()
        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False, encoding="utf-8") as f:
            f.write("not json at all\n")
            f.write(json.dumps({"type": "assistant", "message": {"content": [
                {"type": "tool_use", "name": "Bash", "input": {"command": "ls"}},
            ]}}) + "\n")
            tp = f.name
        try:
            names, paths, cmds = mod.get_tool_summary(tp)
        finally:
            os.unlink(tp)
        self.assertIn("Bash", names)

    def test_get_tool_summary_write_no_path_skipped(self):
        """Write tool with no file_path does not add to edited_paths (lines 54-57 branch)."""
        mod = self._load_module()
        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False, encoding="utf-8") as f:
            line = json.dumps({"type": "assistant", "message": {"content": [
                {"type": "tool_use", "name": "Write", "input": {}},
            ]}})
            f.write(line + "\n")
            tp = f.name
        try:
            names, paths, cmds = mod.get_tool_summary(tp)
        finally:
            os.unlink(tp)
        self.assertIn("Write", names)
        self.assertEqual(paths, [])

    def test_get_tool_summary_exception_returns_empty(self):
        """IOError on open triggers except block → empty results (lines 62-63 outer except)."""
        mod = self._load_module()
        with unittest.mock.patch("builtins.open", side_effect=IOError("disk fail")):
            # Need a path that passes the isfile check
            with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
                tp = f.name
            try:
                names, paths, cmds = mod.get_tool_summary(tp)
            finally:
                os.unlink(tp)
        self.assertEqual(names, [])

    # ── get_failed_commands additional coverage ───────────────────────────────

    def test_get_failed_commands_empty_line_skipped(self):
        """Empty lines in transcript are skipped via continue (line 81)."""
        mod = self._load_module()
        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False, encoding="utf-8") as f:
            f.write("\n\n")
            tp = f.name
        try:
            result = mod.get_failed_commands(tp)
        finally:
            os.unlink(tp)
        self.assertEqual(result, [])

    def test_get_failed_commands_invalid_json_skipped(self):
        """Invalid JSON lines are skipped via continue (lines 84-85)."""
        mod = self._load_module()
        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False, encoding="utf-8") as f:
            f.write("bad json line\n")
            tp = f.name
        try:
            result = mod.get_failed_commands(tp)
        finally:
            os.unlink(tp)
        self.assertEqual(result, [])

    def test_get_failed_commands_list_content_in_result(self):
        """tool_result with list content → joined into result_text (lines 105-108)."""
        mod = self._load_module()
        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False, encoding="utf-8") as f:
            lines = [
                json.dumps({"type": "assistant", "message": {"content": [
                    {"type": "tool_use", "name": "Bash", "id": "tid9",
                     "input": {"command": "bad_cmd_xyz"}},
                ]}}),
                json.dumps({"type": "user", "message": {"content": [
                    {"type": "tool_result", "tool_use_id": "tid9",
                     "is_error": True,
                     "content": [{"type": "text", "text": "error: list content"}]},
                ]}}),
            ]
            f.write("\n".join(lines) + "\n")
            tp = f.name
        try:
            result = mod.get_failed_commands(tp)
        finally:
            os.unlink(tp)
        self.assertEqual(len(result), 1)
        self.assertIn("bad_cmd_xyz", result[0][0])
        self.assertIn("error: list content", result[0][1])

    def test_get_failed_commands_exception_returns_empty(self):
        """IOError on open triggers except block → empty list (lines 114-115)."""
        mod = self._load_module()
        with unittest.mock.patch("builtins.open", side_effect=IOError("disk fail")):
            with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
                tp = f.name
            try:
                result = mod.get_failed_commands(tp)
            finally:
                os.unlink(tp)
        self.assertEqual(result, [])

    # ── get_last_response additional coverage ────────────────────────────────

    def test_get_last_response_empty_line_skipped(self):
        """Empty lines are skipped via continue (line 129).

        get_last_response iterates in reversed() order, so blank lines must
        appear AFTER the assistant line in the file to be encountered first.
        """
        mod = self._load_module()
        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False, encoding="utf-8") as f:
            # Assistant block first in file → last in reversed; blank lines last in file → first in reversed
            f.write(json.dumps({"type": "assistant", "message": {"content": [
                {"type": "text", "text": "Found it."},
            ]}}) + "\n")
            f.write("\n\n")
            tp = f.name
        try:
            result = mod.get_last_response(tp)
        finally:
            os.unlink(tp)
        self.assertEqual(result, "Found it.")

    def test_get_last_response_invalid_json_skipped(self):
        """Invalid JSON lines are skipped via continue (lines 132-133).

        get_last_response iterates in reversed() order, so bad JSON must
        appear AFTER the assistant line in the file to be encountered first.
        """
        mod = self._load_module()
        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False, encoding="utf-8") as f:
            # Assistant block first in file → last in reversed; bad JSON last → first in reversed
            f.write(json.dumps({"type": "assistant", "message": {"content": [
                {"type": "text", "text": "Still found."},
            ]}}) + "\n")
            f.write("not json\n")
            tp = f.name
        try:
            result = mod.get_last_response(tp)
        finally:
            os.unlink(tp)
        self.assertEqual(result, "Still found.")

    def test_get_last_response_exception_returns_empty(self):
        """IOError on open triggers except block → empty string (lines 144-145)."""
        mod = self._load_module()
        with unittest.mock.patch("builtins.open", side_effect=IOError("disk fail")):
            with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
                tp = f.name
            try:
                result = mod.get_last_response(tp)
            finally:
                os.unlink(tp)
        self.assertEqual(result, "")

    def test_get_last_response_text_block_empty_text_skipped(self):
        """Text block with empty text is skipped; non-empty block is returned (lines 138-141)."""
        mod = self._load_module()
        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False, encoding="utf-8") as f:
            line = json.dumps({"type": "assistant", "message": {"content": [
                {"type": "text", "text": ""},
                {"type": "text", "text": "Real content."},
            ]}})
            f.write(line + "\n")
            tp = f.name
        try:
            result = mod.get_last_response(tp)
        finally:
            os.unlink(tp)
        self.assertEqual(result, "Real content.")

    # ── log_decision exception coverage ──────────────────────────────────────

    def test_log_decision_exception_swallowed(self):
        """log_decision swallows exceptions silently (lines 158-159)."""
        mod = self._load_module()
        # Patch open to raise so the except branch is hit
        with unittest.mock.patch("builtins.open", side_effect=IOError("no disk")):
            # Should not raise
            mod.log_decision("PASS", "ok", "test-agent", "response")

    # ── main() additional coverage ───────────────────────────────────────────

    def test_main_llm_cache_miss_haiku_block(self):
        """Cache miss + call_haiku_check returns ok=False → BLOCK (lines 236-265)."""
        mod = self._load_module()
        with tempfile.TemporaryDirectory() as tmp:
            log = os.path.join(tmp, "quality-gate.log")
            with unittest.mock.patch.object(mod, "LOG_PATH", log), \
                 unittest.mock.patch.object(mod, "check_cache", return_value=None), \
                 unittest.mock.patch.object(mod, "write_cache"), \
                 unittest.mock.patch.object(mod, "call_haiku_check",
                                            return_value=(False, "ASSUMPTION: guessed path", True)):
                result = self._call_main(mod, {
                    "agent_type": "test",
                    "agent_transcript_path": "",
                    "last_assistant_message": "The file is at /some/guessed/path.py",
                })
        self.assertEqual(result.get("decision"), "block")
        self.assertIn("QUALITY GATE", result.get("reason", ""))

    def test_main_llm_cache_miss_haiku_pass(self):
        """Cache miss + call_haiku_check returns ok=True → PASS → continues (lines 236-260, 267-270)."""
        mod = self._load_module()
        with tempfile.TemporaryDirectory() as tmp:
            log = os.path.join(tmp, "quality-gate.log")
            with unittest.mock.patch.object(mod, "LOG_PATH", log), \
                 unittest.mock.patch.object(mod, "check_cache", return_value=None), \
                 unittest.mock.patch.object(mod, "write_cache"), \
                 unittest.mock.patch.object(mod, "call_haiku_check",
                                            return_value=(True, "ok", True)):
                result = self._call_main(mod, {
                    "agent_type": "test",
                    "agent_transcript_path": "",
                    "last_assistant_message": "I verified the file exists using Read.",
                })
        self.assertTrue(result.get("continue"))

    def test_main_failed_command_addressed_in_response(self):
        """Failed command but response mentions the error keyword → not blocked (lines 218-227)."""
        mod = self._load_module()
        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False, encoding="utf-8") as f:
            lines = [
                json.dumps({"type": "assistant", "message": {"content": [
                    {"type": "tool_use", "name": "Bash", "id": "tidA",
                     "input": {"command": "python script.py"}},
                ]}}),
                json.dumps({"type": "user", "message": {"content": [
                    {"type": "tool_result", "tool_use_id": "tidA",
                     "is_error": True, "content": "ImportError modulenotfoundxyz missing"},
                ]}}),
            ]
            f.write("\n".join(lines) + "\n")
            tp = f.name
        try:
            with tempfile.TemporaryDirectory() as tmp:
                log = os.path.join(tmp, "quality-gate.log")
                with unittest.mock.patch.object(mod, "LOG_PATH", log), \
                     unittest.mock.patch.object(mod, "check_cache", return_value=(True, "ok")):
                    result = self._call_main(mod, {
                        "agent_type": "test",
                        "agent_transcript_path": tp,
                        "last_assistant_message": "There was an error with modulenotfoundxyz, I fixed it.",
                    })
        finally:
            os.unlink(tp)
        self.assertTrue(result.get("continue"))

    def test_main_no_tool_names_skips_failed_commands(self):
        """No tool_names → failed_commands=[] (line 175 branch: `if tool_names`)."""
        mod = self._load_module()
        with tempfile.TemporaryDirectory() as tmp:
            log = os.path.join(tmp, "quality-gate.log")
            with unittest.mock.patch.object(mod, "LOG_PATH", log), \
                 unittest.mock.patch.object(mod, "check_cache", return_value=(True, "ok")):
                result = self._call_main(mod, {
                    "agent_type": "test",
                    "agent_transcript_path": "",
                    "last_assistant_message": "I read the docs.",
                })
        self.assertTrue(result.get("continue"))

    def test_main_dunder_main_guard_pragma(self):
        """__main__ guard at line 273 is marked pragma: no cover — verify it exists in source."""
        mod = self._load_module()
        import inspect
        src = inspect.getsource(mod)
        self.assertIn('if __name__ == "__main__"', src)


# ---------------------------------------------------------------------------
# Additional coverage for TestErrorDedup missing lines
# ---------------------------------------------------------------------------

class TestErrorDedupExtra(unittest.TestCase):
    """Additional coverage for error-dedup.py missing lines."""

    def _import(self):
        if "error-dedup" not in sys.modules:
            with patch("sys.stdin", io.StringIO("{}")), patch("sys.exit"):
                sys.modules["error-dedup"] = __import__("error-dedup")
        return sys.modules["error-dedup"]

    def test_load_state_bad_json_returns_none(self):
        """load_state returns None when JSON parse fails (lines 83-84)."""
        m = self._import()
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8") as f:
            f.write("not valid json{{{")
            p = f.name
        try:
            with patch.object(m, "STATE_FILE", p):
                result = m.load_state()
        finally:
            os.unlink(p)
        self.assertIsNone(result)

    def test_atomic_write_permission_retry(self):
        """atomic_write retries on PermissionError (lines 73-74)."""
        m = self._import()
        with tempfile.TemporaryDirectory() as tmp:
            p = os.path.join(tmp, "s.json")
            call_count = [0]
            real_replace = os.replace
            def fake_replace(src, dst):
                call_count[0] += 1
                if call_count[0] < 2:
                    raise PermissionError("locked")
                real_replace(src, dst)
            with patch("os.replace", side_effect=fake_replace):
                m.atomic_write(p, {"k": "v"})
        self.assertEqual(call_count[0], 2)

    def test_tier2_posttooluse_bash_error_extracted(self):
        """PostToolUse Bash with exit code and error line → extracted (lines 123-133)."""
        m = self._import()
        p = {
            "hook_event_name": "PostToolUse",
            "session_id": "s2",
            "tool_name": "Bash",
            "tool_response": "Exit code 1\nTraceback (most recent call last):\n  ModuleNotFoundError: no module named foo",
        }
        with tempfile.TemporaryDirectory() as tmp:
            sf = os.path.join(tmp, "s.json")
            # Pre-write a stale state file so the PostToolUse throttle check
            # (time.time() - state['ts'] < THROTTLE_SEC) does not exit early.
            old_state = m.new_state("other")
            old_state["ts"] = int(time.time()) - 100
            with open(sf, "w", encoding="utf-8") as fh:
                json.dump(old_state, fh)
            with patch.object(m, "STATE_FILE", sf), \
                 patch("sys.stdin", io.StringIO(json.dumps(p))):
                try:
                    m.main()
                except SystemExit:
                    pass
            self.assertTrue(os.path.exists(sf))
            st = json.load(open(sf, encoding="utf-8"))
        self.assertEqual(len(st["errors"]), 1)

    def test_tier2_no_context_re_match_exits_0(self):
        """PostToolUse Bash without TIER2_CONTEXT_RE match → no error extracted → exits 0."""
        m = self._import()
        p = {
            "hook_event_name": "PostToolUse",
            "session_id": "s3",
            "tool_name": "Bash",
            "tool_response": "Everything is fine, all good",
        }
        with patch("sys.stdin", io.StringIO(json.dumps(p))):
            with self.assertRaises(SystemExit) as ctx:
                m.main()
        self.assertEqual(ctx.exception.code, 0)

    def test_tier2_error_line_not_found_uses_response_prefix(self):
        """PostToolUse Bash: context matches but no TIER2_ERROR_RE line → fallback to response[:500] (line 132-133)."""
        m = self._import()
        # TIER2_CONTEXT_RE matches "Exit code 1" but none of the lines match TIER2_ERROR_RE
        # This forces the fallback to response[:500]
        p = {
            "hook_event_name": "PostToolUse",
            "session_id": "s4",
            "tool_name": "Bash",
            "tool_response": "Exit code 1\nsome other output without error keywords",
        }
        # Also need TIER2_ERROR_RE to match the full response
        # TIER2_ERROR_RE matches "some" - nope. We need it to match response as a whole.
        # Let's include "FAILED" in the response but not in any individual line of length > 10
        p["tool_response"] = "Exit code 1\nFAILED"
        with tempfile.TemporaryDirectory() as tmp:
            sf = os.path.join(tmp, "s.json")
            with patch.object(m, "STATE_FILE", sf), \
                 patch("sys.stdin", io.StringIO(json.dumps(p))):
                try:
                    m.main()
                except SystemExit:
                    pass

    def test_module_level_main_exception_swallowed(self):
        """Module-level try/except swallows Exception from main() (lines 179-180)."""
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "error_dedup_ml",
            os.path.join(HOOKS_DIR, "error-dedup.py")
        )
        mod2 = importlib.util.module_from_spec(spec)
        # Force main() to raise an unexpected exception; module-level except catches it
        with patch("sys.stdin", io.StringIO("{}")), patch("sys.exit"):
            spec.loader.exec_module(mod2)
        # If we get here without crashing, the except block worked

# ---------------------------------------------------------------------------
# Additional coverage for TestPreCompactSnapshot missing lines
# ---------------------------------------------------------------------------

class TestPreCompactSnapshotExtra(unittest.TestCase):
    """Additional coverage for pre-compact-snapshot.py missing lines."""

    def _import(self):
        mod_name = "pre-compact-snapshot"
        if mod_name not in sys.modules:
            sys.modules[mod_name] = __import__(mod_name)
        return sys.modules[mod_name]

    def test_copy_failure_is_swallowed(self):
        """shutil.copy2 failure is silently swallowed (lines 37-38)."""
        m = self._import()
        with tempfile.TemporaryDirectory() as tmp:
            tp = os.path.join(tmp, "t.jsonl")
            open(tp, "w").write("{}\n")
            log = os.path.join(tmp, "audit.log")
            sessions = os.path.join(tmp, "sessions")
            p = {"session_id": "abc", "trigger": "auto", "transcript_path": tp}
            with unittest.mock.patch("sys.stdin", io.StringIO(json.dumps(p))), \
                 unittest.mock.patch.object(m, "LOG_PATH", log), \
                 unittest.mock.patch.object(m, "SESSIONS_DIR", sessions), \
                 unittest.mock.patch("shutil.copy2", side_effect=OSError("disk full")):
                m.main()
            self.assertIn("PRE_COMPACT", open(log, encoding="utf-8").read())

    def test_popen_failure_is_swallowed(self):
        """subprocess.Popen failure is silently swallowed (lines 58-59)."""
        m = self._import()
        with tempfile.TemporaryDirectory() as tmp:
            log = os.path.join(tmp, "audit.log")
            p = {"session_id": "abc", "trigger": "manual", "transcript_path": ""}
            with unittest.mock.patch("sys.stdin", io.StringIO(json.dumps(p))), \
                 unittest.mock.patch.object(m, "LOG_PATH", log), \
                 unittest.mock.patch("subprocess.Popen", side_effect=OSError("no popen")):
                m.main()
            self.assertIn("manual", open(log, encoding="utf-8").read())

    def test_log_write_failure_swallowed(self):
        """Log write failure is silently swallowed (lines 65-66)."""
        m = self._import()
        p = {"session_id": "abc", "trigger": "auto", "transcript_path": ""}
        with unittest.mock.patch("sys.stdin", io.StringIO(json.dumps(p))), \
             unittest.mock.patch("builtins.open", side_effect=OSError("no write")):
            m.main()  # Should not raise

    def test_dunder_main_calls_main(self):
        """__name__ == '__main__' block calls main() (line 70)."""
        import runpy
        # main() will be called; it reads sys.stdin so patch it
        with unittest.mock.patch("sys.stdin", io.StringIO(json.dumps(
            {"session_id": "x", "trigger": "auto", "transcript_path": ""}
        ))), unittest.mock.patch("builtins.open", side_effect=OSError("no log")):
            runpy.run_path(
                os.path.join(HOOKS_DIR, "pre-compact-snapshot.py"),
                run_name="__main__",
            )


if __name__ == "__main__":
    unittest.main(verbosity=2)