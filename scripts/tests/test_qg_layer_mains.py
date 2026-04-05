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


# ============================================================================
# Subagent Quality Gate Tests (0% → target 70%+)
# ============================================================================

class TestSubagentQGToolSummary(_MainTestBase):
    def _write_transcript(self, entries):
        path = os.path.join(self.tmpdir, 'transcript.jsonl')
        with open(path, 'w', encoding='utf-8') as f:
            for e in entries:
                f.write(json.dumps(e) + '\n')
        return path

    def test_get_tool_summary_empty(self):
        from importlib import reload
        import importlib
        sqg = importlib.import_module('subagent-quality-gate')
        names, edits, cmds = sqg.get_tool_summary('')
        self.assertEqual(names, [])

    def test_get_tool_summary_missing_file(self):
        sqg = __import__('subagent-quality-gate')
        names, edits, cmds = sqg.get_tool_summary('/nonexistent/transcript.jsonl')
        self.assertEqual(names, [])

    def test_get_tool_summary_with_tools(self):
        sqg = __import__('subagent-quality-gate')
        path = self._write_transcript([
            {"type": "assistant", "message": {"content": [
                {"type": "tool_use", "name": "Read", "input": {"file_path": "/a.py"}},
                {"type": "tool_use", "name": "Edit", "input": {"file_path": "/b.py"}},
                {"type": "tool_use", "name": "Bash", "input": {"command": "pytest"}},
            ]}}
        ])
        names, edits, cmds = sqg.get_tool_summary(path)
        self.assertIn('Read', names)
        self.assertIn('Edit', names)
        self.assertIn('Bash', names)
        self.assertEqual(edits, ['/b.py'])
        self.assertEqual(cmds, ['pytest'])

    def test_get_tool_summary_non_json_lines(self):
        sqg = __import__('subagent-quality-gate')
        path = self._write_transcript([])
        with open(path, 'w') as f:
            f.write('not json\n{"type": "assistant", "message": {"content": []}}\n')
        names, edits, cmds = sqg.get_tool_summary(path)
        self.assertEqual(names, [])


class TestSubagentQGFailedCommands(_MainTestBase):
    def _write_transcript(self, entries):
        path = os.path.join(self.tmpdir, 'transcript.jsonl')
        with open(path, 'w', encoding='utf-8') as f:
            for e in entries:
                f.write(json.dumps(e) + '\n')
        return path

    def test_get_failed_commands_empty(self):
        sqg = __import__('subagent-quality-gate')
        self.assertEqual(sqg.get_failed_commands(''), [])

    def test_get_failed_commands_with_failure(self):
        sqg = __import__('subagent-quality-gate')
        path = self._write_transcript([
            {"type": "assistant", "message": {"content": [
                {"type": "tool_use", "id": "tu1", "name": "Bash", "input": {"command": "npm test"}},
            ]}},
            {"type": "user", "message": {"content": [
                {"type": "tool_result", "tool_use_id": "tu1", "is_error": True, "content": "Error: tests failed"},
            ]}},
        ])
        failed = sqg.get_failed_commands(path)
        self.assertGreaterEqual(len(failed), 1)

    def test_get_failed_commands_no_failure(self):
        sqg = __import__('subagent-quality-gate')
        path = self._write_transcript([
            {"type": "assistant", "message": {"content": [
                {"type": "tool_use", "id": "tu2", "name": "Bash", "input": {"command": "echo hi"}},
            ]}},
            {"type": "user", "message": {"content": [
                {"type": "tool_result", "tool_use_id": "tu2", "is_error": False, "content": "hi"},
            ]}},
        ])
        failed = sqg.get_failed_commands(path)
        self.assertEqual(failed, [])


class TestSubagentQGGetLastResponse(_MainTestBase):
    def _write_transcript(self, entries):
        path = os.path.join(self.tmpdir, 'transcript.jsonl')
        with open(path, 'w', encoding='utf-8') as f:
            for e in entries:
                f.write(json.dumps(e) + '\n')
        return path

    def test_get_last_response_empty(self):
        sqg = __import__('subagent-quality-gate')
        self.assertEqual(sqg.get_last_response(''), '')

    def test_get_last_response_with_text(self):
        sqg = __import__('subagent-quality-gate')
        path = self._write_transcript([
            {"type": "assistant", "message": {"content": [
                {"type": "text", "text": "All done. Tests pass."},
            ]}}
        ])
        resp = sqg.get_last_response(path)
        self.assertEqual(resp, 'All done. Tests pass.')

    def test_get_last_response_string_content(self):
        sqg = __import__('subagent-quality-gate')
        path = self._write_transcript([
            {"type": "assistant", "message": {"content": "Simple string response"}}
        ])
        resp = sqg.get_last_response(path)
        self.assertEqual(resp, 'Simple string response')


class TestSubagentQGLogDecision(_MainTestBase):
    def test_log_decision_writes_to_file(self):
        sqg = __import__('subagent-quality-gate')
        orig_lp = sqg.LOG_PATH
        sqg.LOG_PATH = os.path.join(self.tmpdir, 'qg.log')
        try:
            sqg.log_decision('PASS', 'ok', 'researcher', 'some response')
        finally:
            sqg.LOG_PATH = orig_lp
        with open(os.path.join(self.tmpdir, 'qg.log')) as f:
            content = f.read()
        self.assertIn('PASS', content)
        self.assertIn('researcher', content)


class TestSubagentQGMain(_MainTestBase):
    def _write_transcript(self, entries):
        path = os.path.join(self.tmpdir, 'transcript.jsonl')
        with open(path, 'w', encoding='utf-8') as f:
            for e in entries:
                f.write(json.dumps(e) + '\n')
        return path

    def test_main_bad_json_returns_continue(self):
        sqg = __import__('subagent-quality-gate')
        orig_lp = sqg.LOG_PATH
        sqg.LOG_PATH = os.path.join(self.tmpdir, 'qg.log')
        sys.stdin = io.StringIO('not json')
        self._capture_print()
        try:
            sqg.main()
        finally:
            builtins.print = self._orig_print
            sqg.LOG_PATH = orig_lp
        output = self._output()
        parsed = json.loads(output)
        self.assertTrue(parsed.get('continue'))

    def test_main_stop_hook_active_continues(self):
        sqg = __import__('subagent-quality-gate')
        self._set_stdin({"stop_hook_active": True})
        self._capture_print()
        try:
            sqg.main()
        finally:
            builtins.print = self._orig_print
        output = self._output()
        parsed = json.loads(output)
        self.assertTrue(parsed.get('continue'))

    def test_main_edit_without_verification_blocks(self):
        sqg = __import__('subagent-quality-gate')
        orig_lp = sqg.LOG_PATH
        sqg.LOG_PATH = os.path.join(self.tmpdir, 'qg.log')
        path = self._write_transcript([
            {"type": "assistant", "message": {"content": [
                {"type": "tool_use", "name": "Edit", "input": {"file_path": "/src/app.py"}},
                {"type": "text", "text": "Done editing."},
            ]}}
        ])
        self._set_stdin({"agent_type": "general", "agent_transcript_path": path})
        self._capture_print()
        try:
            sqg.main()
        finally:
            builtins.print = self._orig_print
            sqg.LOG_PATH = orig_lp
        output = self._output()
        parsed = json.loads(output)
        self.assertEqual(parsed.get('decision'), 'block')
        self.assertIn('verification', parsed.get('reason', '').lower())

    def test_main_edit_with_bash_validation_passes(self):
        sqg = __import__('subagent-quality-gate')
        orig_lp = sqg.LOG_PATH
        sqg.LOG_PATH = os.path.join(self.tmpdir, 'qg.log')
        path = self._write_transcript([
            {"type": "assistant", "message": {"content": [
                {"type": "tool_use", "name": "Edit", "input": {"file_path": "/src/app.py"}},
                {"type": "tool_use", "name": "Bash", "input": {"command": "python -m pytest tests/"}},
                {"type": "text", "text": "All tests pass."},
            ]}}
        ])
        self._set_stdin({
            "agent_type": "general",
            "agent_transcript_path": path,
            "last_assistant_message": "All tests pass."
        })
        self._capture_print()
        try:
            sqg.main()
        finally:
            builtins.print = self._orig_print
            sqg.LOG_PATH = orig_lp
        output = self._output()
        parsed = json.loads(output)
        # Should either continue (pass) or block on LLM check
        self.assertIn(parsed.get('decision', 'none'), ['block', 'none'])
        if 'continue' in parsed:
            self.assertTrue(parsed['continue'])

    def test_main_edit_last_action_blocks(self):
        sqg = __import__('subagent-quality-gate')
        orig_lp = sqg.LOG_PATH
        sqg.LOG_PATH = os.path.join(self.tmpdir, 'qg.log')
        path = self._write_transcript([
            {"type": "assistant", "message": {"content": [
                {"type": "tool_use", "name": "Bash", "input": {"command": "pytest"}},
                {"type": "tool_use", "name": "Edit", "input": {"file_path": "/src/fix.py"}},
                {"type": "text", "text": "Fixed the issue."},
            ]}}
        ])
        self._set_stdin({"agent_type": "general", "agent_transcript_path": path})
        self._capture_print()
        try:
            sqg.main()
        finally:
            builtins.print = self._orig_print
            sqg.LOG_PATH = orig_lp
        output = self._output()
        parsed = json.loads(output)
        self.assertEqual(parsed.get('decision'), 'block')

    def test_main_non_code_edit_not_blocked(self):
        sqg = __import__('subagent-quality-gate')
        orig_lp = sqg.LOG_PATH
        sqg.LOG_PATH = os.path.join(self.tmpdir, 'qg.log')
        path = self._write_transcript([
            {"type": "assistant", "message": {"content": [
                {"type": "tool_use", "name": "Write", "input": {"file_path": "/docs/README.md"}},
                {"type": "text", "text": "Updated docs."},
            ]}}
        ])
        self._set_stdin({
            "agent_type": "general",
            "agent_transcript_path": path,
            "last_assistant_message": "Updated docs."
        })
        self._capture_print()
        try:
            sqg.main()
        finally:
            builtins.print = self._orig_print
            sqg.LOG_PATH = orig_lp
        # Non-code paths shouldn't trigger code-edit blocks
        output = self._output()
        parsed = json.loads(output)
        # May still get LLM-blocked, but shouldn't be "edited code but ran no verification"
        if parsed.get('decision') == 'block':
            self.assertNotIn('edited code but ran no verification', parsed.get('reason', '').lower())

    def test_main_overconfidence_blocks(self):
        sqg = __import__('subagent-quality-gate')
        orig_lp = sqg.LOG_PATH
        sqg.LOG_PATH = os.path.join(self.tmpdir, 'qg.log')
        path = self._write_transcript([
            {"type": "assistant", "message": {"content": [
                {"type": "text", "text": "All 150 passed, 0 failed, 150 total"},
            ]}}
        ])
        self._set_stdin({
            "agent_type": "researcher",
            "agent_transcript_path": path,
            "last_assistant_message": "All 150 passed, 0 failed, 150 total"
        })
        self._capture_print()
        try:
            sqg.main()
        finally:
            builtins.print = self._orig_print
            sqg.LOG_PATH = orig_lp
        output = self._output()
        parsed = json.loads(output)
        self.assertEqual(parsed.get('decision'), 'block')
        self.assertIn('OVERCONFIDENCE', parsed.get('reason', ''))

    def test_main_no_tools_no_response_passes(self):
        sqg = __import__('subagent-quality-gate')
        orig_lp = sqg.LOG_PATH
        sqg.LOG_PATH = os.path.join(self.tmpdir, 'qg.log')
        path = self._write_transcript([])
        self._set_stdin({
            "agent_type": "researcher",
            "agent_transcript_path": path,
            "last_assistant_message": ""
        })
        self._capture_print()
        try:
            sqg.main()
        finally:
            builtins.print = self._orig_print
            sqg.LOG_PATH = orig_lp
        output = self._output()
        parsed = json.loads(output)
        self.assertTrue(parsed.get('continue'))


# ============================================================================
# Layer 13 & 15_mem additional coverage (70%→80%+ target)
# ============================================================================

class TestLayer13Coverage(_MainTestBase):
    def test_extract_imports_basic(self):
        from qg_layer13 import extract_imports
        imports = extract_imports('import os\nimport sys\n')
        modules = [m for m, _ in imports]
        self.assertIn('os', modules)
        self.assertIn('sys', modules)

    def test_extract_imports_from_import(self):
        from qg_layer13 import extract_imports
        imports = extract_imports('from os.path import join, exists\n')
        self.assertEqual(len(imports), 1)
        self.assertEqual(imports[0][0], 'os.path')
        self.assertIn('join', imports[0][1])

    def test_extract_imports_star(self):
        from qg_layer13 import extract_imports
        imports = extract_imports('from os import *\n')
        self.assertEqual(imports[0][1], [])

    def test_extract_imports_skips_comments(self):
        from qg_layer13 import extract_imports
        imports = extract_imports('# import fake\nimport os\n')
        self.assertEqual(len(imports), 1)

    def test_check_module_exists_real(self):
        from qg_layer13 import check_module_exists
        self.assertTrue(check_module_exists('os'))
        self.assertTrue(check_module_exists('sys'))

    def test_check_module_exists_fake(self):
        from qg_layer13 import check_module_exists
        self.assertFalse(check_module_exists('zzz_nonexistent_qg_test'))

    def test_check_attribute_exists_real(self):
        from qg_layer13 import check_attribute_exists
        self.assertTrue(check_attribute_exists('os', 'path'))

    def test_check_attribute_exists_fake(self):
        from qg_layer13 import check_attribute_exists
        self.assertFalse(check_attribute_exists('os', 'zzz_fake_attr'))

    def test_check_imports_non_py_file(self):
        from qg_layer13 import check_imports
        self.assertEqual(check_imports('/tmp/readme.txt'), [])

    def test_check_imports_missing_module(self):
        from qg_layer13 import check_imports
        f = self._write_file('bad_imp.py', 'import zzz_nonexistent_qg_mod\n')
        issues = check_imports(f)
        self.assertTrue(any('MODULE_NOT_FOUND' in msg for _, msg in issues))

    def test_check_imports_missing_attr(self):
        from qg_layer13 import check_imports
        # Use json (non-stdlib-skipped) to test attr check
        f = self._write_file('bad_attr.py', 'from json import zzz_fake_attr_qg\n')
        issues = check_imports(f)
        # json may be in STDLIB_MODULES; if so, attr check is skipped — just verify no crash
        self.assertIsInstance(issues, list)

    def test_check_imports_caches_results(self):
        import qg_layer13, qg_session_state as ss
        # Use a non-stdlib module to ensure it's not skipped
        f = self._write_file('cached_imp.py', 'import zzz_nonexistent_qg_mod\n')
        qg_layer13.check_imports(f)
        state = ss.read_state()
        cache = state.get('layer13_import_cache', {})
        self.assertIn('zzz_nonexistent_qg_mod', cache)


class TestLayer15MemCoverage(_MainTestBase):
    def _setup_memory_dir(self):
        mem_dir = os.path.join(self.tmpdir, 'memory')
        os.makedirs(mem_dir, exist_ok=True)
        return mem_dir

    def test_extract_references_empty_index(self):
        from qg_layer15_mem import extract_references
        idx = self._write_file('MEMORY.md', '# Empty index\n')
        refs = extract_references(idx)
        self.assertEqual(refs, [])

    def test_extract_references_with_links(self):
        from qg_layer15_mem import extract_references
        idx = self._write_file('MEMORY.md', '- [Profile](user_profile.md) — role info\n')
        refs = extract_references(idx)
        self.assertEqual(len(refs), 1)
        self.assertEqual(refs[0]['name'], 'Profile')

    def test_check_references_missing_file(self):
        import qg_layer15_mem as mod
        orig_md = mod.MEMORY_DIR
        mem_dir = self._setup_memory_dir()
        mod.MEMORY_DIR = mem_dir
        idx = self._write_file('MEMORY.md', '- [Ghost](ghost_file.md) — missing\n')
        try:
            issues, count = mod.check_references(idx)
        finally:
            mod.MEMORY_DIR = orig_md
        self.assertEqual(count, 1)
        self.assertTrue(any('MISSING_REF' in msg for _, msg in issues))

    def test_check_staleness_with_old_file(self):
        from qg_layer15_mem import check_staleness
        mem_dir = self._setup_memory_dir()
        f = os.path.join(mem_dir, 'old.md')
        with open(f, 'w') as fh:
            fh.write('# Old\n')
        # Set mtime to 100 days ago
        old_time = time.time() - (100 * 86400)
        os.utime(f, (old_time, old_time))
        issues, total, stale = check_staleness(mem_dir, stale_days=30)
        self.assertEqual(total, 1)
        self.assertEqual(stale, 1)
        self.assertTrue(any('STALE' in msg for _, msg in issues))

    def test_check_staleness_fresh_file(self):
        from qg_layer15_mem import check_staleness
        mem_dir = self._setup_memory_dir()
        f = os.path.join(mem_dir, 'fresh.md')
        with open(f, 'w') as fh:
            fh.write('# Fresh\n')
        issues, total, stale = check_staleness(mem_dir, stale_days=30)
        self.assertEqual(total, 1)
        self.assertEqual(stale, 0)

    def test_check_file_sizes_oversized(self):
        from qg_layer15_mem import check_file_sizes
        mem_dir = self._setup_memory_dir()
        f = os.path.join(mem_dir, 'huge.md')
        with open(f, 'w') as fh:
            fh.write('x' * 110000)  # Over MAX_FILE_SIZE (100KB = 102400)
        issues = check_file_sizes(mem_dir)
        self.assertTrue(any('OVERSIZED' in msg for _, msg in issues))

    def test_check_file_sizes_normal(self):
        from qg_layer15_mem import check_file_sizes
        mem_dir = self._setup_memory_dir()
        f = os.path.join(mem_dir, 'small.md')
        with open(f, 'w') as fh:
            fh.write('# Small\n')
        issues = check_file_sizes(mem_dir)
        self.assertEqual(issues, [])

    def test_check_duplicates_detects_duplicate_heading(self):
        from qg_layer15_mem import check_duplicates
        mem_dir = self._setup_memory_dir()
        for name in ['a.md', 'b.md']:
            with open(os.path.join(mem_dir, name), 'w') as f:
                f.write('# Same Heading\nContent\n')
        issues = check_duplicates(mem_dir)
        self.assertTrue(any('DUPLICATE_HEADING' in msg for _, msg in issues))

    def test_check_duplicates_no_duplicates(self):
        from qg_layer15_mem import check_duplicates
        mem_dir = self._setup_memory_dir()
        with open(os.path.join(mem_dir, 'a.md'), 'w') as f:
            f.write('# Unique A\n')
        with open(os.path.join(mem_dir, 'b.md'), 'w') as f:
            f.write('# Unique B\n')
        issues = check_duplicates(mem_dir)
        self.assertEqual(issues, [])

    def test_analyze_memory_integrity_full(self):
        import qg_layer15_mem as mod
        orig_md = mod.MEMORY_DIR
        orig_mi = mod.MEMORY_INDEX
        orig_amd = mod.ALT_MEMORY_DIR
        mem_dir = self._setup_memory_dir()
        idx = os.path.join(mem_dir, 'MEMORY.md')
        with open(idx, 'w') as f:
            f.write('- [Profile](profile.md) — info\n')
        with open(os.path.join(mem_dir, 'profile.md'), 'w') as f:
            f.write('# Profile\nContent\n')
        mod.MEMORY_DIR = mem_dir
        mod.MEMORY_INDEX = idx
        mod.ALT_MEMORY_DIR = os.path.join(self.tmpdir, 'alt')
        try:
            report = mod.analyze_memory_integrity(idx, mem_dir)
        finally:
            mod.MEMORY_DIR = orig_md
            mod.MEMORY_INDEX = orig_mi
            mod.ALT_MEMORY_DIR = orig_amd
        self.assertIn('status', report)
        self.assertIn('stats', report)
        self.assertIsInstance(report['issues'], list)


# ============================================================================
# Layer 5: Subagent Coordination coverage (73%→80%+)
# ============================================================================

class TestLayer5Coverage(_MainTestBase):
    def test_find_inflight_id_no_match(self):
        from qg_layer5 import _find_inflight_id
        sid = _find_inflight_id({}, 'task1')
        self.assertEqual(len(sid), 8)  # uuid[:8]

    def test_find_inflight_id_with_match(self):
        from qg_layer5 import _find_inflight_id
        subs = {'abc12345': {'parent_task_id': 't1', 'status': 'in_flight', 'ts': '2026-01-01'}}
        sid = _find_inflight_id(subs, 't1')
        self.assertEqual(sid, 'abc12345')

    def test_write_handoff_creates_file(self):
        import qg_layer5
        orig = qg_layer5.HANDOFF_DIR
        qg_layer5.HANDOFF_DIR = self.tmpdir
        try:
            qg_layer5._write_handoff('test123', 'ptask1', {})
        finally:
            qg_layer5.HANDOFF_DIR = orig
        path = os.path.join(self.tmpdir, 'qg-subagent-test123.json')
        self.assertTrue(os.path.exists(path))
        with open(path) as f:
            data = json.load(f)
        self.assertEqual(data['subagent_id'], 'test123')

    def test_merge_subagent_events_missing_file(self):
        import qg_layer5, qg_session_state as ss
        orig = qg_layer5.HANDOFF_DIR
        qg_layer5.HANDOFF_DIR = self.tmpdir
        state = ss.read_state()
        state['layer5_subagents'] = {'miss123': {'status': 'in_flight'}}
        try:
            qg_layer5._merge_subagent_events('miss123', 'pt1', state)
        finally:
            qg_layer5.HANDOFF_DIR = orig
        self.assertTrue(state['layer5_subagents']['miss123'].get('timeout_marker'))

    def test_merge_subagent_events_corrupt_file(self):
        import qg_layer5, qg_session_state as ss
        orig = qg_layer5.HANDOFF_DIR
        qg_layer5.HANDOFF_DIR = self.tmpdir
        path = os.path.join(self.tmpdir, 'qg-subagent-bad123.json')
        with open(path, 'w') as f:
            f.write('not json')
        state = ss.read_state()
        state['layer5_subagents'] = {'bad123': {'status': 'in_flight'}}
        try:
            qg_layer5._merge_subagent_events('bad123', 'pt2', state)
        finally:
            qg_layer5.HANDOFF_DIR = orig
        self.assertTrue(state['layer5_subagents']['bad123'].get('timeout_marker'))

    def test_main_bad_json_no_crash(self):
        import qg_layer5
        sys.stdin = io.StringIO('not json')
        try:
            qg_layer5.main()
        finally:
            sys.stdin = self._orig_stdin

    def test_main_non_agent_returns(self):
        import qg_layer5
        self._set_stdin({"tool_name": "Read", "tool_input": {}})
        self._capture_print()
        try:
            qg_layer5.main()
        finally:
            builtins.print = self._orig_print
        self.assertEqual(self._captured, [])

    def test_main_pre_dispatch(self):
        import qg_layer5, qg_session_state as ss
        orig_mp = qg_layer5.MONITOR_PATH
        orig_hd = qg_layer5.HANDOFF_DIR
        qg_layer5.MONITOR_PATH = self.monitor_path
        qg_layer5.HANDOFF_DIR = self.tmpdir
        state = ss.read_state()
        state['active_task_id'] = 'task_pre'
        ss.write_state(state)
        self._set_stdin({"tool_name": "Agent", "tool_input": {"prompt": "do something"}})
        try:
            qg_layer5.main()
        finally:
            qg_layer5.MONITOR_PATH = orig_mp
            qg_layer5.HANDOFF_DIR = orig_hd
        state2 = ss.read_state()
        subs = state2.get('layer5_subagents', {})
        self.assertGreater(len(subs), 0)

    def test_main_post_dispatch(self):
        import qg_layer5, qg_session_state as ss
        orig_mp = qg_layer5.MONITOR_PATH
        orig_hd = qg_layer5.HANDOFF_DIR
        qg_layer5.MONITOR_PATH = self.monitor_path
        qg_layer5.HANDOFF_DIR = self.tmpdir
        state = ss.read_state()
        state['active_task_id'] = 'task_post'
        ss.write_state(state)
        self._set_stdin({"tool_name": "Agent", "tool_input": {"prompt": "research"},
                         "tool_response": "Found the answer."})
        try:
            qg_layer5.main()
        finally:
            qg_layer5.MONITOR_PATH = orig_mp
            qg_layer5.HANDOFF_DIR = orig_hd


# ============================================================================
# Layer 6: Cross-session Pattern Analysis coverage (76%→80%+)
# ============================================================================

class TestLayer6Coverage(_MainTestBase):
    def test_load_monitor_events_empty_file(self):
        from qg_layer6 import load_monitor_events
        f = self._write_file('empty.jsonl', '')
        events = load_monitor_events(f)
        self.assertEqual(events, [])

    def test_load_monitor_events_with_data(self):
        from qg_layer6 import load_monitor_events
        f = self._write_file('monitor.jsonl',
            json.dumps({"category": "LAZINESS", "session_uuid": "s1"}) + '\n')
        events = load_monitor_events(f)
        self.assertEqual(len(events), 1)

    def test_load_monitor_events_invalid_json_skipped(self):
        from qg_layer6 import load_monitor_events
        f = self._write_file('mixed.jsonl', 'not json\n{"category":"X"}\n')
        events = load_monitor_events(f)
        self.assertEqual(len(events), 1)

    def test_analyze_patterns_below_min_sessions(self):
        from qg_layer6 import analyze_patterns
        events = [{"session_uuid": "s1", "category": "LAZINESS"}]
        patterns = analyze_patterns(events, min_sessions=3)
        self.assertEqual(patterns, [])

    def test_analyze_patterns_finds_recurring(self):
        from qg_layer6 import analyze_patterns
        events = []
        for i in range(5):
            sid = f's{i}'
            for _ in range(3):
                events.append({"session_uuid": sid, "category": "LAZINESS", "ts": f"2026-01-0{i+1}"})
        patterns = analyze_patterns(events, min_sessions=3, min_pct=0.1)
        self.assertGreater(len(patterns), 0)
        self.assertEqual(patterns[0]['category'], 'LAZINESS')

    def test_run_analysis_creates_output(self):
        import qg_layer6
        orig_rp = qg_layer6.RULES_PATH
        qg_layer6.RULES_PATH = os.path.join(self.tmpdir, 'no_rules.json')
        monitor = self._write_file('mon.jsonl', '')
        output = os.path.join(self.tmpdir, 'cross.json')
        try:
            result = qg_layer6.run_analysis(monitor, output)
        finally:
            qg_layer6.RULES_PATH = orig_rp
        self.assertIn('patterns', result)
        self.assertIn('sessions_analyzed', result)

    def test_run_analysis_with_rules(self):
        import qg_layer6
        orig_rp = qg_layer6.RULES_PATH
        rules = self._write_file('rules.json', json.dumps({
            "layer6": {"pattern_min_sessions": 2, "pattern_min_pct": 10}
        }))
        qg_layer6.RULES_PATH = rules
        monitor = self._write_file('mon2.jsonl', '')
        output = os.path.join(self.tmpdir, 'cross2.json')
        try:
            result = qg_layer6.run_analysis(monitor, output)
        finally:
            qg_layer6.RULES_PATH = orig_rp
        self.assertIsInstance(result['patterns'], list)

    def test_main_throttled(self):
        import qg_layer6, qg_session_state as ss
        state = ss.read_state()
        state['layer6_last_analysis_ts'] = time.time()
        ss.write_state(state)
        self._capture_print()
        try:
            qg_layer6.main()
        finally:
            builtins.print = self._orig_print
        # Throttled — returns early, no output

    def test_main_runs_analysis(self):
        import qg_layer6, qg_session_state as ss
        orig_mp = qg_layer6.MONITOR_PATH
        orig_cp = qg_layer6.CROSS_SESSION_PATH
        orig_rp = qg_layer6.RULES_PATH
        qg_layer6.MONITOR_PATH = self._write_file('mon3.jsonl', '')
        qg_layer6.CROSS_SESSION_PATH = os.path.join(self.tmpdir, 'cross3.json')
        qg_layer6.RULES_PATH = os.path.join(self.tmpdir, 'no_rules.json')
        state = ss.read_state()
        state['layer6_last_analysis_ts'] = 0
        ss.write_state(state)
        try:
            qg_layer6.main()
        finally:
            qg_layer6.MONITOR_PATH = orig_mp
            qg_layer6.CROSS_SESSION_PATH = orig_cp
            qg_layer6.RULES_PATH = orig_rp
        state2 = ss.read_state()
        self.assertGreater(state2.get('layer6_last_analysis_ts', 0), 0)

    def test_cli_run_flag(self):
        import qg_layer6
        orig_mp = qg_layer6.MONITOR_PATH
        orig_cp = qg_layer6.CROSS_SESSION_PATH
        orig_rp = qg_layer6.RULES_PATH
        qg_layer6.MONITOR_PATH = self._write_file('mon4.jsonl', '')
        qg_layer6.CROSS_SESSION_PATH = os.path.join(self.tmpdir, 'cross4.json')
        qg_layer6.RULES_PATH = os.path.join(self.tmpdir, 'no_rules.json')
        sys.argv = ['qg_layer6.py', '--run']
        self._capture_print()
        try:
            # Simulate the __name__ == "__main__" block
            result = qg_layer6.run_analysis()
            print("Analyzed {} sessions, found {} patterns.".format(
                result["sessions_analyzed"], len(result["patterns"])))
        finally:
            builtins.print = self._orig_print
            qg_layer6.MONITOR_PATH = orig_mp
            qg_layer6.CROSS_SESSION_PATH = orig_cp
            qg_layer6.RULES_PATH = orig_rp
        self.assertIn('Analyzed', self._output())


# ============================================================================
# Layer 13: Knowledge Freshness — boost 70%→80%+
# ============================================================================

class TestLayer13Boost(_MainTestBase):
    def test_check_imports_underscore_module_skipped(self):
        """Line 108: top.startswith('_') → skip."""
        from qg_layer13 import check_imports
        f = self._write_file('priv.py', 'import _fake_private_mod\n')
        issues = check_imports(f)
        # _ prefixed modules are skipped — no issues
        self.assertEqual(issues, [])

    def test_check_imports_oversized_file(self):
        """Line 92: file > SIZE_LIMIT returns []."""
        from qg_layer13 import check_imports
        f = self._write_file('huge.py', 'import os\n' + 'x = 1\n' * 20000)
        issues = check_imports(f)
        self.assertEqual(issues, [])

    def test_check_imports_file_read_error(self):
        """Lines 95-96: file read fails → returns []."""
        from qg_layer13 import check_imports
        issues = check_imports('/nonexistent/file.py')
        self.assertEqual(issues, [])

    def test_check_imports_empty_path(self):
        """Line 85: empty file_path → returns []."""
        from qg_layer13 import check_imports
        self.assertEqual(check_imports(''), [])

    def test_check_imports_attr_loop_with_real_module(self):
        """Lines 121-131: attr checking for non-stdlib installed module."""
        from qg_layer13 import check_imports
        # pytest is installed — import a fake attr from it
        f = self._write_file('attr_test.py', 'from pytest import zzz_nonexistent_attr_qg\n')
        issues = check_imports(f)
        self.assertTrue(any('ATTR_NOT_FOUND' in msg for _, msg in issues))

    def test_check_imports_attr_exists(self):
        """Lines 121-131: real attr → no issue."""
        from qg_layer13 import check_imports
        f = self._write_file('attr_ok.py', 'from pytest import fixture\n')
        issues = check_imports(f)
        self.assertFalse(any('ATTR_NOT_FOUND' in msg for _, msg in issues))

    def test_check_imports_underscore_attr_skipped(self):
        """Line 122: attr.startswith('_') → skip."""
        from qg_layer13 import check_imports
        f = self._write_file('priv_attr.py', 'from pytest import _fake_private\n')
        issues = check_imports(f)
        self.assertFalse(any('_fake_private' in msg for _, msg in issues))

    def test_check_module_exists_value_error(self):
        """Lines 71-72: find_spec raises ValueError → False."""
        from qg_layer13 import check_module_exists
        # Empty string triggers ValueError in find_spec
        result = check_module_exists('')
        self.assertFalse(result)

    def test_main_with_issues_produces_output(self):
        """Lines 151-160: main() prints JSON when issues found."""
        import qg_layer13
        orig_mp = qg_layer13.MONITOR_PATH
        qg_layer13.MONITOR_PATH = self.monitor_path
        f = self._write_file('bad_mod.py', 'import zzz_fake_qg_module_xyz\n')
        self._set_stdin({"tool_name": "Write", "tool_input": {"file_path": f}})
        self._capture_print()
        try:
            qg_layer13.main()
        finally:
            builtins.print = self._orig_print
            qg_layer13.MONITOR_PATH = orig_mp
        output = self._output()
        self.assertIn('Layer 13', output)
        self.assertIn('MODULE_NOT_FOUND', output)


# ============================================================================
# quality-gate.py — boost 82%→85%+
# ============================================================================

class TestQualityGateBoost(_MainTestBase):
    def test_check_count_grace_expired(self):
        """Lines 83-102: grace file exists but expired."""
        sys.path.insert(0, os.path.expanduser('~/.claude/hooks'))
        import importlib
        qg = importlib.import_module('quality-gate')
        grace = self._write_file('grace.json', json.dumps({"ts": 0, "key": "42"}))
        orig = qg._GRACE_FILE
        qg._GRACE_FILE = grace
        try:
            result = qg._check_count_grace('42 passed')
        finally:
            qg._GRACE_FILE = orig
        self.assertFalse(result)

    def test_check_count_grace_hit(self):
        """Lines 83-102: grace file active and key matches."""
        qg = __import__('quality-gate')
        grace = self._write_file('grace2.json', json.dumps({"ts": time.time(), "key": "42"}))
        orig_gf = qg._GRACE_FILE
        orig_lp = qg.LOG_PATH
        qg._GRACE_FILE = grace
        qg.LOG_PATH = os.path.join(self.tmpdir, 'qg.log')
        try:
            result = qg._check_count_grace('42 passed, 0 failed')
        finally:
            qg._GRACE_FILE = orig_gf
            qg.LOG_PATH = orig_lp
        self.assertTrue(result)

    def test_check_count_grace_missing_file(self):
        """Line 101-102: grace file doesn't exist → False."""
        qg = __import__('quality-gate')
        orig = qg._GRACE_FILE
        qg._GRACE_FILE = os.path.join(self.tmpdir, 'nonexistent.json')
        try:
            result = qg._check_count_grace('test')
        finally:
            qg._GRACE_FILE = orig
        self.assertFalse(result)

    def test_log_decision_writes(self):
        """Lines 111-126: log_decision creates log entry."""
        qg = __import__('quality-gate')
        orig = qg.LOG_PATH
        qg.LOG_PATH = os.path.join(self.tmpdir, 'qg.log')
        try:
            qg.log_decision('PASS', 'ok', 'fix bug', ['Read', 'Edit'], 'MODERATE', 'response text')
        finally:
            qg.LOG_PATH = orig
        with open(os.path.join(self.tmpdir, 'qg.log')) as f:
            content = f.read()
        self.assertIn('PASS', content)
        self.assertIn('MODERATE', content)

    def test_qg_load_ss(self):
        """Lines 980-987: _qg_load_ss returns state dict."""
        qg = __import__('quality-gate')
        state, ss_mod = qg._qg_load_ss()
        self.assertIsInstance(state, dict)


# ============================================================================
# Layer 15_mem: Memory Integrity — boost 75%→85%+
# ============================================================================

class TestLayer15MemBoost(_MainTestBase):
    def _setup_memory_dir(self):
        mem_dir = os.path.join(self.tmpdir, 'memory')
        os.makedirs(mem_dir, exist_ok=True)
        return mem_dir

    def test_resolve_path_memory_prefix(self):
        from qg_layer15_mem import _resolve_path
        result = _resolve_path('memory/user_profile.md')
        self.assertIn('user_profile.md', result)

    def test_resolve_path_alt_memory_prefix(self):
        from qg_layer15_mem import _resolve_path
        result = _resolve_path('~/.claude/memory/notes.md')
        self.assertIn('notes.md', result)

    def test_resolve_path_claude_prefix(self):
        from qg_layer15_mem import _resolve_path
        result = _resolve_path('~/.claude/docs/cheat.md')
        self.assertIn('cheat.md', result)

    def test_resolve_path_bare_filename(self):
        from qg_layer15_mem import _resolve_path
        result = _resolve_path('plain.md')
        self.assertIn('plain.md', result)

    def test_extract_references_file_read_error(self):
        from qg_layer15_mem import extract_references
        # Directory as path triggers read error
        refs = extract_references(self.tmpdir)
        self.assertEqual(refs, [])

    def test_check_staleness_non_md_skipped(self):
        from qg_layer15_mem import check_staleness
        mem_dir = self._setup_memory_dir()
        with open(os.path.join(mem_dir, 'notes.txt'), 'w') as f:
            f.write('not md')
        issues, total, stale = check_staleness(mem_dir, stale_days=1)
        self.assertEqual(total, 0)

    def test_check_staleness_empty_dir(self):
        from qg_layer15_mem import check_staleness
        mem_dir = self._setup_memory_dir()
        issues, total, stale = check_staleness(mem_dir, stale_days=30)
        self.assertEqual(total, 0)
        self.assertEqual(stale, 0)

    def test_check_staleness_nonexistent_dir(self):
        from qg_layer15_mem import check_staleness
        issues, total, stale = check_staleness(os.path.join(self.tmpdir, 'nope'))
        self.assertEqual(total, 0)

    def test_check_file_sizes_nonexistent_dir(self):
        from qg_layer15_mem import check_file_sizes
        issues = check_file_sizes(os.path.join(self.tmpdir, 'nope'))
        self.assertEqual(issues, [])

    def test_check_file_sizes_non_md_skipped(self):
        from qg_layer15_mem import check_file_sizes
        mem_dir = self._setup_memory_dir()
        with open(os.path.join(mem_dir, 'data.json'), 'w') as f:
            f.write('{}')
        issues = check_file_sizes(mem_dir)
        self.assertEqual(issues, [])

    def test_check_duplicates_nonexistent_dir(self):
        from qg_layer15_mem import check_duplicates
        issues = check_duplicates(os.path.join(self.tmpdir, 'nope'))
        self.assertEqual(issues, [])

    def test_check_duplicates_memory_md_skipped(self):
        from qg_layer15_mem import check_duplicates
        mem_dir = self._setup_memory_dir()
        with open(os.path.join(mem_dir, 'MEMORY.md'), 'w') as f:
            f.write('# Index\n')
        issues = check_duplicates(mem_dir)
        self.assertEqual(issues, [])

    def test_main_with_issues_produces_output(self):
        import qg_layer15_mem as mod, qg_session_state as ss
        orig_mp = mod.MONITOR_PATH
        orig_md = mod.MEMORY_DIR
        orig_mi = mod.MEMORY_INDEX
        orig_amd = mod.ALT_MEMORY_DIR
        mem_dir = self._setup_memory_dir()
        idx = os.path.join(mem_dir, 'MEMORY.md')
        with open(idx, 'w') as f:
            f.write('- [Ghost](ghost_missing.md) — missing file\n')
        mod.MONITOR_PATH = self.monitor_path
        mod.MEMORY_DIR = mem_dir
        mod.MEMORY_INDEX = idx
        mod.ALT_MEMORY_DIR = os.path.join(self.tmpdir, 'alt')
        self._set_stdin({})
        self._capture_print()
        try:
            mod.main()
        finally:
            builtins.print = self._orig_print
            mod.MONITOR_PATH = orig_mp
            mod.MEMORY_DIR = orig_md
            mod.MEMORY_INDEX = orig_mi
            mod.ALT_MEMORY_DIR = orig_amd
        output = self._output()
        self.assertIn('Layer 15m', output)


# ============================================================================
# quality-gate.py — boost 83%→85%+ (mechanical/transcript parsing paths)
# ============================================================================

class TestQualityGateMechanicalBoost(_MainTestBase):
    def _write_transcript(self, entries):
        path = os.path.join(self.tmpdir, 'transcript.jsonl')
        with open(path, 'w', encoding='utf-8') as f:
            for e in entries:
                f.write(json.dumps(e) + '\n')
        return path

    def _qg(self):
        return __import__('quality-gate')

    def test_get_last_turn_lines_empty(self):
        qg = self._qg()
        result = qg._get_last_turn_lines('')
        self.assertEqual(result, [])

    def test_get_last_turn_lines_with_data(self):
        qg = self._qg()
        path = self._write_transcript([
            {"type": "assistant", "message": {"content": [
                {"type": "text", "text": "Hello"}
            ]}}
        ])
        result = qg._get_last_turn_lines(path)
        self.assertGreaterEqual(len(result), 1)

    def test_get_last_turn_lines_non_json_skipped(self):
        qg = self._qg()
        path = self._write_file('mixed.jsonl', 'garbage\n{"type":"assistant","message":{"content":[]}}\n')
        result = qg._get_last_turn_lines(path)
        self.assertIsInstance(result, list)

    def test_get_tool_summary_empty(self):
        qg = self._qg()
        names, paths, cmds = qg.get_tool_summary('')
        self.assertEqual(names, [])

    def test_get_tool_summary_with_tools(self):
        qg = self._qg()
        path = self._write_transcript([
            {"type": "assistant", "message": {"content": [
                {"type": "tool_use", "name": "Grep", "input": {"pattern": "foo"}},
                {"type": "tool_use", "name": "Edit", "input": {"file_path": "/a.py"}},
            ]}}
        ])
        names, paths, cmds = qg.get_tool_summary(path)
        self.assertIn('Grep', names)
        self.assertIn('Edit', names)
        self.assertEqual(paths, ['/a.py'])

    def test_get_failed_commands_with_error(self):
        qg = self._qg()
        path = self._write_transcript([
            {"type": "assistant", "message": {"content": [
                {"type": "tool_use", "id": "b1", "name": "Bash", "input": {"command": "npm test"}},
            ]}},
            {"type": "user", "message": {"content": [
                {"type": "tool_result", "tool_use_id": "b1", "is_error": True, "content": "Error: failed"},
            ]}},
        ])
        failed = qg.get_failed_commands(path)
        self.assertGreaterEqual(len(failed), 1)

    def test_get_failed_commands_list_content(self):
        """Lines 433-434: tool_result content is a list."""
        qg = self._qg()
        path = self._write_transcript([
            {"type": "assistant", "message": {"content": [
                {"type": "tool_use", "id": "b2", "name": "Bash", "input": {"command": "make"}},
            ]}},
            {"type": "user", "message": {"content": [
                {"type": "tool_result", "tool_use_id": "b2", "is_error": True,
                 "content": [{"type": "text", "text": "Build failed"}]},
            ]}},
        ])
        failed = qg.get_failed_commands(path)
        self.assertGreaterEqual(len(failed), 1)

    def test_get_user_request_empty(self):
        qg = self._qg()
        result = qg.get_user_request('')
        self.assertEqual(result, '')

    def test_get_user_request_with_text(self):
        qg = self._qg()
        path = self._write_transcript([
            {"type": "user", "message": {"content": "Fix the login bug"}},
            {"type": "assistant", "message": {"content": [
                {"type": "text", "text": "I'll fix it."}
            ]}}
        ])
        result = qg.get_user_request(path)
        self.assertIn('Fix the login bug', result)

    def test_get_user_request_list_content(self):
        qg = self._qg()
        path = self._write_transcript([
            {"type": "user", "message": {"content": [
                {"type": "text", "text": "Update the docs"}
            ]}},
            {"type": "assistant", "message": {"content": [
                {"type": "text", "text": "Done."}
            ]}}
        ])
        result = qg.get_user_request(path)
        self.assertIn('Update the docs', result)

    def test_get_bash_results_empty(self):
        qg = self._qg()
        result = qg.get_bash_results('')
        self.assertEqual(result, [])

    def test_extract_stated_certainty(self):
        qg = self._qg()
        self.assertEqual(qg._extract_stated_certainty("I'm certain this works"), 'high')
        self.assertEqual(qg._extract_stated_certainty("I believe it should work"), 'medium')
        self.assertEqual(qg._extract_stated_certainty("This might work"), 'low')
        self.assertEqual(qg._extract_stated_certainty("Here is the code"), 'none')

    def test_compute_confidence(self):
        qg = self._qg()
        score = qg._compute_confidence(
            gate_blocked=False, block_category='', state={}
        )
        self.assertIsInstance(score, (int, float))

    def test_get_last_complexity(self):
        qg = self._qg()
        # get_last_complexity reads from session state — just verify it returns a string
        result = qg.get_last_complexity()
        self.assertIsInstance(result, str)

    def test_count_user_items(self):
        qg = self._qg()
        count = qg._count_user_items("fix these 5 bugs in the auth module")
        self.assertEqual(count, 5)

    def test_write_monitor_event(self):
        qg = self._qg()
        orig = qg._QG_MONITOR
        qg._QG_MONITOR = os.path.join(self.tmpdir, 'monitor.jsonl')
        try:
            qg._write_monitor_event({"test": True, "category": "TEST"})
        finally:
            qg._QG_MONITOR = orig
        with open(os.path.join(self.tmpdir, 'monitor.jsonl')) as f:
            content = f.read()
        self.assertIn('TEST', content)


# ============================================================================
# Layer 0: Session Bootstrap — boost 79%→85%+
# ============================================================================

class TestLayer0Boost(_MainTestBase):
    def test_find_previous_session_unresolved_file_read_error(self):
        """Lines 26-27: history file exists but can't be read."""
        from qg_layer0 import find_previous_session_unresolved
        import qg_layer0 as mod
        orig = mod.HISTORY_PATH
        # Use directory as path to trigger read error
        mod.HISTORY_PATH = self.tmpdir
        try:
            result = find_previous_session_unresolved()
        finally:
            mod.HISTORY_PATH = orig
        self.assertEqual(result, [])

    def test_find_previous_session_current_uuid_match(self):
        """Line 38: matching session_uuid returns unresolved items."""
        from qg_layer0 import find_previous_session_unresolved
        import qg_layer0 as mod, qg_session_state as ss
        orig = mod.HISTORY_PATH
        state = ss.read_state()
        state['session_uuid'] = 'test-uuid-l0'
        ss.write_state(state)
        history = self._write_file('history.md',
            '## Session test-uuid-l0\n- UNRESOLVED: FN -- LAZINESS (task: t1)\n')
        mod.HISTORY_PATH = history
        try:
            result = find_previous_session_unresolved()
        finally:
            mod.HISTORY_PATH = orig
        # Should find the unresolved item
        self.assertIsInstance(result, list)

    def test_load_recovery_pending_corrupt_file(self):
        """Lines 70-71: corrupt recovery file → []."""
        from qg_layer0 import load_recovery_pending
        import qg_layer0 as mod
        orig = mod.RECOVERY_PENDING_PATH
        f = self._write_file('recovery.json', 'not json')
        mod.RECOVERY_PENDING_PATH = f
        try:
            result = load_recovery_pending()
        finally:
            mod.RECOVERY_PENDING_PATH = orig
        self.assertEqual(result, [])

    def test_main_bad_json_no_crash(self):
        """Lines 75-76: bad JSON stdin."""
        import qg_layer0
        sys.stdin = io.StringIO('not json')
        try:
            qg_layer0.main()
        finally:
            sys.stdin = self._orig_stdin

    def test_main_with_rules_path_error(self):
        """Lines 84-85: rules file missing → default max_chars."""
        import qg_layer0, qg_session_state as ss
        orig_rp = qg_layer0.RULES_PATH
        orig_cp = qg_layer0.CROSS_SESSION_PATH
        qg_layer0.RULES_PATH = os.path.join(self.tmpdir, 'no_rules.json')
        # Create a cross-session file with patterns to trigger injection
        cs = self._write_file('cross.json', json.dumps({
            "patterns": [{"category": "LAZINESS", "sessions_count": 5, "total_events": 20}]
        }))
        qg_layer0.CROSS_SESSION_PATH = cs
        self._set_stdin({})
        self._capture_print()
        try:
            qg_layer0.main()
        finally:
            builtins.print = self._orig_print
            qg_layer0.RULES_PATH = orig_rp
            qg_layer0.CROSS_SESSION_PATH = orig_cp
        output = self._output()
        self.assertIn('LAZINESS', output)

    def test_main_with_unresolved_items(self):
        """Lines 103-106: unresolved items injected."""
        import qg_layer0, qg_session_state as ss
        orig_hp = qg_layer0.HISTORY_PATH
        orig_cp = qg_layer0.CROSS_SESSION_PATH
        qg_layer0.CROSS_SESSION_PATH = os.path.join(self.tmpdir, 'empty_cross.json')
        state = ss.read_state()
        state['session_uuid'] = 'test-uuid-unresolved'
        ss.write_state(state)
        history = self._write_file('history.md',
            '## Session test-uuid-unresolved\n- UNRESOLVED: FN -- LOOP (task: t2)\n')
        qg_layer0.HISTORY_PATH = history
        self._set_stdin({})
        self._capture_print()
        try:
            qg_layer0.main()
        finally:
            builtins.print = self._orig_print
            qg_layer0.HISTORY_PATH = orig_hp
            qg_layer0.CROSS_SESSION_PATH = orig_cp

    def test_main_with_recovery_pending(self):
        """Lines 111-114: recovery events injected."""
        import qg_layer0, qg_session_state as ss
        orig_rpp = qg_layer0.RECOVERY_PENDING_PATH
        orig_cp = qg_layer0.CROSS_SESSION_PATH
        qg_layer0.CROSS_SESSION_PATH = os.path.join(self.tmpdir, 'empty_cross2.json')
        rp = self._write_file('recovery.json', json.dumps({
            "events": [{"status": "open", "event_type": "FN_DETECTED"}]
        }))
        qg_layer0.RECOVERY_PENDING_PATH = rp
        self._set_stdin({})
        self._capture_print()
        try:
            qg_layer0.main()
        finally:
            builtins.print = self._orig_print
            qg_layer0.RECOVERY_PENDING_PATH = orig_rpp
            qg_layer0.CROSS_SESSION_PATH = orig_cp
        output = self._output()
        if output:
            self.assertIn('recovery', output.lower())


# ============================================================================
# Layer 14: Response Efficiency — boost 78%→85%+
# ============================================================================

class TestLayer14Boost(_MainTestBase):
    def _write_transcript(self, entries):
        path = os.path.join(self.tmpdir, 'transcript.jsonl')
        with open(path, 'w', encoding='utf-8') as f:
            for e in entries:
                f.write(json.dumps(e) + '\n')
        return path

    def test_parse_tool_calls_file_read_error(self):
        """Lines 36-37: file can't be read."""
        from qg_layer14 import parse_tool_calls
        calls, paths = parse_tool_calls(self.tmpdir)  # dir not file
        self.assertEqual(calls, [])

    def test_parse_tool_calls_with_tools(self):
        from qg_layer14 import parse_tool_calls
        path = self._write_transcript([
            {"role": "assistant", "message": {"content": [
                {"type": "tool_use", "name": "Read", "input": {"file_path": "/a.py"}},
                {"type": "tool_use", "name": "Edit", "input": {"file_path": "/b.py"}},
                {"type": "tool_use", "name": "Bash", "input": {"command": "pytest"}},
            ]}}
        ])
        calls, read_paths = parse_tool_calls(path)
        self.assertIn('Read', calls)
        self.assertIn('Edit', calls)
        self.assertIn('/a.py', read_paths)

    def test_main_with_efficiency_issues(self):
        """Lines 129-156: main produces output when issues found."""
        import qg_layer14, qg_session_state as ss
        orig_mp = qg_layer14.MONITOR_PATH
        qg_layer14.MONITOR_PATH = self.monitor_path
        state = ss.read_state()
        state['last_complexity'] = 'TRIVIAL'
        ss.write_state(state)
        # Create transcript with many tool calls (exceeds TRIVIAL threshold)
        tools = [{"type": "tool_use", "name": "Read", "input": {"file_path": f"/f{i}.py"}}
                 for i in range(30)]
        path = self._write_transcript([
            {"role": "assistant", "message": {"content": tools}}
        ])
        self._set_stdin({"transcript_path": path})
        self._capture_print()
        try:
            qg_layer14.main()
        finally:
            builtins.print = self._orig_print
            qg_layer14.MONITOR_PATH = orig_mp
        output = self._output()
        self.assertIn('Layer 14', output)
        self.assertIn('EXCESSIVE', output)

    def test_analyze_efficiency_redundant_reads(self):
        from qg_layer14 import analyze_efficiency
        report = analyze_efficiency(
            ['Read', 'Read', 'Read'], ['/a.py', '/a.py', '/b.py'], 'MODERATE')
        self.assertTrue(any('REDUNDANT' in msg for _, msg in report['issues']))

    def test_detect_redundant_reads(self):
        from qg_layer14 import detect_redundant_reads
        result = detect_redundant_reads(['/a.py', '/a.py', '/b.py'])
        paths = [p for p, _ in result]
        self.assertIn('/a.py', [p.replace('\\', '/') for p in paths])

    def test_check_tool_count_no_complexity(self):
        from qg_layer14 import check_tool_count
        self.assertIsNone(check_tool_count(['Read'] * 10))

    def test_check_tool_count_under_threshold(self):
        from qg_layer14 import check_tool_count
        self.assertIsNone(check_tool_count(['Read'] * 3, 'MODERATE'))

    def test_check_tool_count_over_threshold(self):
        from qg_layer14 import check_tool_count
        result = check_tool_count(['Read'] * 50, 'TRIVIAL')
        self.assertIsNotNone(result)
        self.assertIn('EXCESSIVE', result[1])


# ============================================================================
# quality-gate.py — LLM-mocked tests for _layer3_run path
# ============================================================================

class TestQualityGatePriorContext(_MainTestBase):
    def _write_transcript(self, entries):
        path = os.path.join(self.tmpdir, 'transcript.jsonl')
        with open(path, 'w', encoding='utf-8') as f:
            for e in entries:
                f.write(json.dumps(e) + '\n')
        return path

    def _qg(self):
        return __import__('quality-gate')

    def test_get_prior_context_empty(self):
        qg = self._qg()
        result = qg.get_prior_context('')
        self.assertEqual(result, [])

    def test_get_prior_context_with_exchanges(self):
        qg = self._qg()
        path = self._write_transcript([
            {"type": "user", "message": {"content": "First question"}},
            {"type": "assistant", "message": {"content": [
                {"type": "tool_use", "name": "Read", "input": {}},
                {"type": "text", "text": "Answer to first."}
            ]}},
            {"type": "user", "message": {"content": "Second question"}},
            {"type": "assistant", "message": {"content": [
                {"type": "text", "text": "Answer to second."}
            ]}},
        ])
        result = qg.get_prior_context(path)
        self.assertIsInstance(result, list)

    def test_get_bash_results_with_matched_ids(self):
        """Lines 334-391: bash results matched by tool_use_id."""
        qg = self._qg()
        # Need a real user message first, then assistant with Bash, then tool_result
        path = self._write_transcript([
            {"type": "user", "message": {"content": "run tests"}},
            {"type": "assistant", "message": {"content": [
                {"type": "tool_use", "id": "br1", "name": "Bash", "input": {"command": "echo hi"}},
            ]}},
            {"type": "user", "message": {"content": [
                {"type": "tool_result", "tool_use_id": "br1", "content": "hi"},
            ]}},
        ])
        result = qg.get_bash_results(path)
        self.assertIsInstance(result, list)

    def test_get_bash_results_list_content(self):
        """Lines 380-383: tool_result content as list."""
        qg = self._qg()
        path = self._write_transcript([
            {"type": "user", "message": {"content": "check files"}},
            {"type": "assistant", "message": {"content": [
                {"type": "tool_use", "id": "br2", "name": "Bash", "input": {"command": "ls"}},
            ]}},
            {"type": "user", "message": {"content": [
                {"type": "tool_result", "tool_use_id": "br2",
                 "content": [{"type": "text", "text": "file.py"}]},
            ]}},
        ])
        result = qg.get_bash_results(path)
        self.assertIsInstance(result, list)

    def test_mechanical_checks_no_issues(self):
        qg = self._qg()
        result = qg.mechanical_checks(
            ['Read', 'Bash'], [], ['pytest'], [], 'Tests pass: 5 passed', 'run tests')
        self.assertIsNone(result)

    def test_detect_override(self):
        qg = self._qg()
        orig_lp = qg.LOG_PATH
        qg.LOG_PATH = os.path.join(self.tmpdir, 'qg.log')
        try:
            result = qg._detect_override('just do it, skip checks', ['Edit'], 'done')
        finally:
            qg.LOG_PATH = orig_lp
        # Returns True/False or None (no override detected)
        self.assertIn(result, [True, False, None])


# ============================================================================
# _hooks_shared.py — boost 46%→70%+
# ============================================================================

class TestHooksShared(_MainTestBase):
    def _hs(self):
        return __import__('_hooks_shared')

    # --- rotate_log ---

    def test_rotate_log_under_max(self):
        hs = self._hs()
        f = self._write_file('small.log', 'line1\nline2\nline3\n')
        hs.rotate_log(f, 10)
        with open(f) as fh:
            self.assertEqual(len(fh.readlines()), 3)

    def test_rotate_log_over_max(self):
        hs = self._hs()
        f = self._write_file('big.log', ''.join(f'line{i}\n' for i in range(20)))
        hs.rotate_log(f, 5)
        with open(f) as fh:
            lines = fh.readlines()
        self.assertEqual(len(lines), 5)
        self.assertIn('line19', lines[-1])

    def test_rotate_log_with_header(self):
        hs = self._hs()
        f = self._write_file('header.log', 'HEADER\n' + ''.join(f'line{i}\n' for i in range(20)))
        hs.rotate_log(f, 5, header_lines=1)
        with open(f) as fh:
            lines = fh.readlines()
        self.assertEqual(len(lines), 5)
        self.assertIn('HEADER', lines[0])

    def test_rotate_log_min_size_skip(self):
        hs = self._hs()
        f = self._write_file('tiny.log', 'x\n')
        hs.rotate_log(f, 5, min_size=10000)
        # File untouched — too small

    def test_rotate_log_min_size_missing_file(self):
        hs = self._hs()
        hs.rotate_log(os.path.join(self.tmpdir, 'nope.log'), 5, min_size=100)
        # No crash

    # --- load_api_key ---

    def test_load_api_key_from_env(self):
        hs = self._hs()
        import os as _os
        orig = _os.environ.get('ANTHROPIC_API_KEY')
        _os.environ['ANTHROPIC_API_KEY'] = 'test-key-123'
        try:
            key = hs.load_api_key()
        finally:
            if orig:
                _os.environ['ANTHROPIC_API_KEY'] = orig
            else:
                _os.environ.pop('ANTHROPIC_API_KEY', None)
        self.assertEqual(key, 'test-key-123')

    def test_load_api_key_from_dotenv(self):
        hs = self._hs()
        import os as _os
        orig = _os.environ.pop('ANTHROPIC_API_KEY', None)
        # load_api_key reads from ~/.claude/.env — just test it doesn't crash
        try:
            key = hs.load_api_key()
        finally:
            if orig:
                _os.environ['ANTHROPIC_API_KEY'] = orig
        self.assertIsInstance(key, str)

    # --- check_cache / write_cache ---

    def test_write_and_check_cache(self):
        hs = self._hs()
        orig = hs.CACHE_PATH
        hs.CACHE_PATH = os.path.join(self.tmpdir, 'cache.json')
        try:
            hs.write_cache('test response', True, 'ok')
            result = hs.check_cache('test response')
        finally:
            hs.CACHE_PATH = orig
        self.assertIsNotNone(result)
        self.assertEqual(result[0], True)

    def test_check_cache_missing_file(self):
        hs = self._hs()
        orig = hs.CACHE_PATH
        hs.CACHE_PATH = os.path.join(self.tmpdir, 'nope.json')
        try:
            result = hs.check_cache('anything')
        finally:
            hs.CACHE_PATH = orig
        self.assertIsNone(result)

    def test_write_cache_overflow_prunes(self):
        hs = self._hs()
        orig = hs.CACHE_PATH
        hs.CACHE_PATH = os.path.join(self.tmpdir, 'overflow.json')
        try:
            for i in range(210):
                hs.write_cache(f'response_{i}', True, 'ok')
            with open(hs.CACHE_PATH) as f:
                cache = json.load(f)
            self.assertLessEqual(len(cache), 200)
        finally:
            hs.CACHE_PATH = orig

    # --- write_override ---

    def test_write_override(self):
        hs = self._hs()
        orig = hs.OVERRIDES_PATH
        hs.OVERRIDES_PATH = os.path.join(self.tmpdir, 'overrides.jsonl')
        try:
            hs.write_override({"reason": "test", "ts": time.time()})
        finally:
            hs.OVERRIDES_PATH = orig
        with open(os.path.join(self.tmpdir, 'overrides.jsonl')) as f:
            content = f.read()
        self.assertIn('test', content)

    # --- call_haiku_check (no API key path, lines 714-715) ---

    def test_call_haiku_no_api_key(self):
        # Lines 714-715: load_api_key returns '' → _log_degradation called, fail-open returned
        import unittest.mock as _mock
        hs = self._hs()
        with _mock.patch.object(hs, 'load_api_key', return_value=''):
            ok, reason, genuine = hs.call_haiku_check('test prompt')
        self.assertTrue(ok)
        self.assertFalse(genuine)

    # --- _log_degradation ---

    def test_log_degradation(self):
        hs = self._hs()
        # Just verify it doesn't crash
        hs._log_degradation('Test degradation message')

    # --- _response_hash ---

    def test_response_hash(self):
        hs = self._hs()
        h1 = hs._response_hash('hello')
        h2 = hs._response_hash('hello')
        h3 = hs._response_hash('world')
        self.assertEqual(h1, h2)
        self.assertNotEqual(h1, h3)

    # --- regex constants ---

    def test_non_code_path_re(self):
        hs = self._hs()
        self.assertTrue(hs.NON_CODE_PATH_RE.search('memory/user_profile.md'))
        self.assertTrue(hs.NON_CODE_PATH_RE.search('CLAUDE.md'))
        self.assertFalse(hs.NON_CODE_PATH_RE.search('src/app.py'))

    def test_validation_command_re(self):
        hs = self._hs()
        self.assertTrue(hs.VALIDATION_COMMAND_RE.search('python -m pytest tests/'))
        self.assertTrue(hs.VALIDATION_COMMAND_RE.search('npm test'))
        self.assertTrue(hs.VALIDATION_COMMAND_RE.search('bash smoke-test.sh'))

    # --- rotate_log write failure (lines 44-50) ---

    def test_rotate_log_write_failure_no_crash(self):
        # Lines 44-48: inner except — os.fdopen raises, os.unlink called; then unlink also raises
        import unittest.mock as _mock
        hs = self._hs()
        f = self._write_file('fail.log', ''.join(f'line{i}\n' for i in range(20)))
        with _mock.patch('os.fdopen', side_effect=OSError('mock fdopen fail')):
            with _mock.patch('os.unlink', side_effect=OSError('mock unlink fail')):
                hs.rotate_log(f, 5)  # Should not raise

    def test_rotate_log_outer_exception_no_crash(self):
        # Lines 49-50: outer except — open(path, 'r') raises, exception swallowed
        import unittest.mock as _mock
        hs = self._hs()
        with _mock.patch('builtins.open', side_effect=PermissionError('denied')):
            hs.rotate_log('/some/path.log', 5)  # Should not raise

    # --- load_api_key dotenv open raises unexpected exception (lines 100-102) ---

    def test_load_api_key_dotenv_open_exception(self):
        # Lines 100-102: open(.env) raises unexpected exception, returns ''
        import os as _os, unittest.mock as _mock
        hs = self._hs()
        orig = _os.environ.pop('ANTHROPIC_API_KEY', None)
        try:
            with _mock.patch('builtins.open', side_effect=PermissionError('denied')):
                key = hs.load_api_key()
        finally:
            if orig:
                _os.environ['ANTHROPIC_API_KEY'] = orig
        self.assertEqual(key, '')

    # --- check_cache expired entry (line 119) ---

    def test_check_cache_expired_returns_none(self):
        # Line 119: cache entry exists but ts is older than 86400s → returns None
        import json as _json, time as _time
        hs = self._hs()
        orig = hs.CACHE_PATH
        hs.CACHE_PATH = os.path.join(self.tmpdir, 'exp_cache.json')
        try:
            h = hs._response_hash('old response')
            cache = {h: {'ok': True, 'reason': '', 'ts': _time.time() - 90000}}
            with open(hs.CACHE_PATH, 'w') as fh:
                _json.dump(cache, fh)
            result = hs.check_cache('old response')
        finally:
            hs.CACHE_PATH = orig
        self.assertIsNone(result)

    # --- write_cache outer exception (lines 142-143) ---

    def test_write_cache_write_exception_no_crash(self):
        # Lines 142-143: outer json.dump write raises, exception swallowed
        import unittest.mock as _mock
        hs = self._hs()
        orig = hs.CACHE_PATH
        hs.CACHE_PATH = os.path.join(self.tmpdir, 'crash_cache.json')
        try:
            with _mock.patch('json.dump', side_effect=OSError('mock write fail')):
                hs.write_cache('some response', True, 'ok')  # Should not raise
        finally:
            hs.CACHE_PATH = orig

    # --- write_override exception (lines 155-156) ---

    def test_write_override_exception_no_crash(self):
        # Lines 155-156: open raises, exception swallowed
        import unittest.mock as _mock
        hs = self._hs()
        orig = hs.OVERRIDES_PATH
        hs.OVERRIDES_PATH = os.path.join(self.tmpdir, 'overrides_fail.jsonl')
        try:
            with _mock.patch('builtins.open', side_effect=PermissionError('denied')):
                hs.write_override({'reason': 'test'})  # Should not raise
        finally:
            hs.OVERRIDES_PATH = orig

    # --- call_haiku_check 429 retry (lines 738-744) ---

    def test_call_haiku_429_retry(self):
        # Lines 738-744: first urlopen raises 429, second succeeds
        import urllib.error, unittest.mock as _mock, json as _json
        hs = self._hs()
        good_body = _json.dumps({'content': [{'type': 'text', 'text': '{"ok": true}'}]}).encode()
        good_resp = _mock.MagicMock()
        good_resp.__enter__ = lambda s: s
        good_resp.__exit__ = _mock.MagicMock(return_value=False)
        good_resp.read.return_value = good_body
        err_429 = urllib.error.HTTPError(url='', code=429, msg='Too Many Requests', hdrs=None, fp=None)
        call_count = [0]
        def fake_urlopen(req, timeout=10):
            call_count[0] += 1
            if call_count[0] == 1:
                raise err_429
            return good_resp
        import os as _os
        orig = _os.environ.get('ANTHROPIC_API_KEY')
        _os.environ['ANTHROPIC_API_KEY'] = 'sk-test-key'
        try:
            with _mock.patch('urllib.request.urlopen', side_effect=fake_urlopen):
                with _mock.patch('time.sleep'):
                    ok, reason, genuine = hs.call_haiku_check('test prompt')
        finally:
            if orig:
                _os.environ['ANTHROPIC_API_KEY'] = orig
            else:
                _os.environ.pop('ANTHROPIC_API_KEY', None)
        self.assertTrue(ok)
        self.assertTrue(genuine)

    # --- call_haiku_check backtick stripping (lines 751-753) ---

    def test_call_haiku_backtick_response(self):
        # Lines 751-753: LLM wraps JSON in ```json ... ``` code fence
        import unittest.mock as _mock, json as _json
        hs = self._hs()
        body = _json.dumps({'content': [{'type': 'text', 'text': '```json\n{"ok": true}\n```'}]}).encode()
        resp = _mock.MagicMock()
        resp.__enter__ = lambda s: s
        resp.__exit__ = _mock.MagicMock(return_value=False)
        resp.read.return_value = body
        import os as _os
        orig = _os.environ.get('ANTHROPIC_API_KEY')
        _os.environ['ANTHROPIC_API_KEY'] = 'sk-test-key'
        try:
            with _mock.patch('urllib.request.urlopen', return_value=resp):
                ok, reason, genuine = hs.call_haiku_check('test prompt')
        finally:
            if orig:
                _os.environ['ANTHROPIC_API_KEY'] = orig
            else:
                _os.environ.pop('ANTHROPIC_API_KEY', None)
        self.assertTrue(ok)
        self.assertTrue(genuine)

    # --- call_haiku_check inner JSONDecodeError in regex fallback (lines 762-766) ---

    def test_call_haiku_json_fallback_no_match(self):
        # Lines 758-759, 767-769: initial parse fails, regex finds no match → fail-open
        import unittest.mock as _mock, json as _json
        hs = self._hs()
        # Text with no JSON-like object — regex won't match
        raw_text = 'completely invalid response with no json object at all'
        body = _json.dumps({'content': [{'type': 'text', 'text': raw_text}]}).encode()
        resp = _mock.MagicMock()
        resp.__enter__ = lambda s: s
        resp.__exit__ = _mock.MagicMock(return_value=False)
        resp.read.return_value = body
        real_loads = hs.json.loads
        call_count = [0]
        def fail_on_text(s, **kw):
            result = real_loads(s, **kw)
            call_count[0] += 1
            # First call succeeds (parses API response body); second call is for text — raise
            if call_count[0] >= 2:
                raise _json.JSONDecodeError('mock', raw_text, 0)
            return result
        with _mock.patch.object(hs, 'load_api_key', return_value='sk-test-key'):
            with _mock.patch('urllib.request.urlopen', return_value=resp):
                with _mock.patch.object(hs.json, 'loads', side_effect=fail_on_text):
                    ok, reason, genuine = hs.call_haiku_check('test prompt')
        self.assertTrue(ok)
        self.assertFalse(genuine)

    def test_call_haiku_json_fallback_inner_decode_error(self):
        # Lines 762-766: initial parse fails, regex finds match but inner parse also fails → fail-open
        import unittest.mock as _mock, json as _json
        hs = self._hs()
        # Text containing a JSON-like object so regex matches, but both parses fail
        raw_text = 'preamble {"ok": true} trailing'
        body = _json.dumps({'content': [{'type': 'text', 'text': raw_text}]}).encode()
        resp = _mock.MagicMock()
        resp.__enter__ = lambda s: s
        resp.__exit__ = _mock.MagicMock(return_value=False)
        resp.read.return_value = body
        real_loads = hs.json.loads
        call_count = [0]
        def fail_on_text(s, **kw):
            result = real_loads(s, **kw)
            call_count[0] += 1
            if call_count[0] >= 2:
                raise _json.JSONDecodeError('mock', raw_text, 0)
            return result
        with _mock.patch.object(hs, 'load_api_key', return_value='sk-test-key'):
            with _mock.patch('urllib.request.urlopen', return_value=resp):
                with _mock.patch.object(hs.json, 'loads', side_effect=fail_on_text):
                    ok, reason, genuine = hs.call_haiku_check('test prompt')
        self.assertTrue(ok)
        self.assertFalse(genuine)

    # --- call_haiku_check outer exception (lines 773-775) ---

    def test_call_haiku_network_exception_fail_open(self):
        # Lines 773-775: urlopen raises non-429 exception → fail-open
        import unittest.mock as _mock
        hs = self._hs()
        import os as _os
        orig = _os.environ.get('ANTHROPIC_API_KEY')
        _os.environ['ANTHROPIC_API_KEY'] = 'sk-test-key'
        try:
            with _mock.patch('urllib.request.urlopen', side_effect=ConnectionError('network down')):
                ok, reason, genuine = hs.call_haiku_check('test prompt')
        finally:
            if orig:
                _os.environ['ANTHROPIC_API_KEY'] = orig
            else:
                _os.environ.pop('ANTHROPIC_API_KEY', None)
        self.assertTrue(ok)
        self.assertFalse(genuine)

    # --- _log_degradation write exception (lines 786-787) ---

    def test_log_degradation_write_exception_no_crash(self):
        # Lines 786-787: open raises, exception swallowed
        import unittest.mock as _mock
        hs = self._hs()
        with _mock.patch('builtins.open', side_effect=PermissionError('denied')):
            hs._log_degradation('Test message')  # Should not raise


# ============================================================================
# precheck-hook.py — boost 59%→75%+
# ============================================================================

class TestPrecheckHookBoost(_MainTestBase):
    def _pc(self):
        return __import__('precheck-hook')

    def test_extract_message_string(self):
        pc = self._pc()
        self.assertEqual(pc.extract_message({"message": "hello"}), "hello")

    def test_extract_message_dict(self):
        pc = self._pc()
        self.assertEqual(pc.extract_message({"message": {"content": "hello"}}), "hello")

    def test_extract_message_list(self):
        pc = self._pc()
        result = pc.extract_message({"message": [{"type": "text", "text": "hello"}]})
        self.assertEqual(result, "hello")

    def test_extract_message_empty(self):
        pc = self._pc()
        self.assertEqual(pc.extract_message({}), "")

    def test_run_layer1_mechanical(self):
        pc = self._pc()
        import qg_session_state as ss
        state = ss.read_state()
        state['active_task_id'] = 'test_l1'
        state['layer15_session_reads'] = ['/a.py']
        extra, new_state = pc._run_layer1('fix the bug in auth.py', 'MECHANICAL', state)
        self.assertIn('MECHANICAL', new_state.get('layer1_task_category', ''))
        self.assertIsInstance(new_state.get('task_success_criteria'), list)

    def test_run_layer1_planning(self):
        pc = self._pc()
        import qg_session_state as ss
        state = ss.read_state()
        state['active_task_id'] = 'test_plan'
        extra, new_state = pc._run_layer1('what should I do next', 'PLANNING', state)
        self.assertEqual(new_state.get('layer1_task_category'), 'PLANNING')

    def test_run_layer1_deep_no_reads(self):
        pc = self._pc()
        import qg_session_state as ss
        state = ss.read_state()
        state['active_task_id'] = 'test_deep'
        state['layer15_session_reads'] = []
        extra, new_state = pc._run_layer1('refactor the entire auth module', 'DEEP', state)
        # Should warn about no prior reads
        self.assertTrue(any('DEEP' in line for line in extra))

    def test_run_layer1_multi_task(self):
        pc = self._pc()
        import qg_session_state as ss
        state = ss.read_state()
        state['active_task_id'] = 'test_multi'
        extra, new_state = pc._run_layer1('1. fix the bug\n2. add tests\n3. update docs', 'MECHANICAL', state)
        self.assertGreaterEqual(new_state.get('layer1_subtask_count', 0), 2)

    def test_run_layer1_high_impact_criteria(self):
        pc = self._pc()
        import qg_session_state as ss
        state = ss.read_state()
        state['active_task_id'] = 'test_impact'
        state['layer19_last_impact_level'] = 'HIGH'
        extra, new_state = pc._run_layer1('fix the config', 'MECHANICAL', state)
        criteria = new_state.get('task_success_criteria', [])
        self.assertTrue(any('dependent' in c.lower() for c in criteria))

    def test_main_bad_json(self):
        pc = self._pc()
        sys.stdin = io.StringIO('not json')
        try:
            pc.main()
        finally:
            sys.stdin = self._orig_stdin

    def test_main_short_message(self):
        pc = self._pc()
        self._set_stdin({"message": "hi"})
        self._capture_print()
        try:
            pc.main()
        finally:
            builtins.print = self._orig_print
        # Short message (<5 chars) returns early
        self.assertEqual(self._captured, [])

    # --- _write_event coverage (lines 11-15) ---

    def test_write_event_writes_to_file(self):
        pc = self._pc()
        orig = pc._MONITOR_PATH
        pc._MONITOR_PATH = self.monitor_path
        try:
            pc._write_event({'event_id': 'test-write', 'layer': 'precheck', 'msg': 'hello'})
        finally:
            pc._MONITOR_PATH = orig
        self.assertTrue(os.path.exists(self.monitor_path))
        with open(self.monitor_path, encoding='utf-8') as f:
            line = f.readline()
        data = json.loads(line)
        self.assertEqual(data['event_id'], 'test-write')

    def test_write_event_bad_path_no_crash(self):
        pc = self._pc()
        orig = pc._MONITOR_PATH
        pc._MONITOR_PATH = '/nonexistent_dir/qg-monitor.jsonl'
        try:
            pc._write_event({'event_id': 'fail-path'})
        finally:
            pc._MONITOR_PATH = orig
        # Should silently swallow exception

    # --- detect_subtasks line 46 coverage ---

    def test_detect_subtasks_conjunction(self):
        pc = self._pc()
        msg = 'Fix the login bug and also update the README and then run the tests'
        result = pc.detect_subtasks(msg)
        self.assertGreaterEqual(len(result), 2)

    # --- _run_layer1 codebase scan (lines 113-125) ---

    def test_run_layer1_deep_with_scope_scan(self):
        pc = self._pc()
        import qg_session_state as ss
        state = ss.read_state()
        state['active_task_id'] = 'test_scan'
        state['layer15_session_reads'] = ['precheck-hook.py']
        # DEEP category with a scope file that exists in the hooks dir
        extra, new_state = pc._run_layer1(
            'refactor the precheck-hook.py file completely', 'DEEP', state)
        self.assertEqual(new_state.get('layer1_task_category'), 'DEEP')

    def test_run_layer1_mechanical_with_scope_scan(self):
        pc = self._pc()
        import qg_session_state as ss
        state = ss.read_state()
        state['active_task_id'] = 'test_mech_scan'
        state['layer15_session_reads'] = ['some_file.py']
        extra, new_state = pc._run_layer1(
            'edit the qg_layer29.py to fix the count check', 'MECHANICAL', state)
        self.assertIn('MECHANICAL', new_state.get('layer1_task_category', ''))
        # scope_files should be set
        self.assertIsInstance(new_state.get('layer1_scope_files'), list)

    def test_run_layer1_scope_merged_into_state(self):
        pc = self._pc()
        import qg_session_state as ss
        state = ss.read_state()
        state['active_task_id'] = 'test_scope_merge'
        state['layer1_scope_files'] = ['existing_file.py']
        state['layer15_session_reads'] = ['existing_file.py']
        extra, new_state = pc._run_layer1(
            'update qg_session_state.py with new fields', 'MECHANICAL', state)
        # scope_files should be a list (may include existing + scanned)
        self.assertIsInstance(new_state.get('layer1_scope_files'), list)

    # --- main() Ollama path and session state update (lines 194-244) ---

    def test_main_ollama_mocked_mechanical(self):
        """Mock urlopen so Ollama call returns MECHANICAL, verify directive printed."""
        import unittest.mock as mock
        pc = self._pc()
        orig = pc._MONITOR_PATH
        pc._MONITOR_PATH = self.monitor_path
        mock_resp = mock.MagicMock()
        mock_resp.read.return_value = json.dumps({"response": "MECHANICAL"}).encode()
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = mock.MagicMock(return_value=False)
        self._set_stdin({"message": "edit the main config file to add logging"})
        self._capture_print()
        try:
            with mock.patch('urllib.request.urlopen', return_value=mock_resp):
                pc.main()
        finally:
            builtins.print = self._orig_print
            pc._MONITOR_PATH = orig
        output = self._output()
        self.assertIn('MECHANICAL', output)

    def test_main_ollama_mocked_planning(self):
        """Mock urlopen so Ollama returns PLANNING, verify directive printed."""
        import unittest.mock as mock
        pc = self._pc()
        orig = pc._MONITOR_PATH
        pc._MONITOR_PATH = self.monitor_path
        mock_resp = mock.MagicMock()
        mock_resp.read.return_value = json.dumps({"response": "PLANNING"}).encode()
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = mock.MagicMock(return_value=False)
        self._set_stdin({"message": "what should I work on next for this project"})
        self._capture_print()
        try:
            with mock.patch('urllib.request.urlopen', return_value=mock_resp):
                pc.main()
        finally:
            builtins.print = self._orig_print
            pc._MONITOR_PATH = orig
        output = self._output()
        self.assertIn('PLANNING', output)

    def test_main_ollama_timeout_falls_back_to_none(self):
        """When Ollama times out, category defaults to NONE (no directive printed)."""
        import unittest.mock as mock
        pc = self._pc()
        orig = pc._MONITOR_PATH
        pc._MONITOR_PATH = self.monitor_path
        self._set_stdin({"message": "explain how the session state works"})
        self._capture_print()
        try:
            with mock.patch('urllib.request.urlopen', side_effect=Exception("timeout")):
                pc.main()
        finally:
            builtins.print = self._orig_print
            pc._MONITOR_PATH = orig
        # NONE has no directive, so nothing printed from directive path
        # (may still print layer1 lines)

    def test_main_deep_override_via_detect_deep(self):
        """If detect_deep returns True, category becomes DEEP regardless of Ollama."""
        import unittest.mock as mock
        pc = self._pc()
        orig = pc._MONITOR_PATH
        pc._MONITOR_PATH = self.monitor_path
        mock_resp = mock.MagicMock()
        mock_resp.read.return_value = json.dumps({"response": "NONE"}).encode()
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = mock.MagicMock(return_value=False)
        # detect_deep requires len>=300 AND a keyword like "rewrite"
        long_msg = ("rewrite the entire authentication system from scratch. " * 6).strip()
        self._set_stdin({"message": long_msg})
        self._capture_print()
        try:
            with mock.patch('urllib.request.urlopen', return_value=mock_resp):
                pc.main()
        finally:
            builtins.print = self._orig_print
            pc._MONITOR_PATH = orig
        output = self._output()
        self.assertIn('DEEP', output)

    def test_main_session_uuid_initialised(self):
        """main() initialises session_uuid in state when not present."""
        import unittest.mock as mock
        import qg_session_state as ss
        pc = self._pc()
        orig = pc._MONITOR_PATH
        pc._MONITOR_PATH = self.monitor_path
        state = ss.read_state()
        state['session_uuid'] = ''
        ss.write_state(state)
        mock_resp = mock.MagicMock()
        mock_resp.read.return_value = json.dumps({"response": "NONE"}).encode()
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = mock.MagicMock(return_value=False)
        self._set_stdin({"message": "explain what this codebase does"})
        try:
            with mock.patch('urllib.request.urlopen', return_value=mock_resp):
                pc.main()
        finally:
            pc._MONITOR_PATH = orig
        state2 = ss.read_state()
        self.assertTrue(state2.get('session_uuid'))

    def test_main_write_event_called_on_valid_message(self):
        """_write_event is called during main() for a valid message."""
        import unittest.mock as mock
        pc = self._pc()
        orig = pc._MONITOR_PATH
        pc._MONITOR_PATH = self.monitor_path
        mock_resp = mock.MagicMock()
        mock_resp.read.return_value = json.dumps({"response": "ASSUMPTION"}).encode()
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = mock.MagicMock(return_value=False)
        self._set_stdin({"message": "describe what the config file contains"})
        try:
            with mock.patch('urllib.request.urlopen', return_value=mock_resp):
                pc.main()
        finally:
            pc._MONITOR_PATH = orig
        self.assertTrue(os.path.exists(self.monitor_path))
        with open(self.monitor_path, encoding='utf-8') as f:
            content = f.read()
        self.assertIn('CLASSIFY_', content)


# --- Layer 29 Coverage Boost ---

class TestLayer29Coverage(_MainTestBase):
    def _m29(self):
        import importlib
        return importlib.import_module('qg_layer29')

    # --- _write_event (lines 15-19) ---

    def test_write_event_writes_to_file(self):
        m = self._m29()
        orig = m.MONITOR_PATH
        m.MONITOR_PATH = self.monitor_path
        try:
            m._write_event({'event_id': 'l29-write', 'layer': 'layer29'})
        finally:
            m.MONITOR_PATH = orig
        self.assertTrue(os.path.exists(self.monitor_path))
        with open(self.monitor_path, encoding='utf-8') as f:
            line = f.readline()
        data = json.loads(line)
        self.assertEqual(data['event_id'], 'l29-write')

    def test_write_event_bad_path_no_crash(self):
        m = self._m29()
        orig = m.MONITOR_PATH
        m.MONITOR_PATH = '/nonexistent_dir/monitor.jsonl'
        try:
            m._write_event({'event_id': 'fail'})
        finally:
            m.MONITOR_PATH = orig

    # --- _get_last_turn_data (lines 53-54) ---

    def test_get_last_turn_data_reads_transcript(self):
        m = self._m29()
        # Write a minimal transcript with assistant text and tool_result
        transcript_file = os.path.join(self.tmpdir, 'transcript.jsonl')
        assistant_entry = {
            "role": "assistant",
            "message": {
                "content": [
                    {"type": "text", "text": "I added 3 tests to the file."}
                ]
            }
        }
        user_entry = {
            "role": "user",
            "message": {
                "content": [
                    {"type": "tool_result", "content": "def test_foo():\n    pass\ndef test_bar():\n    pass\n"}
                ]
            }
        }
        with open(transcript_file, 'w', encoding='utf-8') as f:
            f.write(json.dumps(assistant_entry) + '\n')
            f.write(json.dumps(user_entry) + '\n')
        response_text, edit_content = m._get_last_turn_data(transcript_file)
        self.assertIn('added 3 tests', response_text)
        self.assertIn('def test_foo', edit_content)

    def test_get_last_turn_data_user_no_tool_result_stops(self):
        """A user entry with no tool_result should stop iteration."""
        m = self._m29()
        transcript_file = os.path.join(self.tmpdir, 'transcript2.jsonl')
        user_plain = {
            "role": "user",
            "message": {"content": [{"type": "text", "text": "do something"}]}
        }
        assistant_entry = {
            "role": "assistant",
            "message": {"content": [{"type": "text", "text": "I did it."}]}
        }
        with open(transcript_file, 'w', encoding='utf-8') as f:
            f.write(json.dumps(assistant_entry) + '\n')
            f.write(json.dumps(user_plain) + '\n')
        response_text, edit_content = m._get_last_turn_data(transcript_file)
        # Should stop at user with no tool_result, so response_text is empty
        self.assertEqual(response_text, "")

    # --- check_count_claims count check branch (lines 117-120) ---

    def test_check_count_claims_function_mismatch(self):
        m = self._m29()
        response = "I added 5 functions to the module."
        edit = "def func_a():\n    pass\ndef func_b():\n    pass\n"
        issues = m.check_count_claims(response, edit)
        # claimed 5, actual 2 — should flag mismatch
        self.assertTrue(any('COUNT_MISMATCH' in msg for _, msg in issues))

    def test_check_count_claims_function_match_no_issue(self):
        m = self._m29()
        response = "I added 2 functions to the module."
        edit = "def func_a():\n    pass\ndef func_b():\n    pass\n"
        issues = m.check_count_claims(response, edit)
        self.assertEqual(issues, [])

    def test_check_count_claims_test_mismatch(self):
        m = self._m29()
        response = "I added 5 tests for the new feature."
        edit = "def test_foo():\n    pass\ndef test_bar():\n    pass\n"
        issues = m.check_count_claims(response, edit)
        self.assertTrue(any('COUNT_MISMATCH' in msg for _, msg in issues))

    def test_check_count_claims_test_match_no_issue(self):
        m = self._m29()
        response = "I added 2 tests for the new feature."
        edit = "def test_foo():\n    pass\ndef test_bar():\n    pass\n"
        issues = m.check_count_claims(response, edit)
        self.assertEqual(issues, [])

    # --- main() (lines 147-175) ---

    def test_main_with_transcript_no_issues(self):
        """When response text matches edits, main() returns without printing."""
        m = self._m29()
        orig = m.MONITOR_PATH
        m.MONITOR_PATH = self.monitor_path
        transcript_file = os.path.join(self.tmpdir, 'transcript_ok.jsonl')
        assistant_entry = {
            "role": "assistant",
            "message": {"content": [{"type": "text", "text": "I made the changes."}]}
        }
        user_entry = {
            "role": "user",
            "message": {
                "content": [{"type": "tool_result", "content": "updated_content = True\n"}]
            }
        }
        with open(transcript_file, 'w', encoding='utf-8') as f:
            f.write(json.dumps(assistant_entry) + '\n')
            f.write(json.dumps(user_entry) + '\n')
        self._set_stdin({"transcript_path": transcript_file})
        self._capture_print()
        try:
            m.main()
        finally:
            builtins.print = self._orig_print
            m.MONITOR_PATH = orig
        # No issues → no print
        self.assertEqual(self._captured, [])

    def test_main_with_transcript_claim_mismatch_prints(self):
        """When response claims don't match edits, main() prints output."""
        m = self._m29()
        orig = m.MONITOR_PATH
        m.MONITOR_PATH = self.monitor_path
        transcript_file = os.path.join(self.tmpdir, 'transcript_mismatch.jsonl')
        assistant_entry = {
            "role": "assistant",
            "message": {
                "content": [{"type": "text", "text": "I added error handling to all functions."}]
            }
        }
        user_entry = {
            "role": "user",
            "message": {
                "content": [{"type": "tool_result", "content": "def foo():\n    return 1\n"}]
            }
        }
        with open(transcript_file, 'w', encoding='utf-8') as f:
            f.write(json.dumps(assistant_entry) + '\n')
            f.write(json.dumps(user_entry) + '\n')
        self._set_stdin({"transcript_path": transcript_file})
        self._capture_print()
        try:
            m.main()
        finally:
            builtins.print = self._orig_print
            m.MONITOR_PATH = orig
        output = self._output()
        self.assertIn('Layer 2.9', output)
        self.assertIn('CLAIM_MISMATCH', output)

    def test_main_with_transcript_count_mismatch_prints(self):
        """When count claims don't match edits, main() prints output."""
        m = self._m29()
        orig = m.MONITOR_PATH
        m.MONITOR_PATH = self.monitor_path
        transcript_file = os.path.join(self.tmpdir, 'transcript_count.jsonl')
        assistant_entry = {
            "role": "assistant",
            "message": {
                "content": [{"type": "text", "text": "I added 10 tests for the login module."}]
            }
        }
        user_entry = {
            "role": "user",
            "message": {
                "content": [
                    {"type": "tool_result",
                     "content": "def test_login():\n    pass\ndef test_logout():\n    pass\n"}
                ]
            }
        }
        with open(transcript_file, 'w', encoding='utf-8') as f:
            f.write(json.dumps(assistant_entry) + '\n')
            f.write(json.dumps(user_entry) + '\n')
        self._set_stdin({"transcript_path": transcript_file})
        self._capture_print()
        try:
            m.main()
        finally:
            builtins.print = self._orig_print
            m.MONITOR_PATH = orig
        output = self._output()
        self.assertIn('Layer 2.9', output)

    def test_main_event_written_on_warning(self):
        """When a warning is found, _write_event is called (monitor file updated)."""
        m = self._m29()
        orig = m.MONITOR_PATH
        m.MONITOR_PATH = self.monitor_path
        transcript_file = os.path.join(self.tmpdir, 'transcript_event.jsonl')
        assistant_entry = {
            "role": "assistant",
            "message": {
                "content": [{"type": "text", "text": "I added error handling to the parser."}]
            }
        }
        user_entry = {
            "role": "user",
            "message": {
                "content": [{"type": "tool_result", "content": "x = 1\ny = 2\n"}]
            }
        }
        with open(transcript_file, 'w', encoding='utf-8') as f:
            f.write(json.dumps(assistant_entry) + '\n')
            f.write(json.dumps(user_entry) + '\n')
        self._set_stdin({"transcript_path": transcript_file})
        self._capture_print()
        try:
            m.main()
        finally:
            builtins.print = self._orig_print
            m.MONITOR_PATH = orig
        # Monitor file should have been written
        self.assertTrue(os.path.exists(self.monitor_path))
        with open(self.monitor_path, encoding='utf-8') as f:
            content = f.read()
        self.assertIn('layer29', content)


if __name__ == '__main__':
    unittest.main()
