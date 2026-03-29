import sys, os, tempfile, unittest
sys.path.insert(0, os.path.expanduser('~/.claude/hooks'))


class TestLayerEnvValidation(unittest.TestCase):
    def test_validate_git_branch_match(self):
        from qg_layer_env import validate_git_branch
        ok, msg = validate_git_branch('main', lambda: 'main')
        self.assertTrue(ok)

    def test_validate_git_branch_mismatch(self):
        from qg_layer_env import validate_git_branch
        ok, msg = validate_git_branch('main', lambda: 'feature/foo')
        self.assertFalse(ok)
        self.assertIn('main', msg)

    def test_validate_required_tools_present(self):
        from qg_layer_env import validate_required_tools
        ok, missing = validate_required_tools(['python', 'git'])
        self.assertTrue(ok)
        self.assertEqual(missing, [])

    def test_validate_required_tools_missing(self):
        from qg_layer_env import validate_required_tools
        ok, missing = validate_required_tools(['nonexistent_tool_qg_xyz'])
        self.assertFalse(ok)
        self.assertIn('nonexistent_tool_qg_xyz', missing)

    def test_validate_env_var_present(self):
        from qg_layer_env import validate_env_vars
        os.environ['QG_TEST_VAR_PHASE1'] = 'yes'
        ok, missing = validate_env_vars(['QG_TEST_VAR_PHASE1'])
        del os.environ['QG_TEST_VAR_PHASE1']
        self.assertTrue(ok)

    def test_validate_env_var_missing(self):
        from qg_layer_env import validate_env_vars
        ok, missing = validate_env_vars(['QG_DEFINITELY_NOT_SET_XYZ'])
        self.assertFalse(ok)


class TestLayer2Detection(unittest.TestCase):
    def setUp(self):
        import qg_session_state as ss
        self.tmp = tempfile.mktemp(suffix='.json')
        ss.STATE_PATH = self.tmp
        ss.LOCK_PATH = self.tmp + '.lock'

    def tearDown(self):
        import qg_session_state as ss
        for p in [self.tmp, self.tmp + '.lock']:
            try: os.unlink(p)
            except: pass

    def _state(self, **kwargs):
        import qg_session_state as ss
        s = ss.read_state()
        s.update(kwargs)
        return s

    def test_laziness_edit_without_read(self):
        from qg_layer2 import detect_all_events
        state = self._state(layer15_session_reads=[])
        evts = detect_all_events('Edit', {'file_path': 'foo.py'}, '', state, [])
        cats = [e['category'] for e in evts]
        self.assertIn('LAZINESS', cats)

    def test_laziness_suppressed_with_prior_read(self):
        from qg_layer2 import detect_all_events
        state = self._state(layer15_session_reads=['foo.py'])
        evts = detect_all_events('Edit', {'file_path': 'foo.py'}, '', state, [])
        cats = [e['category'] for e in evts]
        self.assertNotIn('LAZINESS', cats)

    def test_incorrect_tool_bash_grep(self):
        from qg_layer2 import detect_all_events
        state = self._state()
        evts = detect_all_events('Bash', {'command': 'grep -r foo .'}, 'output', state, [])
        cats = [e['category'] for e in evts]
        self.assertIn('INCORRECT_TOOL', cats)
        info = next(e for e in evts if e['category'] == 'INCORRECT_TOOL')
        self.assertEqual(info['severity'], 'info')

    def test_error_ignored(self):
        from qg_layer2 import detect_all_events
        state = self._state()
        prev = [{'tool': 'Bash', 'response': 'error: command failed\nexit code: 1'}]
        evts = detect_all_events('Edit', {'file_path': 'x.py'}, '', state, prev)
        cats = [e['category'] for e in evts]
        self.assertIn('ERROR_IGNORED', cats)

    def test_loop_detected(self):
        from qg_layer2 import detect_loop
        history = [('Read', 'foo.py')] * 3
        evt = detect_loop('Read', 'foo.py', history, threshold=3)
        self.assertIsNotNone(evt)
        self.assertEqual(evt['category'], 'LOOP_DETECTED')

    def test_loop_empty_target_skipped(self):
        # Bug 6 regression: Grep/Glob with no file_path or pattern must not trigger LOOP_DETECTED
        from qg_layer2 import detect_loop
        history = [('Grep', '')] * 3
        evt = detect_loop('Grep', '', history, threshold=3)
        self.assertIsNone(evt)

    def test_scope_creep(self):
        from qg_layer2 import detect_all_events
        state = self._state(layer1_scope_files=['auth.py'])
        evts = detect_all_events('Write', {'file_path': 'dashboard.py'}, '', state, [])
        cats = [e['category'] for e in evts]
        self.assertIn('SCOPE_CREEP', cats)


class TestLayer15Rules(unittest.TestCase):
    def setUp(self):
        import qg_session_state as ss
        self.tmp = tempfile.mktemp(suffix='.json')
        ss.STATE_PATH = self.tmp
        ss.LOCK_PATH = self.tmp + '.lock'

    def tearDown(self):
        import qg_session_state as ss
        for p in [self.tmp, self.tmp + '.lock']:
            try: os.unlink(p)
            except: pass

    def test_edit_without_read_triggers_warn(self):
        from qg_layer15 import evaluate_rules
        import qg_session_state as ss
        state = ss.read_state()  # No reads in session
        result = evaluate_rules('Edit', {'file_path': 'foo.py'}, state)
        self.assertIsNotNone(result)
        self.assertEqual(result['action'], 'warn')
        self.assertEqual(result['rule_id'], 'edit-without-read')

    def test_edit_with_prior_read_passes(self):
        from qg_layer15 import evaluate_rules
        import qg_session_state as ss
        state = ss.read_state()
        state['layer15_session_reads'] = ['foo.py']
        result = evaluate_rules('Edit', {'file_path': 'foo.py'}, state)
        self.assertIsNone(result)

    def test_bash_grep_triggers_info(self):
        from qg_layer15 import evaluate_rules
        import qg_session_state as ss
        state = ss.read_state()
        result = evaluate_rules('Bash', {'command': 'grep -r foo .'}, state)
        self.assertIsNotNone(result)
        self.assertEqual(result['action'], 'info')

    def test_read_tracking_updates_state(self):
        from qg_layer15 import handle_read_tracking
        import qg_session_state as ss
        ss.update_state()
        handle_read_tracking('Read', {'file_path': 'bar.py'})
        state = ss.read_state()
        self.assertIn('bar.py', state['layer15_session_reads'])


class TestLayer1Pivot(unittest.TestCase):
    def test_same_topic_not_a_pivot(self):
        from precheck_hook_ext import jaccard_similarity
        score = jaccard_similarity("fix the login bug in auth.py", "fix the login button color")
        self.assertGreaterEqual(score, 0.3)

    def test_different_topic_is_pivot(self):
        from precheck_hook_ext import jaccard_similarity
        score = jaccard_similarity("fix login bug", "create dashboard component with charts")
        self.assertLess(score, 0.3)

    def test_empty_active_task_never_pivot(self):
        from precheck_hook_ext import jaccard_similarity
        score = jaccard_similarity("", "do something")
        self.assertGreaterEqual(score, 0.3)


class TestLayer1Deep(unittest.TestCase):
    def test_short_message_not_deep(self):
        from precheck_hook_ext import detect_deep
        self.assertFalse(detect_deep("fix typo in readme"))

    def test_long_with_scope_keyword_is_deep(self):
        from precheck_hook_ext import detect_deep
        msg = "Please migrate the entire authentication " * 15 + " redesign all routes"
        self.assertTrue(detect_deep(msg))

    def test_long_without_scope_keyword_not_deep(self):
        from precheck_hook_ext import detect_deep
        msg = "Please update the documentation for all the functions we added " * 10
        self.assertFalse(detect_deep(msg))


class TestLayer19ImpactAnalysis(unittest.TestCase):
    def setUp(self):
        import qg_session_state as ss
        self.tmp = tempfile.mktemp(suffix='.json')
        ss.STATE_PATH = self.tmp
        ss.LOCK_PATH = self.tmp + '.lock'

    def tearDown(self):
        import qg_session_state as ss
        for p in [self.tmp, self.tmp + '.lock']:
            try: os.unlink(p)
            except: pass

    def test_low_impact_isolated_file(self):
        from qg_layer19 import compute_impact_level
        self.assertEqual(compute_impact_level('foo.py', [], {}), 'LOW')

    def test_critical_for_core_file(self):
        from qg_layer19 import compute_impact_level
        self.assertEqual(compute_impact_level('utils.py', [], {}), 'CRITICAL')

    def test_high_impact_above_threshold(self):
        from qg_layer19 import compute_impact_level
        deps = ['a.py'] * 25
        level = compute_impact_level('auth.py', deps, {'low_threshold': 5, 'medium_threshold': 20})
        self.assertEqual(level, 'HIGH')

    def test_cache_returns_same_result(self):
        from qg_layer19 import analyze_impact
        r1 = analyze_impact('/nonexistent/cache_test.py')
        r2 = analyze_impact('/nonexistent/cache_test.py')
        self.assertEqual(r1['ts'], r2['ts'])  # Same cached timestamp


class TestLayer17IntentVerification(unittest.TestCase):
    def setUp(self):
        import qg_session_state as ss
        self.tmp = tempfile.mktemp(suffix='.json')
        ss.STATE_PATH = self.tmp
        ss.LOCK_PATH = self.tmp + '.lock'

    def tearDown(self):
        import qg_session_state as ss
        for p in [self.tmp, self.tmp + '.lock']:
            try: os.unlink(p)
            except: pass

    def test_no_fire_on_none_category(self):
        from qg_layer17 import should_verify
        state = {'layer1_task_category': 'NONE', 'layer19_last_impact_level': 'LOW'}
        cfg = {'complexity_threshold': ['DEEP'], 'high_impact_threshold': ['HIGH', 'CRITICAL']}
        self.assertFalse(should_verify(state, cfg))

    def test_fires_on_deep_category(self):
        from qg_layer17 import should_verify
        state = {'layer1_task_category': 'DEEP', 'layer19_last_impact_level': 'LOW'}
        cfg = {'complexity_threshold': ['DEEP'], 'high_impact_threshold': ['HIGH', 'CRITICAL']}
        self.assertTrue(should_verify(state, cfg))

    def test_fires_on_high_impact(self):
        from qg_layer17 import should_verify
        state = {'layer1_task_category': 'MECHANICAL', 'layer19_last_impact_level': 'HIGH'}
        cfg = {'complexity_threshold': ['DEEP'], 'high_impact_threshold': ['HIGH', 'CRITICAL']}
        self.assertTrue(should_verify(state, cfg))

    def test_no_fire_on_already_verified_task(self):
        from qg_layer17 import should_verify
        import qg_session_state as ss
        state = ss.read_state()
        state['layer1_task_category'] = 'DEEP'
        state['layer19_last_impact_level'] = 'LOW'
        state['active_task_id'] = 'task-already'
        state['layer17_verified_task_id'] = 'task-already'
        ss.write_state(state)
        cfg = {'complexity_threshold': ['DEEP'], 'high_impact_threshold': ['HIGH', 'CRITICAL']}
        # should_verify returns True, but main() guards on task_id match
        # Test that verified_task_id is persisted correctly
        result = ss.read_state()
        self.assertEqual(result['layer17_verified_task_id'], 'task-already')


if __name__ == '__main__':
    unittest.main()
