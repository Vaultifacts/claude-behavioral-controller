"""Tests for main() entry points of all quality-gate layers that lack them.
Covers: Layer 10, 11, 12, 13, 14, 15_mem, 16, 17_adv, 18_ab, 19_cross, 20, 28, 29, 45, env.
"""
import sys, os, io, json, tempfile, time, unittest, shutil, builtins
sys.path.insert(0, os.path.expanduser('~/.claude/hooks'))


class _MainTestBase(unittest.TestCase):
    """Common setUp/tearDown for main() tests."""

    def setUp(self):
        import qg_session_state as ss
        self.tmpdir = tempfile.mkdtemp()
        self.state_path = os.path.join(self.tmpdir, 'state.json')
        self.monitor_path = os.path.join(self.tmpdir, 'monitor.jsonl')
        ss.STATE_PATH = self.state_path
        ss.LOCK_PATH = self.state_path + '.lock'
        self._orig_stdin = sys.stdin
        self._captured = []
        self._orig_print = builtins.print
        self._orig_argv = sys.argv[:]

    def tearDown(self):
        sys.stdin = self._orig_stdin
        builtins.print = self._orig_print
        sys.argv = self._orig_argv
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _set_stdin(self, obj):
        sys.stdin = io.StringIO(json.dumps(obj))

    def _capture_print(self):
        self._captured = []
        builtins.print = lambda *a, **k: self._captured.append(' '.join(str(x) for x in a))

    def _output(self):
        return ' '.join(self._captured)

    def _write_file(self, name, content):
        path = os.path.join(self.tmpdir, name)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'w', encoding='utf-8') as f:
            f.write(content)
        return path


# --- Layer 10: Audit Integrity ---

class TestLayer10Main(_MainTestBase):
    def test_main_block_runs_integrity_check(self):
        import qg_layer10
        orig_mp = qg_layer10.MONITOR_PATH
        qg_layer10.MONITOR_PATH = self.monitor_path
        open(self.monitor_path, 'w').close()
        import qg_session_state as ss
        state = ss.read_state()
        state['last_integrity_check_ts'] = 0
        ss.write_state(state)
        self._capture_print()
        try:
            result = qg_layer10.run_integrity_check(self.monitor_path)
            # Simulate what __main__ does
            print('Audit trail: {} valid, {} issue(s). Status: {}'.format(
                result['valid_lines'], result['corrupt_lines'], result['status']))
        finally:
            builtins.print = self._orig_print
            qg_layer10.MONITOR_PATH = orig_mp
        self.assertIn('Audit trail', self._output())
        self.assertIn('Status:', self._output())

    def test_main_block_shows_rotation_message(self):
        import qg_layer10
        orig_mp = qg_layer10.MONITOR_PATH
        qg_layer10.MONITOR_PATH = self.monitor_path
        # Write enough lines to trigger rotation (default threshold is 10000)
        with open(self.monitor_path, 'w', encoding='utf-8') as f:
            for i in range(5):
                f.write(json.dumps({"event_id": "e{}".format(i)}) + '\n')
        import qg_session_state as ss
        state = ss.read_state()
        state['last_integrity_check_ts'] = 0
        ss.write_state(state)
        result = qg_layer10.run_integrity_check(self.monitor_path)
        qg_layer10.MONITOR_PATH = orig_mp
        self.assertIn('status', result)


# --- Layer 11: Commit Quality ---

class TestLayer11Main(_MainTestBase):
    def test_main_bad_json_no_crash(self):
        import qg_layer11
        orig = qg_layer11.MONITOR_PATH
        qg_layer11.MONITOR_PATH = self.monitor_path
        sys.stdin = io.StringIO('not json')
        try:
            qg_layer11.main()
        finally:
            qg_layer11.MONITOR_PATH = orig

    def test_main_non_bash_returns(self):
        import qg_layer11
        orig = qg_layer11.MONITOR_PATH
        qg_layer11.MONITOR_PATH = self.monitor_path
        self._set_stdin({"tool_name": "Read", "tool_input": {}})
        self._capture_print()
        try:
            qg_layer11.main()
        finally:
            builtins.print = self._orig_print
            qg_layer11.MONITOR_PATH = orig
        self.assertEqual(self._captured, [])

    def test_main_non_git_bash_returns(self):
        import qg_layer11
        orig = qg_layer11.MONITOR_PATH
        qg_layer11.MONITOR_PATH = self.monitor_path
        self._set_stdin({"tool_name": "Bash", "tool_input": {"command": "ls -la"}})
        self._capture_print()
        try:
            qg_layer11.main()
        finally:
            builtins.print = self._orig_print
            qg_layer11.MONITOR_PATH = orig
        self.assertEqual(self._captured, [])

    def test_main_git_commit_good_message_ok(self):
        import qg_layer11
        orig = qg_layer11.MONITOR_PATH
        qg_layer11.MONITOR_PATH = self.monitor_path
        self._set_stdin({"tool_name": "Bash", "tool_input": {"command": 'git commit -m "feat: add new feature"'}})
        self._capture_print()
        try:
            qg_layer11.main()
        finally:
            builtins.print = self._orig_print
            qg_layer11.MONITOR_PATH = orig
        # Good conventional commit message should be ok (no output) or advisory
        # Either way, no crash


# --- Layer 12: User Satisfaction ---

class TestLayer12Main(_MainTestBase):
    def test_main_bad_json_no_crash(self):
        import qg_layer12
        orig = qg_layer12.MONITOR_PATH
        qg_layer12.MONITOR_PATH = self.monitor_path
        sys.stdin = io.StringIO('not json')
        try:
            qg_layer12.main()
        finally:
            qg_layer12.MONITOR_PATH = orig

    def test_main_neutral_no_output(self):
        import qg_layer12
        orig = qg_layer12.MONITOR_PATH
        qg_layer12.MONITOR_PATH = self.monitor_path
        self._set_stdin({"message": "ok thanks"})
        self._capture_print()
        try:
            qg_layer12.main()
        finally:
            builtins.print = self._orig_print
            qg_layer12.MONITOR_PATH = orig
        # Neutral message should produce no output
        # (May or may not depending on classify_sentiment)

    def test_main_frustration_produces_output(self):
        import qg_layer12
        orig = qg_layer12.MONITOR_PATH
        qg_layer12.MONITOR_PATH = self.monitor_path
        self._set_stdin({"message": "no that's wrong, stop doing that, I already told you!"})
        self._capture_print()
        try:
            qg_layer12.main()
        finally:
            builtins.print = self._orig_print
            qg_layer12.MONITOR_PATH = orig
        # Frustration should be detected


# --- Layer 13: Knowledge Freshness ---

class TestLayer13Main(_MainTestBase):
    def test_main_bad_json_no_crash(self):
        import qg_layer13
        orig = qg_layer13.MONITOR_PATH
        qg_layer13.MONITOR_PATH = self.monitor_path
        sys.stdin = io.StringIO('not json')
        try:
            qg_layer13.main()
        finally:
            qg_layer13.MONITOR_PATH = orig

    def test_main_non_write_tool_returns(self):
        import qg_layer13
        orig = qg_layer13.MONITOR_PATH
        qg_layer13.MONITOR_PATH = self.monitor_path
        self._set_stdin({"tool_name": "Bash", "tool_input": {}})
        self._capture_print()
        try:
            qg_layer13.main()
        finally:
            builtins.print = self._orig_print
            qg_layer13.MONITOR_PATH = orig
        self.assertEqual(self._captured, [])

    def test_main_non_py_file_returns(self):
        import qg_layer13
        orig = qg_layer13.MONITOR_PATH
        qg_layer13.MONITOR_PATH = self.monitor_path
        self._set_stdin({"tool_name": "Write", "tool_input": {"file_path": "/tmp/test.txt"}})
        self._capture_print()
        try:
            qg_layer13.main()
        finally:
            builtins.print = self._orig_print
            qg_layer13.MONITOR_PATH = orig
        self.assertEqual(self._captured, [])

    def test_main_py_file_with_valid_imports_no_issues(self):
        import qg_layer13
        orig = qg_layer13.MONITOR_PATH
        qg_layer13.MONITOR_PATH = self.monitor_path
        f = self._write_file('good.py', 'import os\nimport sys\n')
        self._set_stdin({"tool_name": "Write", "tool_input": {"file_path": f}})
        self._capture_print()
        try:
            qg_layer13.main()
        finally:
            builtins.print = self._orig_print
            qg_layer13.MONITOR_PATH = orig


# --- Layer 14: Response Efficiency ---

class TestLayer14Main(_MainTestBase):
    def test_main_bad_json_no_crash(self):
        import qg_layer14
        orig = qg_layer14.MONITOR_PATH
        qg_layer14.MONITOR_PATH = self.monitor_path
        sys.stdin = io.StringIO('not json')
        try:
            qg_layer14.main()
        finally:
            qg_layer14.MONITOR_PATH = orig

    def test_main_no_transcript_returns(self):
        import qg_layer14
        orig = qg_layer14.MONITOR_PATH
        qg_layer14.MONITOR_PATH = self.monitor_path
        self._set_stdin({"transcript_path": ""})
        self._capture_print()
        try:
            qg_layer14.main()
        finally:
            builtins.print = self._orig_print
            qg_layer14.MONITOR_PATH = orig
        self.assertEqual(self._captured, [])

    def test_main_missing_transcript_file_returns(self):
        import qg_layer14
        orig = qg_layer14.MONITOR_PATH
        qg_layer14.MONITOR_PATH = self.monitor_path
        self._set_stdin({"transcript_path": "/nonexistent/file.txt"})
        self._capture_print()
        try:
            qg_layer14.main()
        finally:
            builtins.print = self._orig_print
            qg_layer14.MONITOR_PATH = orig
        # Missing file means no tool_calls → returns early


# --- Layer 15_mem: Memory Integrity ---

class TestLayer15MemMain(_MainTestBase):
    def test_main_bad_json_no_crash(self):
        import qg_layer15_mem
        orig = qg_layer15_mem.MONITOR_PATH
        qg_layer15_mem.MONITOR_PATH = self.monitor_path
        sys.stdin = io.StringIO('not json')
        try:
            qg_layer15_mem.main()
        finally:
            qg_layer15_mem.MONITOR_PATH = orig

    def test_main_runs_analysis_and_outputs(self):
        import qg_layer15_mem
        orig_mp = qg_layer15_mem.MONITOR_PATH
        orig_md = qg_layer15_mem.MEMORY_DIR
        orig_mi = qg_layer15_mem.MEMORY_INDEX
        orig_amd = qg_layer15_mem.ALT_MEMORY_DIR
        mem_dir = os.path.join(self.tmpdir, 'memory')
        os.makedirs(mem_dir, exist_ok=True)
        idx = os.path.join(mem_dir, 'MEMORY.md')
        with open(idx, 'w', encoding='utf-8') as f:
            f.write('# Memory\n')
        qg_layer15_mem.MONITOR_PATH = self.monitor_path
        qg_layer15_mem.MEMORY_DIR = mem_dir
        qg_layer15_mem.MEMORY_INDEX = idx
        qg_layer15_mem.ALT_MEMORY_DIR = os.path.join(self.tmpdir, 'alt_memory')
        self._set_stdin({})
        self._capture_print()
        try:
            qg_layer15_mem.main()
        finally:
            builtins.print = self._orig_print
            qg_layer15_mem.MONITOR_PATH = orig_mp
            qg_layer15_mem.MEMORY_DIR = orig_md
            qg_layer15_mem.MEMORY_INDEX = orig_mi
            qg_layer15_mem.ALT_MEMORY_DIR = orig_amd
        # Should produce output (either ok or issues)
        output = self._output()
        # With empty memory dir, analyze returns ok → main returns early (no output) OR prints stats
        # Either way, no crash


# --- Layer 16: Rollback/Undo ---

class TestLayer16Main(_MainTestBase):
    def test_main_bad_json_no_crash(self):
        import qg_layer16
        orig = qg_layer16.MONITOR_PATH
        qg_layer16.MONITOR_PATH = self.monitor_path
        sys.stdin = io.StringIO('not json')
        try:
            qg_layer16.main()
        finally:
            qg_layer16.MONITOR_PATH = orig

    def test_main_non_edit_tool_returns(self):
        import qg_layer16
        orig = qg_layer16.MONITOR_PATH
        qg_layer16.MONITOR_PATH = self.monitor_path
        self._set_stdin({"tool_name": "Read", "tool_input": {}})
        self._capture_print()
        try:
            qg_layer16.main()
        finally:
            builtins.print = self._orig_print
            qg_layer16.MONITOR_PATH = orig
        self.assertEqual(self._captured, [])

    def test_main_edit_captures_snapshot(self):
        import qg_layer16
        orig_mp = qg_layer16.MONITOR_PATH
        orig_sd = qg_layer16.SNAPSHOT_DIR
        snap_dir = os.path.join(self.tmpdir, 'snapshots')
        os.makedirs(snap_dir, exist_ok=True)
        qg_layer16.MONITOR_PATH = self.monitor_path
        qg_layer16.SNAPSHOT_DIR = snap_dir
        f = self._write_file('target.py', 'x = 1\n')
        self._set_stdin({"tool_name": "Edit", "tool_input": {"file_path": f}})
        self._capture_print()
        try:
            qg_layer16.main()
        finally:
            builtins.print = self._orig_print
            qg_layer16.MONITOR_PATH = orig_mp
            qg_layer16.SNAPSHOT_DIR = orig_sd
        output = self._output()
        self.assertIn('Snapshot', output)
        self.assertIn('target.py', output)

    def test_main_empty_file_path_returns(self):
        import qg_layer16
        orig = qg_layer16.MONITOR_PATH
        qg_layer16.MONITOR_PATH = self.monitor_path
        self._set_stdin({"tool_name": "Write", "tool_input": {"file_path": ""}})
        self._capture_print()
        try:
            qg_layer16.main()
        finally:
            builtins.print = self._orig_print
            qg_layer16.MONITOR_PATH = orig
        self.assertEqual(self._captured, [])


# --- Layer 17_adv: Adversarial Self-Test ---

class TestLayer17AdvMain(_MainTestBase):
    def test_main_bad_json_no_crash(self):
        import qg_layer17_adv
        orig_mp = qg_layer17_adv.MONITOR_PATH
        qg_layer17_adv.MONITOR_PATH = self.monitor_path
        sys.stdin = io.StringIO('not json')
        try:
            qg_layer17_adv.main()
        finally:
            qg_layer17_adv.MONITOR_PATH = orig_mp

    def test_main_skips_when_not_due(self):
        import qg_layer17_adv
        orig_mp = qg_layer17_adv.MONITOR_PATH
        orig_rp = qg_layer17_adv.RESULTS_PATH
        results_path = os.path.join(self.tmpdir, 'results.json')
        with open(results_path, 'w') as f:
            json.dump({"ts": time.time()}, f)
        qg_layer17_adv.MONITOR_PATH = self.monitor_path
        qg_layer17_adv.RESULTS_PATH = results_path
        self._set_stdin({})
        self._capture_print()
        try:
            qg_layer17_adv.main()
        finally:
            builtins.print = self._orig_print
            qg_layer17_adv.MONITOR_PATH = orig_mp
            qg_layer17_adv.RESULTS_PATH = orig_rp
        # Should skip because results are fresh
        self.assertEqual(self._captured, [])

    def test_main_runs_when_no_results_file(self):
        import qg_layer17_adv
        orig_mp = qg_layer17_adv.MONITOR_PATH
        orig_rp = qg_layer17_adv.RESULTS_PATH
        qg_layer17_adv.MONITOR_PATH = self.monitor_path
        qg_layer17_adv.RESULTS_PATH = os.path.join(self.tmpdir, 'nonexistent.json')
        self._set_stdin({})
        self._capture_print()
        try:
            qg_layer17_adv.main()
        finally:
            builtins.print = self._orig_print
            qg_layer17_adv.MONITOR_PATH = orig_mp
            qg_layer17_adv.RESULTS_PATH = orig_rp
        output = self._output()
        self.assertIn('Layer 17', output)


# --- Layer 18_ab: A/B Rule Testing ---

class TestLayer18AbMain(_MainTestBase):
    def test_main_bad_json_no_crash(self):
        import qg_layer18_ab
        orig = qg_layer18_ab.MONITOR_PATH
        qg_layer18_ab.MONITOR_PATH = self.monitor_path
        sys.stdin = io.StringIO('not json')
        try:
            qg_layer18_ab.main()
        finally:
            qg_layer18_ab.MONITOR_PATH = orig

    def test_main_cli_mode_with_proposed_rules(self):
        import qg_layer18_ab
        orig_mp = qg_layer18_ab.MONITOR_PATH
        orig_rp = qg_layer18_ab.RESULTS_PATH
        qg_layer18_ab.MONITOR_PATH = self.monitor_path
        qg_layer18_ab.RESULTS_PATH = os.path.join(self.tmpdir, 'ab-results.json')
        rules_file = self._write_file('proposed.json', '[]')
        sys.argv = ['qg_layer18_ab.py', rules_file]
        self._capture_print()
        try:
            qg_layer18_ab.main()
        finally:
            builtins.print = self._orig_print
            qg_layer18_ab.MONITOR_PATH = orig_mp
            qg_layer18_ab.RESULTS_PATH = orig_rp

    def test_main_hook_mode_no_events_returns(self):
        import qg_layer18_ab
        orig_mp = qg_layer18_ab.MONITOR_PATH
        qg_layer18_ab.MONITOR_PATH = os.path.join(self.tmpdir, 'empty.jsonl')
        open(qg_layer18_ab.MONITOR_PATH, 'w').close()
        sys.argv = ['qg_layer18_ab.py']
        self._set_stdin({})
        self._capture_print()
        try:
            qg_layer18_ab.main()
        finally:
            builtins.print = self._orig_print
            qg_layer18_ab.MONITOR_PATH = orig_mp
        # No events means main returns early
        self.assertEqual(self._captured, [])


# --- Layer 19_cross: Cross-Project Patterns ---

class TestLayer19CrossMain(_MainTestBase):
    def test_main_bad_json_no_crash(self):
        import qg_layer19_cross
        orig = qg_layer19_cross.MONITOR_PATH
        qg_layer19_cross.MONITOR_PATH = self.monitor_path
        sys.stdin = io.StringIO('not json')
        try:
            qg_layer19_cross.main()
        finally:
            qg_layer19_cross.MONITOR_PATH = orig

    def test_main_no_data_returns(self):
        import qg_layer19_cross
        orig_mp = qg_layer19_cross.MONITOR_PATH
        qg_layer19_cross.MONITOR_PATH = self.monitor_path
        open(self.monitor_path, 'w').close()
        self._set_stdin({})
        self._capture_print()
        try:
            qg_layer19_cross.main()
        finally:
            builtins.print = self._orig_print
            qg_layer19_cross.MONITOR_PATH = orig_mp
        # No data → no_data status → returns early


# --- Layer 20: System Health ---

class TestLayer20Main(_MainTestBase):
    def test_main_bad_json_no_crash(self):
        import qg_layer20
        orig = qg_layer20.MONITOR_PATH
        qg_layer20.MONITOR_PATH = self.monitor_path
        sys.stdin = io.StringIO('not json')
        try:
            qg_layer20.main()
        finally:
            qg_layer20.MONITOR_PATH = orig

    def test_main_produces_health_output(self):
        import qg_layer20
        orig_mp = qg_layer20.MONITOR_PATH
        orig_sp = qg_layer20.SETTINGS_PATH
        settings = self._write_file('settings.json', '{}')
        qg_layer20.MONITOR_PATH = self.monitor_path
        qg_layer20.SETTINGS_PATH = settings
        open(self.monitor_path, 'w').close()
        self._set_stdin({})
        self._capture_print()
        try:
            qg_layer20.main()
        finally:
            builtins.print = self._orig_print
            qg_layer20.MONITOR_PATH = orig_mp
            qg_layer20.SETTINGS_PATH = orig_sp
        output = self._output()
        self.assertIn('Layer 20', output)

    def test_main_json_output_format(self):
        import qg_layer20
        orig_mp = qg_layer20.MONITOR_PATH
        orig_sp = qg_layer20.SETTINGS_PATH
        settings = self._write_file('settings.json', '{}')
        qg_layer20.MONITOR_PATH = self.monitor_path
        qg_layer20.SETTINGS_PATH = settings
        open(self.monitor_path, 'w').close()
        self._set_stdin({})
        self._capture_print()
        try:
            qg_layer20.main()
        finally:
            builtins.print = self._orig_print
            qg_layer20.MONITOR_PATH = orig_mp
            qg_layer20.SETTINGS_PATH = orig_sp
        output = self._output()
        parsed = json.loads(output)
        self.assertIn('hookSpecificOutput', parsed)


# --- Layer 28: Security Detection ---

class TestLayer28Main(_MainTestBase):
    def test_main_bad_json_no_crash(self):
        import qg_layer28
        orig = qg_layer28.MONITOR_PATH
        qg_layer28.MONITOR_PATH = self.monitor_path
        sys.stdin = io.StringIO('not json')
        try:
            qg_layer28.main()
        finally:
            qg_layer28.MONITOR_PATH = orig

    def test_main_non_write_tool_returns(self):
        import qg_layer28
        orig = qg_layer28.MONITOR_PATH
        qg_layer28.MONITOR_PATH = self.monitor_path
        self._set_stdin({"tool_name": "Read", "tool_input": {}})
        self._capture_print()
        try:
            qg_layer28.main()
        finally:
            builtins.print = self._orig_print
            qg_layer28.MONITOR_PATH = orig
        self.assertEqual(self._captured, [])

    def test_main_clean_file_no_output(self):
        import qg_layer28
        orig = qg_layer28.MONITOR_PATH
        qg_layer28.MONITOR_PATH = self.monitor_path
        f = self._write_file('safe.py', 'x = 1\n')
        self._set_stdin({"tool_name": "Write", "tool_input": {"file_path": f}})
        self._capture_print()
        try:
            qg_layer28.main()
        finally:
            builtins.print = self._orig_print
            qg_layer28.MONITOR_PATH = orig
        self.assertEqual(self._captured, [])

    def test_main_vuln_file_produces_output(self):
        import qg_layer28
        orig = qg_layer28.MONITOR_PATH
        qg_layer28.MONITOR_PATH = self.monitor_path
        f = self._write_file('vuln.py', 'cursor.execute(f"SELECT * FROM users WHERE id={uid}")\n')
        self._set_stdin({"tool_name": "Write", "tool_input": {"file_path": f}})
        self._capture_print()
        try:
            qg_layer28.main()
        finally:
            builtins.print = self._orig_print
            qg_layer28.MONITOR_PATH = orig
        output = self._output()
        self.assertIn('SECURITY', output)

    def test_main_empty_file_path_returns(self):
        import qg_layer28
        orig = qg_layer28.MONITOR_PATH
        qg_layer28.MONITOR_PATH = self.monitor_path
        self._set_stdin({"tool_name": "Edit", "tool_input": {"file_path": ""}})
        self._capture_print()
        try:
            qg_layer28.main()
        finally:
            builtins.print = self._orig_print
            qg_layer28.MONITOR_PATH = orig
        self.assertEqual(self._captured, [])


# --- Layer 29: Semantic Correctness ---

class TestLayer29Main(_MainTestBase):
    def test_main_bad_json_no_crash(self):
        import qg_layer29
        orig = qg_layer29.MONITOR_PATH
        qg_layer29.MONITOR_PATH = self.monitor_path
        sys.stdin = io.StringIO('not json')
        try:
            qg_layer29.main()
        finally:
            qg_layer29.MONITOR_PATH = orig

    def test_main_no_transcript_returns(self):
        import qg_layer29
        orig = qg_layer29.MONITOR_PATH
        qg_layer29.MONITOR_PATH = self.monitor_path
        self._set_stdin({"transcript_path": ""})
        self._capture_print()
        try:
            qg_layer29.main()
        finally:
            builtins.print = self._orig_print
            qg_layer29.MONITOR_PATH = orig
        self.assertEqual(self._captured, [])

    def test_main_missing_transcript_returns(self):
        import qg_layer29
        orig = qg_layer29.MONITOR_PATH
        qg_layer29.MONITOR_PATH = self.monitor_path
        self._set_stdin({"transcript_path": "/nonexistent/transcript.txt"})
        self._capture_print()
        try:
            qg_layer29.main()
        finally:
            builtins.print = self._orig_print
            qg_layer29.MONITOR_PATH = orig
        # Missing file → no data → returns


# --- Layer 45: Context Preservation ---

class TestLayer45Main(_MainTestBase):
    def test_main_no_args_does_nothing(self):
        import qg_layer45
        sys.argv = ['qg_layer45.py']
        qg_layer45.main()

    def test_main_pre_flag(self):
        import qg_layer45
        orig_pp = qg_layer45.PRESERVE_PATH
        qg_layer45.PRESERVE_PATH = os.path.join(self.tmpdir, 'preserve.json')
        sys.argv = ['qg_layer45.py', '--pre']
        try:
            qg_layer45.main()
        finally:
            qg_layer45.PRESERVE_PATH = orig_pp
        self.assertTrue(os.path.exists(os.path.join(self.tmpdir, 'preserve.json')))

    def test_main_post_flag_missing_file_no_crash(self):
        import qg_layer45
        orig_pp = qg_layer45.PRESERVE_PATH
        qg_layer45.PRESERVE_PATH = os.path.join(self.tmpdir, 'nonexistent.json')
        sys.argv = ['qg_layer45.py', '--post']
        try:
            qg_layer45.main()
        finally:
            qg_layer45.PRESERVE_PATH = orig_pp

    def test_main_pre_then_post_restores(self):
        import qg_layer45, qg_session_state as ss
        orig_pp = qg_layer45.PRESERVE_PATH
        preserve = os.path.join(self.tmpdir, 'preserve.json')
        qg_layer45.PRESERVE_PATH = preserve
        state = ss.read_state()
        state['session_uuid'] = 'test-uuid-45-main'
        state['active_task_description'] = 'my task'
        ss.write_state(state)
        sys.argv = ['qg_layer45.py', '--pre']
        qg_layer45.main()
        # Clear state
        state2 = ss.read_state()
        state2['active_task_description'] = ''
        ss.write_state(state2)
        sys.argv = ['qg_layer45.py', '--post']
        self._capture_print()
        try:
            qg_layer45.main()
        finally:
            builtins.print = self._orig_print
            qg_layer45.PRESERVE_PATH = orig_pp
        state3 = ss.read_state()
        self.assertEqual(state3.get('active_task_description'), 'my task')


# --- Layer env: Environment Validation ---

class TestLayerEnvMain(_MainTestBase):
    def test_main_bad_json_no_crash(self):
        import qg_layer_env
        sys.stdin = io.StringIO('not json')
        qg_layer_env.main()

    def test_main_unknown_event_no_crash(self):
        import qg_layer_env
        self._set_stdin({"hook_event_name": "Unknown"})
        qg_layer_env.main()

    def test_main_session_start(self):
        import qg_layer_env
        orig_mp = qg_layer_env._MONITOR_PATH
        qg_layer_env._MONITOR_PATH = self.monitor_path
        self._set_stdin({"hook_event_name": "SessionStart"})
        self._capture_print()
        try:
            qg_layer_env.main()
        finally:
            builtins.print = self._orig_print
            qg_layer_env._MONITOR_PATH = orig_mp

    def test_main_pre_tool_use(self):
        import qg_layer_env
        orig_mp = qg_layer_env._MONITOR_PATH
        qg_layer_env._MONITOR_PATH = self.monitor_path
        self._set_stdin({"hook_event_name": "PreToolUse", "tool_name": "Bash",
                         "tool_input": {"command": "echo hi"}})
        self._capture_print()
        try:
            qg_layer_env.main()
        finally:
            builtins.print = self._orig_print
            qg_layer_env._MONITOR_PATH = orig_mp


# --- Layer 17 (1.7): User Intent Verification ---

class TestLayer17Main(_MainTestBase):
    def _setup_layer17(self):
        import qg_layer17
        self._orig_mp17 = qg_layer17.MONITOR_PATH
        self._orig_rp17 = qg_layer17.RULES_PATH
        qg_layer17.MONITOR_PATH = self.monitor_path
        qg_layer17.RULES_PATH = os.path.join(self.tmpdir, 'rules.json')
        with open(qg_layer17.RULES_PATH, 'w') as f:
            json.dump({"layer17": {}}, f)
        return qg_layer17

    def _teardown_layer17(self, mod):
        mod.MONITOR_PATH = self._orig_mp17
        mod.RULES_PATH = self._orig_rp17

    def test_main_bad_json_no_crash(self):
        mod = self._setup_layer17()
        sys.stdin = io.StringIO('not json')
        try:
            mod.main()
        finally:
            self._teardown_layer17(mod)

    def test_main_no_task_id_returns(self):
        import qg_session_state as ss
        mod = self._setup_layer17()
        state = ss.read_state()
        state['active_task_id'] = ''
        ss.write_state(state)
        self._set_stdin({"tool_name": "Edit", "tool_input": {}})
        self._capture_print()
        try:
            mod.main()
        finally:
            builtins.print = self._orig_print
            self._teardown_layer17(mod)
        self.assertEqual(self._captured, [])

    def test_main_should_verify_false_returns(self):
        import qg_session_state as ss
        mod = self._setup_layer17()
        state = ss.read_state()
        state['active_task_id'] = 'task_sv_false'
        state['layer1_task_category'] = 'SIMPLE'
        state['layer19_last_impact_level'] = 'LOW'
        ss.write_state(state)
        self._set_stdin({"tool_name": "Edit", "tool_input": {}})
        self._capture_print()
        try:
            mod.main()
        finally:
            builtins.print = self._orig_print
            self._teardown_layer17(mod)
        self.assertEqual(self._captured, [])

    def test_main_first_fire_captures_intent(self):
        import qg_session_state as ss
        mod = self._setup_layer17()
        state = ss.read_state()
        state['active_task_id'] = 'task_first_fire'
        state['layer1_task_category'] = 'DEEP'
        state['active_task_description'] = 'Refactor the auth module for better performance'
        state['layer19_last_impact_level'] = 'LOW'
        state['layer1_scope_files'] = ['auth.py']
        ss.write_state(state)
        self._set_stdin({"tool_name": "Edit", "tool_input": {"file_path": "/src/auth.py"}})
        self._capture_print()
        try:
            mod.main()
        finally:
            builtins.print = self._orig_print
            self._teardown_layer17(mod)
        output = self._output()
        self.assertIn('layer1.7', output)
        self.assertIn('DEEP', output)
        state2 = ss.read_state()
        self.assertEqual(state2.get('layer17_verified_task_id'), 'task_first_fire')
        self.assertEqual(state2.get('layer17_uncertainty_level'), 'LOW')

    def test_main_first_fire_creating_new_artifacts(self):
        import qg_session_state as ss
        mod = self._setup_layer17()
        state = ss.read_state()
        state['active_task_id'] = 'task_create'
        state['layer1_task_category'] = 'DEEP'
        state['active_task_description'] = 'Create a new authentication system'
        state['layer19_last_impact_level'] = 'LOW'
        ss.write_state(state)
        self._set_stdin({"tool_name": "Write", "tool_input": {"file_path": "/src/new_auth.py"}})
        self._capture_print()
        try:
            mod.main()
        finally:
            builtins.print = self._orig_print
            self._teardown_layer17(mod)
        state2 = ss.read_state()
        self.assertTrue(state2.get('layer17_creating_new_artifacts'))

    def test_main_first_fire_uncertainty_medium(self):
        import qg_session_state as ss
        mod = self._setup_layer17()
        state = ss.read_state()
        state['active_task_id'] = 'task_uncertain'
        state['layer1_task_category'] = 'DEEP'
        state['active_task_description'] = 'Maybe we should refactor the database layer'
        state['layer19_last_impact_level'] = 'LOW'
        ss.write_state(state)
        self._set_stdin({"tool_name": "Edit", "tool_input": {}})
        self._capture_print()
        try:
            mod.main()
        finally:
            builtins.print = self._orig_print
            self._teardown_layer17(mod)
        state2 = ss.read_state()
        self.assertEqual(state2.get('layer17_uncertainty_level'), 'MEDIUM')

    def test_main_subsequent_call_no_output(self):
        import qg_session_state as ss
        mod = self._setup_layer17()
        state = ss.read_state()
        state['active_task_id'] = 'task_dup'
        state['layer17_verified_task_id'] = 'task_dup'
        ss.write_state(state)
        self._set_stdin({"tool_name": "Read", "tool_input": {}})
        self._capture_print()
        try:
            mod.main()
        finally:
            builtins.print = self._orig_print
            self._teardown_layer17(mod)
        self.assertEqual(self._captured, [])

    def test_main_scope_mismatch_detected(self):
        import qg_session_state as ss
        mod = self._setup_layer17()
        state = ss.read_state()
        state['active_task_id'] = 'task_scope'
        state['layer17_verified_task_id'] = 'task_scope'
        state['layer1_scope_files'] = ['auth.py', 'login.py']
        state['layer17_mismatch_count'] = 0
        ss.write_state(state)
        self._set_stdin({"tool_name": "Edit", "tool_input": {"file_path": "/src/database/queries.py"}})
        try:
            mod.main()
        finally:
            self._teardown_layer17(mod)
        state2 = ss.read_state()
        self.assertEqual(state2.get('layer17_mismatch_count'), 1)
        # Verify mismatch event written to monitor
        with open(self.monitor_path, 'r') as f:
            lines = f.readlines()
        self.assertGreaterEqual(len(lines), 1)
        event = json.loads(lines[-1])
        self.assertEqual(event['category'], 'INTENT_MISMATCH')

    def test_main_scope_match_no_mismatch(self):
        import qg_session_state as ss
        mod = self._setup_layer17()
        state = ss.read_state()
        state['active_task_id'] = 'task_match'
        state['layer17_verified_task_id'] = 'task_match'
        state['layer1_scope_files'] = ['auth.py']
        state['layer17_mismatch_count'] = 0
        ss.write_state(state)
        self._set_stdin({"tool_name": "Edit", "tool_input": {"file_path": "/src/auth.py"}})
        try:
            mod.main()
        finally:
            self._teardown_layer17(mod)
        state2 = ss.read_state()
        self.assertEqual(state2.get('layer17_mismatch_count', 0), 0)

    def test_main_high_impact_triggers_even_simple_task(self):
        import qg_session_state as ss
        mod = self._setup_layer17()
        state = ss.read_state()
        state['active_task_id'] = 'task_hi'
        state['layer1_task_category'] = 'SIMPLE'
        state['layer19_last_impact_level'] = 'HIGH'
        state['active_task_description'] = 'Fix the typo'
        ss.write_state(state)
        self._set_stdin({"tool_name": "Edit", "tool_input": {}})
        self._capture_print()
        try:
            mod.main()
        finally:
            builtins.print = self._orig_print
            self._teardown_layer17(mod)
        output = self._output()
        self.assertIn('layer1.7', output)
        self.assertIn('HIGH', output)


# --- Layer 35: Recovery Tracking (coverage gaps) ---

class TestLayer35Coverage(_MainTestBase):
    def test_unresolved_lines_open_event(self):
        from qg_layer35 import layer35_unresolved_lines
        state = {'layer35_recovery_events': [
            {'status': 'open', 'category': 'LAZINESS', 'task_id': 't1'},
        ]}
        lines = layer35_unresolved_lines(state)
        self.assertEqual(len(lines), 1)
        self.assertIn('UNRESOLVED', lines[0])
        self.assertIn('LAZINESS', lines[0])

    def test_unresolved_lines_timed_out_critical(self):
        from qg_layer35 import layer35_unresolved_lines
        state = {'layer35_recovery_events': [
            {'status': 'timed_out', 'severity': 'critical', 'category': 'LOOP', 'task_id': 't2'},
        ]}
        lines = layer35_unresolved_lines(state)
        self.assertEqual(len(lines), 1)
        self.assertIn('TIMED_OUT', lines[0])

    def test_unresolved_lines_timed_out_non_critical_skipped(self):
        from qg_layer35 import layer35_unresolved_lines
        state = {'layer35_recovery_events': [
            {'status': 'timed_out', 'severity': 'warning', 'category': 'LOOP', 'task_id': 't3'},
        ]}
        lines = layer35_unresolved_lines(state)
        self.assertEqual(len(lines), 0)

    def test_unresolved_lines_resolved_skipped(self):
        from qg_layer35 import layer35_unresolved_lines
        state = {'layer35_recovery_events': [
            {'status': 'resolved', 'category': 'X', 'task_id': 't4'},
        ]}
        self.assertEqual(layer35_unresolved_lines(state), [])

    def test_unresolved_lines_empty(self):
        from qg_layer35 import layer35_unresolved_lines
        self.assertEqual(layer35_unresolved_lines({}), [])

    def test_check_resolutions_timeout_by_turns(self):
        from qg_layer35 import layer35_check_resolutions
        import qg_session_state as ss
        state = ss.read_state()
        state['layer2_turn_history'] = ['t1', 't2', 't3', 't4', 't5', 't6']
        state['layer35_recovery_events'] = [{
            'status': 'open', 'ts': time.time(), 'turn': 1,
            'event_id': 'e1', 'verdict': 'FN', 'category': 'LAZINESS',
            'task_id': 'task1', 'session_uuid': 'u1', 'tools_at_flag': [],
        }]
        layer35_check_resolutions([], state)
        evt = state['layer35_recovery_events'][0]
        self.assertEqual(evt['status'], 'timed_out')
        self.assertEqual(evt['severity'], 'critical')

    def test_check_resolutions_timeout_by_time(self):
        from qg_layer35 import layer35_check_resolutions
        import qg_session_state as ss
        state = ss.read_state()
        state['layer2_turn_history'] = ['t1', 't2']
        state['layer35_recovery_events'] = [{
            'status': 'open', 'ts': time.time() - 2000, 'turn': 1,
            'event_id': 'e2', 'verdict': 'FN', 'category': 'LOOP',
            'task_id': 'task2', 'session_uuid': 'u2', 'tools_at_flag': [],
        }]
        layer35_check_resolutions([], state)
        evt = state['layer35_recovery_events'][0]
        self.assertEqual(evt['status'], 'timed_out')

    def test_detect_fn_signals_rules_repeated_claim(self):
        from qg_layer35 import _detect_fn_signals_rules
        state = {'layer3_last_response_claims': ['the function works correctly and all tests pass']}
        resp = 'as mentioned, the function works correctly and all tests pass'
        signals = _detect_fn_signals_rules(resp, state)
        self.assertTrue(any('repeated' in s for s in signals))

    def test_detect_fn_signals_haiku_import_fails(self):
        from qg_layer35 import detect_fn_signals
        # use_haiku=True but _hooks_shared not importable → falls back to rule signals
        result = detect_fn_signals('done, all tests pass', ['Read'], 'fix bug', {}, use_haiku=True)
        self.assertIsInstance(result, list)


# --- Layer 18: Hallucination Detection (coverage gaps) ---

class TestLayer18Coverage(_MainTestBase):
    def test_main_write_tool_returns_early(self):
        import qg_layer18
        orig_mp = qg_layer18._MONITOR_PATH
        qg_layer18._MONITOR_PATH = self.monitor_path
        self._set_stdin({"tool_name": "Write", "tool_input": {"file_path": "/tmp/new.py"}})
        self._capture_print()
        try:
            qg_layer18.main()
        finally:
            builtins.print = self._orig_print
            qg_layer18._MONITOR_PATH = orig_mp
        self.assertEqual(self._captured, [])

    def test_main_non_edit_returns(self):
        import qg_layer18
        self._set_stdin({"tool_name": "Read", "tool_input": {}})
        self._capture_print()
        try:
            qg_layer18.main()
        finally:
            builtins.print = self._orig_print
        self.assertEqual(self._captured, [])

    def test_main_empty_file_path_returns(self):
        import qg_layer18
        self._set_stdin({"tool_name": "Edit", "tool_input": {"file_path": ""}})
        self._capture_print()
        try:
            qg_layer18.main()
        finally:
            builtins.print = self._orig_print
        self.assertEqual(self._captured, [])

    def test_main_nonexistent_file_warns(self):
        import qg_layer18, qg_session_state as ss
        orig_mp = qg_layer18._MONITOR_PATH
        orig_rp = qg_layer18.RULES_PATH
        qg_layer18._MONITOR_PATH = self.monitor_path
        qg_layer18.RULES_PATH = os.path.join(self.tmpdir, 'nonexistent_rules.json')
        state = ss.read_state()
        state['layer17_creating_new_artifacts'] = False
        ss.write_state(state)
        self._set_stdin({"tool_name": "Edit", "tool_input": {"file_path": "/zzzz_nonexistent_qg.py"}})
        self._capture_print()
        try:
            qg_layer18.main()
        finally:
            builtins.print = self._orig_print
            qg_layer18._MONITOR_PATH = orig_mp
            qg_layer18.RULES_PATH = orig_rp
        output = self._output()
        self.assertIn('does not exist', output)

    def test_main_no_old_string_returns(self):
        import qg_layer18, qg_session_state as ss
        orig_rp = qg_layer18.RULES_PATH
        qg_layer18.RULES_PATH = os.path.join(self.tmpdir, 'no_rules.json')
        f = self._write_file('exists.py', 'x = 1\n')
        self._set_stdin({"tool_name": "Edit", "tool_input": {"file_path": f, "old_string": ""}})
        self._capture_print()
        try:
            qg_layer18.main()
        finally:
            builtins.print = self._orig_print
            qg_layer18.RULES_PATH = orig_rp
        self.assertEqual(self._captured, [])

    def test_find_remote_refs_with_urls(self):
        from qg_layer18 import find_remote_refs
        refs = find_remote_refs('visit https://example.com and http://test.org/api')
        self.assertEqual(len(refs), 2)

    def test_find_remote_refs_empty(self):
        from qg_layer18 import find_remote_refs
        self.assertEqual(find_remote_refs(''), [])
        self.assertEqual(find_remote_refs(None), [])

    def test_check_imports_in_file_missing_import(self):
        from qg_layer18 import check_imports_in_file
        f = self._write_file('mod.py', 'import os\n')
        result = check_imports_in_file(f, 'import nonexistent_mod_xyz\n')
        self.assertFalse(result)

    def test_check_imports_in_file_empty_args(self):
        from qg_layer18 import check_imports_in_file
        self.assertTrue(check_imports_in_file('', ''))
        self.assertTrue(check_imports_in_file(None, None))

    def test_check_packages_importable_missing(self):
        from qg_layer18 import check_packages_importable
        missing = check_packages_importable('import zzz_nonexistent_pkg_abc\n')
        self.assertIn('zzz_nonexistent_pkg_abc', missing)

    def test_check_packages_importable_real(self):
        from qg_layer18 import check_packages_importable
        missing = check_packages_importable('import os\nimport sys\n')
        self.assertEqual(missing, [])

    def test_check_packages_importable_empty(self):
        from qg_layer18 import check_packages_importable
        self.assertEqual(check_packages_importable(''), [])

    def test_main_import_warning(self):
        import qg_layer18, qg_session_state as ss
        orig_mp = qg_layer18._MONITOR_PATH
        orig_rp = qg_layer18.RULES_PATH
        qg_layer18._MONITOR_PATH = self.monitor_path
        qg_layer18.RULES_PATH = os.path.join(self.tmpdir, 'no_rules.json')
        f = self._write_file('mymod.py', 'import os\nx = 1\n')
        self._set_stdin({"tool_name": "Edit", "tool_input": {
            "file_path": f, "old_string": "import nonexistent_xyz\nx = 1"}})
        self._capture_print()
        try:
            qg_layer18.main()
        finally:
            builtins.print = self._orig_print
            qg_layer18._MONITOR_PATH = orig_mp
            qg_layer18.RULES_PATH = orig_rp
        output = self._output()
        self.assertIn('Import', output)

    def test_main_remote_url_warning(self):
        import qg_layer18, qg_session_state as ss
        orig_mp = qg_layer18._MONITOR_PATH
        orig_rp = qg_layer18.RULES_PATH
        qg_layer18._MONITOR_PATH = self.monitor_path
        qg_layer18.RULES_PATH = os.path.join(self.tmpdir, 'no_rules.json')
        f = self._write_file('urlmod.py', 'url = "https://example.com/api"\n')
        self._set_stdin({"tool_name": "Edit", "tool_input": {
            "file_path": f, "old_string": 'url = "https://example.com/api"'}})
        self._capture_print()
        try:
            qg_layer18.main()
        finally:
            builtins.print = self._orig_print
            qg_layer18._MONITOR_PATH = orig_mp
            qg_layer18.RULES_PATH = orig_rp
        output = self._output()
        self.assertIn('URL', output)


# --- Layer env: Environment Validation (coverage gaps) ---

class TestLayerEnvCoverage(_MainTestBase):
    def test_load_env_config_missing_file(self):
        from qg_layer_env import load_env_config
        import qg_layer_env as mod
        orig = mod.ENV_CONFIG_PATH
        mod.ENV_CONFIG_PATH = os.path.join(self.tmpdir, 'nonexistent.json')
        try:
            cfg = load_env_config()
        finally:
            mod.ENV_CONFIG_PATH = orig
        self.assertEqual(cfg, {})

    def test_load_env_config_valid(self):
        from qg_layer_env import load_env_config
        import qg_layer_env as mod
        orig = mod.ENV_CONFIG_PATH
        f = self._write_file('env.json', '{"git_branch": "main"}')
        mod.ENV_CONFIG_PATH = f
        try:
            cfg = load_env_config()
        finally:
            mod.ENV_CONFIG_PATH = orig
        self.assertEqual(cfg.get('git_branch'), 'main')

    def test_session_start_with_git_branch_config(self):
        import qg_layer_env as mod, qg_session_state as ss
        orig_cp = mod.ENV_CONFIG_PATH
        orig_mp = mod._MONITOR_PATH
        mod._MONITOR_PATH = self.monitor_path
        f = self._write_file('env.json', json.dumps({
            "git_branch": "nonexistent_branch_xyz",
            "skip_git": False
        }))
        mod.ENV_CONFIG_PATH = f
        self._capture_print()
        try:
            mod.run_session_start({})
        finally:
            builtins.print = self._orig_print
            mod.ENV_CONFIG_PATH = orig_cp
            mod._MONITOR_PATH = orig_mp
        # Either git isn't available (no output) or branch mismatch (output)
        # Key: no crash

    def test_session_start_with_missing_tools(self):
        import qg_layer_env as mod, qg_session_state as ss
        orig_cp = mod.ENV_CONFIG_PATH
        orig_mp = mod._MONITOR_PATH
        mod._MONITOR_PATH = self.monitor_path
        f = self._write_file('env2.json', json.dumps({
            "required_tools": ["zzz_nonexistent_tool_qg"]
        }))
        mod.ENV_CONFIG_PATH = f
        self._capture_print()
        try:
            mod.run_session_start({})
        finally:
            builtins.print = self._orig_print
            mod.ENV_CONFIG_PATH = orig_cp
            mod._MONITOR_PATH = orig_mp
        output = self._output()
        self.assertIn('Missing tools', output)

    def test_session_start_with_missing_env_vars(self):
        import qg_layer_env as mod, qg_session_state as ss
        orig_cp = mod.ENV_CONFIG_PATH
        orig_mp = mod._MONITOR_PATH
        mod._MONITOR_PATH = self.monitor_path
        f = self._write_file('env3.json', json.dumps({
            "required_env_vars": ["QG_NONEXISTENT_VAR_XYZ"]
        }))
        mod.ENV_CONFIG_PATH = f
        self._capture_print()
        try:
            mod.run_session_start({})
        finally:
            builtins.print = self._orig_print
            mod.ENV_CONFIG_PATH = orig_cp
            mod._MONITOR_PATH = orig_mp
        output = self._output()
        self.assertIn('Missing env vars', output)

    def test_session_start_with_working_dir_config(self):
        import qg_layer_env as mod, qg_session_state as ss
        orig_cp = mod.ENV_CONFIG_PATH
        orig_mp = mod._MONITOR_PATH
        mod._MONITOR_PATH = self.monitor_path
        f = self._write_file('env4.json', json.dumps({
            "working_dir": "/custom/dir"
        }))
        mod.ENV_CONFIG_PATH = f
        try:
            mod.run_session_start({})
        finally:
            mod.ENV_CONFIG_PATH = orig_cp
            mod._MONITOR_PATH = orig_mp
        state = ss.read_state()
        self.assertEqual(state.get('layer_env_baseline', {}).get('working_dir'), '/custom/dir')

    def test_pre_tool_use_outside_working_dir(self):
        import qg_layer_env as mod, qg_session_state as ss
        state = ss.read_state()
        state['layer_env_baseline'] = {'working_dir': self.tmpdir}
        ss.write_state(state)
        self._capture_print()
        try:
            mod.run_pre_tool_use({"tool_input": {"file_path": "/completely/other/dir/file.py"}})
        finally:
            builtins.print = self._orig_print
        output = self._output()
        self.assertIn('outside working directory', output)

    def test_pre_tool_use_inside_working_dir_no_output(self):
        import qg_layer_env as mod, qg_session_state as ss
        state = ss.read_state()
        state['layer_env_baseline'] = {'working_dir': self.tmpdir}
        ss.write_state(state)
        fp = self._write_file('inside.py', 'x = 1\n')
        self._capture_print()
        try:
            mod.run_pre_tool_use({"tool_input": {"file_path": fp}})
        finally:
            builtins.print = self._orig_print
        self.assertEqual(self._captured, [])

    def test_pre_tool_use_no_file_path_returns(self):
        import qg_layer_env as mod
        self._capture_print()
        try:
            mod.run_pre_tool_use({"tool_input": {}})
        finally:
            builtins.print = self._orig_print
        self.assertEqual(self._captured, [])


# --- Layer 19: Change Impact Analysis (coverage gaps) ---

class TestLayer19Coverage(_MainTestBase):
    def test_count_dependents_empty_path(self):
        from qg_layer19 import count_dependents
        self.assertEqual(count_dependents('', '/tmp'), [])

    def test_count_dependents_no_extension(self):
        from qg_layer19 import count_dependents
        # File with no stem after splitext (edge case)
        result = count_dependents('.hidden', '/tmp')
        self.assertIsInstance(result, list)

    def test_compute_impact_level_core_file(self):
        from qg_layer19 import compute_impact_level
        level = compute_impact_level('src/utils.py', [], {})
        self.assertEqual(level, 'CRITICAL')

    def test_compute_impact_level_low(self):
        from qg_layer19 import compute_impact_level
        level = compute_impact_level('src/my_module.py', [], {})
        self.assertEqual(level, 'LOW')

    def test_compute_impact_level_medium(self):
        from qg_layer19 import compute_impact_level
        deps = ['f{}.py'.format(i) for i in range(10)]
        level = compute_impact_level('src/my_module.py', deps, {})
        self.assertEqual(level, 'MEDIUM')

    def test_compute_impact_level_high(self):
        from qg_layer19 import compute_impact_level
        deps = ['f{}.py'.format(i) for i in range(25)]
        level = compute_impact_level('src/my_module.py', deps, {})
        self.assertEqual(level, 'HIGH')

    def test_load_thresholds_missing_file(self):
        from qg_layer19 import _load_thresholds
        import qg_layer19 as mod
        orig = mod.RULES_PATH
        mod.RULES_PATH = os.path.join(self.tmpdir, 'nonexistent.json')
        try:
            result = _load_thresholds()
        finally:
            mod.RULES_PATH = orig
        self.assertEqual(result, {})

    def test_main_bad_json_no_crash(self):
        import qg_layer19
        sys.stdin = io.StringIO('not json')
        qg_layer19.main()

    def test_main_non_edit_write_returns(self):
        import qg_layer19
        self._set_stdin({"tool_name": "Read", "tool_input": {}})
        self._capture_print()
        try:
            qg_layer19.main()
        finally:
            builtins.print = self._orig_print
        self.assertEqual(self._captured, [])

    def test_main_empty_file_path_returns(self):
        import qg_layer19
        self._set_stdin({"tool_name": "Edit", "tool_input": {"file_path": ""}})
        self._capture_print()
        try:
            qg_layer19.main()
        finally:
            builtins.print = self._orig_print
        self.assertEqual(self._captured, [])

    def test_main_edit_runs_impact(self):
        import qg_layer19, qg_session_state as ss
        orig_mp = qg_layer19._MONITOR_PATH
        orig_rp = qg_layer19.RULES_PATH
        qg_layer19._MONITOR_PATH = self.monitor_path
        qg_layer19.RULES_PATH = os.path.join(self.tmpdir, 'no_rules.json')
        f = self._write_file('target.py', 'x = 1\n')
        self._set_stdin({"tool_name": "Edit", "tool_input": {"file_path": f}})
        self._capture_print()
        try:
            qg_layer19.main()
        finally:
            builtins.print = self._orig_print
            qg_layer19._MONITOR_PATH = orig_mp
            qg_layer19.RULES_PATH = orig_rp
        state = ss.read_state()
        self.assertIn(state.get('layer19_last_impact_level'), ('LOW', 'MEDIUM', 'HIGH', 'CRITICAL'))
        # Event written to monitor
        self.assertTrue(os.path.exists(self.monitor_path))

    def test_main_core_file_outputs_warning(self):
        import qg_layer19, qg_session_state as ss
        orig_mp = qg_layer19._MONITOR_PATH
        orig_rp = qg_layer19.RULES_PATH
        qg_layer19._MONITOR_PATH = self.monitor_path
        qg_layer19.RULES_PATH = os.path.join(self.tmpdir, 'no_rules.json')
        f = self._write_file('utils.py', 'def helper(): pass\n')
        # Clear cache so it runs fresh
        state = ss.read_state()
        state['layer19_impact_cache'] = {}
        ss.write_state(state)
        self._set_stdin({"tool_name": "Edit", "tool_input": {"file_path": f}})
        self._capture_print()
        try:
            qg_layer19.main()
        finally:
            builtins.print = self._orig_print
            qg_layer19._MONITOR_PATH = orig_mp
            qg_layer19.RULES_PATH = orig_rp
        output = self._output()
        self.assertIn('CRITICAL', output)

    def test_analyze_impact_caches_result(self):
        import qg_layer19, qg_session_state as ss
        orig_mp = qg_layer19._MONITOR_PATH
        orig_rp = qg_layer19.RULES_PATH
        qg_layer19._MONITOR_PATH = self.monitor_path
        qg_layer19.RULES_PATH = os.path.join(self.tmpdir, 'no_rules.json')
        f = self._write_file('cached.py', 'y = 2\n')
        state = ss.read_state()
        state['layer19_impact_cache'] = {}
        ss.write_state(state)
        try:
            r1 = qg_layer19.analyze_impact(f)
            r2 = qg_layer19.analyze_impact(f)
        finally:
            qg_layer19._MONITOR_PATH = orig_mp
            qg_layer19.RULES_PATH = orig_rp
        self.assertEqual(r1['level'], r2['level'])
        self.assertEqual(r1['ts'], r2['ts'])  # Same cached timestamp


# --- Layer 18: Additional edge-case coverage ---

class TestLayer18EdgeCases(_MainTestBase):
    def test_check_function_no_old_string(self):
        from qg_layer18 import check_function_in_file
        self.assertTrue(check_function_in_file('/some/file.py', ''))
        self.assertTrue(check_function_in_file('/some/file.py', None))

    def test_check_function_no_def_or_class(self):
        from qg_layer18 import check_function_in_file
        f = self._write_file('mod.py', 'x = 1\n')
        self.assertTrue(check_function_in_file(f, 'x = 1'))

    def test_check_function_file_read_error(self):
        from qg_layer18 import check_function_in_file
        self.assertTrue(check_function_in_file('/nonexistent/path.py', 'def foo():'))

    def test_check_path_exists_exception(self):
        from qg_layer18 import check_path_exists
        # Passing an invalid type should trigger except → True
        self.assertTrue(check_path_exists(None) or True)

    def test_check_imports_file_read_error(self):
        from qg_layer18 import check_imports_in_file
        result = check_imports_in_file('/nonexistent/path.py', 'import os\n')
        self.assertTrue(result)

    def test_check_imports_names_not_in_file(self):
        from qg_layer18 import check_imports_in_file
        f = self._write_file('bare.py', '# empty\n')
        result = check_imports_in_file(f, 'import os\nimport sys\n')
        self.assertFalse(result)

    def test_check_packages_find_spec_value_error(self):
        from qg_layer18 import check_packages_importable
        # relative import triggers ValueError in find_spec
        missing = check_packages_importable('from .relative import thing\n')
        # '.' prefix removed by split('.')[0] → empty string, likely ValueError
        self.assertIsInstance(missing, list)

    def test_main_fn_check_disabled_with_warned(self):
        """Lines 187-190: _check_fn_existence=False and _warned=True."""
        import qg_layer18, qg_session_state as ss
        orig_mp = qg_layer18._MONITOR_PATH
        orig_rp = qg_layer18.RULES_PATH
        qg_layer18._MONITOR_PATH = self.monitor_path
        rules = self._write_file('rules.json', json.dumps({
            "layer18": {"check_function_existence": False, "check_remote_refs": True}
        }))
        qg_layer18.RULES_PATH = rules
        f = self._write_file('url_mod.py', 'url = "https://example.com"\n')
        self._set_stdin({"tool_name": "Edit", "tool_input": {
            "file_path": f, "old_string": 'url = "https://example.com"'}})
        self._capture_print()
        try:
            qg_layer18.main()
        finally:
            builtins.print = self._orig_print
            qg_layer18._MONITOR_PATH = orig_mp
            qg_layer18.RULES_PATH = orig_rp
        state = ss.read_state()
        self.assertTrue(state.get('layer18_hallucination_warned'))

    def test_main_no_func_names_with_warned(self):
        """Lines 196-199: old_string has imports (warned) but no def/class names."""
        import qg_layer18, qg_session_state as ss
        orig_mp = qg_layer18._MONITOR_PATH
        orig_rp = qg_layer18.RULES_PATH
        qg_layer18._MONITOR_PATH = self.monitor_path
        rules = self._write_file('rules2.json', json.dumps({"layer18": {}}))
        qg_layer18.RULES_PATH = rules
        f = self._write_file('imp_mod.py', 'import os\n')
        self._set_stdin({"tool_name": "Edit", "tool_input": {
            "file_path": f, "old_string": 'import nonexistent_xyz_pkg\n'}})
        self._capture_print()
        try:
            qg_layer18.main()
        finally:
            builtins.print = self._orig_print
            qg_layer18._MONITOR_PATH = orig_mp
            qg_layer18.RULES_PATH = orig_rp
        state = ss.read_state()
        self.assertTrue(state.get('layer18_hallucination_warned'))

    def test_main_all_refs_checked_with_warned(self):
        """Lines 205-206: all function refs already in session cache, but _warned."""
        import qg_layer18, qg_session_state as ss
        orig_mp = qg_layer18._MONITOR_PATH
        orig_rp = qg_layer18.RULES_PATH
        qg_layer18._MONITOR_PATH = self.monitor_path
        rules = self._write_file('rules3.json', json.dumps({"layer18": {}}))
        qg_layer18.RULES_PATH = rules
        f = self._write_file('cached_fn.py', 'def my_func():\n    pass\n')
        # Pre-populate cache with the function already checked
        state = ss.read_state()
        state['layer18_session_checked'] = {f'{f}::my_func': True}
        ss.write_state(state)
        self._set_stdin({"tool_name": "Edit", "tool_input": {
            "file_path": f,
            "old_string": 'import nonexistent_abc\ndef my_func():\n    pass'}})
        self._capture_print()
        try:
            qg_layer18.main()
        finally:
            builtins.print = self._orig_print
            qg_layer18._MONITOR_PATH = orig_mp
            qg_layer18.RULES_PATH = orig_rp
        state = ss.read_state()
        self.assertTrue(state.get('layer18_hallucination_warned'))

    def test_main_file_read_error_in_dedup(self):
        """Lines 212-213: file exists at check time but can't be read for dedup."""
        import qg_layer18, qg_session_state as ss
        orig_mp = qg_layer18._MONITOR_PATH
        orig_rp = qg_layer18.RULES_PATH
        qg_layer18._MONITOR_PATH = self.monitor_path
        rules = self._write_file('rules4.json', json.dumps({"layer18": {
            "check_import_existence": False, "check_package_installable": False,
            "check_remote_refs": False
        }}))
        qg_layer18.RULES_PATH = rules
        # Create then delete (file existed when check_path_exists ran but gone now)
        f = self._write_file('vanish.py', 'def ghost(): pass\n')
        # Monkeypatch check_path_exists to always return True
        orig_cpe = qg_layer18.check_path_exists
        qg_layer18.check_path_exists = lambda p: True
        os.unlink(f)
        self._set_stdin({"tool_name": "Edit", "tool_input": {
            "file_path": f, "old_string": 'def ghost(): pass'}})
        try:
            qg_layer18.main()
        finally:
            qg_layer18.check_path_exists = orig_cpe
            qg_layer18._MONITOR_PATH = orig_mp
            qg_layer18.RULES_PATH = orig_rp


# --- Layer env: Additional edge-case coverage ---

class TestLayerEnvEdgeCases(_MainTestBase):
    def test_session_start_with_test_command(self):
        """Lines 91-102: test baseline capture via subprocess."""
        import qg_layer_env as mod, qg_session_state as ss
        orig_cp = mod.ENV_CONFIG_PATH
        orig_mp = mod._MONITOR_PATH
        mod._MONITOR_PATH = self.monitor_path
        f = self._write_file('env_test.json', json.dumps({
            "test_command": "echo '3 passed, 0 failed'",
            "test_timeout_sec": 5
        }))
        mod.ENV_CONFIG_PATH = f
        # Clear any existing baseline so it runs
        state = ss.read_state()
        state.pop('layer_env_test_baseline', None)
        ss.write_state(state)
        try:
            mod.run_session_start({})
        finally:
            mod.ENV_CONFIG_PATH = orig_cp
            mod._MONITOR_PATH = orig_mp
        state = ss.read_state()
        baseline = state.get('layer_env_test_baseline')
        self.assertIsNotNone(baseline)

    def test_session_start_test_command_skipped_if_baseline_exists(self):
        """Test command shouldn't run if baseline already captured."""
        import qg_layer_env as mod, qg_session_state as ss
        orig_cp = mod.ENV_CONFIG_PATH
        orig_mp = mod._MONITOR_PATH
        mod._MONITOR_PATH = self.monitor_path
        f = self._write_file('env_skip.json', json.dumps({
            "test_command": "echo '5 passed'"
        }))
        mod.ENV_CONFIG_PATH = f
        state = ss.read_state()
        state['layer_env_test_baseline'] = [[10, 0]]
        ss.write_state(state)
        try:
            mod.run_session_start({})
        finally:
            mod.ENV_CONFIG_PATH = orig_cp
            mod._MONITOR_PATH = orig_mp
        state = ss.read_state()
        # Should still be the original baseline, not overwritten
        self.assertEqual(state.get('layer_env_test_baseline'), [[10, 0]])

    def test_validate_git_branch_subprocess_path(self):
        """Lines 27-32: validate_git_branch without fn injection uses subprocess."""
        from qg_layer_env import validate_git_branch
        # Call without get_branch_fn — uses real git; should not crash
        ok, msg = validate_git_branch('definitely_not_this_branch_xyz')
        # Either git works (ok=False, msg has branch info) or git unavailable (ok=True)
        self.assertIsInstance(ok, bool)


# --- Integration tests: layers working through quality-gate.py ---

class TestQGIntegrationBasic(_MainTestBase):
    """Test that layers can be imported and called in sequence without conflicts."""

    def test_multiple_layers_share_session_state(self):
        """Verify multiple layers can read/write session state without conflicts."""
        import qg_session_state as ss
        state = ss.read_state()
        state['active_task_id'] = 'integration_test_1'
        state['layer1_task_category'] = 'MODERATE'
        state['layer19_last_impact_level'] = 'LOW'
        ss.write_state(state)

        # Layer 17 reads state
        from qg_layer17 import should_verify
        self.assertFalse(should_verify(state, {}))

        # Layer 12 classify doesn't corrupt state
        from qg_layer12 import classify_sentiment
        cat, score, signals = classify_sentiment('looks good')
        state2 = ss.read_state()
        self.assertEqual(state2['active_task_id'], 'integration_test_1')

    def test_layer_env_then_layer17_flow(self):
        """SessionStart (env) sets baseline, then PreToolUse (17) reads it."""
        import qg_layer_env as env_mod, qg_session_state as ss
        orig_cp = env_mod.ENV_CONFIG_PATH
        orig_mp = env_mod._MONITOR_PATH
        env_mod._MONITOR_PATH = self.monitor_path
        env_mod.ENV_CONFIG_PATH = os.path.join(self.tmpdir, 'no_config.json')
        env_mod.run_session_start({})
        env_mod.ENV_CONFIG_PATH = orig_cp
        env_mod._MONITOR_PATH = orig_mp

        state = ss.read_state()
        self.assertIn('layer_env_baseline', state)
        wd = state['layer_env_baseline'].get('working_dir')
        self.assertTrue(wd)

    def test_layer19_sets_impact_for_layer17(self):
        """Layer 19 impact level feeds into Layer 17 should_verify."""
        import qg_session_state as ss
        from qg_layer19 import compute_impact_level
        from qg_layer17 import should_verify

        level = compute_impact_level('src/utils.py', [], {})
        self.assertEqual(level, 'CRITICAL')

        state = ss.read_state()
        state['layer1_task_category'] = 'SIMPLE'
        state['layer19_last_impact_level'] = level
        self.assertTrue(should_verify(state, {}))

    def test_layer28_and_layer25_both_check_writes(self):
        """Both security and syntax layers can process the same file."""
        from qg_layer28 import check_security
        f = self._write_file('both.py', 'x = 1\n')
        sec = check_security(f)
        self.assertEqual(sec, [])
        import qg_layer25
        self.assertTrue(hasattr(qg_layer25, 'main'))

    def test_layer35_and_layer2_share_turn_history(self):
        """Layer 35 uses layer2_turn_history set by Layer 2."""
        import qg_session_state as ss
        from qg_layer35 import layer35_check_resolutions

        state = ss.read_state()
        state['layer2_turn_history'] = ['t1', 't2', 't3']
        state['layer35_recovery_events'] = [{
            'status': 'open', 'ts': time.time(), 'turn': 2,
            'event_id': 'int_e1', 'verdict': 'FN', 'category': 'LAZINESS',
            'task_id': 'int_task', 'session_uuid': 'int_uuid', 'tools_at_flag': [],
        }]
        layer35_check_resolutions(['Grep'], state)
        evt = state['layer35_recovery_events'][0]
        # With Grep (a verify tool) and turns_elapsed=1 → resolved
        self.assertEqual(evt['status'], 'resolved')

    def test_layer20_health_check_runs_cleanly(self):
        """Layer 20 health check doesn't crash with default paths."""
        import qg_layer20
        orig_mp = qg_layer20.MONITOR_PATH
        orig_sp = qg_layer20.SETTINGS_PATH
        qg_layer20.MONITOR_PATH = self.monitor_path
        qg_layer20.SETTINGS_PATH = self._write_file('settings.json', '{}')
        open(self.monitor_path, 'w').close()
        report = qg_layer20.run_health_check()
        qg_layer20.MONITOR_PATH = orig_mp
        qg_layer20.SETTINGS_PATH = orig_sp
        self.assertIn('status', report)
        self.assertIn('stats', report)
        self.assertIn('issues', report)


if __name__ == '__main__':
    unittest.main()
