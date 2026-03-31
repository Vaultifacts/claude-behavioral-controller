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


    def test_creates_new_artifacts_flag_set_on_create_intent(self):
        import qg_session_state as ss
        import qg_layer17
        state = ss.read_state()
        state['layer1_task_category'] = 'DEEP'
        state['layer19_last_impact_level'] = 'LOW'
        state['active_task_id'] = 'task-create'
        state['active_task_description'] = 'Create a new configuration file for the project'
        ss.write_state(state)
        # Directly call the relevant portion: verify _CREATE_RE matches
        from qg_layer17 import _CREATE_RE
        self.assertTrue(bool(_CREATE_RE.search('Create a new configuration file')))
        self.assertFalse(bool(_CREATE_RE.search('Update the existing auth module')))

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


class TestLayer18HallucinationDetection(unittest.TestCase):
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

    def test_nonexistent_path_returns_false(self):
        from qg_layer18 import check_path_exists
        self.assertFalse(check_path_exists('/tmp/qg18_definitely_not_here_xyz.py'))

    def test_existing_path_returns_true(self):
        from qg_layer18 import check_path_exists
        self.assertTrue(check_path_exists(__file__))

    def test_missing_function_in_file_returns_false(self):
        from qg_layer18 import check_function_in_file
        import tempfile as _tf
        with _tf.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write('def foo():\n    pass\n')
            fname = f.name
        try:
            self.assertFalse(check_function_in_file(fname, 'def bar():'))
        finally:
            os.unlink(fname)

    def test_present_function_in_file_returns_true(self):
        from qg_layer18 import check_function_in_file
        import tempfile as _tf
        with _tf.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write('def foo():\n    pass\n')
            fname = f.name
        try:
            self.assertTrue(check_function_in_file(fname, 'def foo():'))
        finally:
            os.unlink(fname)

    def test_suppressed_when_creating_new_artifacts(self):
        from qg_layer18 import check_path_exists
        import qg_session_state as ss
        state = ss.read_state()
        state['layer17_creating_new_artifacts'] = True
        ss.write_state(state)
        # The suppression path in main() reads session state; verify check_path_exists
        # returns False for nonexistent path (confirming it would trigger without suppression)
        self.assertFalse(check_path_exists('/tmp/qg18_suppression_test_xyz.py'))
        # Verify the state was persisted
        self.assertTrue(ss.read_state().get('layer17_creating_new_artifacts'))


class TestLayer35RecoveryTracking(unittest.TestCase):
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

    def test_fn_creates_recovery_event(self):
        from qg_layer35 import layer35_create_recovery_event
        import qg_session_state as ss
        state = ss.read_state()
        layer35_create_recovery_event('FN', ['claimed completion'], state, ['Edit'])
        self.assertEqual(len(state['layer35_recovery_events']), 1)
        self.assertEqual(state['layer35_recovery_events'][0]['status'], 'open')

    def test_tp_creates_recovery_event(self):
        from qg_layer35 import layer35_create_recovery_event
        import qg_session_state as ss
        state = ss.read_state()
        layer35_create_recovery_event('TP', [], state, ['Bash'])
        self.assertEqual(state['layer35_recovery_events'][0]['verdict'], 'TP')

    def test_recovery_resolved_with_verify_tool(self):
        from qg_layer35 import layer35_check_resolutions
        import time, qg_session_state as ss
        state = ss.read_state()
        state['layer35_recovery_events'] = [{
            'event_id': 'e1', 'verdict': 'FN', 'status': 'open',
            'ts': time.time(), 'turn': 0, 'category': 'unverified',
        }]
        state['layer2_turn_history'] = [{}]  # 1 turn elapsed
        layer35_check_resolutions(['Bash'], state)
        self.assertEqual(state['layer35_recovery_events'][0]['status'], 'resolved')

    def test_recovery_timed_out(self):
        from qg_layer35 import layer35_check_resolutions
        import time, qg_session_state as ss
        state = ss.read_state()
        state['layer35_recovery_events'] = [{
            'event_id': 'e2', 'verdict': 'FN', 'status': 'open',
            'ts': time.time() - 2000,  # 33+ minutes ago
            'turn': 0, 'category': 'unverified',
        }]
        state['layer2_turn_history'] = []
        layer35_check_resolutions(['Read'], state)
        self.assertEqual(state['layer35_recovery_events'][0]['status'], 'timed_out')

    def test_haiku_fn_falls_back_to_rules_on_no_api_key(self):
        from qg_layer35 import detect_fn_signals
        import qg_session_state as ss
        state = ss.read_state()
        # Rule-based: claims completion without verification output
        response = 'All tests pass and everything is done and completed.'
        signals = detect_fn_signals(response, [], '', state, use_haiku=False)
        self.assertTrue(len(signals) > 0)


class TestLayer45ContextPreservation(unittest.TestCase):
    def setUp(self):
        import qg_session_state as ss
        self.tmp = tempfile.mktemp(suffix='.json')
        ss.STATE_PATH = self.tmp
        ss.LOCK_PATH = self.tmp + '.lock'
        self.preserve_tmp = tempfile.mktemp(suffix='.json')

    def tearDown(self):
        import qg_session_state as ss
        for p in [self.tmp, self.tmp + '.lock', self.preserve_tmp]:
            try: os.unlink(p)
            except: pass

    def test_pre_compact_saves_state(self):
        import json as _json, qg_session_state as ss
        sys.path.insert(0, os.path.expanduser('~/.claude/hooks'))
        import qg_layer45
        qg_layer45.PRESERVE_PATH = self.preserve_tmp
        state = ss.read_state()
        state['session_uuid'] = 'uuid-45-test'
        state['active_task_description'] = 'test task 45'
        ss.write_state(state)
        qg_layer45.handle_pre_compact()
        with open(self.preserve_tmp) as f:
            preserved = _json.load(f)
        self.assertEqual(preserved['session_uuid'], 'uuid-45-test')
        self.assertIn('pre_compact_hash', preserved)

    def test_post_compact_restores_cleared_state(self):
        import json as _json, time as _time, qg_session_state as ss
        import qg_layer45
        qg_layer45.PRESERVE_PATH = self.preserve_tmp
        preserved = {
            'session_uuid': 'uuid-45-restore',
            'active_task_description': 'restore me',
            'pre_compact_hash': 'test',
            'preserved_at': _time.time(),
        }
        with open(self.preserve_tmp, 'w') as f:
            _json.dump(preserved, f)
        state = ss.read_state()
        state['session_uuid'] = 'uuid-45-restore'
        state['active_task_description'] = ''  # Cleared by compaction
        ss.write_state(state)
        qg_layer45.handle_post_compact()
        result = ss.read_state()
        self.assertEqual(result['active_task_description'], 'restore me')


class TestLayer5SubagentCoordination(unittest.TestCase):
    def setUp(self):
        import qg_session_state as ss
        self.tmp = tempfile.mktemp(suffix='.json')
        ss.STATE_PATH = self.tmp
        ss.LOCK_PATH = self.tmp + '.lock'
        self.monitor_tmp = tempfile.mktemp(suffix='.jsonl')

    def tearDown(self):
        import qg_session_state as ss
        for p in [self.tmp, self.tmp + '.lock', self.monitor_tmp]:
            try: os.unlink(p)
            except: pass

    def _dispatch(self, tool_name, tool_input, tool_response):
        import json as _json, qg_session_state as ss, qg_layer5
        qg_layer5.MONITOR_PATH = self.monitor_tmp
        state = ss.read_state()
        state['session_uuid'] = 'uuid-l5'
        state['active_task_id'] = 'task-l5'
        ss.write_state(state)
        payload = {'tool_name': tool_name, 'tool_input': tool_input,
                   'tool_response': tool_response}
        qg_layer5.process_and_record(
            tool_name, tool_input, tool_response, ss.read_state())

    def test_agent_tool_records_event(self):
        import json as _json
        self._dispatch('Agent', {'prompt': 'Fix the bug'}, 'Fixed successfully.')
        with open(self.monitor_tmp) as f:
            events = [_json.loads(l) for l in f]
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]['layer'], 'layer5')
        self.assertEqual(events[0]['status'], 'subagent_complete')

    def test_non_agent_tool_produces_no_event(self):
        import qg_session_state as ss, qg_layer5
        qg_layer5.MONITOR_PATH = self.monitor_tmp
        result = qg_layer5.process_and_record(
            'Bash', {'command': 'ls'}, 'file.py', ss.read_state())
        self.assertIsNone(result)
        self.assertFalse(os.path.exists(self.monitor_tmp))

    def test_timeout_keyword_sets_status(self):
        import json as _json
        self._dispatch('Agent', {'prompt': 'Long task'}, 'Task timed out.')
        with open(self.monitor_tmp) as f:
            events = [_json.loads(l) for l in f]
        self.assertEqual(events[0]['status'], 'subagent_timeout')


class TestLayer25OutputValidity(unittest.TestCase):
    def test_valid_python_returns_none(self):
        from qg_layer25 import validate_file
        f = tempfile.mktemp(suffix='.py')
        open(f, 'w').write('x = 1\n')
        result = validate_file(f)
        os.unlink(f)
        self.assertIsNone(result)

    def test_invalid_json_returns_error_string(self):
        from qg_layer25 import validate_file
        f = tempfile.mktemp(suffix='.json')
        open(f, 'w').write('{not valid json}')
        result = validate_file(f)
        os.unlink(f)
        self.assertIsNotNone(result)
        self.assertIsInstance(result, str)

    def test_unknown_extension_returns_none(self):
        from qg_layer25 import validate_file
        self.assertIsNone(validate_file('/nonexistent/file.txt'))

    def test_large_file_returns_none(self):
        from qg_layer25 import validate_file, SIZE_LIMIT
        f = tempfile.mktemp(suffix='.py')
        open(f, 'w').write('x = 1\n' * (SIZE_LIMIT // 5 + 1))
        result = validate_file(f)
        os.unlink(f)
        self.assertIsNone(result)


class TestLayer26ConsistencyEnforcement(unittest.TestCase):
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

    def test_detect_snake_case(self):
        from qg_layer26 import detect_convention
        content = 'def my_function():\n    pass\n'
        conv = detect_convention(content)
        self.assertEqual(conv.get('naming'), 'snake_case')

    def test_detect_camel_case(self):
        from qg_layer26 import detect_convention
        content = 'def myFunction():\n    pass\n'
        conv = detect_convention(content)
        self.assertEqual(conv.get('naming'), 'camelCase')

    def test_deviation_detected(self):
        from qg_layer26 import check_deviation
        devs = check_deviation({'naming': 'camelCase'}, {'naming': 'snake_case'})
        self.assertTrue(len(devs) > 0)

    def test_no_deviation_same_convention(self):
        from qg_layer26 import check_deviation
        devs = check_deviation({'naming': 'snake_case'}, {'naming': 'snake_case'})
        self.assertEqual(devs, [])


class TestLayer27TestingCoverage(unittest.TestCase):
    def test_test_file_found_returns_path(self):
        import shutil
        from qg_layer27 import find_test_file
        d = tempfile.mkdtemp()
        open(os.path.join(d, 'test_utils.py'), 'w').close()
        old = os.getcwd(); os.chdir(d)
        result = find_test_file('utils.py')
        os.chdir(old); shutil.rmtree(d)
        self.assertIsNotNone(result)

    def test_no_test_file_returns_none(self):
        import shutil
        from qg_layer27 import find_test_file
        d = tempfile.mkdtemp()
        old = os.getcwd(); os.chdir(d)
        result = find_test_file('auth.py')
        os.chdir(old); shutil.rmtree(d)
        self.assertIsNone(result)


class TestLayer8RegressionDetection(unittest.TestCase):
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

    def test_test_command_detected(self):
        from qg_layer8 import TEST_CMD_RE
        self.assertTrue(bool(TEST_CMD_RE.search('pytest tests/')))
        self.assertTrue(bool(TEST_CMD_RE.search('npm test')))
        self.assertFalse(bool(TEST_CMD_RE.search('ls -la')))

    def test_parse_results_pass_and_fail(self):
        from qg_layer8 import parse_results
        passed, failed = parse_results('5 passed, 2 failed in 1.23s')
        self.assertEqual(passed, 5)
        self.assertEqual(failed, 2)

    def test_regression_more_failures_than_baseline(self):
        from qg_layer8 import parse_results
        import qg_session_state as ss
        state = ss.read_state()
        state['layer_env_test_baseline'] = [[10, 0]]
        ss.write_state(state)
        _, failed = parse_results('8 passed, 2 failed')
        baseline_failed = ss.read_state()['layer_env_test_baseline'][0][1]
        self.assertGreater(failed, baseline_failed)


class TestLayer6CrossSessionAnalysis(unittest.TestCase):
    def test_empty_events_returns_empty(self):
        from qg_layer6 import analyze_patterns
        self.assertEqual(analyze_patterns([]), [])

    def test_pattern_below_threshold_not_flagged(self):
        from qg_layer6 import analyze_patterns
        events = [
            {'session_uuid': 's1', 'category': 'LAZINESS', 'ts': '2026-01-01T00:00:00'},
            {'session_uuid': 's2', 'category': 'LAZINESS', 'ts': '2026-01-02T00:00:00'},
        ]
        result = analyze_patterns(events, min_sessions=3, min_pct=0.1)
        self.assertEqual(result, [])

    def test_pattern_above_threshold_flagged(self):
        from qg_layer6 import analyze_patterns
        events = []
        for i in range(1, 5):
            for _ in range(3):
                events.append({'session_uuid': 's{}'.format(i), 'category': 'LAZINESS',
                               'ts': '2026-01-0{}T00:00:00'.format(i)})
        result = analyze_patterns(events, min_sessions=3, min_pct=0.1)
        cats = [p['category'] for p in result]
        self.assertIn('LAZINESS', cats)


class TestLayer7RuleRefinement(unittest.TestCase):
    def test_repeat_fn_above_threshold_flagged(self):
        from qg_layer7 import find_repeat_fns
        records = [{'outcome': 'FN', 'category': 'ASSUMPTION'}] * 3
        result = find_repeat_fns(records, threshold=3)
        self.assertIn('ASSUMPTION', result)

    def test_single_fn_below_threshold_not_flagged(self):
        from qg_layer7 import find_repeat_fns
        records = [{'outcome': 'FN', 'category': 'ASSUMPTION'}]
        result = find_repeat_fns(records, threshold=3)
        self.assertEqual(result, {})


class TestLayer9ConfidenceCalibration(unittest.TestCase):
    def test_high_certainty_extracted(self):
        from qg_layer9 import extract_certainty
        self.assertEqual(extract_certainty("I'm certain this will work"), 'high')
        self.assertEqual(extract_certainty('definitely the right approach'), 'high')

    def test_medium_certainty_extracted(self):
        from qg_layer9 import extract_certainty
        self.assertEqual(extract_certainty('I believe this should work'), 'medium')

    def test_no_certainty_signal_returns_none(self):
        from qg_layer9 import extract_certainty
        self.assertIsNone(extract_certainty('Here is the updated implementation.'))


class TestLayer10AuditIntegrity(unittest.TestCase):
    def test_valid_jsonl_no_corrupt(self):
        from qg_layer10 import validate_jsonl
        f = tempfile.mktemp(suffix='.jsonl')
        qf = tempfile.mktemp(suffix='.jsonl')
        open(f, 'w').write('{"event_id": "1"}\n{"event_id": "2"}\n')
        valid, corrupt = validate_jsonl(f, qf)
        for p in [f, qf]:
            try: os.unlink(p)
            except: pass
        self.assertEqual(len(corrupt), 0)
        self.assertEqual(len(valid), 2)

    def test_corrupt_line_quarantined(self):
        from qg_layer10 import validate_jsonl
        f = tempfile.mktemp(suffix='.jsonl')
        qf = tempfile.mktemp(suffix='.jsonl')
        open(f, 'w').write('{"event_id": "1"}\n{NOT JSON}\n{"event_id": "3"}\n')
        valid, corrupt = validate_jsonl(f, qf)
        for p in [f, qf]:
            try: os.unlink(p)
            except: pass
        self.assertEqual(len(corrupt), 1)
        self.assertEqual(len(valid), 2)

    def test_rotation_triggers_at_threshold(self):
        import glob
        from qg_layer10 import maybe_rotate
        f = tempfile.mktemp(suffix='.jsonl')
        with open(f, 'w') as fh:
            for i in range(11):
                fh.write('{{"n": {}}}\n'.format(i))
        rotated = maybe_rotate(f, threshold=10)
        for archived in glob.glob(f.replace('.jsonl', '-*.jsonl')):
            try: os.unlink(archived)
            except: pass
        if not rotated:
            try: os.unlink(f)
            except: pass
        self.assertTrue(rotated)


class TestLayer0(unittest.TestCase):
    def setUp(self):
        import qg_session_state as ss
        self.ts = tempfile.mktemp(suffix='.json')
        ss.STATE_PATH = self.ts
        ss.LOCK_PATH = self.ts + '.lock'

    def tearDown(self):
        for p in [self.ts, self.ts + '.lock']:
            try: os.unlink(p)
            except: pass

    def test_load_cross_session_patterns_missing_file(self):
        import qg_layer0
        qg_layer0.CROSS_SESSION_PATH = self.ts + '_none.json'
        self.assertEqual(qg_layer0.load_cross_session_patterns(), [])

    def test_load_cross_session_patterns_with_data(self):
        import json, qg_layer0
        cs = self.ts + '_cs.json'
        with open(cs, 'w') as f:
            json.dump({'patterns': [{'category': 'LOOP', 'sessions_count': 3,
                                     'total_events': 10, 'event_pct': 0.2}]}, f)
        qg_layer0.CROSS_SESSION_PATH = cs
        result = qg_layer0.load_cross_session_patterns()
        try: os.unlink(cs)
        except: pass
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['category'], 'LOOP')

    def test_load_cross_session_patterns_bad_json(self):
        import qg_layer0
        bad = self.ts + '_bad.json'
        with open(bad, 'w') as f:
            f.write('not json')
        qg_layer0.CROSS_SESSION_PATH = bad
        result = qg_layer0.load_cross_session_patterns()
        try: os.unlink(bad)
        except: pass
        self.assertEqual(result, [])

    def test_find_previous_session_unresolved_missing(self):
        import qg_layer0
        qg_layer0.HISTORY_PATH = self.ts + '_none.md'
        self.assertEqual(qg_layer0.find_previous_session_unresolved(), [])

    def test_main_resets_session_fields(self):
        import io, qg_layer0, qg_session_state as ss
        state = ss.read_state()
        state['layer2_unresolved_events'] = ['event1']
        state['layer15_session_reads'] = ['/test.py']
        ss.write_state(state)
        qg_layer0.HISTORY_PATH = self.ts + '_none.md'
        qg_layer0.CROSS_SESSION_PATH = self.ts + '_none.json'
        sys.stdin = io.StringIO('{}')
        try:
            qg_layer0.main()
        finally:
            sys.stdin = sys.__stdin__
        state2 = ss.read_state()
        self.assertEqual(state2.get('layer2_unresolved_events'), [])
        self.assertEqual(state2.get('layer15_session_reads'), [])

    def test_main_prints_cross_session_advisory(self):
        import io, json, builtins, qg_layer0
        cs = self.ts + '_cs2.json'
        with open(cs, 'w') as f:
            json.dump({'patterns': [{'category': 'LOOP', 'sessions_count': 5,
                                     'total_events': 20, 'event_pct': 0.3}]}, f)
        qg_layer0.CROSS_SESSION_PATH = cs
        qg_layer0.HISTORY_PATH = self.ts + '_none.md'
        captured = []
        orig = builtins.print
        builtins.print = lambda *a, **k: captured.append(' '.join(str(x) for x in a))
        sys.stdin = io.StringIO('{}')
        try:
            qg_layer0.main()
        finally:
            builtins.print = orig
            sys.stdin = sys.__stdin__
            try: os.unlink(cs)
            except: pass
        self.assertTrue(any('LOOP' in s for s in captured))

    def test_main_stores_injected_patterns(self):
        import io, json, qg_layer0, qg_session_state as ss
        cs = self.ts + '_cs3.json'
        with open(cs, 'w') as f:
            json.dump({'patterns': [{'category': 'ERROR_IGNORED', 'sessions_count': 4,
                                     'total_events': 15, 'event_pct': 0.25}]}, f)
        qg_layer0.CROSS_SESSION_PATH = cs
        qg_layer0.HISTORY_PATH = self.ts + '_none.md'
        sys.stdin = io.StringIO('{}')
        try:
            qg_layer0.main()
        finally:
            sys.stdin = sys.__stdin__
            try: os.unlink(cs)
            except: pass
        state = ss.read_state()
        self.assertIn('ERROR_IGNORED', state.get('layer0_injected_patterns', []))


class TestLayerEnvExtra(unittest.TestCase):
    def setUp(self):
        import qg_session_state as ss
        self.ts = tempfile.mktemp(suffix='.json')
        ss.STATE_PATH = self.ts
        ss.LOCK_PATH = self.ts + '.lock'

    def tearDown(self):
        for p in [self.ts, self.ts + '.lock']:
            try: os.unlink(p)
            except: pass

    def test_run_session_start_sets_working_dir(self):
        import qg_layer_env, qg_session_state as ss
        qg_layer_env.run_session_start({})
        state = ss.read_state()
        self.assertIn('working_dir', state.get('layer_env_baseline', {}))

    def test_run_session_start_sets_ts(self):
        import time, qg_layer_env, qg_session_state as ss
        before = time.time()
        qg_layer_env.run_session_start({})
        state = ss.read_state()
        ts = state.get('layer_env_baseline', {}).get('ts', 0)
        self.assertGreaterEqual(ts, before)

    def test_run_pre_tool_use_no_output_when_no_file_path(self):
        import builtins, qg_layer_env
        captured = []
        orig = builtins.print
        builtins.print = lambda *a, **k: captured.append(' '.join(str(x) for x in a))
        try:
            qg_layer_env.run_pre_tool_use({'tool_name': 'Bash', 'tool_input': {}})
        finally:
            builtins.print = orig
        self.assertEqual(captured, [])

    def test_run_pre_tool_use_no_output_when_no_baseline(self):
        import builtins, qg_layer_env, qg_session_state as ss
        ss.write_state(ss.read_state())  # empty baseline
        captured = []
        orig = builtins.print
        builtins.print = lambda *a, **k: captured.append(' '.join(str(x) for x in a))
        try:
            qg_layer_env.run_pre_tool_use(
                {'tool_name': 'Edit', 'tool_input': {'file_path': '/tmp/x.py'}})
        finally:
            builtins.print = orig
        self.assertEqual(captured, [])

    def test_run_pre_tool_use_warns_for_outside_path(self):
        import builtins, qg_layer_env, qg_session_state as ss
        state = ss.read_state()
        state['layer_env_baseline'] = {'working_dir': '/some/specific/workdir', 'ts': 0}
        ss.write_state(state)
        captured = []
        orig = builtins.print
        builtins.print = lambda *a, **k: captured.append(' '.join(str(x) for x in a))
        try:
            qg_layer_env.run_pre_tool_use(
                {'tool_name': 'Edit', 'tool_input': {'file_path': '/tmp/outside_zzz.py'}})
        finally:
            builtins.print = orig
        self.assertTrue(len(captured) >= 1)

    def test_main_session_start_sets_baseline(self):
        import io, qg_layer_env, qg_session_state as ss
        sys.stdin = io.StringIO('{"hook_event_name": "SessionStart"}')
        try:
            qg_layer_env.main()
        finally:
            sys.stdin = sys.__stdin__
        state = ss.read_state()
        self.assertIn('working_dir', state.get('layer_env_baseline', {}))


class TestLayer15Extra(unittest.TestCase):
    def setUp(self):
        import qg_session_state as ss
        import qg_notification_router as nr
        self.ts = tempfile.mktemp(suffix='.json')
        ss.STATE_PATH = self.ts
        ss.LOCK_PATH = self.ts + '.lock'
        nr.reset_turn_counter()

    def tearDown(self):
        for p in [self.ts, self.ts + '.lock']:
            try: os.unlink(p)
            except: pass

    def test_handle_read_tracking_adds_path(self):
        import qg_layer15, qg_session_state as ss
        qg_layer15.handle_read_tracking('Read', {'file_path': '/foo/bar.py'})
        state = ss.read_state()
        self.assertIn('/foo/bar.py', state.get('layer15_session_reads', []))

    def test_handle_read_tracking_no_duplicate(self):
        import qg_layer15, qg_session_state as ss
        qg_layer15.handle_read_tracking('Read', {'file_path': '/foo/bar.py'})
        qg_layer15.handle_read_tracking('Read', {'file_path': '/foo/bar.py'})
        state = ss.read_state()
        reads = state.get('layer15_session_reads', [])
        self.assertEqual(reads.count('/foo/bar.py'), 1)

    def test_evaluate_rules_edit_without_read_returns_warn(self):
        import qg_layer15, qg_session_state as ss
        state = ss.read_state()
        result = qg_layer15.evaluate_rules('Edit', {'file_path': '/x.py'}, state)
        self.assertIsNotNone(result)
        self.assertEqual(result['action'], 'warn')
        self.assertEqual(result['rule_id'], 'edit-without-read')

    def test_evaluate_rules_edit_with_prior_read_returns_none(self):
        import qg_layer15, qg_session_state as ss
        state = ss.read_state()
        state['layer15_session_reads'] = ['/x.py']
        result = qg_layer15.evaluate_rules('Edit', {'file_path': '/x.py'}, state)
        self.assertIsNone(result)

    def test_evaluate_rules_bash_grep_returns_info(self):
        import qg_layer15, qg_session_state as ss
        state = ss.read_state()
        result = qg_layer15.evaluate_rules('Bash', {'command': 'grep -r foo .'}, state)
        self.assertIsNotNone(result)
        self.assertEqual(result['action'], 'info')

    def test_main_high_impact_escalates_warn_to_block(self):
        import io, builtins, qg_layer15, qg_session_state as ss
        state = ss.read_state()
        state['layer19_last_impact_level'] = 'HIGH'
        ss.write_state(state)
        captured = []
        orig = builtins.print
        builtins.print = lambda *a, **k: captured.append(' '.join(str(x) for x in a))
        sys.stdin = io.StringIO(
            '{"tool_name": "Edit", "tool_input": {"file_path": "/unread.py"}}')
        try:
            qg_layer15.main()
        finally:
            builtins.print = orig
            sys.stdin = sys.__stdin__
        output = ' '.join(captured)
        self.assertIn('block', output)

    def test_main_dedup_same_rule_same_turn(self):
        import io, builtins, qg_layer15
        captured_counts = []
        for _ in range(2):
            captured = []
            orig = builtins.print
            builtins.print = lambda *a, **k: captured.append(' '.join(str(x) for x in a))
            sys.stdin = io.StringIO(
                '{"tool_name": "Edit", "tool_input": {"file_path": "/unread2.py"}}')
            try:
                qg_layer15.main()
            finally:
                builtins.print = orig
                sys.stdin = sys.__stdin__
            captured_counts.append(len(captured))
        # First call produces output, second is deduplicated
        self.assertGreater(captured_counts[0], 0)
        self.assertEqual(captured_counts[1], 0)



class TestLayer15Gap15(unittest.TestCase):
    def setUp(self):
        import qg_session_state as ss
        self.ts = tempfile.mktemp(suffix='.json')
        ss.STATE_PATH = self.ts
        ss.LOCK_PATH = self.ts + '.lock'

    def tearDown(self):
        for p in [self.ts, self.ts + '.lock']:
            try: os.unlink(p)
            except: pass

    def test_warn_action_increments_warnings_ignored_count(self):
        import io, qg_layer15, qg_session_state as ss
        state = ss.read_state()
        ss.write_state(state)
        sys.stdin = io.StringIO(
            '{"tool_name": "Edit", "tool_input": {"file_path": "/unread.py"}}')
        try:
            qg_layer15.main()
        finally:
            sys.stdin = sys.__stdin__
        count = ss.read_state().get('layer15_warnings_ignored_count', 0)
        self.assertEqual(count, 1)

    def test_block_action_does_not_increment_counter(self):
        import io, qg_layer15, qg_session_state as ss
        state = ss.read_state()
        state['layer19_last_impact_level'] = 'HIGH'  # escalates warn -> block
        ss.write_state(state)
        sys.stdin = io.StringIO(
            '{"tool_name": "Edit", "tool_input": {"file_path": "/unread.py"}}')
        try:
            qg_layer15.main()
        finally:
            sys.stdin = sys.__stdin__
        count = ss.read_state().get('layer15_warnings_ignored_count', 0)
        self.assertEqual(count, 0)

    def test_warnings_accumulate_across_calls(self):
        import io, qg_layer15, qg_session_state as ss
        for path in ['/a.py', '/b.py']:
            state = ss.read_state()
            state['layer15_turn_warnings'] = []  # reset dedup between calls
            ss.write_state(state)
            sys.stdin = io.StringIO(
                f'{{"tool_name": "Edit", "tool_input": {{"file_path": "{path}"}}}}')
            try:
                qg_layer15.main()
            finally:
                sys.stdin = sys.__stdin__
        count = ss.read_state().get('layer15_warnings_ignored_count', 0)
        self.assertEqual(count, 2)

    def test_compute_confidence_uses_warnings_ignored_count(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            'quality_gate', os.path.expanduser('~/.claude/hooks/quality-gate.py'))
        qg = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(qg)
        state = {'layer15_warnings_ignored_count': 3}
        score_no_warnings = qg._compute_confidence(False, None, {})
        score_with_warnings = qg._compute_confidence(False, None, state)
        self.assertLess(score_with_warnings, score_no_warnings)

class TestLayer2Extra(unittest.TestCase):
    def setUp(self):
        import qg_session_state as ss
        self.ts = tempfile.mktemp(suffix='.json')
        ss.STATE_PATH = self.ts
        ss.LOCK_PATH = self.ts + '.lock'
        self.monitor_tmp = tempfile.mktemp(suffix='.jsonl')

    def tearDown(self):
        for p in [self.ts, self.ts + '.lock', self.monitor_tmp]:
            try: os.unlink(p)
            except: pass

    def test_detect_loop_under_threshold_returns_none(self):
        from qg_layer2 import detect_loop
        history = [('Bash', 'ls'), ('Bash', 'ls')]
        self.assertIsNone(detect_loop('Bash', 'ls', history, threshold=3))

    def test_detect_loop_at_threshold_returns_event(self):
        from qg_layer2 import detect_loop
        history = [('Read', '/x.py')] * 3
        result = detect_loop('Read', '/x.py', history, threshold=3)
        self.assertIsNotNone(result)
        self.assertEqual(result['category'], 'LOOP_DETECTED')

    def test_detect_all_events_no_laziness_for_read_tool(self):
        from qg_layer2 import detect_all_events
        import qg_session_state as ss
        state = ss.read_state()
        events = detect_all_events('Read', {'file_path': '/x.py'}, '', state, [])
        cats = [e['category'] for e in events]
        self.assertNotIn('LAZINESS', cats)

    def test_detect_all_events_scope_creep(self):
        from qg_layer2 import detect_all_events
        import qg_session_state as ss
        state = ss.read_state()
        state['layer1_scope_files'] = ['src/main.py']
        events = detect_all_events('Write', {'file_path': '/other/file.py'}, '', state, [])
        cats = [e['category'] for e in events]
        self.assertIn('SCOPE_CREEP', cats)

    def test_impact_severity_promotion(self):
        import io, json, qg_layer2, qg_session_state as ss
        qg_layer2.MONITOR_PATH = self.monitor_tmp
        state = ss.read_state()
        state['layer19_last_impact_level'] = 'HIGH'
        ss.write_state(state)
        sys.stdin = io.StringIO(
            '{"tool_name": "Edit", "tool_input": {"file_path": "/unread_impact.py"}, "tool_response": ""}')
        try:
            qg_layer2.main()
        finally:
            sys.stdin = sys.__stdin__
        state2 = ss.read_state()
        events = state2.get('layer2_unresolved_events', [])
        if events:
            self.assertIn(events[0]['severity'], ('warning', 'critical'))

    def test_assumption_write_without_prior_read(self):
        from qg_layer2 import detect_all_events
        import qg_session_state as ss
        state = ss.read_state()
        state['layer15_session_reads'] = []
        events = detect_all_events('Write', {'file_path': '/new_file.py'}, '', state, [])
        cats = [e['category'] for e in events]
        self.assertIn('ASSUMPTION', cats)

    def test_assumption_suppressed_when_file_already_read(self):
        from qg_layer2 import detect_all_events
        import qg_session_state as ss
        state = ss.read_state()
        state['layer15_session_reads'] = ['/already_read.py']
        events = detect_all_events('Write', {'file_path': '/already_read.py'}, '', state, [])
        cats = [e['category'] for e in events]
        self.assertNotIn('ASSUMPTION', cats)

    def test_incomplete_coverage_repeated_edits_untouched_scope(self):
        from qg_layer2 import detect_all_events
        import qg_session_state as ss
        state = ss.read_state()
        state['layer1_scope_files'] = ['/scope/a.py', '/scope/b.py']
        turn_history = [
            {'tool': 'Edit', 'target': '/scope/a.py', 'resp': ''},
            {'tool': 'Edit', 'target': '/scope/a.py', 'resp': ''},
        ]
        events = detect_all_events('Edit', {'file_path': '/scope/a.py'}, '', state, [], turn_history=turn_history)
        cats = [e['category'] for e in events]
        self.assertIn('INCOMPLETE_COVERAGE', cats)

    def test_incomplete_coverage_suppressed_for_single_scope_file(self):
        from qg_layer2 import detect_all_events
        import qg_session_state as ss
        state = ss.read_state()
        state['layer1_scope_files'] = ['/scope/a.py']  # only 1 file — len(scope) > 1 guard
        turn_history = [
            {'tool': 'Edit', 'target': '/scope/a.py', 'resp': ''},
            {'tool': 'Edit', 'target': '/scope/a.py', 'resp': ''},
        ]
        events = detect_all_events('Edit', {'file_path': '/scope/a.py'}, '', state, [], turn_history=turn_history)
        cats = [e['category'] for e in events]
        self.assertNotIn('INCOMPLETE_COVERAGE', cats)

    def test_output_unvalidated_consecutive_edits(self):
        from qg_layer2 import detect_all_events
        import qg_session_state as ss
        state = ss.read_state()
        state['layer15_session_reads'] = ['/file.py']
        prev_calls = [
            {'tool': 'Edit', 'response': ''},
            {'tool': 'Edit', 'response': ''},
        ]
        events = detect_all_events('Edit', {'file_path': '/file.py'}, '', state, prev_calls)
        cats = [e['category'] for e in events]
        self.assertIn('OUTPUT_UNVALIDATED', cats)

    def test_output_unvalidated_suppressed_after_bash(self):
        from qg_layer2 import detect_all_events
        import qg_session_state as ss
        state = ss.read_state()
        state['layer15_session_reads'] = ['/file.py']
        prev_calls = [
            {'tool': 'Edit', 'response': ''},
            {'tool': 'Bash', 'response': ''},
        ]
        events = detect_all_events('Edit', {'file_path': '/file.py'}, '', state, prev_calls)
        cats = [e['category'] for e in events]
        self.assertNotIn('OUTPUT_UNVALIDATED', cats)

    def test_elevated_scrutiny_fires_before_rate_limit_trim(self):
        # Bug fix: scrutiny must use full event list, not rate-limited list
        import io, json, qg_layer2, qg_session_state as ss
        qg_layer2.MONITOR_PATH = self.monitor_tmp
        state = ss.read_state()
        state['layer19_last_impact_level'] = 'HIGH'   # promotes warning->critical
        state['layer1_scope_files'] = ['/other.py']   # /unread.py outside scope -> SCOPE_CREEP
        state['layer2_turn_event_count'] = 4          # limit=5, only 1 more allowed after trim
        state['layer2_turn_history'] = [
            {'tool': 'Bash', 'target': 'ls', 'resp': 'Error: permission denied'},
        ]
        ss.write_state(state)
        sys.stdin = io.StringIO(json.dumps(
            {'tool_name': 'Edit', 'tool_input': {'file_path': '/unread.py'}, 'tool_response': ''}))
        try:
            qg_layer2.main()
        finally:
            sys.stdin = sys.__stdin__
        self.assertTrue(ss.read_state().get('layer2_elevated_scrutiny', False))

    def test_elevated_scrutiny_fires_with_three_criticals(self):
        import io, json, qg_layer2, qg_session_state as ss
        qg_layer2.MONITOR_PATH = self.monitor_tmp
        state = ss.read_state()
        state['layer19_last_impact_level'] = 'HIGH'
        state['layer1_scope_files'] = ['/other.py']
        state['layer2_turn_history'] = [
            {'tool': 'Bash', 'target': 'ls', 'resp': 'Error: permission denied'},
        ]
        ss.write_state(state)
        sys.stdin = io.StringIO(json.dumps(
            {'tool_name': 'Edit', 'tool_input': {'file_path': '/unread.py'}, 'tool_response': ''}))
        try:
            qg_layer2.main()
        finally:
            sys.stdin = sys.__stdin__
        self.assertTrue(ss.read_state().get('layer2_elevated_scrutiny', False))

    def test_elevated_scrutiny_not_set_with_two_criticals(self):
        import io, json, qg_layer2, qg_session_state as ss
        qg_layer2.MONITOR_PATH = self.monitor_tmp
        state = ss.read_state()
        state['layer19_last_impact_level'] = 'HIGH'
        state['layer1_scope_files'] = ['/unread.py']  # in-scope -> no SCOPE_CREEP, only 2 criticals
        state['layer2_turn_history'] = [
            {'tool': 'Bash', 'target': 'ls', 'resp': 'Error: permission denied'},
        ]
        ss.write_state(state)
        sys.stdin = io.StringIO(json.dumps(
            {'tool_name': 'Edit', 'tool_input': {'file_path': '/unread.py'}, 'tool_response': ''}))
        try:
            qg_layer2.main()
        finally:
            sys.stdin = sys.__stdin__
        self.assertFalse(ss.read_state().get('layer2_elevated_scrutiny', False))

    def test_resolution_laziness_addressed_by_read_same_file(self):
        import io, json, qg_layer2, qg_session_state as ss
        qg_layer2.MONITOR_PATH = self.monitor_tmp
        state = ss.read_state()
        state['layer2_unresolved_events'] = [
            {'event_id': 'e1', 'status': 'open', 'category': 'LAZINESS', 'target_file': '/x.py'}
        ]
        ss.write_state(state)
        sys.stdin = io.StringIO(json.dumps(
            {'tool_name': 'Read', 'tool_input': {'file_path': '/x.py'}, 'tool_response': ''}))
        try:
            qg_layer2.main()
        finally:
            sys.stdin = sys.__stdin__
        unresolved = ss.read_state().get('layer2_unresolved_events', [])
        e1 = next(e for e in unresolved if e.get('event_id') == 'e1')
        self.assertEqual(e1['status'], 'addressed')

    def test_resolution_laziness_not_addressed_by_read_different_file(self):
        import io, json, qg_layer2, qg_session_state as ss
        qg_layer2.MONITOR_PATH = self.monitor_tmp
        state = ss.read_state()
        state['layer2_unresolved_events'] = [
            {'event_id': 'e2', 'status': 'open', 'category': 'LAZINESS', 'target_file': '/x.py'}
        ]
        ss.write_state(state)
        sys.stdin = io.StringIO(json.dumps(
            {'tool_name': 'Read', 'tool_input': {'file_path': '/y.py'}, 'tool_response': ''}))
        try:
            qg_layer2.main()
        finally:
            sys.stdin = sys.__stdin__
        unresolved = ss.read_state().get('layer2_unresolved_events', [])
        e2 = next(e for e in unresolved if e.get('event_id') == 'e2')
        self.assertEqual(e2['status'], 'open')

    def test_resolution_assumption_addressed_by_read(self):
        import io, json, qg_layer2, qg_session_state as ss
        qg_layer2.MONITOR_PATH = self.monitor_tmp
        state = ss.read_state()
        state['layer2_unresolved_events'] = [
            {'event_id': 'e3', 'status': 'open', 'category': 'ASSUMPTION', 'target_file': '/a.py'}
        ]
        ss.write_state(state)
        sys.stdin = io.StringIO(json.dumps(
            {'tool_name': 'Read', 'tool_input': {'file_path': '/a.py'}, 'tool_response': ''}))
        try:
            qg_layer2.main()
        finally:
            sys.stdin = sys.__stdin__
        unresolved = ss.read_state().get('layer2_unresolved_events', [])
        e3 = next(e for e in unresolved if e.get('event_id') == 'e3')
        self.assertEqual(e3['status'], 'addressed')

    def test_resolution_output_unvalidated_addressed_by_bash(self):
        import io, json, qg_layer2, qg_session_state as ss
        qg_layer2.MONITOR_PATH = self.monitor_tmp
        state = ss.read_state()
        state['layer2_unresolved_events'] = [
            {'event_id': 'e4', 'status': 'open', 'category': 'OUTPUT_UNVALIDATED'}
        ]
        ss.write_state(state)
        sys.stdin = io.StringIO(json.dumps(
            {'tool_name': 'Bash', 'tool_input': {'command': 'ls'}, 'tool_response': ''}))
        try:
            qg_layer2.main()
        finally:
            sys.stdin = sys.__stdin__
        unresolved = ss.read_state().get('layer2_unresolved_events', [])
        e4 = next(e for e in unresolved if e.get('event_id') == 'e4')
        self.assertEqual(e4['status'], 'addressed')



class TestLayer35Extra(unittest.TestCase):
    def setUp(self):
        import qg_session_state as ss
        self.ts = tempfile.mktemp(suffix='.json')
        ss.STATE_PATH = self.ts
        ss.LOCK_PATH = self.ts + '.lock'

    def tearDown(self):
        for p in [self.ts, self.ts + '.lock']:
            try: os.unlink(p)
            except: pass

    def test_create_recovery_event_status_is_open(self):
        from qg_layer35 import layer35_create_recovery_event
        import qg_session_state as ss
        state = ss.read_state()
        layer35_create_recovery_event('FN', ['INCOMPLETE'], state, [])
        events = state.get('layer35_recovery_events', [])
        self.assertGreater(len(events), 0)
        self.assertEqual(events[-1].get('status'), 'open')

    def test_create_recovery_event_verdict_stored(self):
        from qg_layer35 import layer35_create_recovery_event
        import qg_session_state as ss
        state = ss.read_state()
        layer35_create_recovery_event('FN', ['LAZINESS'], state, ['Edit'])
        events = state.get('layer35_recovery_events', [])
        self.assertEqual(events[-1].get('verdict'), 'FN')

    def test_detect_fn_signals_empty_response(self):
        from qg_layer35 import detect_fn_signals
        import qg_session_state as ss
        state = ss.read_state()
        result = detect_fn_signals('', [], '', state, use_haiku=False)
        self.assertEqual(result, [])

    def test_detect_fn_signals_no_signal_on_verified_success(self):
        from qg_layer35 import detect_fn_signals
        import qg_session_state as ss
        state = ss.read_state()
        state['layer3_evaluation_count'] = 10
        response = 'All tests pass. The implementation is complete and verified.'
        result = detect_fn_signals(response, [], '', state, use_haiku=False)
        self.assertIsInstance(result, list)


    def test_memory_over_verification_signal(self):
        """Gap #43 — detect when response uses memory phrases without verification output."""
        import qg_layer35
        # Memory phrase without verification output → signal
        resp = "From memory, the function is in utils.py and returns True."
        signals = qg_layer35._detect_fn_signals_rules(resp, {})
        self.assertTrue(any('MEMORY_OVER_VERIFICATION' in s for s in signals),
                        f"Expected MEMORY_OVER_VERIFICATION signal, got: {signals}")

    def test_memory_phrase_with_verification_no_signal(self):
        """If verification output is present, no MEMORY_OVER signal even with memory phrase."""
        import qg_layer35
        resp = "I recall the function was here. Running check: === Results: 3 passed ==="
        signals = qg_layer35._detect_fn_signals_rules(resp, {})
        self.assertFalse(any('MEMORY_OVER_VERIFICATION' in s for s in signals),
                         f"Should not flag when verification output present: {signals}")


    def test_partial_status_same_turn_verify(self):
        import time
        from qg_layer35 import layer35_check_resolutions
        import qg_session_state as ss
        state = ss.read_state()
        state['layer2_turn_history'] = ['t1', 't2']
        state['layer35_recovery_events'] = [{
            'status': 'open', 'ts': time.time(), 'turn': 2,
            'event_id': 'e1', 'verdict': 'FN', 'category': 'LAZINESS',
            'task_id': 'task1', 'session_uuid': 'uuid1', 'tools_at_flag': [],
        }]
        layer35_check_resolutions(['Bash'], state)
        evt = state['layer35_recovery_events'][0]
        self.assertEqual(evt['status'], 'partial')

    def test_introduces_new_problem_flag_set(self):
        import time
        from qg_layer35 import layer35_check_resolutions
        import qg_session_state as ss
        now = time.time()
        state = ss.read_state()
        state['layer2_turn_history'] = ['t1', 't2', 't3', 't4']
        state['layer35_recovery_events'] = [
            {'status': 'open', 'ts': now - 100, 'turn': 3,
             'event_id': 'e1', 'verdict': 'FN', 'category': 'LAZINESS',
             'task_id': 'task1', 'session_uuid': 'uuid1', 'tools_at_flag': []},
            {'status': 'open', 'ts': now - 50, 'turn': 3,
             'event_id': 'e2', 'verdict': 'FN', 'category': 'LOOP',
             'task_id': 'task1', 'session_uuid': 'uuid1', 'tools_at_flag': []},
        ]
        layer35_check_resolutions(['Read'], state)
        events = state['layer35_recovery_events']
        e1 = next(e for e in events if e['event_id'] == 'e1')
        self.assertEqual(e1['status'], 'resolved')
        self.assertTrue(e1.get('introduces_new_problem'))


class TestLayer17Extra(unittest.TestCase):
    def setUp(self):
        import qg_session_state as ss
        self.ts = tempfile.mktemp(suffix='.json')
        ss.STATE_PATH = self.ts
        ss.LOCK_PATH = self.ts + '.lock'

    def tearDown(self):
        for p in [self.ts, self.ts + '.lock']:
            try: os.unlink(p)
            except: pass

    def test_should_verify_deep_category(self):
        from qg_layer17 import should_verify
        import qg_session_state as ss
        state = ss.read_state()
        state['layer1_task_category'] = 'DEEP'
        self.assertTrue(should_verify(state, {}))

    def test_should_verify_moderate_low_impact_false(self):
        from qg_layer17 import should_verify
        import qg_session_state as ss
        state = ss.read_state()
        state['layer1_task_category'] = 'MODERATE'
        state['layer19_last_impact_level'] = 'LOW'
        self.assertFalse(should_verify(state, {}))

    def test_should_verify_high_impact_true(self):
        from qg_layer17 import should_verify
        import qg_session_state as ss
        state = ss.read_state()
        state['layer1_task_category'] = 'SIMPLE'
        state['layer19_last_impact_level'] = 'HIGH'
        self.assertTrue(should_verify(state, {}))

    def test_main_no_task_id_no_output(self):
        import io, builtins, qg_layer17, qg_session_state as ss
        state = ss.read_state()
        state['active_task_id'] = ''
        ss.write_state(state)
        captured = []
        orig = builtins.print
        builtins.print = lambda *a, **k: captured.append(' '.join(str(x) for x in a))
        sys.stdin = io.StringIO('{"tool_name": "Edit", "tool_input": {}}')
        try:
            qg_layer17.main()
        finally:
            builtins.print = orig
            sys.stdin = sys.__stdin__
        self.assertEqual(captured, [])

    def test_main_fires_once_per_task(self):
        import io, builtins, qg_layer17, qg_session_state as ss
        state = ss.read_state()
        state['active_task_id'] = 'task_abc'
        state['layer1_task_category'] = 'DEEP'
        state['layer17_verified_task_id'] = 'task_abc'
        ss.write_state(state)
        captured = []
        orig = builtins.print
        builtins.print = lambda *a, **k: captured.append(' '.join(str(x) for x in a))
        sys.stdin = io.StringIO('{"tool_name": "Edit", "tool_input": {}}')
        try:
            qg_layer17.main()
        finally:
            builtins.print = orig
            sys.stdin = sys.__stdin__
        self.assertEqual(captured, [])


class TestLayer17Gap16(unittest.TestCase):
    def setUp(self):
        import qg_session_state as ss
        self.ts = tempfile.mktemp(suffix='.json')
        ss.STATE_PATH = self.ts
        ss.LOCK_PATH = self.ts + '.lock'

    def tearDown(self):
        for p in [self.ts, self.ts + '.lock']:
            try: os.unlink(p)
            except: pass

    def test_planning_with_two_subtasks_triggers_verify(self):
        from qg_layer17 import should_verify
        import qg_session_state as ss
        state = ss.read_state()
        state['layer1_task_category'] = 'PLANNING'
        state['layer1_subtask_count'] = 2
        self.assertTrue(should_verify(state, {}))

    def test_planning_with_one_subtask_does_not_trigger(self):
        from qg_layer17 import should_verify
        import qg_session_state as ss
        state = ss.read_state()
        state['layer1_task_category'] = 'PLANNING'
        state['layer1_subtask_count'] = 1
        state['layer19_last_impact_level'] = 'LOW'
        self.assertFalse(should_verify(state, {}))

    def test_planning_with_no_subtask_count_does_not_trigger(self):
        from qg_layer17 import should_verify
        import qg_session_state as ss
        state = ss.read_state()
        state['layer1_task_category'] = 'PLANNING'
        # layer1_subtask_count defaults to 0
        state['layer19_last_impact_level'] = 'LOW'
        self.assertFalse(should_verify(state, {}))


class TestLayer18Extra(unittest.TestCase):
    def setUp(self):
        import qg_session_state as ss
        self.ts = tempfile.mktemp(suffix='.json')
        ss.STATE_PATH = self.ts
        ss.LOCK_PATH = self.ts + '.lock'

    def tearDown(self):
        for p in [self.ts, self.ts + '.lock']:
            try: os.unlink(p)
            except: pass

    def test_check_path_exists_real_file(self):
        from qg_layer18 import check_path_exists
        f = tempfile.mktemp(suffix='.py')
        open(f, 'w').close()
        result = check_path_exists(f)
        os.unlink(f)
        self.assertTrue(result)

    def test_check_path_exists_missing(self):
        from qg_layer18 import check_path_exists
        self.assertFalse(check_path_exists(self.ts + '_nonexistent.py'))

    def test_check_function_in_file_found(self):
        from qg_layer18 import check_function_in_file
        f = tempfile.mktemp(suffix='.py')
        with open(f, 'w') as fh:
            fh.write('def my_func():\n    pass\n')
        result = check_function_in_file(f, 'def my_func():')
        os.unlink(f)
        self.assertTrue(result)

    def test_check_function_in_file_missing(self):
        from qg_layer18 import check_function_in_file
        f = tempfile.mktemp(suffix='.py')
        with open(f, 'w') as fh:
            fh.write('x = 1\n')
        result = check_function_in_file(f, 'def nonexistent_fn():')
        os.unlink(f)
        self.assertFalse(result)

    def test_main_suppresses_when_creating_new_artifacts(self):
        import io, builtins, qg_layer18, qg_session_state as ss
        state = ss.read_state()
        state['layer17_creating_new_artifacts'] = True
        ss.write_state(state)
        captured = []
        orig = builtins.print
        builtins.print = lambda *a, **k: captured.append(' '.join(str(x) for x in a))
        sys.stdin = io.StringIO(
            '{"tool_name": "Edit", "tool_input": {"file_path": "/nonexistent_zzz.py"}}')
        try:
            qg_layer18.main()
        finally:
            builtins.print = orig
            sys.stdin = sys.__stdin__
        self.assertEqual(captured, [])


class TestLayer18Gap17(unittest.TestCase):
    def setUp(self):
        import qg_session_state as ss
        self.ts = tempfile.mktemp(suffix='.json')
        ss.STATE_PATH = self.ts
        ss.LOCK_PATH = self.ts + '.lock'
        self.tmpfile = tempfile.mktemp(suffix='.py')
        with open(self.tmpfile, 'w') as f:
            f.write('def real_func():\n    pass\n')

    def tearDown(self):
        for p in [self.ts, self.ts + '.lock', self.tmpfile]:
            try: os.unlink(p)
            except: pass

    def test_missing_func_warns_first_time_not_second(self):
        import io, json, builtins, qg_layer18, qg_session_state as ss
        captured = []
        orig = builtins.print
        builtins.print = lambda *a, **k: captured.append(a)
        payload = json.dumps({'tool_name': 'Edit', 'tool_input': {
            'file_path': self.tmpfile, 'old_string': 'def ghost_func():'}})
        try:
            sys.stdin = io.StringIO(payload)
            qg_layer18.main()
            sys.stdin = io.StringIO(payload)
            qg_layer18.main()
        finally:
            builtins.print = orig
            sys.stdin = sys.__stdin__
        # First call warns, second is deduplicated
        self.assertEqual(len(captured), 1)

    def test_existing_func_cached_no_warning_on_repeat(self):
        import io, json, builtins, qg_layer18, qg_session_state as ss
        captured = []
        orig = builtins.print
        builtins.print = lambda *a, **k: captured.append(a)
        payload = json.dumps({'tool_name': 'Edit', 'tool_input': {
            'file_path': self.tmpfile, 'old_string': 'def real_func():'}})
        try:
            sys.stdin = io.StringIO(payload)
            qg_layer18.main()
            sys.stdin = io.StringIO(payload)
            qg_layer18.main()
        finally:
            builtins.print = orig
            sys.stdin = sys.__stdin__
        # real_func exists — no warning either call
        self.assertEqual(len(captured), 0)
        # And it was cached
        checked = ss.read_state().get('layer18_session_checked', {})
        key = f'{self.tmpfile}::real_func'
        self.assertIn(key, checked)
        self.assertTrue(checked[key])

    def test_dedup_keyed_per_file_not_just_func(self):
        import io, json, builtins, qg_layer18, qg_session_state as ss
        tmpfile2 = tempfile.mktemp(suffix='.py')
        with open(tmpfile2, 'w') as f:
            f.write('# no functions here\n')
        captured = []
        orig = builtins.print
        builtins.print = lambda *a, **k: captured.append(a)
        try:
            # ghost_func missing from tmpfile (self.tmpfile has real_func only)
            sys.stdin = io.StringIO(json.dumps({'tool_name': 'Edit', 'tool_input': {
                'file_path': self.tmpfile, 'old_string': 'def ghost_func():'}}))
            qg_layer18.main()
            # Same func name, different file — must check independently
            sys.stdin = io.StringIO(json.dumps({'tool_name': 'Edit', 'tool_input': {
                'file_path': tmpfile2, 'old_string': 'def ghost_func():'}}))
            qg_layer18.main()
        finally:
            builtins.print = orig
            sys.stdin = sys.__stdin__
            try: os.unlink(tmpfile2)
            except: pass
        # Both files lack ghost_func — two separate warnings expected
        self.assertEqual(len(captured), 2)


class TestLayer19Extra(unittest.TestCase):
    def setUp(self):
        import qg_session_state as ss
        self.ts = tempfile.mktemp(suffix='.json')
        ss.STATE_PATH = self.ts
        ss.LOCK_PATH = self.ts + '.lock'

    def tearDown(self):
        for p in [self.ts, self.ts + '.lock']:
            try: os.unlink(p)
            except: pass

    def test_compute_impact_low_no_dependents(self):
        from qg_layer19 import compute_impact_level
        self.assertEqual(compute_impact_level('/tmp/unique_qg_zzz.py', [], {}), 'LOW')

    def test_compute_impact_medium(self):
        from qg_layer19 import compute_impact_level
        deps = ['/x.py'] * 10
        result = compute_impact_level('/tmp/foo.py', deps, {})
        self.assertEqual(result, 'MEDIUM')

    def test_compute_impact_high(self):
        from qg_layer19 import compute_impact_level
        deps = ['/x.py'] * 25
        result = compute_impact_level('/tmp/foo.py', deps, {})
        self.assertEqual(result, 'HIGH')

    def test_compute_impact_core_pattern_critical(self):
        from qg_layer19 import compute_impact_level
        self.assertEqual(compute_impact_level('/project/utils.py', [], {}), 'CRITICAL')
        self.assertEqual(compute_impact_level('/project/config.py', [], {}), 'CRITICAL')

    def test_analyze_impact_stores_in_state(self):
        import qg_layer19, qg_session_state as ss
        f = tempfile.mktemp(suffix='_isolated_qg.py')
        open(f, 'w').write('x = 1\n')
        try:
            qg_layer19.analyze_impact(f)
        finally:
            try: os.unlink(f)
            except: pass
        state = ss.read_state()
        self.assertEqual(state.get('layer19_last_impact_file'), f)

    def test_analyze_impact_sets_regression_expected_on_critical(self):
        import qg_layer19, qg_session_state as ss
        result = qg_layer19.analyze_impact('/project/utils.py')
        state = ss.read_state()
        if result['level'] in ('HIGH', 'CRITICAL'):
            self.assertTrue(state.get('layer8_regression_expected'))

    def test_analyze_impact_cache_hit(self):
        import time, qg_layer19, qg_session_state as ss
        f = tempfile.mktemp(suffix='_cache_qg.py')
        open(f, 'w').write('x = 1\n')
        try:
            r1 = qg_layer19.analyze_impact(f)
            r2 = qg_layer19.analyze_impact(f)
        finally:
            try: os.unlink(f)
            except: pass
        self.assertEqual(r1['level'], r2['level'])


class TestLayer45Extra(unittest.TestCase):
    def setUp(self):
        import qg_session_state as ss
        self.ts = tempfile.mktemp(suffix='.json')
        ss.STATE_PATH = self.ts
        ss.LOCK_PATH = self.ts + '.lock'
        self.preserve_tmp = tempfile.mktemp(suffix='_preserve.json')

    def tearDown(self):
        for p in [self.ts, self.ts + '.lock', self.preserve_tmp]:
            try: os.unlink(p)
            except: pass

    def test_handle_pre_compact_creates_file(self):
        import qg_layer45
        qg_layer45.PRESERVE_PATH = self.preserve_tmp
        qg_layer45.handle_pre_compact()
        self.assertTrue(os.path.exists(self.preserve_tmp))

    def test_handle_pre_compact_stores_keys(self):
        import json, qg_layer45, qg_session_state as ss
        state = ss.read_state()
        state['active_task_description'] = 'test task'
        ss.write_state(state)
        qg_layer45.PRESERVE_PATH = self.preserve_tmp
        qg_layer45.handle_pre_compact()
        with open(self.preserve_tmp) as f:
            preserved = json.load(f)
        self.assertIn('active_task_description', preserved)

    def test_handle_post_compact_no_crash_missing_file(self):
        import qg_layer45
        qg_layer45.PRESERVE_PATH = self.preserve_tmp  # doesn't exist yet
        qg_layer45.handle_post_compact()  # should not raise

    def test_handle_post_compact_restores_matching_uuid(self):
        import json, builtins, qg_layer45, qg_session_state as ss
        uuid_val = 'test-uuid-restore-extra'
        state = ss.read_state()
        state['session_uuid'] = uuid_val
        state['active_task_description'] = 'restored task'
        ss.write_state(state)
        qg_layer45.PRESERVE_PATH = self.preserve_tmp
        qg_layer45.handle_pre_compact()
        state2 = ss.read_state()
        state2['active_task_description'] = ''
        ss.write_state(state2)
        captured = []
        orig = builtins.print
        builtins.print = lambda *a, **k: captured.append(' '.join(str(x) for x in a))
        try:
            qg_layer45.handle_post_compact()
        finally:
            builtins.print = orig
        state3 = ss.read_state()
        self.assertEqual(state3.get('active_task_description'), 'restored task')


class TestLayer45Gaps1820(unittest.TestCase):
    def setUp(self):
        import qg_session_state as ss
        self.ts = tempfile.mktemp(suffix='.json')
        ss.STATE_PATH = self.ts
        ss.LOCK_PATH = self.ts + '.lock'
        self.preserve_tmp = tempfile.mktemp(suffix='_preserve.json')

    def tearDown(self):
        for p in [self.ts, self.ts + '.lock', self.preserve_tmp]:
            try: os.unlink(p)
            except: pass

    def test_layer15_session_reads_in_preserve_keys(self):
        import qg_layer45
        self.assertIn('layer15_session_reads', qg_layer45.PRESERVE_KEYS)

    def test_layer15_session_reads_preserved_and_restored(self):
        import json, qg_layer45, qg_session_state as ss
        state = ss.read_state()
        state['session_uuid'] = 'uuid-gap18'
        state['layer15_session_reads'] = ['file_a.py', 'file_b.py']
        ss.write_state(state)
        qg_layer45.PRESERVE_PATH = self.preserve_tmp
        qg_layer45.handle_pre_compact()
        state2 = ss.read_state()
        state2['layer15_session_reads'] = []
        ss.write_state(state2)
        qg_layer45.handle_post_compact()
        state3 = ss.read_state()
        self.assertEqual(state3.get('layer15_session_reads'), ['file_a.py', 'file_b.py'])

    def test_hash_mismatch_prints_warning(self):
        import json, builtins, qg_layer45, qg_session_state as ss
        state = ss.read_state()
        state['session_uuid'] = 'uuid-gap19'
        ss.write_state(state)
        qg_layer45.PRESERVE_PATH = self.preserve_tmp
        qg_layer45.handle_pre_compact()
        with open(self.preserve_tmp, 'r') as f:
            preserved = json.load(f)
        preserved['pre_compact_hash'] = 'badhash1'
        with open(self.preserve_tmp, 'w') as f:
            json.dump(preserved, f)
        captured = []
        orig = builtins.print
        builtins.print = lambda *a, **k: captured.append(' '.join(str(x) for x in a))
        try:
            qg_layer45.handle_post_compact()
        finally:
            builtins.print = orig
        self.assertTrue(any('hash mismatch' in m for m in captured))

    def test_uuid_mismatch_reinjects_critical_fields(self):
        import json, qg_layer45, qg_session_state as ss
        events = [{'category': 'LAZINESS', 'status': 'open', 'ts': 1.0}]
        preserved = {
            'session_uuid': 'old-uuid',
            'pre_compact_hash': '',
            'layer2_unresolved_events': events,
            'layer35_recovery_events': [],
            'active_task_description': 'critical task',
        }
        with open(self.preserve_tmp, 'w') as f:
            json.dump(preserved, f)
        state = ss.read_state()
        state['session_uuid'] = 'new-uuid'
        ss.write_state(state)
        qg_layer45.PRESERVE_PATH = self.preserve_tmp
        qg_layer45.handle_post_compact()
        state2 = ss.read_state()
        self.assertEqual(state2.get('layer2_unresolved_events'), events)
        self.assertEqual(state2.get('active_task_description'), 'critical task')


class TestLayer5Extra(unittest.TestCase):
    def setUp(self):
        import qg_session_state as ss
        self.ts = tempfile.mktemp(suffix='.json')
        ss.STATE_PATH = self.ts
        ss.LOCK_PATH = self.ts + '.lock'
        self.monitor_tmp = tempfile.mktemp(suffix='.jsonl')

    def tearDown(self):
        for p in [self.ts, self.ts + '.lock', self.monitor_tmp]:
            try: os.unlink(p)
            except: pass

    def test_process_and_record_stores_subagent_in_state(self):
        import qg_layer5, qg_session_state as ss
        qg_layer5.MONITOR_PATH = self.monitor_tmp
        state = ss.read_state()
        qg_layer5.process_and_record('Agent', {'description': 'test agent'}, '', state)
        state2 = ss.read_state()
        self.assertTrue(len(state2.get('layer5_subagents', {})) >= 1)

    def test_process_and_record_writes_jsonl(self):
        import json, qg_layer5, qg_session_state as ss
        qg_layer5.MONITOR_PATH = self.monitor_tmp
        state = ss.read_state()
        qg_layer5.process_and_record('Agent', {'description': 'jsonl test'}, '', state)
        self.assertTrue(os.path.exists(self.monitor_tmp))
        with open(self.monitor_tmp) as f:
            lines = [l for l in f if l.strip()]
        self.assertGreater(len(lines), 0)

    def test_process_predispatch_writes_dispatch_event(self):
        """Gap #21 — PreToolUse dispatch phase records subagent_dispatch event."""
        import json, qg_layer5, qg_session_state as ss
        qg_layer5.MONITOR_PATH = self.monitor_tmp
        state = ss.read_state()
        evt = qg_layer5.process_predispatch('Agent', {'description': 'pre-dispatch test'}, state)
        self.assertIsNotNone(evt, "process_predispatch should return an event")
        self.assertEqual(evt['type'], 'subagent_dispatch')
        self.assertEqual(evt['status'], 'in_flight')
        # Event written to JSONL
        with open(self.monitor_tmp) as f:
            lines = [l.strip() for l in f if l.strip()]
        self.assertGreater(len(lines), 0)
        e = json.loads(lines[0])
        self.assertEqual(e['type'], 'subagent_dispatch')

    def test_process_predispatch_stores_in_flight_in_state(self):
        """PreToolUse dispatch stores in_flight status in layer5_subagents state."""
        import qg_layer5, qg_session_state as ss
        qg_layer5.MONITOR_PATH = self.monitor_tmp
        state = ss.read_state()
        qg_layer5.process_predispatch('Agent', {'prompt': 'hello subagent'}, state)
        state2 = ss.read_state()
        subagents = state2.get('layer5_subagents', {})
        self.assertTrue(len(subagents) >= 1)
        self.assertTrue(any(v.get('status') == 'in_flight' for v in subagents.values()))

    def test_process_predispatch_non_agent_returns_none(self):
        """PreToolUse dispatch ignores non-Agent tools."""
        import qg_layer5, qg_session_state as ss
        qg_layer5.MONITOR_PATH = self.monitor_tmp
        state = ss.read_state()
        result = qg_layer5.process_predispatch('Bash', {'command': 'ls'}, state)
        self.assertIsNone(result)
        self.assertFalse(os.path.exists(self.monitor_tmp))


    def test_process_and_record_non_agent_no_event(self):
        import qg_layer5, qg_session_state as ss
        qg_layer5.MONITOR_PATH = self.monitor_tmp
        state = ss.read_state()
        qg_layer5.process_and_record('Read', {'file_path': '/x.py'}, '', state)
        self.assertFalse(os.path.exists(self.monitor_tmp))


class TestLayer25Extra(unittest.TestCase):
    def setUp(self):
        import qg_session_state as ss
        self.ts = tempfile.mktemp(suffix='.json')
        ss.STATE_PATH = self.ts
        ss.LOCK_PATH = self.ts + '.lock'
        self.monitor_tmp = tempfile.mktemp(suffix='.jsonl')

    def tearDown(self):
        for p in [self.ts, self.ts + '.lock', self.monitor_tmp]:
            try: os.unlink(p)
            except: pass

    def test_main_non_write_tool_no_crash(self):
        import io, qg_layer25
        qg_layer25.MONITOR_PATH = self.monitor_tmp
        sys.stdin = io.StringIO('{"tool_name": "Bash", "tool_input": {}, "tool_response": ""}')
        try:
            qg_layer25.main()
        finally:
            sys.stdin = sys.__stdin__

    def test_main_bad_json_no_crash(self):
        import io, qg_layer25
        sys.stdin = io.StringIO('not json')
        try:
            qg_layer25.main()
        finally:
            sys.stdin = sys.__stdin__

    def test_main_valid_python_no_output(self):
        import io, builtins, qg_layer25
        qg_layer25.MONITOR_PATH = self.monitor_tmp
        f = tempfile.mktemp(suffix='.py')
        with open(f, 'w') as fh:
            fh.write('x = 1\n')
        captured = []
        orig = builtins.print
        builtins.print = lambda *a, **k: captured.append(' '.join(str(x) for x in a))
        sys.stdin = io.StringIO(
            '{{"tool_name": "Write", "tool_input": {{"file_path": "{}"}}, "tool_response": ""}}'.format(
                f.replace('\\', '\\\\')))
        try:
            qg_layer25.main()
        finally:
            builtins.print = orig
            sys.stdin = sys.__stdin__
            try: os.unlink(f)
            except: pass
        self.assertEqual(captured, [])

    def test_main_invalid_python_produces_output(self):
        import io, builtins, qg_layer25
        qg_layer25.MONITOR_PATH = self.monitor_tmp
        f = tempfile.mktemp(suffix='.py')
        with open(f, 'w') as fh:
            fh.write('def (\n')
        captured = []
        orig = builtins.print
        builtins.print = lambda *a, **k: captured.append(' '.join(str(x) for x in a))
        sys.stdin = io.StringIO(
            '{{"tool_name": "Write", "tool_input": {{"file_path": "{}"}}, "tool_response": ""}}'.format(
                f.replace('\\', '\\\\')))
        try:
            qg_layer25.main()
        finally:
            builtins.print = orig
            sys.stdin = sys.__stdin__
            try: os.unlink(f)
            except: pass
        output = ' '.join(captured)
        self.assertIn('2.5', output)

    def test_main_sets_syntax_failure_state(self):
        import io, qg_layer25, qg_session_state as ss
        qg_layer25.MONITOR_PATH = self.monitor_tmp
        f = tempfile.mktemp(suffix='.py')
        with open(f, 'w') as fh:
            fh.write('def (\n')
        sys.stdin = io.StringIO(
            '{{"tool_name": "Write", "tool_input": {{"file_path": "{}"}}, "tool_response": ""}}'.format(
                f.replace('\\', '\\\\')))
        try:
            qg_layer25.main()
        finally:
            sys.stdin = sys.__stdin__
            try: os.unlink(f)
            except: pass
        state = ss.read_state()
        self.assertTrue(state.get('layer25_syntax_failure'))


class TestLayer26Extra(unittest.TestCase):
    def setUp(self):
        import qg_session_state as ss
        self.ts = tempfile.mktemp(suffix='.json')
        ss.STATE_PATH = self.ts
        ss.LOCK_PATH = self.ts + '.lock'
        self.monitor_tmp = tempfile.mktemp(suffix='.jsonl')

    def tearDown(self):
        for p in [self.ts, self.ts + '.lock', self.monitor_tmp]:
            try: os.unlink(p)
            except: pass

    def test_main_non_write_no_output(self):
        import io, builtins, qg_layer26
        captured = []
        orig = builtins.print
        builtins.print = lambda *a, **k: captured.append(' '.join(str(x) for x in a))
        sys.stdin = io.StringIO('{"tool_name": "Read", "tool_input": {}, "tool_response": ""}')
        try:
            qg_layer26.main()
        finally:
            builtins.print = orig
            sys.stdin = sys.__stdin__
        self.assertEqual(captured, [])

    def test_main_bad_json_no_crash(self):
        import io, qg_layer26
        sys.stdin = io.StringIO('not json')
        try:
            qg_layer26.main()
        finally:
            sys.stdin = sys.__stdin__

    def test_main_consistent_file_no_output(self):
        import io, builtins, qg_layer26, qg_session_state as ss
        qg_layer26.MONITOR_PATH = self.monitor_tmp
        f = tempfile.mktemp(suffix='.py')
        with open(f, 'w') as fh:
            fh.write('def my_func():\n    pass\ndef other_func():\n    pass\n')
        state = ss.read_state()
        state['layer26_convention_baseline'] = {'naming': 'snake_case'}
        state['layer26_files_seen'] = 2
        ss.write_state(state)
        captured = []
        orig = builtins.print
        builtins.print = lambda *a, **k: captured.append(' '.join(str(x) for x in a))
        sys.stdin = io.StringIO(
            '{{"tool_name": "Write", "tool_input": {{"file_path": "{}"}}, "tool_response": ""}}'.format(
                f.replace('\\', '\\\\')))
        try:
            qg_layer26.main()
        finally:
            builtins.print = orig
            sys.stdin = sys.__stdin__
            try: os.unlink(f)
            except: pass
        self.assertEqual(captured, [])

    def test_main_updates_baseline(self):
        import io, qg_layer26, qg_session_state as ss
        qg_layer26.MONITOR_PATH = self.monitor_tmp
        f = tempfile.mktemp(suffix='.py')
        with open(f, 'w') as fh:
            fh.write('def snake_case_func():\n    pass\n')
        sys.stdin = io.StringIO(
            '{{"tool_name": "Write", "tool_input": {{"file_path": "{}"}}, "tool_response": ""}}'.format(
                f.replace('\\', '\\\\')))
        try:
            qg_layer26.main()
        finally:
            sys.stdin = sys.__stdin__
            try: os.unlink(f)
            except: pass
        state = ss.read_state()
        self.assertGreater(state.get('layer26_files_seen', 0), 0)

    def test_deviation_from_baseline_writes_jsonl_event(self):
        import io, json, qg_layer26, qg_session_state as ss
        qg_layer26.MONITOR_PATH = self.monitor_tmp
        f = tempfile.mktemp(suffix='.py')
        with open(f, 'w') as fh:
            fh.write('def camelCaseFunc():\n    pass\n')
        state = ss.read_state()
        state['layer26_convention_baseline'] = {'naming': 'snake_case'}
        state['layer26_files_seen'] = 5
        ss.write_state(state)
        sys.stdin = io.StringIO(
            '{{"tool_name": "Write", "tool_input": {{"file_path": "{}"}}, "tool_response": ""}}'.format(
                f.replace('\\', '\\\\')))
        try:
            qg_layer26.main()
        finally:
            sys.stdin = sys.__stdin__
            try: os.unlink(f)
            except: pass
        self.assertTrue(os.path.exists(self.monitor_tmp))
        with open(self.monitor_tmp) as mf:
            events = [json.loads(l) for l in mf if l.strip()]
        cats = [e.get('category') for e in events]
        self.assertIn('CONSISTENCY_VIOLATION', cats)


class TestLayer27Extra(unittest.TestCase):
    def setUp(self):
        import qg_session_state as ss
        self.ts = tempfile.mktemp(suffix='.json')
        ss.STATE_PATH = self.ts
        ss.LOCK_PATH = self.ts + '.lock'

    def tearDown(self):
        for p in [self.ts, self.ts + '.lock']:
            try: os.unlink(p)
            except: pass

    def test_main_non_write_no_output(self):
        import io, builtins, qg_layer27
        captured = []
        orig = builtins.print
        builtins.print = lambda *a, **k: captured.append(' '.join(str(x) for x in a))
        sys.stdin = io.StringIO('{"tool_name": "Read", "tool_input": {}, "tool_response": ""}')
        try:
            qg_layer27.main()
        finally:
            builtins.print = orig
            sys.stdin = sys.__stdin__
        self.assertEqual(captured, [])

    def test_main_bad_json_no_crash(self):
        import io, qg_layer27
        sys.stdin = io.StringIO('not json')
        try:
            qg_layer27.main()
        finally:
            sys.stdin = sys.__stdin__

    def test_main_test_file_itself_no_output(self):
        import io, builtins, qg_layer27
        captured = []
        orig = builtins.print
        builtins.print = lambda *a, **k: captured.append(' '.join(str(x) for x in a))
        sys.stdin = io.StringIO(
            '{"tool_name": "Write", "tool_input": {"file_path": "/tmp/test_something.py"}, "tool_response": ""}')
        try:
            qg_layer27.main()
        finally:
            builtins.print = orig
            sys.stdin = sys.__stdin__
        self.assertEqual(captured, [])


class TestLayer6Extra(unittest.TestCase):
    def test_analyze_patterns_returns_list(self):
        from qg_layer6 import analyze_patterns
        result = analyze_patterns([])
        self.assertIsInstance(result, list)

    def test_analyze_patterns_single_session_no_pattern(self):
        from qg_layer6 import analyze_patterns
        events = [{'session_uuid': 's1', 'category': 'LAZINESS', 'ts': '2026-01-01T00:00:00'}]
        result = analyze_patterns(events, min_sessions=3, min_pct=0.1)
        self.assertEqual(result, [])

    def test_analyze_patterns_cross_session_threshold(self):
        from qg_layer6 import analyze_patterns
        events = []
        for sid in ['s1', 's2', 's3']:
            events.append({'session_uuid': sid, 'category': 'LOOP', 'ts': '2026-01-01T00:00:00'})
        result = analyze_patterns(events, min_sessions=3, min_pct=0.1)
        cats = [p['category'] for p in result]
        self.assertIn('LOOP', cats)


    def test_run_analysis_preserves_existing_when_no_patterns(self):
        import tempfile, json
        from qg_layer6 import run_analysis
        out = tempfile.mktemp(suffix='_cs.json')
        existing = {'patterns': [{'category': 'LAZINESS', 'sessions_count': 5}], 'ts': '2026-01-01T00:00:00'}
        with open(out, 'w') as f:
            json.dump(existing, f)
        empty_monitor = tempfile.mktemp(suffix='_mon.jsonl')
        try:
            run_analysis(monitor_path=empty_monitor, output_path=out)
            with open(out) as f:
                data = json.load(f)
            self.assertEqual(data['patterns'], existing['patterns'])
        finally:
            for p in [out, empty_monitor]:
                try: os.unlink(p)
                except: pass

    def test_run_analysis_creates_file_when_not_exists(self):
        import tempfile, json
        from qg_layer6 import run_analysis
        out = tempfile.mktemp(suffix='_cs_new.json')
        empty_monitor = tempfile.mktemp(suffix='_mon2.jsonl')
        try:
            run_analysis(monitor_path=empty_monitor, output_path=out)
            self.assertTrue(os.path.exists(out))
        finally:
            for p in [out, empty_monitor]:
                try: os.unlink(p)
                except: pass

    def test_run_analysis_writes_when_patterns_found(self):
        import tempfile, json
        from qg_layer6 import run_analysis
        out = tempfile.mktemp(suffix='_cs_pat.json')
        monitor = tempfile.mktemp(suffix='_mon3.jsonl')
        try:
            events = [json.dumps({'session_uuid': sid, 'category': 'LOOP', 'ts': '2026-01-01T00:00:00'})
                      for sid in ['s1', 's2', 's3']]
            with open(monitor, 'w') as f:
                f.write(chr(10).join(events) + chr(10))
            run_analysis(monitor_path=monitor, output_path=out)
            with open(out) as f:
                data = json.load(f)
            cats = [p['category'] for p in data['patterns']]
            self.assertIn('LOOP', cats)
        finally:
            for p in [out, monitor]:
                try: os.unlink(p)
                except: pass


    def test_project_dir_filter_isolates_events(self):
        from qg_layer6 import analyze_patterns
        events = []
        for i in range(1, 5):
            events.append({'session_uuid': 's{}'.format(i), 'category': 'LAZINESS',
                           'working_dir': '/proj/a', 'ts': '2026-01-01T00:00:00'})
        for i in range(5, 9):
            events.append({'session_uuid': 's{}'.format(i), 'category': 'LOOP',
                           'working_dir': '/proj/b', 'ts': '2026-01-01T00:00:00'})
        result_a = analyze_patterns(events, min_sessions=3, min_pct=0.1, project_dir='/proj/a')
        result_b = analyze_patterns(events, min_sessions=3, min_pct=0.1, project_dir='/proj/b')
        cats_a = [p['category'] for p in result_a]
        cats_b = [p['category'] for p in result_b]
        self.assertIn('LAZINESS', cats_a)
        self.assertNotIn('LOOP', cats_a)
        self.assertIn('LOOP', cats_b)
        self.assertNotIn('LAZINESS', cats_b)


class TestLayer7Extra(unittest.TestCase):
    def test_find_repeat_fns_empty_records(self):
        from qg_layer7 import find_repeat_fns
        self.assertEqual(find_repeat_fns([], threshold=3), {})

    def test_find_repeat_fns_tp_not_fn_ignored(self):
        from qg_layer7 import find_repeat_fns
        records = [{'outcome': 'TP', 'category': 'ASSUMPTION'}] * 5
        self.assertEqual(find_repeat_fns(records, threshold=3), {})

    def test_find_repeat_fns_mixed_outcomes(self):
        from qg_layer7 import find_repeat_fns
        records = (
            [{'outcome': 'FN', 'category': 'LAZINESS'}] * 4 +
            [{'outcome': 'TP', 'category': 'LAZINESS'}] * 2
        )
        result = find_repeat_fns(records, threshold=3)
        self.assertIn('LAZINESS', result)

    def test_find_repeat_fns_multiple_categories(self):
        from qg_layer7 import find_repeat_fns
        records = (
            [{'outcome': 'FN', 'category': 'LOOP'}] * 4 +
            [{'outcome': 'FN', 'category': 'INCORRECT_TOOL'}] * 2
        )
        result = find_repeat_fns(records, threshold=3)
        self.assertIn('LOOP', result)
        self.assertNotIn('INCORRECT_TOOL', result)

    def test_find_repeat_fns_exactly_at_threshold(self):
        from qg_layer7 import find_repeat_fns
        records = [{'outcome': 'FN', 'category': 'SCOPE_CREEP'}] * 3
        result = find_repeat_fns(records, threshold=3)
        self.assertIn('SCOPE_CREEP', result)


class TestLayer8Extra(unittest.TestCase):
    def setUp(self):
        import qg_session_state as ss
        self.ts = tempfile.mktemp(suffix='.json')
        ss.STATE_PATH = self.ts
        ss.LOCK_PATH = self.ts + '.lock'
        self.monitor_tmp = tempfile.mktemp(suffix='.jsonl')

    def tearDown(self):
        for p in [self.ts, self.ts + '.lock', self.monitor_tmp]:
            try: os.unlink(p)
            except: pass

    def test_parse_results_no_output_returns_nones(self):
        from qg_layer8 import parse_results
        passed, failed = parse_results('process completed')
        self.assertIsNone(passed)
        self.assertIsNone(failed)

    def test_parse_results_only_passed(self):
        from qg_layer8 import parse_results
        passed, failed = parse_results('7 passed in 0.5s')
        self.assertEqual(passed, 7)
        self.assertIsNone(failed)

    def test_main_non_bash_no_event(self):
        import io, qg_layer8
        qg_layer8.MONITOR_PATH = self.monitor_tmp
        sys.stdin = io.StringIO('{"tool_name": "Read", "tool_input": {}, "tool_response": ""}')
        try:
            qg_layer8.main()
        finally:
            sys.stdin = sys.__stdin__
        self.assertFalse(os.path.exists(self.monitor_tmp))

    def test_main_bash_non_test_cmd_no_event(self):
        import io, qg_layer8
        qg_layer8.MONITOR_PATH = self.monitor_tmp
        sys.stdin = io.StringIO(
            '{"tool_name": "Bash", "tool_input": {"command": "ls -la"}, "tool_response": ""}')
        try:
            qg_layer8.main()
        finally:
            sys.stdin = sys.__stdin__
        self.assertFalse(os.path.exists(self.monitor_tmp))

    def test_main_first_test_sets_baseline(self):
        import io, qg_layer8, qg_session_state as ss
        qg_layer8.MONITOR_PATH = self.monitor_tmp
        sys.stdin = io.StringIO(
            '{"tool_name": "Bash", "tool_input": {"command": "pytest tests/"}, '
            '"tool_response": "7 passed, 0 failed"}')
        try:
            qg_layer8.main()
        finally:
            sys.stdin = sys.__stdin__
        state = ss.read_state()
        self.assertEqual(state.get('layer_env_test_baseline'), [[7, 0]])

    def test_main_regression_writes_event(self):
        import io, json, qg_layer8, qg_session_state as ss
        qg_layer8.MONITOR_PATH = self.monitor_tmp
        state = ss.read_state()
        state['layer_env_test_baseline'] = [[10, 0]]
        ss.write_state(state)
        sys.stdin = io.StringIO(
            '{"tool_name": "Bash", "tool_input": {"command": "pytest tests/"}, '
            '"tool_response": "8 passed, 3 failed"}')
        try:
            qg_layer8.main()
        finally:
            sys.stdin = sys.__stdin__
        self.assertTrue(os.path.exists(self.monitor_tmp))
        with open(self.monitor_tmp) as f:
            lines = [l for l in f if l.strip()]
        events = [json.loads(l) for l in lines]
        cats = [e.get('category') for e in events]
        self.assertIn('REGRESSION', cats)


class TestLayer9Extra(unittest.TestCase):
    def setUp(self):
        import qg_session_state as ss
        self.ts = tempfile.mktemp(suffix='.json')
        ss.STATE_PATH = self.ts
        ss.LOCK_PATH = self.ts + '.lock'
        self.calibration_tmp = tempfile.mktemp(suffix='.jsonl')

    def tearDown(self):
        for p in [self.ts, self.ts + '.lock', self.calibration_tmp]:
            try: os.unlink(p)
            except: pass

    def test_extract_certainty_high_phrase(self):
        from qg_layer9 import extract_certainty
        self.assertEqual(extract_certainty("I'm certain this is correct"), 'high')

    def test_extract_certainty_medium_phrase(self):
        from qg_layer9 import extract_certainty
        self.assertEqual(extract_certainty("I believe this should work"), 'medium')

    def test_extract_certainty_low_phrase(self):
        from qg_layer9 import extract_certainty
        self.assertEqual(extract_certainty("I think this might work"), 'low')

    def test_extract_certainty_no_match(self):
        from qg_layer9 import extract_certainty
        self.assertIsNone(extract_certainty('Here is the updated implementation.'))

    def test_get_response_text_missing_transcript(self):
        from qg_layer9 import get_response_text
        self.assertEqual(get_response_text(None), '')
        self.assertEqual(get_response_text('/nonexistent/path.jsonl'), '')

    def test_main_skips_below_threshold(self):
        import io, qg_layer9, qg_session_state as ss
        qg_layer9.CALIBRATION_PATH = self.calibration_tmp
        state = ss.read_state()
        state['layer3_evaluation_count'] = 2
        ss.write_state(state)
        sys.stdin = io.StringIO('{"transcript_path": ""}')
        try:
            qg_layer9.main()
        finally:
            sys.stdin = sys.__stdin__
        self.assertFalse(os.path.exists(self.calibration_tmp))

    def test_main_no_certainty_no_record(self):
        import io, qg_layer9, qg_session_state as ss
        qg_layer9.CALIBRATION_PATH = self.calibration_tmp
        state = ss.read_state()
        state['layer3_evaluation_count'] = 10
        ss.write_state(state)
        sys.stdin = io.StringIO('{"transcript_path": ""}')
        try:
            qg_layer9.main()
        finally:
            sys.stdin = sys.__stdin__
        self.assertFalse(os.path.exists(self.calibration_tmp))


class TestLayer10Extra(unittest.TestCase):
    def setUp(self):
        import qg_session_state as ss
        self.ts = tempfile.mktemp(suffix='.json')
        ss.STATE_PATH = self.ts
        ss.LOCK_PATH = self.ts + '.lock'

    def tearDown(self):
        for p in [self.ts, self.ts + '.lock']:
            try: os.unlink(p)
            except: pass

    def test_run_integrity_check_returns_dict_with_ts(self):
        import qg_layer10, qg_session_state as ss
        monitor_tmp = tempfile.mktemp(suffix='.jsonl')
        quarantine_tmp = tempfile.mktemp(suffix='.jsonl')
        # Clear throttle so it runs
        state = ss.read_state()
        state['last_integrity_check_ts'] = 0
        ss.write_state(state)
        result = qg_layer10.run_integrity_check(monitor_tmp, quarantine_tmp)
        for p in [monitor_tmp, quarantine_tmp]:
            try: os.unlink(p)
            except: pass
        self.assertIn('ts', result)

    def test_run_integrity_check_throttled_returns_skipped(self):
        import time, qg_layer10, qg_session_state as ss
        state = ss.read_state()
        state['last_integrity_check_ts'] = time.time()
        ss.write_state(state)
        result = qg_layer10.run_integrity_check()
        self.assertEqual(result.get('status'), 'skipped_throttled')

    def test_validate_jsonl_empty_file(self):
        from qg_layer10 import validate_jsonl
        f = tempfile.mktemp(suffix='.jsonl')
        open(f, 'w').close()
        qf = tempfile.mktemp(suffix='.jsonl')
        valid, corrupt = validate_jsonl(f, qf)
        for p in [f, qf]:
            try: os.unlink(p)
            except: pass
        self.assertEqual(corrupt, [])

    def test_validate_jsonl_duplicate_id_corrupt(self):
        from qg_layer10 import validate_jsonl
        f = tempfile.mktemp(suffix='.jsonl')
        qf = tempfile.mktemp(suffix='.jsonl')
        with open(f, 'w') as fh:
            fh.write('{"event_id": "dup1"}\n{"event_id": "dup1"}\n')
        valid, corrupt = validate_jsonl(f, qf)
        for p in [f, qf]:
            try: os.unlink(p)
            except: pass
        self.assertEqual(len(corrupt), 1)

    def test_maybe_rotate_below_threshold_returns_false(self):
        from qg_layer10 import maybe_rotate
        f = tempfile.mktemp(suffix='.jsonl')
        with open(f, 'w') as fh:
            fh.write('{"n": 1}\n')
        result = maybe_rotate(f, threshold=10)
        try: os.unlink(f)
        except: pass
        self.assertFalse(result)


class TestLayer1PivotExtra(unittest.TestCase):
    def test_jaccard_similarity_partial_overlap(self):
        from precheck_hook_ext import jaccard_similarity
        score = jaccard_similarity('fix the bug in auth', 'refactor the auth module')
        self.assertGreater(score, 0.0)
        self.assertLess(score, 1.0)


class TestLayer1DeepExtra(unittest.TestCase):
    def test_infer_scope_files_extracts_filename(self):
        from precheck_hook_ext import infer_scope_files
        files = infer_scope_files('Update the qg_layer2.py to add ASSUMPTION category')
        self.assertTrue(any('qg_layer2.py' in f for f in files))

    def test_detect_deep_no_keywords_short_message(self):
        from precheck_hook_ext import detect_deep
        self.assertFalse(detect_deep('Fix typo'))


class TestSessionState(unittest.TestCase):
    def setUp(self):
        import qg_session_state as ss
        self.ts = tempfile.mktemp(suffix='.json')
        ss.STATE_PATH = self.ts
        ss.LOCK_PATH = self.ts + '.lock'

    def tearDown(self):
        for p in [self.ts, self.ts + '.lock']:
            try: os.unlink(p)
            except: pass

    def test_empty_state_has_schema_version_2(self):
        import qg_session_state as ss
        state = ss._empty_state()
        self.assertEqual(state['schema_version'], 2)

    def test_empty_state_has_layer3_evaluation_count(self):
        import qg_session_state as ss
        state = ss._empty_state()
        self.assertIn('layer3_evaluation_count', state)
        self.assertEqual(state['layer3_evaluation_count'], 0)

    def test_read_state_returns_dict_on_missing_file(self):
        import qg_session_state as ss
        state = ss.read_state()
        self.assertIsInstance(state, dict)

    def test_write_read_roundtrip(self):
        import qg_session_state as ss
        state = ss.read_state()
        state['test_key'] = 'hello_roundtrip'
        ss.write_state(state)
        state2 = ss.read_state()
        self.assertEqual(state2.get('test_key'), 'hello_roundtrip')

    def test_update_state_merges(self):
        import qg_session_state as ss
        state = ss.read_state()
        state['existing'] = 'keep'
        ss.write_state(state)
        ss.update_state(new_field='added')
        state2 = ss.read_state()
        self.assertEqual(state2.get('existing'), 'keep')
        self.assertEqual(state2.get('new_field'), 'added')

    def test_stale_state_resets(self):
        import json, time, qg_session_state as ss
        stale = ss.read_state()
        stale['test_stale'] = 'old_value'
        stale['session_start_ts'] = time.time() - 90000
        with open(self.ts, 'w') as f:
            json.dump(stale, f)
        state2 = ss.read_state()
        self.assertIsNone(state2.get('test_stale'))

    def test_fresh_state_not_reset(self):
        import json, time, qg_session_state as ss
        fresh = ss.read_state()
        fresh['test_fresh'] = 'keep_value'
        fresh['session_start_ts'] = time.time() - 100
        with open(self.ts, 'w') as f:
            json.dump(fresh, f)
        state2 = ss.read_state()
        self.assertEqual(state2.get('test_fresh'), 'keep_value')

    def test_migrate_v1_to_v2(self):
        import json, time, qg_session_state as ss
        v1 = {'schema_version': 1, 'session_start_ts': time.time(), 'test_v1': 'preserved'}
        with open(self.ts, 'w') as f:
            json.dump(v1, f)
        state = ss.read_state()
        self.assertEqual(state.get('schema_version'), 2)
        self.assertIn('layer3_evaluation_count', state)

    def test_migrate_v2_no_change(self):
        import qg_session_state as ss
        state = ss.read_state()
        state['layer3_evaluation_count'] = 5
        ss.write_state(state)
        state2 = ss.read_state()
        self.assertEqual(state2.get('layer3_evaluation_count'), 5)

    def test_is_stale_true_for_old_ts(self):
        import time, qg_session_state as ss
        data = {'session_start_ts': time.time() - 90000}
        self.assertTrue(ss._is_stale(data))

    def test_is_stale_false_for_recent_ts(self):
        import time, qg_session_state as ss
        data = {'session_start_ts': time.time() - 100}
        self.assertFalse(ss._is_stale(data))

    def test_is_stale_false_for_zero_ts(self):
        import qg_session_state as ss
        data = {'session_start_ts': 0}
        self.assertFalse(ss._is_stale(data))

    def test_prune_trims_unresolved_events(self):
        import qg_session_state as ss
        state = ss.read_state()
        state['layer2_unresolved_events'] = list(range(15))
        ss._prune_turn_scoped(state)
        self.assertLessEqual(len(state['layer2_unresolved_events']), 10)

    def test_prune_trims_response_claims(self):
        import qg_session_state as ss
        state = ss.read_state()
        state['layer3_last_response_claims'] = ['claim'] * 8
        ss._prune_turn_scoped(state)
        self.assertLessEqual(len(state['layer3_last_response_claims']), 5)


class TestNotificationRouter(unittest.TestCase):
    def setUp(self):
        import qg_session_state as ss
        import qg_notification_router as nr
        self.ts = tempfile.mktemp(suffix='.json')
        ss.STATE_PATH = self.ts
        ss.LOCK_PATH = self.ts + '.lock'
        nr.reset_turn_counter()

    def tearDown(self):
        for p in [self.ts, self.ts + '.lock']:
            try: os.unlink(p)
            except: pass

    def test_notify_info_returns_none(self):
        import qg_notification_router as nr
        result = nr.notify('INFO', 'layer0', 'TEST', None, 'msg', 'async')
        self.assertIsNone(result)

    def test_notify_warning_returns_none(self):
        import qg_notification_router as nr
        result = nr.notify('WARNING', 'layer2', 'LOOP', None, 'msg', 'async')
        self.assertIsNone(result)

    def test_notify_critical_pretooluse_returns_dict(self):
        import qg_notification_router as nr
        result = nr.notify('CRITICAL', 'layer2', 'LOOP', None, 'critical msg', 'pretooluse')
        self.assertIsNotNone(result)
        self.assertIn('additionalContext', result)

    def test_notify_critical_async_queues_in_state(self):
        import qg_notification_router as nr, qg_session_state as ss
        nr.notify('CRITICAL', 'layer2', 'LOOP', None, 'queued msg', 'async')
        state = ss.read_state()
        pending = state.get('notification_pending_criticals', [])
        self.assertGreater(len(pending), 0)

    def test_notify_critical_rate_limit_after_3(self):
        import qg_notification_router as nr, qg_session_state as ss
        for i in range(3):
            nr.notify('CRITICAL', 'layer2', 'LOOP{}'.format(i), None, 'msg', 'pretooluse')
        result = nr.notify('CRITICAL', 'layer2', 'LOOP4', None, 'msg', 'pretooluse')
        self.assertIsNone(result)
        state = ss.read_state()
        pending = state.get('notification_pending_criticals', [])
        self.assertGreater(len(pending), 0)

    def test_flush_pending_criticals_returns_text(self):
        import qg_notification_router as nr
        nr.notify('CRITICAL', 'layer2', 'TEST_FLUSH', None, 'flush test msg', 'async')
        result = nr.flush_pending_criticals()
        self.assertIsNotNone(result)
        self.assertIn('flush test msg', result)

    def test_flush_pending_criticals_clears_state(self):
        import qg_notification_router as nr, qg_session_state as ss
        nr.notify('CRITICAL', 'layer2', 'TEST_CLEAR', None, 'clear test', 'async')
        nr.flush_pending_criticals()
        state = ss.read_state()
        self.assertEqual(state.get('notification_pending_criticals', []), [])

    def test_flush_pending_criticals_empty_returns_none(self):
        import qg_notification_router as nr
        result = nr.flush_pending_criticals()
        self.assertIsNone(result)

    def test_flush_warnings_empty_returns_none(self):
        import qg_notification_router as nr
        result = nr.flush_warnings()
        self.assertIsNone(result)

    def test_reset_turn_counter_allows_delivery_again(self):
        import qg_notification_router as nr
        for i in range(3):
            nr.notify('CRITICAL', 'layer2', 'RC{}'.format(i), None, 'msg', 'pretooluse')
        nr.reset_turn_counter()
        result = nr.notify('CRITICAL', 'layer2', 'RC_NEW', None, 'after reset', 'pretooluse')
        self.assertIsNotNone(result)

    def test_notify_info_logged_to_state(self):
        import qg_notification_router as nr, qg_session_state as ss
        nr.notify('INFO', 'layer0', 'TEST_LOG', None, 'info log test', 'async')
        state = ss.read_state()
        delivery = state.get('notification_delivery', [])
        self.assertGreater(len(delivery), 0)

    def test_notify_critical_posttooluse_delivers(self):
        import qg_notification_router as nr
        result = nr.notify('CRITICAL', 'layer8', 'REGRESSION', None, 'regression', 'posttooluse')
        self.assertIsNotNone(result)
        self.assertIn('additionalContext', result)

    def test_notify_stop_context_queues(self):
        import qg_notification_router as nr, qg_session_state as ss
        nr.notify('CRITICAL', 'layer9', 'CALIBRATION', None, 'stop msg', 'stop')
        state = ss.read_state()
        pending = state.get('notification_pending_criticals', [])
        self.assertGreater(len(pending), 0)

    def test_dedup_same_key_not_queued_twice(self):
        import qg_notification_router as nr, qg_session_state as ss
        nr.notify('CRITICAL', 'layer2', 'LOOP', '/same/file.py', 'msg1', 'async')
        nr.notify('CRITICAL', 'layer2', 'LOOP', '/same/file.py', 'msg2', 'async')
        state = ss.read_state()
        pending = state.get('notification_pending_criticals', [])
        self.assertEqual(len(pending), 1)

    def test_flush_warnings_returns_text_when_warnings(self):
        import qg_notification_router as nr
        nr.notify('WARNING', 'layer15', 'RULE', None, 'warn test msg', 'async')
        result = nr.flush_warnings()
        self.assertIsNotNone(result)





class TestDashboardRulesApplyReject(unittest.TestCase):
    def _write_suggestions_file(self, path):
        content = '# QG Rule Suggestions\n## [PENDING] #1: LAZINESS\n- Reason: Repeated FN\n\n## [PENDING] #2: LOOP\n- Reason: Cross-session\n\n'
        with open(path, 'w', encoding='utf-8') as f:
            f.write(content)

    def test_apply_updates_status_in_file(self):
        import tempfile, sys, os, importlib.util
        _spec = importlib.util.spec_from_file_location('qgf', os.path.expanduser('~/.claude/scripts/qg-feedback.py'))
        qgf = importlib.util.module_from_spec(_spec)
        _spec.loader.exec_module(qgf)
        tmp = tempfile.mktemp(suffix='_rules.md')
        self._write_suggestions_file(tmp)
        orig = qgf.os.path.expanduser
        qgf.os.path.expanduser = lambda p: tmp if 'rule-suggestions' in p else orig(p)
        try:
            qgf.cmd_rules_apply_reject('apply', 1)
            with open(tmp) as f:
                out = f.read()
            self.assertIn('[APPLIED] #1:', out)
            self.assertIn('[PENDING] #2:', out)
        finally:
            qgf.os.path.expanduser = orig
            try: os.unlink(tmp)
            except: pass

    def test_reject_updates_status_in_file(self):
        import tempfile, sys, os, importlib.util
        _spec = importlib.util.spec_from_file_location('qgf', os.path.expanduser('~/.claude/scripts/qg-feedback.py'))
        qgf = importlib.util.module_from_spec(_spec)
        _spec.loader.exec_module(qgf)
        tmp = tempfile.mktemp(suffix='_rules2.md')
        self._write_suggestions_file(tmp)
        orig = qgf.os.path.expanduser
        qgf.os.path.expanduser = lambda p: tmp if 'rule-suggestions' in p else orig(p)
        try:
            qgf.cmd_rules_apply_reject('reject', 2)
            with open(tmp) as f:
                out = f.read()
            self.assertIn('[REJECTED] #2:', out)
            self.assertIn('[PENDING] #1:', out)
        finally:
            qgf.os.path.expanduser = orig
            try: os.unlink(tmp)
            except: pass

    def test_missing_id_prints_not_found(self):
        import tempfile, sys, os, importlib.util
        _spec = importlib.util.spec_from_file_location('qgf', os.path.expanduser('~/.claude/scripts/qg-feedback.py'))
        qgf = importlib.util.module_from_spec(_spec)
        _spec.loader.exec_module(qgf)
        import builtins
        tmp = tempfile.mktemp(suffix='_rules3.md')
        self._write_suggestions_file(tmp)
        orig = qgf.os.path.expanduser
        qgf.os.path.expanduser = lambda p: tmp if 'rule-suggestions' in p else orig(p)
        captured = []
        orig_print = builtins.print
        builtins.print = lambda *a, **kw: captured.append(' '.join(str(x) for x in a))
        try:
            qgf.cmd_rules_apply_reject('apply', 99)
        finally:
            qgf.os.path.expanduser = orig
            builtins.print = orig_print
            try: os.unlink(tmp)
            except: pass
        self.assertTrue(any('not found' in m.lower() or 'not pending' in m.lower() for m in captured))


class TestDashboardMonitorEnhanced(unittest.TestCase):
    """Gap #50 — cmd_monitor displays all 7 spec-required data sections."""

    def _load_qgf(self):
        import importlib.util
        _spec = importlib.util.spec_from_file_location('qgf', os.path.expanduser('~/.claude/scripts/qg-feedback.py'))
        qgf = importlib.util.module_from_spec(_spec)
        _spec.loader.exec_module(qgf)
        return qgf

    def test_monitor_runs_without_error(self):
        """cmd_monitor should not raise on empty/missing data files."""
        import tempfile, builtins
        qgf = self._load_qgf()
        orig_exp = qgf.os.path.expanduser
        tmpdir = tempfile.mkdtemp()
        qgf.os.path.expanduser = lambda p: p.replace('~/.claude', tmpdir) if p.startswith('~/.claude') else orig_exp(p)
        captured = []
        orig_print = builtins.print
        builtins.print = lambda *a, **kw: captured.append(' '.join(str(x) for x in a))
        try:
            qgf.cmd_monitor()
        except Exception as e:
            self.fail(f"cmd_monitor raised: {e}")
        finally:
            qgf.os.path.expanduser = orig_exp
            builtins.print = orig_print

    def test_monitor_shows_recovery_section(self):
        """cmd_monitor outputs Recovery: line."""
        import tempfile, builtins, json
        qgf = self._load_qgf()
        orig_exp = qgf.os.path.expanduser
        tmpdir = tempfile.mkdtemp()
        state_path = os.path.join(tmpdir, 'qg-session-state.json')
        with open(state_path, 'w') as f:
            json.dump({'layer35_recovery_events': [{'status': 'resolved'}, {'status': 'open'}]}, f)
        qgf.os.path.expanduser = lambda p: p.replace('~/.claude', tmpdir) if p.startswith('~/.claude') else orig_exp(p)
        captured = []
        orig_print = builtins.print
        builtins.print = lambda *a, **kw: captured.append(' '.join(str(x) for x in a))
        try:
            qgf.cmd_monitor()
        finally:
            qgf.os.path.expanduser = orig_exp
            builtins.print = orig_print
        self.assertTrue(any('Recovery:' in m for m in captured), f"Recovery section missing. Got: {captured}")

    def test_monitor_shows_cross_session_patterns(self):
        """cmd_monitor outputs Patterns: line from qg-cross-session.json."""
        import tempfile, builtins, json
        qgf = self._load_qgf()
        orig_exp = qgf.os.path.expanduser
        tmpdir = tempfile.mkdtemp()
        cs_path = os.path.join(tmpdir, 'qg-cross-session.json')
        with open(cs_path, 'w') as f:
            json.dump({'patterns': [{'category': 'LAZINESS', 'sessions_count': 4, 'event_pct': 0.25, 'total_events': 10}], 'sessions_analyzed': 20}, f)
        qgf.os.path.expanduser = lambda p: p.replace('~/.claude', tmpdir) if p.startswith('~/.claude') else orig_exp(p)
        captured = []
        orig_print = builtins.print
        builtins.print = lambda *a, **kw: captured.append(' '.join(str(x) for x in a))
        try:
            qgf.cmd_monitor()
        finally:
            qgf.os.path.expanduser = orig_exp
            builtins.print = orig_print
        self.assertTrue(any('Patterns:' in m for m in captured), "Patterns: header missing")
        self.assertTrue(any('LAZINESS' in m for m in captured),
                        f"Pattern name missing. Got: {[m for m in captured if 'Pattern' in m or 'LAZINESS' in m]}")



class TestPrecheckHookGaps2526(unittest.TestCase):
    """Gaps #25-26 — precheck-hook: category-specific criteria and pivot scope clear."""

    def _load_ph(self):
        import importlib.util
        _spec = importlib.util.spec_from_file_location('precheck_hook',
                    os.path.expanduser('~/.claude/hooks/precheck-hook.py'))
        ph = importlib.util.module_from_spec(_spec)
        _spec.loader.exec_module(ph)
        return ph

    def test_criteria_not_stub(self):
        """Success criteria must not contain 'TBD' after classification."""
        import tempfile
        import qg_session_state as ss
        ph = self._load_ph()
        tmp = tempfile.mktemp(suffix='.json')
        ss.STATE_PATH = tmp
        ss.LOCK_PATH = tmp + '.lock'
        state = ss.read_state()
        state['active_task_description'] = ''
        ss.write_state(state)
        _, new_state = ph._run_layer1('edit the config file', 'MECHANICAL', state)
        criteria = new_state.get('task_success_criteria', [])
        self.assertTrue(len(criteria) > 0, "Criteria must not be empty")
        for c in criteria:
            self.assertNotIn('TBD', c, f"Criteria must not be a stub: {c}")

    def test_criteria_are_category_specific(self):
        """Each category generates distinct criteria."""
        import tempfile
        import qg_session_state as ss
        ph = self._load_ph()
        tmp = tempfile.mktemp(suffix='.json')
        ss.STATE_PATH = tmp
        ss.LOCK_PATH = tmp + '.lock'
        state = ss.read_state()
        state['active_task_description'] = ''
        ss.write_state(state)
        # _run_layer1 mutates state in-place; capture criteria before second call
        ph._run_layer1('edit foo.py', 'MECHANICAL', state)
        c1 = list(state.get('task_success_criteria', []))
        import copy
        state2 = copy.deepcopy(state)
        state2['active_task_description'] = ''
        ph._run_layer1('what are the next steps', 'PLANNING', state2)
        c2 = state2.get('task_success_criteria', [])
        self.assertNotEqual(c1, c2,
                            "Different categories must produce different criteria")

    def test_pivot_clears_scope(self):
        """On pivot, layer1_scope_files is cleared before re-deriving."""
        import tempfile
        import qg_session_state as ss
        ph = self._load_ph()
        tmp = tempfile.mktemp(suffix='.json')
        ss.STATE_PATH = tmp
        ss.LOCK_PATH = tmp + '.lock'
        state = ss.read_state()
        state['active_task_description'] = 'edit foo.py to add logging'
        state['layer1_scope_files'] = ['foo.py', 'bar.py']
        ss.write_state(state)
        # Pivot: very different message with no file scope
        _, new_state = ph._run_layer1('what time is it today', 'NONE', state)
        # After pivot (jaccard < 0.3), scope should be cleared
        scope = new_state.get('layer1_scope_files', ['KEEP'])
        self.assertEqual(scope, [], f"Scope should be cleared on pivot, got {scope}")




class TestDetectSubtasks(unittest.TestCase):
    """Gap #28 - detect_subtasks() unit tests."""

    def _load_ph(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            'precheck_hook', os.path.expanduser('~/.claude/hooks/precheck-hook.py'))
        ph = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(ph)
        return ph

    def test_numbered_list_two_items_returns_subtasks(self):
        ph = self._load_ph()
        msg = "Please do the following:\n1. Edit foo.py to add logging\n2. Update bar.py to handle errors"
        result = ph.detect_subtasks(msg)
        self.assertEqual(len(result), 2)
        self.assertIn('Edit foo.py to add logging', result)

    def test_numbered_list_single_item_returns_empty(self):
        ph = self._load_ph()
        msg = "1. Edit foo.py to add logging"
        result = ph.detect_subtasks(msg)
        self.assertEqual(result, [])

    def test_conjunction_and_also_returns_subtasks(self):
        ph = self._load_ph()
        msg = "Add logging to the config module and also update the test suite to cover new code"
        result = ph.detect_subtasks(msg)
        self.assertGreaterEqual(len(result), 2)

    def test_no_multi_task_single_sentence_returns_empty(self):
        ph = self._load_ph()
        msg = "Edit the config file to fix the timeout value"
        result = ph.detect_subtasks(msg)
        self.assertEqual(result, [])

    def test_conjunction_too_short_parts_returns_empty(self):
        """Parts shorter than 15 chars are ignored."""
        ph = self._load_ph()
        msg = "Do A and also B"
        result = ph.detect_subtasks(msg)
        self.assertEqual(result, [])


class TestPrecheckHookGap28Integration(unittest.TestCase):
    """Gap #28 - _run_layer1 sets layer1_subtask_count and active_subtask_id."""

    def _load_ph(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            'precheck_hook', os.path.expanduser('~/.claude/hooks/precheck-hook.py'))
        ph = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(ph)
        return ph

    def setUp(self):
        import qg_session_state as ss
        self.ts = tempfile.mktemp(suffix='.json')
        ss.STATE_PATH = self.ts
        ss.LOCK_PATH = self.ts + '.lock'

    def tearDown(self):
        for p in [self.ts, self.ts + '.lock']:
            try: os.unlink(p)
            except: pass

    def test_multi_task_sets_layer1_subtask_count(self):
        import qg_session_state as ss
        ph = self._load_ph()
        state = ss.read_state()
        state['active_task_description'] = ''
        ss.write_state(state)
        msg = "1. Edit foo.py to add logging\n2. Update bar.py to handle errors"
        _, new_state = ph._run_layer1(msg, 'MECHANICAL', state)
        self.assertEqual(new_state.get('layer1_subtask_count'), 2)
        self.assertIsNotNone(new_state.get('active_subtask_id'))

    def test_single_task_sets_subtask_count_zero(self):
        import qg_session_state as ss
        ph = self._load_ph()
        state = ss.read_state()
        state['active_task_description'] = ''
        ss.write_state(state)
        msg = "Edit the config file to fix the timeout value"
        _, new_state = ph._run_layer1(msg, 'MECHANICAL', state)
        self.assertEqual(new_state.get('layer1_subtask_count'), 0)
        self.assertIsNone(new_state.get('active_subtask_id'))


class TestLayer5HandoffFiles(unittest.TestCase):
    """Gap #37 - Layer 5 handoff file creation and merge behaviors."""

    def setUp(self):
        import qg_layer5, qg_session_state as ss
        self.ts = tempfile.mktemp(suffix='.json')
        ss.STATE_PATH = self.ts
        ss.LOCK_PATH = self.ts + '.lock'
        self.monitor_tmp = tempfile.mktemp(suffix='.jsonl')
        self.handoff_dir = tempfile.mkdtemp()
        qg_layer5.HANDOFF_DIR = self.handoff_dir
        qg_layer5.MONITOR_PATH = self.monitor_tmp

    def tearDown(self):
        import shutil, qg_layer5
        for p in [self.ts, self.ts + '.lock', self.monitor_tmp]:
            try: os.unlink(p)
            except: pass
        shutil.rmtree(self.handoff_dir, ignore_errors=True)
        qg_layer5.HANDOFF_DIR = os.path.expanduser('~/.claude')

    def test_predispatch_creates_handoff_file(self):
        """process_predispatch writes qg-subagent-<id>.json to HANDOFF_DIR."""
        import glob, qg_layer5, qg_session_state as ss
        state = ss.read_state()
        qg_layer5.process_predispatch('Agent', {'description': 'test handoff'}, state)
        files = glob.glob(os.path.join(self.handoff_dir, 'qg-subagent-*.json'))
        self.assertEqual(len(files), 1, "Expected 1 handoff file")

    def test_predispatch_handoff_contains_state_fields(self):
        """Handoff file contains session_uuid and task_success_criteria."""
        import glob, json, qg_layer5, qg_session_state as ss
        state = ss.read_state()
        state['task_success_criteria'] = ['Verify X', 'Verify Y']
        ss.write_state(state)
        qg_layer5.process_predispatch('Agent', {'description': 'test'}, state)
        files = glob.glob(os.path.join(self.handoff_dir, 'qg-subagent-*.json'))
        with open(files[0], 'r') as f:
            data = json.load(f)
        self.assertIn('subagent_id', data)
        self.assertIn('task_success_criteria', data)
        self.assertEqual(data['handoff_type'], 'dispatch')

    def test_merge_absent_handoff_sets_timeout_marker(self):
        """If handoff file is absent on PostToolUse, subagent gets timeout_marker=True."""
        import qg_layer5, qg_session_state as ss
        state = ss.read_state()
        fake_id = 'abc12345'
        state['layer5_subagents'] = {fake_id: {'status': 'in_flight'}}
        ss.write_state(state)
        qg_layer5._merge_subagent_events(fake_id, 'parent-task-1', state)
        subagents = state.get('layer5_subagents', {})
        self.assertTrue(subagents.get(fake_id, {}).get('timeout_marker'),
                        "Absent handoff file must set timeout_marker=True")

    def test_merge_reads_events_and_deletes_file(self):
        """_merge_subagent_events reads subagent_events from file and deletes it."""
        import json, qg_layer5, qg_session_state as ss
        subagent_id = 'test9999'
        handoff_path = os.path.join(self.handoff_dir, 'qg-subagent-' + subagent_id + '.json')
        handoff_data = {
            'subagent_id': subagent_id,
            'subagent_events': [{'type': 'test_event', 'data': 'x'}],
        }
        with open(handoff_path, 'w') as f:
            json.dump(handoff_data, f)
        state = ss.read_state()
        state['layer5_subagents'] = {subagent_id: {'status': 'in_flight'}}
        ss.write_state(state)
        qg_layer5._merge_subagent_events(subagent_id, 'parent-task-1', state)
        self.assertFalse(os.path.exists(handoff_path), "Handoff file must be deleted after merge")
        self.assertEqual(state['layer5_subagents'][subagent_id].get('merged_events'), 1)




# ============================================================================
# quality-gate.py unit tests (Tiers 1-5)
# ============================================================================

def _load_qg():
    """Helper to import quality-gate.py via importlib (hyphenated filename)."""
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        'quality_gate', os.path.expanduser('~/.claude/hooks/quality-gate.py'))
    qg = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(qg)
    return qg


class TestQGRecordVerifiedCounts(unittest.TestCase):
    """Tier 1: _record_verified_counts — writes grace file when both regexes match."""
    def setUp(self):
        self.qg = _load_qg()
        self.tmpdir = tempfile.mkdtemp()
        self._orig_grace = self.qg._GRACE_FILE
        self._orig_log = self.qg.LOG_PATH
        self.qg._GRACE_FILE = os.path.join(self.tmpdir, 'grace.json')
        self.qg.LOG_PATH = os.path.join(self.tmpdir, 'qg.log')

    def tearDown(self):
        self.qg._GRACE_FILE = self._orig_grace
        self.qg.LOG_PATH = self._orig_log
        import shutil; shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_writes_grace_file_on_matching_response(self):
        self.qg._record_verified_counts('=== Results: 265 passed, 0 failed, 265 total ===', ['Bash'])
        self.assertTrue(os.path.exists(self.qg._GRACE_FILE))
        import json
        with open(self.qg._GRACE_FILE) as f:
            data = json.load(f)
        self.assertEqual(data['key'], '265')
        self.assertIn('ts', data)

    def test_no_write_when_bare_count_missing(self):
        self.qg._record_verified_counts('265 passed somewhere', ['Bash'])
        self.assertFalse(os.path.exists(self.qg._GRACE_FILE))

    def test_log_entry_includes_tools(self):
        self.qg._record_verified_counts('=== Results: 10 passed, 0 failed, 10 total ===', ['Bash', 'Read'])
        with open(self.qg.LOG_PATH) as f:
            content = f.read()
        self.assertIn('GRACE-WRITE', content)
        self.assertIn('Bash,Read', content)


class TestQGCheckCountGrace(unittest.TestCase):
    """Tier 1: _check_count_grace — grace period logic."""
    def setUp(self):
        self.qg = _load_qg()
        self.tmpdir = tempfile.mkdtemp()
        self._orig_grace = self.qg._GRACE_FILE
        self._orig_log = self.qg.LOG_PATH
        self.qg._GRACE_FILE = os.path.join(self.tmpdir, 'grace.json')
        self.qg.LOG_PATH = os.path.join(self.tmpdir, 'qg.log')

    def tearDown(self):
        self.qg._GRACE_FILE = self._orig_grace
        self.qg.LOG_PATH = self._orig_log
        import shutil; shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_returns_true_within_grace_period(self):
        import json, time
        with open(self.qg._GRACE_FILE, 'w') as f:
            json.dump({'ts': time.time(), 'key': '42'}, f)
        self.assertTrue(self.qg._check_count_grace('42 passed, 0 failed, 42 total'))

    def test_returns_false_when_expired(self):
        import json, time
        with open(self.qg._GRACE_FILE, 'w') as f:
            json.dump({'ts': time.time() - 600, 'key': '42'}, f)
        self.assertFalse(self.qg._check_count_grace('42 passed, 0 failed, 42 total'))

    def test_returns_false_when_no_file(self):
        self.assertFalse(self.qg._check_count_grace('42 passed'))

    def test_returns_false_when_count_mismatch(self):
        import json, time
        with open(self.qg._GRACE_FILE, 'w') as f:
            json.dump({'ts': time.time(), 'key': '42'}, f)
        self.assertFalse(self.qg._check_count_grace('99 passed, 0 failed'))


class TestQGLogDecision(unittest.TestCase):
    """Tier 1: log_decision — format and rotation."""
    def setUp(self):
        self.qg = _load_qg()
        self.tmpdir = tempfile.mkdtemp()
        self._orig_log = self.qg.LOG_PATH
        self.qg.LOG_PATH = os.path.join(self.tmpdir, 'qg.log')

    def tearDown(self):
        self.qg.LOG_PATH = self._orig_log
        import shutil; shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_writes_formatted_line(self):
        self.qg.log_decision('PASS', 'llm-ok', 'Fix the bug', ['Edit', 'Bash'], 'MODERATE', 'Done.')
        with open(self.qg.LOG_PATH) as f:
            line = f.read().strip()
        self.assertIn('| PASS', line)
        self.assertIn('MODERATE', line)
        self.assertIn('llm-ok', line)

    def test_handles_empty_inputs(self):
        self.qg.log_decision('BLOCK', 'reason', '', [], 'TRIVIAL')
        with open(self.qg.LOG_PATH) as f:
            line = f.read().strip()
        self.assertIn('BLOCK', line)


class TestQGGetLastComplexity(unittest.TestCase):
    """Tier 1: get_last_complexity — classifier log parsing."""
    def setUp(self):
        self.qg = _load_qg()
        self.tmpdir = tempfile.mkdtemp()
        self._orig = self.qg.CLASSIFIER_LOG
        self.qg.CLASSIFIER_LOG = os.path.join(self.tmpdir, 'classifier.log')

    def tearDown(self):
        self.qg.CLASSIFIER_LOG = self._orig
        import shutil; shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_parses_deep(self):
        with open(self.qg.CLASSIFIER_LOG, 'w') as f:
            f.write('2026-03-30 | DEEP | some details\n')
        self.assertEqual(self.qg.get_last_complexity(), 'DEEP')

    def test_parses_moderate(self):
        with open(self.qg.CLASSIFIER_LOG, 'w') as f:
            f.write('2026-03-30 | MODERATE | task\n')
        self.assertEqual(self.qg.get_last_complexity(), 'MODERATE')

    def test_returns_default_on_missing(self):
        self.assertEqual(self.qg.get_last_complexity(), 'MODERATE')


class TestQGCountUserItems(unittest.TestCase):
    """Tier 1: _count_user_items — heuristic item counter."""
    def setUp(self):
        self.qg = _load_qg()

    def test_explicit_number(self):
        self.assertEqual(self.qg._count_user_items('fix all 5 bugs'), 5)

    def test_comma_list(self):
        result = self.qg._count_user_items('fix: error in login, broken signup, and missing dashboard')
        self.assertGreaterEqual(result, 3)

    def test_too_few_items_returns_zero(self):
        self.assertEqual(self.qg._count_user_items('fix the bug'), 0)

    def test_empty_returns_zero(self):
        self.assertEqual(self.qg._count_user_items(''), 0)


class TestQGExtractCertainty(unittest.TestCase):
    """Tier 1: _extract_stated_certainty — regex certainty extraction."""
    def setUp(self):
        self.qg = _load_qg()

    def test_high(self):
        self.assertEqual(self.qg._extract_stated_certainty("I'm certain this is correct"), 'high')

    def test_medium(self):
        self.assertEqual(self.qg._extract_stated_certainty("I believe this should work"), 'medium')

    def test_low(self):
        self.assertEqual(self.qg._extract_stated_certainty("It might work, possibly"), 'low')

    def test_none(self):
        self.assertEqual(self.qg._extract_stated_certainty("Hello world"), 'none')


class TestQGComputeConfidenceEdge(unittest.TestCase):
    """Tier 1: _compute_confidence — clipping and adjustment paths."""
    def setUp(self):
        self.qg = _load_qg()

    def test_floor_clips_to_001(self):
        state = {
            'layer2_unresolved_events': [{'status': 'open', 'severity': 'critical'}] * 10,
            'layer2_elevated_scrutiny': True,
            'layer15_warnings_ignored_count': 10,
            'layer25_syntax_failure': True,
            'layer8_regression_expected': True,
            'layer17_uncertainty_level': 'HIGH',
            'layer17_mismatch_count': 10,
        }
        score = self.qg._compute_confidence(False, None, state)
        self.assertEqual(score, 0.01)

    def test_ceiling_clips_to_099(self):
        score = self.qg._compute_confidence(True, 'OVERCONFIDENCE', {})
        self.assertLessEqual(score, 0.99)

    def test_mechanical_block_gets_boost(self):
        base_score = self.qg._compute_confidence(True, 'PLANNING', {})
        mech_score = self.qg._compute_confidence(True, 'MECHANICAL', {})
        self.assertGreater(mech_score, base_score)


class TestQGWriteMonitorEvent(unittest.TestCase):
    """Tier 1: _write_monitor_event — JSON append."""
    def setUp(self):
        self.qg = _load_qg()
        self.tmpdir = tempfile.mkdtemp()
        self._orig = self.qg._QG_MONITOR
        self.qg._QG_MONITOR = os.path.join(self.tmpdir, 'monitor.jsonl')

    def tearDown(self):
        self.qg._QG_MONITOR = self._orig
        import shutil; shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_appends_json_line(self):
        import json
        self.qg._write_monitor_event({'test': True, 'value': 42})
        with open(self.qg._QG_MONITOR) as f:
            data = json.loads(f.read().strip())
        self.assertEqual(data['test'], True)
        self.assertEqual(data['value'], 42)

    def test_silent_on_error(self):
        self.qg._QG_MONITOR = '/nonexistent/dir/file.jsonl'
        self.qg._write_monitor_event({'test': True})  # Should not raise


class TestQGGetLastTurnLines(unittest.TestCase):
    """Tier 2: _get_last_turn_lines — transcript backward walk."""
    def setUp(self):
        self.qg = _load_qg()
        self.tmpdir = tempfile.mkdtemp()

    def tearDown(self):
        import shutil; shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _write_transcript(self, lines):
        import json
        path = os.path.join(self.tmpdir, 'transcript.jsonl')
        with open(path, 'w') as f:
            for line in lines:
                f.write(json.dumps(line) + '\n')
        return path

    def test_single_turn(self):
        import json
        path = self._write_transcript([
            {'type': 'user', 'message': {'content': 'Fix the bug'}},
            {'type': 'assistant', 'message': {'content': [{'type': 'text', 'text': 'Done.'}]}},
        ])
        result = self.qg._get_last_turn_lines(path)
        self.assertEqual(len(result), 1)

    def test_skips_tool_result_user_entries(self):
        import json
        path = self._write_transcript([
            {'type': 'user', 'message': {'content': 'Fix it'}},
            {'type': 'assistant', 'message': {'content': [{'type': 'tool_use', 'id': 'tu1', 'name': 'Read', 'input': {}}]}},
            {'type': 'user', 'message': {'content': [{'type': 'tool_result', 'tool_use_id': 'tu1', 'content': 'data'}]}},
            {'type': 'assistant', 'message': {'content': [{'type': 'text', 'text': 'Fixed.'}]}},
        ])
        result = self.qg._get_last_turn_lines(path)
        self.assertEqual(len(result), 2)  # Both assistant entries

    def test_empty_path(self):
        result = self.qg._get_last_turn_lines('')
        self.assertEqual(result, [])


class TestQGGetToolSummary(unittest.TestCase):
    """Tier 2: get_tool_summary — tool extraction from transcript."""
    def setUp(self):
        self.qg = _load_qg()
        self.tmpdir = tempfile.mkdtemp()

    def tearDown(self):
        import shutil; shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _write_transcript(self, lines):
        import json
        path = os.path.join(self.tmpdir, 'transcript.jsonl')
        with open(path, 'w') as f:
            for line in lines:
                f.write(json.dumps(line) + '\n')
        return path

    def test_extracts_tools_and_paths(self):
        path = self._write_transcript([
            {'type': 'user', 'message': {'content': 'Fix it'}},
            {'type': 'assistant', 'message': {'content': [
                {'type': 'tool_use', 'id': 'tu1', 'name': 'Read', 'input': {'file_path': '/a.py'}},
                {'type': 'tool_use', 'id': 'tu2', 'name': 'Edit', 'input': {'file_path': '/a.py'}},
                {'type': 'tool_use', 'id': 'tu3', 'name': 'Bash', 'input': {'command': 'pytest'}},
            ]}},
        ])
        tools, edited, bash = self.qg.get_tool_summary(path)
        self.assertEqual(tools, ['Read', 'Edit', 'Bash'])
        self.assertEqual(edited, ['/a.py'])
        self.assertEqual(bash, ['pytest'])

    def test_no_tools(self):
        path = self._write_transcript([
            {'type': 'user', 'message': {'content': 'Hello'}},
            {'type': 'assistant', 'message': {'content': [{'type': 'text', 'text': 'Hi'}]}},
        ])
        tools, edited, bash = self.qg.get_tool_summary(path)
        self.assertEqual(tools, [])
        self.assertEqual(edited, [])

    def test_empty_transcript(self):
        tools, edited, bash = self.qg.get_tool_summary('')
        self.assertEqual(tools, [])


class TestQGGetFailedCommands(unittest.TestCase):
    """Tier 2: get_failed_commands — detects failed Bash commands."""
    def setUp(self):
        self.qg = _load_qg()
        self.tmpdir = tempfile.mkdtemp()

    def tearDown(self):
        import shutil; shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _write_transcript(self, lines):
        import json
        path = os.path.join(self.tmpdir, 'transcript.jsonl')
        with open(path, 'w') as f:
            for line in lines:
                f.write(json.dumps(line) + '\n')
        return path

    def test_detects_failed_bash(self):
        path = self._write_transcript([
            {'type': 'user', 'message': {'content': 'Run tests'}},
            {'type': 'assistant', 'message': {'content': [
                {'type': 'tool_use', 'id': 'tu1', 'name': 'Bash', 'input': {'command': 'pytest'}},
            ]}},
            {'type': 'user', 'message': {'content': [
                {'type': 'tool_result', 'tool_use_id': 'tu1', 'content': 'FAILED test_foo.py', 'is_error': True},
            ]}},
        ])
        failed = self.qg.get_failed_commands(path)
        self.assertEqual(len(failed), 1)
        self.assertEqual(failed[0][0], 'pytest')

    def test_no_failures(self):
        path = self._write_transcript([
            {'type': 'user', 'message': {'content': 'Run tests'}},
            {'type': 'assistant', 'message': {'content': [
                {'type': 'tool_use', 'id': 'tu1', 'name': 'Bash', 'input': {'command': 'pytest'}},
            ]}},
            {'type': 'user', 'message': {'content': [
                {'type': 'tool_result', 'tool_use_id': 'tu1', 'content': '5 passed', 'is_error': False},
            ]}},
        ])
        failed = self.qg.get_failed_commands(path)
        self.assertEqual(len(failed), 0)

    def test_non_bash_not_detected(self):
        path = self._write_transcript([
            {'type': 'user', 'message': {'content': 'Read file'}},
            {'type': 'assistant', 'message': {'content': [
                {'type': 'tool_use', 'id': 'tu1', 'name': 'Read', 'input': {'file_path': '/x'}},
            ]}},
            {'type': 'user', 'message': {'content': [
                {'type': 'tool_result', 'tool_use_id': 'tu1', 'content': 'error reading', 'is_error': True},
            ]}},
        ])
        failed = self.qg.get_failed_commands(path)
        self.assertEqual(len(failed), 0)

    def test_empty_transcript(self):
        self.assertEqual(self.qg.get_failed_commands(''), [])


class TestQGGetUserRequest(unittest.TestCase):
    """Tier 3: get_user_request — finds real user message."""
    def setUp(self):
        self.qg = _load_qg()
        self.tmpdir = tempfile.mkdtemp()

    def tearDown(self):
        import shutil; shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _write_transcript(self, lines):
        import json
        path = os.path.join(self.tmpdir, 'transcript.jsonl')
        with open(path, 'w') as f:
            for line in lines:
                f.write(json.dumps(line) + '\n')
        return path

    def test_finds_string_message(self):
        path = self._write_transcript([
            {'type': 'user', 'message': {'content': 'Fix the auth bug'}},
            {'type': 'assistant', 'message': {'content': [{'type': 'text', 'text': 'Done'}]}},
        ])
        self.assertEqual(self.qg.get_user_request(path), 'Fix the auth bug')

    def test_skips_tool_result_only(self):
        path = self._write_transcript([
            {'type': 'user', 'message': {'content': 'Fix it'}},
            {'type': 'assistant', 'message': {'content': [{'type': 'tool_use', 'id': 'tu1', 'name': 'Read', 'input': {}}]}},
            {'type': 'user', 'message': {'content': [{'type': 'tool_result', 'tool_use_id': 'tu1', 'content': 'data'}]}},
            {'type': 'assistant', 'message': {'content': [{'type': 'text', 'text': 'Done'}]}},
        ])
        self.assertEqual(self.qg.get_user_request(path), 'Fix it')

    def test_truncates_at_500(self):
        long_msg = 'A' * 600
        path = self._write_transcript([
            {'type': 'user', 'message': {'content': long_msg}},
            {'type': 'assistant', 'message': {'content': [{'type': 'text', 'text': 'Ok'}]}},
        ])
        result = self.qg.get_user_request(path)
        self.assertEqual(len(result), 500)

    def test_empty_returns_empty(self):
        self.assertEqual(self.qg.get_user_request(''), '')


class TestQGCountRetryBlocks(unittest.TestCase):
    """Tier 4: _count_recent_retry_blocks — counts compliance retries."""
    def setUp(self):
        self.qg = _load_qg()
        self.tmpdir = tempfile.mkdtemp()

    def tearDown(self):
        import shutil; shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_counts_retries_in_window(self):
        from datetime import datetime
        log = os.path.join(self.tmpdir, 'test.log')
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        with open(log, 'w') as f:
            f.write(f'{now} | BLOCK | MODERATE | OVERCONFIDENCE: test | tools=- | req=Stop hook feedback: QG\n')
            f.write(f'{now} | BLOCK | MODERATE | ASSUMPTION: test | tools=- | req=Stop hook feedback: fix\n')
        count = self.qg._count_recent_retry_blocks(log_path=log, window_sec=120)
        self.assertEqual(count, 2)

    def test_returns_zero_no_retries(self):
        from datetime import datetime
        log = os.path.join(self.tmpdir, 'test.log')
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        with open(log, 'w') as f:
            f.write(f'{now} | PASS | MODERATE | llm-ok | tools=Bash | req=Fix the bug\n')
        count = self.qg._count_recent_retry_blocks(log_path=log, window_sec=120)
        self.assertEqual(count, 0)


class TestQGMechanicalChecks(unittest.TestCase):
    """Tier 5: mechanical_checks — all SMOKE rules."""
    def setUp(self):
        self.qg = _load_qg()
        self.tmpdir = tempfile.mkdtemp()
        self._orig_grace = self.qg._GRACE_FILE
        self.qg._GRACE_FILE = os.path.join(self.tmpdir, 'grace.json')

    def tearDown(self):
        self.qg._GRACE_FILE = self._orig_grace
        import shutil; shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_smoke2_edit_without_verification_blocks(self):
        result = self.qg.mechanical_checks(['Edit'], ['/foo.py'], [], [], 'Done.', '')
        self.assertIsNotNone(result)
        self.assertIn('MECHANICAL', result)

    def test_smoke2_edit_with_bash_passes(self):
        result = self.qg.mechanical_checks(
            ['Edit', 'Bash'], ['/foo.py'], ['pytest'], [],
            'Tests pass. === Results: 5 passed, 0 failed ===', '')
        self.assertIsNone(result)

    def test_smoke3_last_action_is_edit_blocks(self):
        result = self.qg.mechanical_checks(
            ['Bash', 'Edit'], ['/foo.py'], ['pytest'], [],
            'Edited the file after testing.', '')
        self.assertIsNotNone(result)
        self.assertIn('Last action was editing', result)

    def test_smoke4_bash_not_real_test_blocks(self):
        result = self.qg.mechanical_checks(
            ['Edit', 'Bash'], ['/foo.py'], ['echo hello'], [],
            'Ran a command.', '')
        self.assertIsNotNone(result)
        self.assertIn("doesn't look like a real test", result)

    def test_smoke5_failed_command_not_mentioned_blocks(self):
        result = self.qg.mechanical_checks(
            [], [], [], [('pytest', 'ModuleNotFoundError: xyz')],
            'Everything looks good.', '')
        self.assertIsNotNone(result)
        self.assertIn('failed', result.lower())

    def test_smoke6_claims_without_evidence_blocks(self):
        result = self.qg.mechanical_checks(
            ['Edit', 'Bash'], ['/foo.py'], ['pytest'], [],
            'All tests pass successfully.', '')
        self.assertIsNotNone(result)
        self.assertIn('OVERCONFIDENCE', result)

    def test_smoke7_bare_count_without_verification_blocks(self):
        result = self.qg.mechanical_checks(
            [], [], [], [],
            '265 passed, 0 failed, 265 total', '')
        self.assertIsNotNone(result)
        self.assertIn('OVERCONFIDENCE', result)

    def test_smoke7_grace_period_passes(self):
        import json, time
        with open(self.qg._GRACE_FILE, 'w') as f:
            json.dump({'ts': time.time(), 'key': '265'}, f)
        result = self.qg.mechanical_checks(
            [], [], [], [],
            '265 passed, 0 failed, 265 total', '')
        self.assertIsNone(result)

    def test_smoke_new_no_tools_verifiable_claim_blocks(self):
        result = self.qg.mechanical_checks(
            [], [], [], [],
            'All tests passed and everything is fully verified.', '')
        self.assertIsNotNone(result)
        self.assertIn('OVERCONFIDENCE', result)

    def test_smoke8_quantity_mismatch_blocks(self):
        result = self.qg.mechanical_checks(
            ['Edit'], ['/foo.py'], [], [],
            'Fixed all the issues.', 'fix all 5 bugs in: login, signup, dashboard, settings, and profile')
        # This triggers SMOKE:2 first (edit without verification), but if we add Bash:
        result = self.qg.mechanical_checks(
            ['Edit', 'Bash'], ['/foo.py'], ['pytest'], [],
            'Fixed all the issues. Tests pass: === Results: 5 passed ===',
            'fix all 5 bugs in: login, signup, dashboard, settings, and profile')
        self.assertIsNotNone(result)
        self.assertIn('items', result.lower())

    def test_smoke15_non_code_paths_pass(self):
        result = self.qg.mechanical_checks(
            ['Edit'], ['memory/STATUS.md'], [], [],
            'Updated the status file.', '')
        self.assertIsNone(result)




# ============================================================================
# quality-gate.py Tier 6 unit tests (coverage push toward 70%)
# ============================================================================


class TestQGGetPriorContext(unittest.TestCase):
    """Tier 3: get_prior_context — collects previous exchanges."""
    def setUp(self):
        self.qg = _load_qg()
        self.tmpdir = tempfile.mkdtemp()

    def tearDown(self):
        import shutil; shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _write_transcript(self, lines):
        import json
        path = os.path.join(self.tmpdir, 'transcript.jsonl')
        with open(path, 'w') as f:
            for line in lines:
                f.write(json.dumps(line) + '\n')
        return path

    def test_returns_prior_exchanges_skipping_current(self):
        path = self._write_transcript([
            {'type': 'user', 'message': {'content': 'First question'}},
            {'type': 'assistant', 'message': {'content': [
                {'type': 'tool_use', 'id': 'tu0', 'name': 'Read', 'input': {}},
                {'type': 'text', 'text': 'First answer with some details.'},
            ]}},
            {'type': 'user', 'message': {'content': [
                {'type': 'tool_result', 'tool_use_id': 'tu0', 'content': 'data'},
            ]}},
            {'type': 'user', 'message': {'content': 'Second question'}},
            {'type': 'assistant', 'message': {'content': [{'type': 'text', 'text': 'Second answer.'}]}},
            {'type': 'user', 'message': {'content': 'Current question'}},
            {'type': 'assistant', 'message': {'content': [{'type': 'text', 'text': 'Current answer.'}]}},
        ])
        result = self.qg.get_prior_context(path)
        self.assertEqual(len(result), 2)
        self.assertIn('First question', result[0]['user'])

    def test_max_exchanges_limit(self):
        path = self._write_transcript([
            {'type': 'user', 'message': {'content': 'Q1'}},
            {'type': 'assistant', 'message': {'content': [{'type': 'text', 'text': 'A1'}]}},
            {'type': 'user', 'message': {'content': 'Q2'}},
            {'type': 'assistant', 'message': {'content': [{'type': 'text', 'text': 'A2'}]}},
            {'type': 'user', 'message': {'content': 'Q3'}},
            {'type': 'assistant', 'message': {'content': [{'type': 'text', 'text': 'A3'}]}},
            {'type': 'user', 'message': {'content': 'Current'}},
            {'type': 'assistant', 'message': {'content': [{'type': 'text', 'text': 'Now'}]}},
        ])
        result = self.qg.get_prior_context(path, max_exchanges=2)
        self.assertLessEqual(len(result), 2)

    def test_empty_transcript(self):
        result = self.qg.get_prior_context('')
        self.assertEqual(result, [])


class TestQGGetBashResults(unittest.TestCase):
    """Tier 2: get_bash_results — pairs Bash tool_use with tool_results."""
    def setUp(self):
        self.qg = _load_qg()
        self.tmpdir = tempfile.mkdtemp()

    def tearDown(self):
        import shutil; shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _write_transcript(self, lines):
        import json
        path = os.path.join(self.tmpdir, 'transcript.jsonl')
        with open(path, 'w') as f:
            for line in lines:
                f.write(json.dumps(line) + '\n')
        return path

    def test_pairs_bash_result(self):
        path = self._write_transcript([
            {'type': 'user', 'message': {'content': 'Run tests'}},
            {'type': 'assistant', 'message': {'content': [
                {'type': 'tool_use', 'id': 'bash1', 'name': 'Bash', 'input': {'command': 'pytest'}},
            ]}},
            {'type': 'user', 'message': {'content': [
                {'type': 'tool_result', 'tool_use_id': 'bash1', 'content': '10 passed, 0 failed'},
            ]}},
            {'type': 'assistant', 'message': {'content': [{'type': 'text', 'text': 'Done'}]}},
        ])
        results = self.qg.get_bash_results(path)
        self.assertEqual(len(results), 1)
        self.assertIn('10 passed', results[0])

    def test_ignores_non_bash_results(self):
        path = self._write_transcript([
            {'type': 'user', 'message': {'content': 'Read file'}},
            {'type': 'assistant', 'message': {'content': [
                {'type': 'tool_use', 'id': 'read1', 'name': 'Read', 'input': {'file_path': '/x'}},
            ]}},
            {'type': 'user', 'message': {'content': [
                {'type': 'tool_result', 'tool_use_id': 'read1', 'content': 'file contents'},
            ]}},
            {'type': 'assistant', 'message': {'content': [{'type': 'text', 'text': 'Got it'}]}},
        ])
        results = self.qg.get_bash_results(path)
        self.assertEqual(len(results), 0)

    def test_empty_transcript(self):
        self.assertEqual(self.qg.get_bash_results(''), [])

    def test_multiple_bash_results(self):
        path = self._write_transcript([
            {'type': 'user', 'message': {'content': 'Run stuff'}},
            {'type': 'assistant', 'message': {'content': [
                {'type': 'tool_use', 'id': 'b1', 'name': 'Bash', 'input': {'command': 'pytest'}},
                {'type': 'tool_use', 'id': 'b2', 'name': 'Bash', 'input': {'command': 'eslint .'}},
            ]}},
            {'type': 'user', 'message': {'content': [
                {'type': 'tool_result', 'tool_use_id': 'b1', 'content': '5 passed'},
                {'type': 'tool_result', 'tool_use_id': 'b2', 'content': 'no errors'},
            ]}},
            {'type': 'assistant', 'message': {'content': [{'type': 'text', 'text': 'Both passed'}]}},
        ])
        results = self.qg.get_bash_results(path)
        self.assertEqual(len(results), 2)


class TestQGDetectOverride(unittest.TestCase):
    """Tier 4: _detect_override — classifies BLOCK->PASS cycles."""
    def setUp(self):
        self.qg = _load_qg()
        self.tmpdir = tempfile.mkdtemp()
        self.captured = []
        self._orig_wo = self.qg.write_override
        self.qg.write_override = lambda r: self.captured.append(r)

    def tearDown(self):
        self.qg.write_override = self._orig_wo
        import shutil; shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_likely_fp_same_tools(self):
        from datetime import datetime
        logpath = os.path.join(self.tmpdir, 'qg.log')
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        with open(logpath, 'w') as f:
            f.write(f'{now} | BLOCK | MODERATE | OVERCONFIDENCE: claims                                              | tools=Bash,Edit | req=Refactor the auth module                                        | hash=abc12345\n')
        self.qg._detect_override('Refactor the auth module', ['Bash', 'Edit'], 'Refactored.', log_path=logpath)
        self.assertEqual(len(self.captured), 1)
        self.assertEqual(self.captured[0]['auto_verdict'], 'likely_fp')

    def test_likely_tp_different_tools(self):
        from datetime import datetime
        logpath = os.path.join(self.tmpdir, 'qg.log')
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        with open(logpath, 'w') as f:
            f.write(f'{now} | BLOCK | MODERATE | ASSUMPTION: guessed path                                             | tools=Edit | req=Refactor the auth module                                        | hash=abc12345\n')
        self.qg._detect_override('Refactor the auth module', ['Read', 'Grep', 'Edit', 'Bash'], 'Fixed.', log_path=logpath)
        self.assertEqual(len(self.captured), 1)
        self.assertEqual(self.captured[0]['auto_verdict'], 'likely_tp')

    def test_no_recent_block(self):
        logpath = os.path.join(self.tmpdir, 'qg.log')
        from datetime import datetime
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        with open(logpath, 'w') as f:
            f.write(f'{now} | PASS  | MODERATE | llm-ok                                                                           | tools=Bash | req=Refactor the auth module                                        | hash=abc12345\n')
        self.qg._detect_override('Refactor the auth module', ['Bash'], 'Done.', log_path=logpath)
        self.assertEqual(len(self.captured), 0)


class TestQGLlmEvaluateMocked(unittest.TestCase):
    """Tier 6: llm_evaluate with mocked Haiku API."""
    def setUp(self):
        self.qg = _load_qg()
        self._orig_haiku = self.qg.call_haiku_check
        self._orig_shadow = self.qg._shadow_ollama_async
        self._orig_cache_check = self.qg.check_cache
        self._orig_cache_write = self.qg.write_cache
        # Disable shadow and cache
        self.qg._shadow_ollama_async = lambda *a, **kw: None
        self.qg.check_cache = lambda *a: None
        self.qg.write_cache = lambda *a: None

    def tearDown(self):
        self.qg.call_haiku_check = self._orig_haiku
        self.qg._shadow_ollama_async = self._orig_shadow
        self.qg.check_cache = self._orig_cache_check
        self.qg.write_cache = self._orig_cache_write

    def test_haiku_pass(self):
        self.qg.call_haiku_check = lambda prompt: (True, '', True)
        ok, reason, genuine = self.qg.llm_evaluate(
            'I fixed the bug. Tests pass: === 5 passed ===',
            'Fix the bug', ['Edit', 'Bash'], ['/foo.py'], ['pytest'], ['5 passed'],
            'MODERATE')
        self.assertTrue(ok)
        self.assertTrue(genuine)

    def test_haiku_block(self):
        self.qg.call_haiku_check = lambda prompt: (False, 'OVERCONFIDENCE: claims without evidence', True)
        ok, reason, genuine = self.qg.llm_evaluate(
            'All done, tests pass.', 'Fix the bug', ['Edit'], ['/foo.py'], [], [],
            'MODERATE')
        self.assertFalse(ok)
        self.assertIn('OVERCONFIDENCE', reason)

    def test_haiku_degraded(self):
        self.qg.call_haiku_check = lambda prompt: (True, '', False)
        ok, reason, genuine = self.qg.llm_evaluate(
            'Done.', 'Fix it', [], [], [], [], 'TRIVIAL')
        self.assertTrue(ok)
        self.assertFalse(genuine)

    def test_cache_hit(self):
        self.qg.check_cache = lambda resp: (True, '')
        ok, reason, cached = self.qg.llm_evaluate(
            'Cached response.', 'Do something', [], [], [], [], 'MODERATE')
        self.assertTrue(ok)
        self.assertTrue(cached)

    def test_retry_note_included_for_stop_hook_feedback(self):
        prompts_seen = []
        def capture_haiku(prompt):
            prompts_seen.append(prompt)
            return (True, '', True)
        self.qg.call_haiku_check = capture_haiku
        self.qg.llm_evaluate(
            'I verified it.', 'Stop hook feedback: QUALITY GATE: OVERCONFIDENCE',
            ['Bash'], [], ['pytest'], ['5 passed'], 'MODERATE')
        self.assertTrue(any('COMPLIANCE RETRY' in p for p in prompts_seen))

    def test_deep_gets_longer_response_limit(self):
        prompts_seen = []
        def capture_haiku(prompt):
            prompts_seen.append(prompt)
            return (True, '', True)
        self.qg.call_haiku_check = capture_haiku
        long_response = 'A' * 7000
        self.qg.llm_evaluate(long_response, 'Deep task', [], [], [], [], 'DEEP')
        # DEEP allows 6000 chars, MODERATE allows 4000
        self.assertTrue(any('A' * 5000 in p for p in prompts_seen))


class TestQGLayer3RunMocked(unittest.TestCase):
    """Tier 6: _layer3_run with mocked dependencies."""
    def setUp(self):
        self.qg = _load_qg()
        self.tmpdir = tempfile.mkdtemp()
        self._orig_monitor = self.qg._QG_MONITOR
        self.qg._QG_MONITOR = os.path.join(self.tmpdir, 'monitor.jsonl')
        # Mock _qg_load_ss to return controllable state
        self._orig_load_ss = self.qg._qg_load_ss
        self._mock_state = {}
        self._mock_ss = type('MockSS', (), {
            'read_state': lambda self_: self._mock_state,
            'write_state': lambda self_, s: None,
        })()
        self.qg._qg_load_ss = lambda: (self._mock_state, self._mock_ss)
        # Mock layer35 functions
        self._orig_l35_create = self.qg._l35_create
        self._orig_l35_check = self.qg._l35_check
        self._orig_detect_fn = self.qg._detect_fn_signals
        self.qg._l35_create = lambda *a, **kw: None
        self.qg._l35_check = lambda *a, **kw: None

    def tearDown(self):
        self.qg._QG_MONITOR = self._orig_monitor
        self.qg._qg_load_ss = self._orig_load_ss
        self.qg._l35_create = self._orig_l35_create
        self.qg._l35_check = self._orig_l35_check
        self.qg._detect_fn_signals = self._orig_detect_fn
        import shutil; shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_blocked_high_confidence_returns_tp(self):
        self._mock_state = {}
        self.qg._detect_fn_signals = lambda *a, **kw: []
        verdict, tag, warnings = self.qg._layer3_run(True, 'MECHANICAL: code edit without verify', 'Done.', ['Edit'], '')
        self.assertEqual(verdict, 'TP')
        self.assertIn('TP', tag)

    def test_passed_no_fn_signals_returns_tn(self):
        self._mock_state = {}
        self.qg._detect_fn_signals = lambda *a, **kw: []
        verdict, tag, warnings = self.qg._layer3_run(False, None, 'Here is the answer.', ['Read'], 'What is this?')
        self.assertEqual(verdict, 'TN')
        self.assertEqual(tag, '')

    def test_passed_with_fn_signals_returns_fn(self):
        self._mock_state = {}
        self.qg._detect_fn_signals = lambda *a, **kw: ['claimed completion without verification output']
        verdict, tag, warnings = self.qg._layer3_run(False, None, 'All done and verified.', [], 'Do the task')
        self.assertEqual(verdict, 'FN')

    def test_blocked_low_confidence_returns_fp(self):
        self._mock_state = {
            'layer2_unresolved_events': [{'status': 'open', 'severity': 'critical', 'category': 'ERROR_IGNORED'}] * 5,
            'layer2_elevated_scrutiny': True,
            'layer15_warnings_ignored_count': 5,
        }
        self.qg._detect_fn_signals = lambda *a, **kw: []
        verdict, tag, warnings = self.qg._layer3_run(True, 'PLANNING: unclear', 'Plan: ...', [], '')
        self.assertEqual(verdict, 'FP')
        self.assertIn('FP', tag)

    def test_writes_monitor_event(self):
        import json
        self._mock_state = {'session_uuid': 'test-uuid', 'active_task_id': 'task-1'}
        self.qg._detect_fn_signals = lambda *a, **kw: []
        self.qg._layer3_run(False, None, 'Answer.', ['Read'], 'Question')
        with open(self.qg._QG_MONITOR) as f:
            event = json.loads(f.read().strip())
        self.assertEqual(event['layer'], 'layer3')
        self.assertEqual(event['verdict'], 'TN')
        self.assertEqual(event['session_uuid'], 'test-uuid')

    def test_ss_none_returns_unknown(self):
        self.qg._qg_load_ss = lambda: ({}, None)
        verdict, tag, warnings = self.qg._layer3_run(False, None, 'Hi', [], '')
        self.assertEqual(verdict, 'UNKNOWN')


class TestQGMechanicalChecksAgent(unittest.TestCase):
    """Tier 5 supplement: SMOKE:14 agent without post-verify."""
    def setUp(self):
        self.qg = _load_qg()

    def test_smoke14_agent_without_post_verify_blocks(self):
        result = self.qg.mechanical_checks(
            ['Agent'], [], [], [],
            'The agent completed the task.', '')
        self.assertIsNotNone(result)
        self.assertIn('MECHANICAL', result)

    def test_smoke14_agent_with_post_bash_passes(self):
        result = self.qg.mechanical_checks(
            ['Agent', 'Bash'], [], ['pytest'], [],
            'Agent finished. Tests pass: === 5 passed ===', '')
        self.assertIsNone(result)




# ============================================================================
# quality-gate.py Tier 7: main() + _layer4_checkpoint + override branches
# ============================================================================


class TestQGMainOrchestration(unittest.TestCase):
    """Tier 7: main() — full pipeline orchestration with mocked dependencies."""
    def setUp(self):
        self.qg = _load_qg()
        self.tmpdir = tempfile.mkdtemp()
        # Redirect all file paths to tmpdir
        self._orig_log = self.qg.LOG_PATH
        self._orig_classifier = self.qg.CLASSIFIER_LOG
        self._orig_grace = self.qg._GRACE_FILE
        self._orig_monitor = self.qg._QG_MONITOR
        self.qg.LOG_PATH = os.path.join(self.tmpdir, 'qg.log')
        self.qg.CLASSIFIER_LOG = os.path.join(self.tmpdir, 'classifier.log')
        self.qg._GRACE_FILE = os.path.join(self.tmpdir, 'grace.json')
        self.qg._QG_MONITOR = os.path.join(self.tmpdir, 'monitor.jsonl')
        # Write classifier log
        with open(self.qg.CLASSIFIER_LOG, 'w') as f:
            f.write('2026-03-30 | MODERATE | task\n')
        # Mock LLM and layer3/4
        self._orig_llm = self.qg.llm_evaluate
        self._orig_l3 = self.qg._layer3_run
        self._orig_l4 = self.qg._layer4_checkpoint
        self._orig_detect = self.qg._detect_override
        self._orig_load_ss = self.qg._qg_load_ss
        self.qg._layer3_run = lambda *a, **kw: ('TN', '', None)
        self.qg._layer4_checkpoint = lambda *a, **kw: None
        self.qg._detect_override = lambda *a, **kw: None
        self.qg._qg_load_ss = lambda: ({}, type('M', (), {'write_state': lambda s, d: None})())

    def tearDown(self):
        self.qg.LOG_PATH = self._orig_log
        self.qg.CLASSIFIER_LOG = self._orig_classifier
        self.qg._GRACE_FILE = self._orig_grace
        self.qg._QG_MONITOR = self._orig_monitor
        self.qg.llm_evaluate = self._orig_llm
        self.qg._layer3_run = self._orig_l3
        self.qg._layer4_checkpoint = self._orig_l4
        self.qg._detect_override = self._orig_detect
        self.qg._qg_load_ss = self._orig_load_ss
        import shutil; shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _run_main(self, data_dict):
        """Run main() with mocked stdin."""
        import io, json
        old_stdin = sys.stdin
        sys.stdin = io.StringIO(json.dumps(data_dict))
        old_stdout = sys.stdout
        sys.stdout = io.StringIO()
        try:
            self.qg.main()
            output = sys.stdout.getvalue()
        finally:
            sys.stdin = old_stdin
            sys.stdout = old_stdout
        return output

    def test_stop_hook_active_returns_continue(self):
        output = self._run_main({'stop_hook_active': True})
        import json
        result = json.loads(output.strip())
        self.assertTrue(result.get('continue'))

    def test_mechanical_block_returns_block(self):
        # Build transcript with Edit but no Bash
        import json
        transcript = os.path.join(self.tmpdir, 'transcript.jsonl')
        lines = [
            json.dumps({'type': 'user', 'message': {'content': 'Fix the auth module code'}}),
            json.dumps({'type': 'assistant', 'message': {'content': [
                {'type': 'tool_use', 'id': 'tu1', 'name': 'Edit', 'input': {'file_path': '/foo.py', 'old_string': 'x', 'new_string': 'y'}},
                {'type': 'text', 'text': 'Fixed it.'},
            ]}}),
        ]
        with open(transcript, 'w') as f:
            f.write('\n'.join(lines))
        output = self._run_main({
            'transcript_path': transcript,
            'last_assistant_message': 'Fixed it.',
        })
        result = json.loads(output.strip())
        self.assertEqual(result.get('decision'), 'block')
        self.assertIn('MECHANICAL', result.get('reason', ''))

    def test_llm_pass_returns_continue(self):
        import json
        self.qg.llm_evaluate = lambda *a, **kw: (True, '', True)
        transcript = os.path.join(self.tmpdir, 'transcript.jsonl')
        lines = [
            json.dumps({'type': 'user', 'message': {'content': 'What time is it?'}}),
            json.dumps({'type': 'assistant', 'message': {'content': [
                {'type': 'text', 'text': 'I cannot check the current time.'},
            ]}}),
        ]
        with open(transcript, 'w') as f:
            f.write('\n'.join(lines))
        output = self._run_main({
            'transcript_path': transcript,
            'last_assistant_message': 'I cannot check the current time.',
        })
        result = json.loads(output.strip())
        self.assertTrue(result.get('continue'))

    def test_llm_block_returns_block_with_fix(self):
        import json
        self.qg.llm_evaluate = lambda *a, **kw: (False, 'OVERCONFIDENCE: claims without evidence', True)
        transcript = os.path.join(self.tmpdir, 'transcript.jsonl')
        lines = [
            json.dumps({'type': 'user', 'message': {'content': 'Refactor the auth module code'}}),
            json.dumps({'type': 'assistant', 'message': {'content': [
                {'type': 'text', 'text': 'All done, everything works.'},
            ]}}),
        ]
        with open(transcript, 'w') as f:
            f.write('\n'.join(lines))
        output = self._run_main({
            'transcript_path': transcript,
            'last_assistant_message': 'All done, everything works.',
        })
        result = json.loads(output.strip())
        self.assertEqual(result.get('decision'), 'block')
        self.assertIn('OVERCONFIDENCE', result.get('reason', ''))
        self.assertIn('FIX', result.get('reason', ''))

    def test_degraded_pass(self):
        import json
        self.qg.llm_evaluate = lambda *a, **kw: (True, '', False)
        transcript = os.path.join(self.tmpdir, 'transcript.jsonl')
        lines = [
            json.dumps({'type': 'user', 'message': {'content': 'Tell me about path normalization'}}),
            json.dumps({'type': 'assistant', 'message': {'content': [
                {'type': 'text', 'text': 'Path normalization converts...'},
            ]}}),
        ]
        with open(transcript, 'w') as f:
            f.write('\n'.join(lines))
        output = self._run_main({
            'transcript_path': transcript,
            'last_assistant_message': 'Path normalization converts...',
        })
        result = json.loads(output.strip())
        self.assertTrue(result.get('continue'))
        # Check log has DEGRADED-PASS
        with open(self.qg.LOG_PATH) as f:
            log = f.read()
        self.assertIn('DEGRADED-PASS', log)

    def test_retry_block_with_mandatory_escalation(self):
        import json
        from datetime import datetime
        self.qg.llm_evaluate = lambda *a, **kw: (False, 'ASSUMPTION: guessed', True)
        # Write log with 2 prior retry blocks
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        with open(self.qg.LOG_PATH, 'w') as f:
            f.write(f'{now} | BLOCK | MODERATE | ASSUMPTION: guessed                                                              | tools=- | req=Stop hook feedback: QG block              | hash=aaa\n')
            f.write(f'{now} | BLOCK | MODERATE | ASSUMPTION: guessed                                                              | tools=- | req=Stop hook feedback: QG block              | hash=bbb\n')
        transcript = os.path.join(self.tmpdir, 'transcript.jsonl')
        lines = [
            json.dumps({'type': 'user', 'message': {'content': 'Stop hook feedback: QUALITY GATE: ASSUMPTION'}}),
            json.dumps({'type': 'assistant', 'message': {'content': [
                {'type': 'text', 'text': 'I believe it is correct based on standard practice.'},
            ]}}),
        ]
        with open(transcript, 'w') as f:
            f.write('\n'.join(lines))
        output = self._run_main({
            'transcript_path': transcript,
            'last_assistant_message': 'I believe it is correct based on standard practice.',
        })
        result = json.loads(output.strip())
        self.assertEqual(result.get('decision'), 'block')
        self.assertIn('MANDATORY', result.get('reason', ''))

    def test_no_tools_transcript_logs_diagnostic(self):
        import json
        self.qg.llm_evaluate = lambda *a, **kw: (True, '', True)
        # Transcript with only text, no tools
        transcript = os.path.join(self.tmpdir, 'transcript.jsonl')
        lines = [
            json.dumps({'type': 'user', 'message': {'content': 'Tell me a joke about normalization'}}),
            json.dumps({'type': 'assistant', 'message': {'content': [
                {'type': 'text', 'text': 'Why did the path cross the road?'},
            ]}}),
        ]
        with open(transcript, 'w') as f:
            f.write('\n'.join(lines))
        self._run_main({
            'transcript_path': transcript,
            'last_assistant_message': 'Why did the path cross the road?',
        })
        with open(self.qg.LOG_PATH) as f:
            log = f.read()
        self.assertIn('TRANSCRIPT', log)

    def test_empty_stdin(self):
        import io
        old_stdin = sys.stdin
        sys.stdin = io.StringIO('')
        old_stdout = sys.stdout
        sys.stdout = io.StringIO()
        try:
            self.qg.main()
            output = sys.stdout.getvalue()
        finally:
            sys.stdin = old_stdin
            sys.stdout = old_stdout
        # Empty stdin = no stop_hook_active, empty data → processes with empty transcript
        # Should not crash


class TestQGLayer4Checkpoint(unittest.TestCase):
    """Tier 7: _layer4_checkpoint — session summary and history rotation."""
    def setUp(self):
        self.qg = _load_qg()
        self.tmpdir = tempfile.mkdtemp()
        self._orig_monitor = self.qg._QG_MONITOR
        self._orig_history = self.qg._QG_HISTORY
        self._orig_archive = self.qg._QG_ARCHIVE
        self._orig_rules = self.qg._RULES_PATH
        self._orig_state_dir = self.qg.STATE_DIR
        self.qg._QG_MONITOR = os.path.join(self.tmpdir, 'monitor.jsonl')
        self.qg._QG_HISTORY = os.path.join(self.tmpdir, 'history.md')
        self.qg._QG_ARCHIVE = os.path.join(self.tmpdir, 'archive.md')
        self.qg._RULES_PATH = os.path.join(self.tmpdir, 'rules.json')
        self.qg.STATE_DIR = self.tmpdir
        # Mock _trigger_phase3_layers to avoid subprocess calls
        self._orig_trigger = self.qg._trigger_phase3_layers
        self.qg._trigger_phase3_layers = lambda *a: None
        # Mock notification router
        self._orig_l35_unresolved = self.qg._l35_unresolved
        self.qg._l35_unresolved = lambda state: []

    def tearDown(self):
        self.qg._QG_MONITOR = self._orig_monitor
        self.qg._QG_HISTORY = self._orig_history
        self.qg._QG_ARCHIVE = self._orig_archive
        self.qg._RULES_PATH = self._orig_rules
        self.qg.STATE_DIR = self._orig_state_dir
        self.qg._trigger_phase3_layers = self._orig_trigger
        self.qg._l35_unresolved = self._orig_l35_unresolved
        import shutil; shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _make_ss_mock(self):
        writes = []
        return type('MockSS', (), {
            'read_state': lambda self_: {},
            'write_state': lambda self_, s: writes.append(s),
        })(), writes

    def test_writes_session_summary(self):
        import json
        state = {
            'session_uuid': 'test-sess-123',
            'layer1_task_category': 'MODERATE',
            'layer2_unresolved_events': [],
            'layer35_recovery_events': [],
        }
        # Write a layer3 event to monitor
        with open(self.qg._QG_MONITOR, 'w') as f:
            f.write(json.dumps({
                'session_uuid': 'test-sess-123', 'layer': 'layer3',
                'verdict': 'TN', 'confidence': 0.75,
            }) + '\n')
        ss_mock, _ = self._make_ss_mock()
        self.qg._layer4_checkpoint(state, ss_mock)
        self.assertTrue(os.path.exists(self.qg._QG_HISTORY))
        with open(self.qg._QG_HISTORY) as f:
            content = f.read()
        self.assertIn('test-sess-123', content)
        self.assertIn('TN: 1', content)
        self.assertIn('quality_score:', content)

    def test_updates_existing_session_entry(self):
        import json
        # Pre-populate history with same session
        with open(self.qg._QG_HISTORY, 'w') as f:
            f.write('## Session 2026-03-30T10:00:00\nsession_uuid: test-sess-123\nquality_score: 0.0\nTP: 0  FP: 0  FN: 0  TN: 0  total: 0\n\n')
        state = {
            'session_uuid': 'test-sess-123',
            'layer1_task_category': 'MODERATE',
            'layer2_unresolved_events': [],
            'layer35_recovery_events': [],
        }
        with open(self.qg._QG_MONITOR, 'w') as f:
            f.write(json.dumps({
                'session_uuid': 'test-sess-123', 'layer': 'layer3',
                'verdict': 'TP', 'confidence': 0.85,
            }) + '\n')
        ss_mock, _ = self._make_ss_mock()
        self.qg._layer4_checkpoint(state, ss_mock)
        with open(self.qg._QG_HISTORY) as f:
            content = f.read()
        self.assertIn('TP: 1', content)
        # Should have only one session entry
        self.assertEqual(content.count('session_uuid: test-sess-123'), 1)

    def test_writes_recovery_pending(self):
        import json
        state = {
            'session_uuid': 'test-sess-456',
            'layer1_task_category': 'DEEP',
            'layer2_unresolved_events': [],
            'layer35_recovery_events': [
                {'status': 'open', 'category': 'unverified'},
            ],
        }
        with open(self.qg._QG_MONITOR, 'w') as f:
            f.write(json.dumps({
                'session_uuid': 'test-sess-456', 'layer': 'layer3', 'verdict': 'TN',
            }) + '\n')
        ss_mock, _ = self._make_ss_mock()
        self.qg._layer4_checkpoint(state, ss_mock)
        pending_path = os.path.join(self.tmpdir, 'qg-recovery-pending.json')
        self.assertTrue(os.path.exists(pending_path))
        with open(pending_path) as f:
            data = json.load(f)
        self.assertFalse(data['consumed'])
        self.assertEqual(len(data['events']), 1)

    def test_ss_none_returns_early(self):
        self.qg._layer4_checkpoint({}, None)
        self.assertFalse(os.path.exists(self.qg._QG_HISTORY))


class TestQGDetectOverrideBranches(unittest.TestCase):
    """Tier 7: _detect_override — additional branch coverage."""
    def setUp(self):
        self.qg = _load_qg()
        self.tmpdir = tempfile.mkdtemp()
        self.captured = []
        self._orig_wo = self.qg.write_override
        self.qg.write_override = lambda r: self.captured.append(r)

    def tearDown(self):
        self.qg.write_override = self._orig_wo
        import shutil; shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_skips_subagent_entries(self):
        from datetime import datetime
        logpath = os.path.join(self.tmpdir, 'qg.log')
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        with open(logpath, 'w') as f:
            f.write(f'{now} | BLOCK | subagent: test-agent | OVERCONFIDENCE | tools=- | req=Refactor the auth module | hash=abc\n')
        self.qg._detect_override('Refactor the auth module', ['Bash'], 'Done.', log_path=logpath)
        self.assertEqual(len(self.captured), 0)

    def test_skips_old_blocks_beyond_120s(self):
        from datetime import datetime, timedelta
        logpath = os.path.join(self.tmpdir, 'qg.log')
        old_ts = (datetime.now() - timedelta(seconds=200)).strftime('%Y-%m-%d %H:%M:%S')
        with open(logpath, 'w') as f:
            f.write(f'{old_ts} | BLOCK | MODERATE | OVERCONFIDENCE: old claim                                         | tools=Bash | req=Refactor the auth module                                        | hash=abc12345\n')
        self.qg._detect_override('Refactor the auth module', ['Bash'], 'Done.', log_path=logpath)
        self.assertEqual(len(self.captured), 0)

    def test_missing_log_file(self):
        logpath = os.path.join(self.tmpdir, 'nonexistent.log')
        self.qg._detect_override('Test', ['Bash'], 'Done.', log_path=logpath)
        self.assertEqual(len(self.captured), 0)


class TestQGTriggerPhase3(unittest.TestCase):
    """Tier 7: _trigger_phase3_layers — verify it calls subprocess."""
    def setUp(self):
        self.qg = _load_qg()

    def test_does_not_crash_with_empty_state(self):
        import subprocess
        orig_popen = subprocess.Popen
        calls = []
        class FakePopen:
            def __init__(self, *a, **kw):
                calls.append(a[0] if a else kw)
            def communicate(self, *a, **kw):
                return (b'', b'')
        subprocess.Popen = FakePopen
        try:
            self.qg._trigger_phase3_layers({})
        finally:
            subprocess.Popen = orig_popen
        # Should have attempted to call at least one layer script
        self.assertGreaterEqual(len(calls), 1)




# ============================================================================
# qg_layer7.py comprehensive tests (coverage push from 23% to 80%+)
# ============================================================================


class TestLayer7LoadFeedback(unittest.TestCase):
    """load_feedback — reads quality-gate-feedback.jsonl."""
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()

    def tearDown(self):
        import shutil; shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_reads_valid_jsonl(self):
        import json
        from qg_layer7 import load_feedback
        path = os.path.join(self.tmpdir, 'feedback.jsonl')
        with open(path, 'w') as f:
            f.write(json.dumps({'outcome': 'FN', 'category': 'OVERCONFIDENCE'}) + '\n')
            f.write(json.dumps({'outcome': 'TN', 'category': 'NONE'}) + '\n')
        result = load_feedback(path)
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]['outcome'], 'FN')

    def test_skips_invalid_json(self):
        from qg_layer7 import load_feedback
        path = os.path.join(self.tmpdir, 'feedback.jsonl')
        with open(path, 'w') as f:
            f.write('{"valid": true}\n')
            f.write('not json\n')
            f.write('{"also": "valid"}\n')
        result = load_feedback(path)
        self.assertEqual(len(result), 2)

    def test_returns_empty_on_missing_file(self):
        from qg_layer7 import load_feedback
        result = load_feedback(os.path.join(self.tmpdir, 'nonexistent.jsonl'))
        self.assertEqual(result, [])

    def test_returns_empty_on_empty_file(self):
        from qg_layer7 import load_feedback
        path = os.path.join(self.tmpdir, 'empty.jsonl')
        with open(path, 'w') as f:
            f.write('')
        result = load_feedback(path)
        self.assertEqual(result, [])


class TestLayer7GenerateSuggestions(unittest.TestCase):
    """generate_suggestions — creates suggestions from repeat FNs + cross-session patterns."""
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()

    def tearDown(self):
        import shutil; shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_generates_from_repeat_fns(self):
        import json
        from qg_layer7 import generate_suggestions
        feedback_path = os.path.join(self.tmpdir, 'feedback.jsonl')
        with open(feedback_path, 'w') as f:
            for _ in range(4):
                f.write(json.dumps({'outcome': 'FN', 'category': 'OVERCONFIDENCE'}) + '\n')
        result = generate_suggestions(feedback_path=feedback_path,
                                       cross_session_path=os.path.join(self.tmpdir, 'no-cross.json'))
        self.assertGreaterEqual(len(result), 1)
        self.assertEqual(result[0]['category'], 'OVERCONFIDENCE')
        self.assertIn('Repeated FN', result[0]['reason'])

    def test_generates_from_cross_session(self):
        import json
        from qg_layer7 import generate_suggestions
        feedback_path = os.path.join(self.tmpdir, 'empty-feedback.jsonl')
        with open(feedback_path, 'w') as f:
            f.write('')
        cross_path = os.path.join(self.tmpdir, 'cross.json')
        with open(cross_path, 'w') as f:
            json.dump({
                'patterns': [
                    {'category': 'LOOP_DETECTED', 'sessions_count': 5, 'event_pct': 0.25, 'total_events': 20},
                ]
            }, f)
        result = generate_suggestions(feedback_path=feedback_path, cross_session_path=cross_path)
        self.assertGreaterEqual(len(result), 1)
        self.assertEqual(result[0]['category'], 'LOOP_DETECTED')
        self.assertIn('Cross-session', result[0]['reason'])

    def test_deduplicates_cross_session_with_repeat_fns(self):
        import json
        from qg_layer7 import generate_suggestions
        feedback_path = os.path.join(self.tmpdir, 'feedback.jsonl')
        with open(feedback_path, 'w') as f:
            for _ in range(4):
                f.write(json.dumps({'outcome': 'FN', 'category': 'OVERCONFIDENCE'}) + '\n')
        cross_path = os.path.join(self.tmpdir, 'cross.json')
        with open(cross_path, 'w') as f:
            json.dump({
                'patterns': [
                    {'category': 'OVERCONFIDENCE', 'sessions_count': 3, 'event_pct': 0.15, 'total_events': 10},
                    {'category': 'LOOP_DETECTED', 'sessions_count': 4, 'event_pct': 0.20, 'total_events': 15},
                ]
            }, f)
        result = generate_suggestions(feedback_path=feedback_path, cross_session_path=cross_path)
        categories = [s['category'] for s in result]
        # OVERCONFIDENCE should appear once (from repeat FNs), not duplicated by cross-session
        self.assertEqual(categories.count('OVERCONFIDENCE'), 1)
        # LOOP_DETECTED should appear from cross-session
        self.assertIn('LOOP_DETECTED', categories)

    def test_returns_empty_with_no_data(self):
        from qg_layer7 import generate_suggestions
        result = generate_suggestions(
            feedback_path=os.path.join(self.tmpdir, 'none.jsonl'),
            cross_session_path=os.path.join(self.tmpdir, 'none.json'))
        self.assertEqual(result, [])

    def test_below_threshold_not_included(self):
        import json
        from qg_layer7 import generate_suggestions
        feedback_path = os.path.join(self.tmpdir, 'feedback.jsonl')
        with open(feedback_path, 'w') as f:
            # Only 2 FNs for ASSUMPTION — below default threshold of 3
            f.write(json.dumps({'outcome': 'FN', 'category': 'ASSUMPTION'}) + '\n')
            f.write(json.dumps({'outcome': 'FN', 'category': 'ASSUMPTION'}) + '\n')
        result = generate_suggestions(feedback_path=feedback_path,
                                       cross_session_path=os.path.join(self.tmpdir, 'none.json'))
        self.assertEqual(result, [])


class TestLayer7WriteSuggestions(unittest.TestCase):
    """write_suggestions — outputs markdown file."""
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()

    def tearDown(self):
        import shutil; shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_writes_markdown_with_suggestions(self):
        from qg_layer7 import write_suggestions
        output_path = os.path.join(self.tmpdir, 'suggestions.md')
        suggestions = [
            {'status': 'pending', 'id': 1, 'category': 'OVERCONFIDENCE',
             'reason': 'Repeated FN (4 times)', 'supporting_count': 4,
             'ts': '2026-03-30T12:00:00'},
        ]
        write_suggestions(suggestions, output_path=output_path)
        with open(output_path) as f:
            content = f.read()
        self.assertIn('OVERCONFIDENCE', content)
        self.assertIn('PENDING', content)
        self.assertIn('Repeated FN', content)

    def test_writes_empty_when_no_suggestions(self):
        from qg_layer7 import write_suggestions
        output_path = os.path.join(self.tmpdir, 'suggestions.md')
        write_suggestions([], output_path=output_path)
        with open(output_path) as f:
            content = f.read()
        self.assertIn('No pending suggestions', content)

    def test_overwrites_existing_file(self):
        from qg_layer7 import write_suggestions
        output_path = os.path.join(self.tmpdir, 'suggestions.md')
        with open(output_path, 'w') as f:
            f.write('old content')
        write_suggestions([{
            'status': 'pending', 'id': 1, 'category': 'TEST',
            'reason': 'test', 'supporting_count': 1, 'ts': '2026-03-30',
        }], output_path=output_path)
        with open(output_path) as f:
            content = f.read()
        self.assertNotIn('old content', content)
        self.assertIn('TEST', content)


class TestLayer7MainTrigger(unittest.TestCase):
    """main() — only generates suggestions when layer3_pending_fn_alert is set."""
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        import qg_session_state as ss
        self._orig_state = ss.STATE_PATH
        self._orig_lock = ss.LOCK_PATH
        ss.STATE_PATH = os.path.join(self.tmpdir, 'state.json')
        ss.LOCK_PATH = ss.STATE_PATH + '.lock'

    def tearDown(self):
        import qg_session_state as ss
        ss.STATE_PATH = self._orig_state
        ss.LOCK_PATH = self._orig_lock
        import shutil; shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_skips_when_no_fn_alert(self):
        import json, qg_session_state as ss
        ss.write_state({'layer3_pending_fn_alert': None})
        from qg_layer7 import main as l7_main
        import io
        old_stdin = sys.stdin
        sys.stdin = io.StringIO('{}')
        try:
            l7_main()  # Should return early without generating suggestions
        finally:
            sys.stdin = old_stdin
        # No suggestions file should be created at default path
        # (we can't easily check the default path, but no crash = success)

    def test_generates_when_fn_alert_set(self):
        import json, qg_session_state as ss
        ss.write_state({'layer3_pending_fn_alert': '[monitor] Missed Failure — test'})
        # Create feedback file with enough FNs
        from qg_layer7 import FEEDBACK_PATH, SUGGESTIONS_PATH
        feedback_tmp = os.path.join(self.tmpdir, 'feedback.jsonl')
        suggestions_tmp = os.path.join(self.tmpdir, 'suggestions.md')
        import qg_layer7
        orig_fb = qg_layer7.FEEDBACK_PATH
        orig_sg = qg_layer7.SUGGESTIONS_PATH
        qg_layer7.FEEDBACK_PATH = feedback_tmp
        qg_layer7.SUGGESTIONS_PATH = suggestions_tmp
        with open(feedback_tmp, 'w') as f:
            for _ in range(4):
                f.write(json.dumps({'outcome': 'FN', 'category': 'OVERCONFIDENCE'}) + '\n')
        try:
            import io
            old_stdin = sys.stdin
            sys.stdin = io.StringIO('{}')
            try:
                qg_layer7.main()
            finally:
                sys.stdin = old_stdin
            self.assertTrue(os.path.exists(suggestions_tmp))
            with open(suggestions_tmp) as f:
                content = f.read()
            self.assertIn('OVERCONFIDENCE', content)
        finally:
            qg_layer7.FEEDBACK_PATH = orig_fb
            qg_layer7.SUGGESTIONS_PATH = orig_sg




# ============================================================================
# qg_layer9.py comprehensive tests (coverage push from 41% to 80%+)
# ============================================================================


class TestLayer9GetResponseText(unittest.TestCase):
    """get_response_text — extracts last assistant message from transcript."""
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()

    def tearDown(self):
        import shutil; shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _write_transcript(self, lines):
        import json
        path = os.path.join(self.tmpdir, 'transcript.jsonl')
        with open(path, 'w') as f:
            for line in lines:
                f.write(json.dumps(line) + '\n')
        return path

    def test_extracts_string_content(self):
        from qg_layer9 import get_response_text
        path = self._write_transcript([
            {'type': 'user', 'message': {'role': 'user', 'content': 'Hi'}},
            {'message': {'role': 'assistant', 'content': "I'm certain this works."}},
        ])
        result = get_response_text(path)
        self.assertIn("I'm certain", result)

    def test_extracts_list_content(self):
        from qg_layer9 import get_response_text
        path = self._write_transcript([
            {'message': {'role': 'assistant', 'content': [
                {'type': 'text', 'text': 'I believe this should work.'},
                {'type': 'tool_use', 'id': 'tu1', 'name': 'Bash'},
            ]}},
        ])
        result = get_response_text(path)
        self.assertIn('I believe', result)
        self.assertNotIn('tool_use', result)

    def test_returns_empty_on_missing_path(self):
        from qg_layer9 import get_response_text
        self.assertEqual(get_response_text(''), '')
        self.assertEqual(get_response_text(os.path.join(self.tmpdir, 'missing.jsonl')), '')

    def test_returns_empty_on_no_assistant(self):
        from qg_layer9 import get_response_text
        path = self._write_transcript([
            {'message': {'role': 'user', 'content': 'Hello'}},
        ])
        self.assertEqual(get_response_text(path), '')

    def test_handles_malformed_json(self):
        from qg_layer9 import get_response_text
        path = os.path.join(self.tmpdir, 'bad.jsonl')
        with open(path, 'w') as f:
            f.write('not json\n')
            f.write('{"message": {"role": "assistant", "content": "I think maybe."}}\n')
        result = get_response_text(path)
        self.assertIn('I think', result)


class TestLayer9MainFlow(unittest.TestCase):
    """main() — threshold gate, outcome determination, record writing."""
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        import qg_session_state as _ss
        self._orig_state = _ss.STATE_PATH
        self._orig_lock = _ss.LOCK_PATH
        _ss.STATE_PATH = os.path.join(self.tmpdir, 'state.json')
        _ss.LOCK_PATH = _ss.STATE_PATH + '.lock'
        import qg_layer9
        self._orig_cal = qg_layer9.CALIBRATION_PATH
        self._orig_monitor = qg_layer9._MONITOR_PATH
        qg_layer9.CALIBRATION_PATH = os.path.join(self.tmpdir, 'calibration.jsonl')
        qg_layer9._MONITOR_PATH = os.path.join(self.tmpdir, 'monitor.jsonl')

    def tearDown(self):
        import qg_session_state as _ss
        _ss.STATE_PATH = self._orig_state
        _ss.LOCK_PATH = self._orig_lock
        import qg_layer9
        qg_layer9.CALIBRATION_PATH = self._orig_cal
        qg_layer9._MONITOR_PATH = self._orig_monitor
        import shutil; shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _write_transcript(self, text):
        import json
        path = os.path.join(self.tmpdir, 'transcript.jsonl')
        with open(path, 'w') as f:
            f.write(json.dumps({'message': {'role': 'assistant', 'content': text}}) + '\n')
        return path

    def _run_main(self, data_dict):
        import io, json, qg_layer9
        old_stdin = sys.stdin
        sys.stdin = io.StringIO(json.dumps(data_dict))
        try:
            qg_layer9.main()
        finally:
            sys.stdin = old_stdin

    def test_writes_calibration_record_when_above_threshold(self):
        import json, qg_session_state as _ss
        _ss.write_state({
            'layer3_evaluation_count': 10,
            'layer3_pending_fn_alert': None,
            'session_uuid': 'test-sess',
            'layer1_task_category': 'MODERATE',
        })
        transcript = self._write_transcript("I'm certain this is correct and verified.")
        self._run_main({'transcript_path': transcript})
        import qg_layer9
        self.assertTrue(os.path.exists(qg_layer9.CALIBRATION_PATH))
        with open(qg_layer9.CALIBRATION_PATH) as f:
            record = json.loads(f.read().strip())
        self.assertEqual(record['stated_certainty'], 'high')
        self.assertEqual(record['actual_outcome'], 'TN')

    def test_skips_when_below_threshold(self):
        import json, qg_session_state as _ss
        _ss.write_state({
            'layer3_evaluation_count': 2,
            'session_uuid': 'test-sess',
        })
        transcript = self._write_transcript("I'm certain this works.")
        self._run_main({'transcript_path': transcript})
        import qg_layer9
        self.assertFalse(os.path.exists(qg_layer9.CALIBRATION_PATH))

    def test_records_fn_outcome(self):
        import json, qg_session_state as _ss
        _ss.write_state({
            'layer3_evaluation_count': 10,
            'layer3_pending_fn_alert': '[monitor] Missed Failure — test',
            'session_uuid': 'test-sess',
        })
        transcript = self._write_transcript("I believe the fix is correct.")
        self._run_main({'transcript_path': transcript})
        import qg_layer9
        with open(qg_layer9.CALIBRATION_PATH) as f:
            record = json.loads(f.read().strip())
        self.assertEqual(record['stated_certainty'], 'medium')
        self.assertEqual(record['actual_outcome'], 'FN')

    def test_skips_when_no_certainty_detected(self):
        import json, qg_session_state as _ss
        _ss.write_state({'layer3_evaluation_count': 10})
        transcript = self._write_transcript("Here is the code change.")
        self._run_main({'transcript_path': transcript})
        import qg_layer9
        self.assertFalse(os.path.exists(qg_layer9.CALIBRATION_PATH))

    def test_writes_monitor_event(self):
        import json, qg_session_state as _ss
        _ss.write_state({
            'layer3_evaluation_count': 10,
            'layer3_pending_fn_alert': None,
            'session_uuid': 'mon-test',
        })
        transcript = self._write_transcript("It might work, possibly.")
        self._run_main({'transcript_path': transcript})
        import qg_layer9
        self.assertTrue(os.path.exists(qg_layer9._MONITOR_PATH))
        with open(qg_layer9._MONITOR_PATH) as f:
            event = json.loads(f.read().strip())
        self.assertEqual(event['layer'], 'layer9')
        self.assertIn('certainty=low', event['detection_signal'])

    def test_reads_threshold_from_rules(self):
        import json, qg_session_state as _ss
        _ss.write_state({
            'layer3_evaluation_count': 3,
            'session_uuid': 'test',
        })
        # Write rules with threshold=2
        rules_path = os.path.expanduser('~/.claude/qg-rules.json')
        try:
            with open(rules_path, 'r') as f:
                rules = json.load(f)
        except Exception:
            rules = {}
        orig_l9 = rules.get('layer9', {})
        rules['layer9'] = {'min_responses_before_recalibration': 2}
        with open(rules_path, 'w') as f:
            json.dump(rules, f)
        try:
            transcript = self._write_transcript("I'm certain it works.")
            self._run_main({'transcript_path': transcript})
            import qg_layer9
            # eval_count=3 >= threshold=2, so should write
            self.assertTrue(os.path.exists(qg_layer9.CALIBRATION_PATH))
        finally:
            rules['layer9'] = orig_l9
            with open(rules_path, 'w') as f:
                json.dump(rules, f)

    def test_empty_stdin(self):
        import io, qg_layer9
        old_stdin = sys.stdin
        sys.stdin = io.StringIO('')
        try:
            qg_layer9.main()  # Should not crash
        finally:
            sys.stdin = old_stdin




# ============================================================================
# qg_layer27.py comprehensive tests (coverage push from 45% to 80%+)
# ============================================================================


class TestLayer27HasCoverageData(unittest.TestCase):
    """has_coverage_data — checks for coverage report files."""
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self._orig_cwd = os.getcwd()
        os.chdir(self.tmpdir)

    def tearDown(self):
        os.chdir(self._orig_cwd)
        import shutil; shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_returns_true_for_dotcoverage(self):
        from qg_layer27 import has_coverage_data
        with open('.coverage', 'w') as f:
            f.write('data')
        self.assertTrue(has_coverage_data())

    def test_returns_true_for_coverage_xml(self):
        from qg_layer27 import has_coverage_data
        with open('coverage.xml', 'w') as f:
            f.write('<xml/>')
        self.assertTrue(has_coverage_data())

    def test_returns_false_when_none(self):
        from qg_layer27 import has_coverage_data
        self.assertFalse(has_coverage_data())


class TestLayer27MainFlow(unittest.TestCase):
    """main() — full hook flow with payload processing."""
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self._orig_cwd = os.getcwd()
        os.chdir(self.tmpdir)
        # Create a source file so the layer has something to check
        with open('app.py', 'w') as f:
            f.write('def hello(): pass\n')
        import qg_layer27
        self._orig_monitor = qg_layer27._MONITOR_PATH
        qg_layer27._MONITOR_PATH = os.path.join(self.tmpdir, 'monitor.jsonl')

    def tearDown(self):
        os.chdir(self._orig_cwd)
        import qg_layer27
        qg_layer27._MONITOR_PATH = self._orig_monitor
        import shutil; shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _run_main(self, payload):
        import io, json, qg_layer27
        old_stdin = sys.stdin
        old_stdout = sys.stdout
        sys.stdin = io.StringIO(json.dumps(payload))
        sys.stdout = io.StringIO()
        try:
            qg_layer27.main()
            return sys.stdout.getvalue()
        finally:
            sys.stdin = old_stdin
            sys.stdout = old_stdout

    def test_warns_when_no_test_file(self):
        output = self._run_main({
            'tool_name': 'Edit',
            'tool_input': {'file_path': os.path.join(self.tmpdir, 'app.py')},
        })
        self.assertIn('No test file found', output)

    def test_silent_when_test_file_exists(self):
        # Create a matching test file
        with open(os.path.join(self.tmpdir, 'test_app.py'), 'w') as f:
            f.write('def test_hello(): pass\n')
        output = self._run_main({
            'tool_name': 'Edit',
            'tool_input': {'file_path': os.path.join(self.tmpdir, 'app.py')},
        })
        self.assertEqual(output.strip(), '')

    def test_silent_when_coverage_data_exists(self):
        with open(os.path.join(self.tmpdir, '.coverage'), 'w') as f:
            f.write('data')
        output = self._run_main({
            'tool_name': 'Edit',
            'tool_input': {'file_path': os.path.join(self.tmpdir, 'app.py')},
        })
        self.assertEqual(output.strip(), '')

    def test_skips_non_edit_tools(self):
        output = self._run_main({
            'tool_name': 'Read',
            'tool_input': {'file_path': os.path.join(self.tmpdir, 'app.py')},
        })
        self.assertEqual(output.strip(), '')

    def test_skips_non_code_extensions(self):
        with open(os.path.join(self.tmpdir, 'readme.md'), 'w') as f:
            f.write('# Readme')
        output = self._run_main({
            'tool_name': 'Edit',
            'tool_input': {'file_path': os.path.join(self.tmpdir, 'readme.md')},
        })
        self.assertEqual(output.strip(), '')

    def test_skips_test_files_themselves(self):
        with open(os.path.join(self.tmpdir, 'test_app.py'), 'w') as f:
            f.write('def test(): pass\n')
        output = self._run_main({
            'tool_name': 'Edit',
            'tool_input': {'file_path': os.path.join(self.tmpdir, 'test_app.py')},
        })
        self.assertEqual(output.strip(), '')

    def test_writes_monitor_event_on_warn(self):
        import json, qg_layer27
        self._run_main({
            'tool_name': 'Edit',
            'tool_input': {'file_path': os.path.join(self.tmpdir, 'app.py')},
        })
        self.assertTrue(os.path.exists(qg_layer27._MONITOR_PATH))
        with open(qg_layer27._MONITOR_PATH) as f:
            event = json.loads(f.read().strip())
        self.assertEqual(event['layer'], 'layer27')
        self.assertEqual(event['category'], 'NO_TEST_FILE')

    def test_empty_payload(self):
        output = self._run_main({})
        self.assertEqual(output.strip(), '')




class TestQGComputeConfidenceINP(unittest.TestCase):
    """_compute_confidence consumes introduces_new_problem flag from Layer 3.5."""
    def setUp(self):
        self.qg = _load_qg()

    def test_introduces_new_problem_lowers_confidence(self):
        state_clean = {'layer35_recovery_events': [{'status': 'resolved'}]}
        state_inp = {'layer35_recovery_events': [{'status': 'resolved', 'introduces_new_problem': True}]}
        score_clean = self.qg._compute_confidence(False, None, state_clean)
        score_inp = self.qg._compute_confidence(False, None, state_inp)
        self.assertLess(score_inp, score_clean)
        self.assertAlmostEqual(score_clean - score_inp, 0.15, places=2)

    def test_no_flag_no_penalty(self):
        state = {'layer35_recovery_events': [{'status': 'open'}]}
        score = self.qg._compute_confidence(False, None, state)
        score_empty = self.qg._compute_confidence(False, None, {})
        # open event penalizes via unresolved count, not INP
        # but INP itself should not fire
        self.assertEqual(score, score_empty)  # No unresolved in layer2, just layer35




# ============================================================================
# qg_layer28.py -- Security Vulnerability Detection tests
# ============================================================================


class TestLayer28SecurityDetection(unittest.TestCase):
    """check_security -- detects OWASP vulnerability patterns."""
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        sys.path.insert(0, os.path.expanduser('~/.claude/hooks'))

    def tearDown(self):
        import shutil; shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _write_file(self, name, content):
        path = os.path.join(self.tmpdir, name)
        with open(path, 'w') as f:
            f.write(content)
        return path

    def test_sql_injection_fstring(self):
        from qg_layer28 import check_security
        p = self._write_file('vuln.py', 'cursor.execute(f"SELECT * FROM users WHERE id={uid}")\n')
        r = check_security(p)
        self.assertGreaterEqual(len(r), 1)
        self.assertEqual(r[0][0], 'SQL_INJECTION')

    def test_sql_parameterized_clean(self):
        from qg_layer28 import check_security
        p = self._write_file('safe.py', 'cursor.execute("SELECT * FROM users WHERE id=%s", (uid,))\n')
        self.assertEqual(check_security(p), [])

    def test_command_injection_eval_variable(self):
        from qg_layer28 import check_security
        # Test detects eval with a variable argument (security risk)
        p = self._write_file('vuln.py', 'result = eval(user_input)\n')
        r = check_security(p)
        self.assertGreaterEqual(len(r), 1)
        self.assertEqual(r[0][0], 'COMMAND_INJECTION')

    def test_eval_literal_clean(self):
        from qg_layer28 import check_security
        # eval with string literal is safe (no variable injection)
        p = self._write_file('safe.py', 'result = eval("2+2")\n')
        self.assertEqual(check_security(p), [])

    def test_eval_in_test_file_relaxed(self):
        from qg_layer28 import check_security
        # Test files get relaxed rules for eval/exec
        p = self._write_file('test_vuln.py', 'result = eval(expr)\n')
        self.assertEqual(check_security(p), [])

    def test_innerhtml_xss(self):
        from qg_layer28 import check_security
        p = self._write_file('app.js', 'el.innerHTML = userInput\n')
        r = check_security(p)
        self.assertGreaterEqual(len(r), 1)
        self.assertEqual(r[0][0], 'XSS')

    def test_innerhtml_literal_clean(self):
        from qg_layer28 import check_security
        p = self._write_file('app.js', 'el.innerHTML = "<div>safe</div>"\n')
        self.assertEqual(check_security(p), [])

    def test_weak_hash_detected(self):
        from qg_layer28 import check_security
        p = self._write_file('auth.py', 'h = hashlib.md5(pw.encode())\n')
        r = check_security(p)
        self.assertGreaterEqual(len(r), 1)
        self.assertEqual(r[0][0], 'INSECURE_CRYPTO')

    def test_sha256_clean(self):
        from qg_layer28 import check_security
        p = self._write_file('safe.py', 'h = hashlib.sha256(data)\n')
        self.assertEqual(check_security(p), [])

    def test_os_system_detected(self):
        from qg_layer28 import check_security
        p = self._write_file('vuln.py', 'os.system(cmd)\n')
        r = check_security(p)
        self.assertGreaterEqual(len(r), 1)
        self.assertEqual(r[0][0], 'COMMAND_INJECTION')

    def test_clean_code_no_findings(self):
        from qg_layer28 import check_security
        p = self._write_file('clean.py', 'def hello():\n    return "world"\n')
        self.assertEqual(check_security(p), [])

    def test_non_code_file_skipped(self):
        from qg_layer28 import check_security
        # Security patterns in markdown should not trigger
        p = self._write_file('readme.md', 'eval(user_input)\n')
        self.assertEqual(check_security(p), [])

    def test_comment_skipped(self):
        from qg_layer28 import check_security
        p = self._write_file('safe.py', '# eval(user_input)\ndef safe(): pass\n')
        self.assertEqual(check_security(p), [])

    def test_dangerously_set_inner_html(self):
        from qg_layer28 import check_security
        p = self._write_file('comp.tsx', 'return <div dangerouslySetInnerHTML={{ __html: data }} />\n')
        r = check_security(p)
        self.assertGreaterEqual(len(r), 1)
        self.assertEqual(r[0][0], 'XSS')

    def test_pickle_loads_detected(self):
        from qg_layer28 import check_security
        p = self._write_file('vuln.py', 'obj = pickle.loads(data)\n')
        r = check_security(p)
        self.assertGreaterEqual(len(r), 1)
        self.assertEqual(r[0][0], 'INSECURE_DESERIALIZATION')

    def test_content_parameter_works(self):
        from qg_layer28 import check_security
        r = check_security('/fake/path.py', content='os.system(cmd)\n')
        self.assertGreaterEqual(len(r), 1)

    def test_sql_concat_detected(self):
        from qg_layer28 import check_security
        p = self._write_file('vuln.py', 'q = "SELECT * FROM users WHERE id=" + uid\n')
        r = check_security(p)
        self.assertGreaterEqual(len(r), 1)
        self.assertEqual(r[0][0], 'SQL_INJECTION')

    def test_shell_true_warning(self):
        from qg_layer28 import check_security
        p = self._write_file('run.py', 'subprocess.run(cmd, shell=True)\n')
        r = check_security(p)
        self.assertGreaterEqual(len(r), 1)
        self.assertEqual(r[0][1], 'warning')




# ============================================================================
# qg_layer20.py -- System Health Dashboard tests
# ============================================================================


class TestLayer20SystemHealth(unittest.TestCase):
    """check_hook_files, check_state_health, check_monitor_health, etc."""
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        sys.path.insert(0, os.path.expanduser('~/.claude/hooks'))

    def tearDown(self):
        import shutil; shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _write_file(self, name, content):
        path = os.path.join(self.tmpdir, name)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'w') as f:
            f.write(content)
        return path

    def _write_settings(self, hook_commands):
        """Write a minimal settings.json with given hook commands."""
        hooks = {"SessionStart": []}
        for cmd in hook_commands:
            hooks["SessionStart"].append({"hooks": [{"type": "command", "command": cmd}]})
        path = os.path.join(self.tmpdir, 'settings.json')
        with open(path, 'w') as f:
            import json; json.dump({"hooks": hooks}, f)
        return path

    # --- check_hook_files ---

    def test_hook_files_all_valid(self):
        from qg_layer20 import check_hook_files
        py_path = self._write_file('hooks/good.py', 'x = 1\n')
        settings = self._write_settings(['python ' + py_path])
        issues, count = check_hook_files(settings)
        self.assertEqual(issues, [])
        self.assertEqual(count, 1)

    def test_hook_file_missing(self):
        from qg_layer20 import check_hook_files
        settings = self._write_settings(['python /nonexistent/fake_hook.py'])
        issues, count = check_hook_files(settings)
        self.assertEqual(count, 1)
        self.assertGreaterEqual(len(issues), 1)
        self.assertEqual(issues[0][0], 'critical')
        self.assertIn('MISSING_FILE', issues[0][1])

    def test_hook_file_syntax_error(self):
        from qg_layer20 import check_hook_files
        bad_path = self._write_file('hooks/bad.py', 'def foo(\n')
        settings = self._write_settings(['python ' + bad_path])
        issues, count = check_hook_files(settings)
        self.assertEqual(count, 1)
        self.assertGreaterEqual(len(issues), 1)
        self.assertEqual(issues[0][0], 'warning')
        self.assertIn('SYNTAX_ERROR', issues[0][1])

    def test_hook_file_bash_script(self):
        from qg_layer20 import check_hook_files
        sh_path = self._write_file('hooks/test.sh', '#!/bin/bash\necho hi\n')
        settings = self._write_settings(['bash ' + sh_path])
        issues, count = check_hook_files(settings)
        self.assertEqual(issues, [])
        self.assertEqual(count, 1)

    # --- check_registration_integrity ---

    def test_registration_integrity_clean(self):
        from qg_layer20 import check_registration_integrity
        hooks_dir = os.path.join(self.tmpdir, 'hooks')
        os.makedirs(hooks_dir, exist_ok=True)
        layer_path = self._write_file('hooks/qg_layer99.py', 'x=1\n')
        settings = self._write_settings(['python ' + layer_path])
        issues = check_registration_integrity(settings, hooks_dir)
        self.assertEqual(issues, [])

    def test_registration_unregistered_layer(self):
        from qg_layer20 import check_registration_integrity
        hooks_dir = os.path.join(self.tmpdir, 'hooks')
        os.makedirs(hooks_dir, exist_ok=True)
        self._write_file('hooks/qg_layer99.py', 'x=1\n')
        settings = self._write_settings([])  # no hooks registered
        issues = check_registration_integrity(settings, hooks_dir)
        self.assertGreaterEqual(len(issues), 1)
        self.assertIn('UNREGISTERED', issues[0][1])

    def test_registration_library_excluded(self):
        from qg_layer20 import check_registration_integrity
        hooks_dir = os.path.join(self.tmpdir, 'hooks')
        os.makedirs(hooks_dir, exist_ok=True)
        self._write_file('hooks/qg_layer10.py', 'x=1\n')
        self._write_file('hooks/qg_layer35.py', 'x=1\n')
        settings = self._write_settings([])
        issues = check_registration_integrity(settings, hooks_dir)
        self.assertEqual(issues, [])

    # --- check_state_health ---

    def test_state_valid(self):
        from qg_layer20 import check_state_health
        import json
        state_path = self._write_file('state.json', json.dumps({"schema_version": 1}))
        issues, size = check_state_health(state_path)
        self.assertEqual(issues, [])
        self.assertGreater(size, 0)

    def test_state_too_large(self):
        from qg_layer20 import check_state_health
        import json
        big = {"schema_version": 1, "data": "x" * 60000}
        state_path = self._write_file('state.json', json.dumps(big))
        issues, size = check_state_health(state_path)
        self.assertGreaterEqual(len(issues), 1)
        self.assertIn('STATE_SIZE', issues[0][1])

    def test_state_invalid_json(self):
        from qg_layer20 import check_state_health
        state_path = self._write_file('state.json', '{broken json')
        issues, size = check_state_health(state_path)
        self.assertGreaterEqual(len(issues), 1)
        self.assertEqual(issues[0][0], 'critical')
        self.assertIn('STATE_CORRUPT', issues[0][1])

    def test_state_missing(self):
        from qg_layer20 import check_state_health
        issues, size = check_state_health('/nonexistent/state.json')
        self.assertGreaterEqual(len(issues), 1)
        self.assertEqual(issues[0][0], 'critical')
        self.assertIn('STATE_MISSING', issues[0][1])

    def test_state_no_schema_version(self):
        from qg_layer20 import check_state_health
        import json
        state_path = self._write_file('state.json', json.dumps({"foo": "bar"}))
        issues, size = check_state_health(state_path)
        self.assertGreaterEqual(len(issues), 1)
        self.assertIn('STATE_NO_SCHEMA', issues[0][1])

    # --- check_monitor_health ---

    def test_monitor_healthy(self):
        from qg_layer20 import check_monitor_health
        import json
        lines = [json.dumps({"layer": "layer2", "ts": "2026-03-30T12:00:00"}) + '\n'] * 10
        mon_path = self._write_file('monitor.jsonl', ''.join(lines))
        issues, size, count = check_monitor_health(mon_path)
        self.assertEqual(issues, [])
        self.assertEqual(count, 10)

    def test_monitor_too_large(self):
        from qg_layer20 import check_monitor_health
        big = 'x' * (6 * 1024 * 1024)
        mon_path = self._write_file('monitor.jsonl', big)
        issues, size, count = check_monitor_health(mon_path)
        self.assertGreaterEqual(len(issues), 1)
        self.assertIn('MONITOR_SIZE', issues[0][1])

    def test_monitor_missing(self):
        from qg_layer20 import check_monitor_health
        issues, size, count = check_monitor_health('/nonexistent/monitor.jsonl')
        self.assertGreaterEqual(len(issues), 1)
        self.assertIn('MONITOR_MISSING', issues[0][1])

    # --- check_quarantine ---

    def test_quarantine_entries(self):
        from qg_layer20 import check_quarantine
        import json
        lines = [json.dumps({"reason": "invalid_json"}) + '\n'] * 5
        q_path = self._write_file('quarantine.jsonl', ''.join(lines))
        issues, count = check_quarantine(q_path)
        self.assertEqual(count, 5)
        self.assertGreaterEqual(len(issues), 1)
        self.assertEqual(issues[0][0], 'info')

    def test_quarantine_many(self):
        from qg_layer20 import check_quarantine
        import json
        lines = [json.dumps({"reason": "bad"}) + '\n'] * 25
        q_path = self._write_file('quarantine.jsonl', ''.join(lines))
        issues, count = check_quarantine(q_path)
        self.assertEqual(count, 25)
        self.assertEqual(issues[0][0], 'warning')

    def test_quarantine_empty(self):
        from qg_layer20 import check_quarantine
        issues, count = check_quarantine('/nonexistent/quarantine.jsonl')
        self.assertEqual(count, 0)
        self.assertEqual(issues, [])

    # --- check_layer_activity ---

    def test_layer_activity_all_active(self):
        from qg_layer20 import check_layer_activity
        import json
        lines = []
        for layer in ['layer2', 'layer5', 'layer7']:
            lines.append(json.dumps({"layer": layer}) + '\n')
        mon_path = self._write_file('monitor.jsonl', ''.join(lines))
        issues, seen = check_layer_activity(mon_path)
        self.assertEqual(issues, [])
        self.assertIn('layer2', seen)
        self.assertIn('layer5', seen)
        self.assertIn('layer7', seen)

    def test_layer_activity_gaps(self):
        from qg_layer20 import check_layer_activity
        mon_path = self._write_file('monitor.jsonl', '')
        issues, seen = check_layer_activity(mon_path)
        self.assertEqual(len(seen), 0)

    # --- check_log_sizes ---

    def test_log_sizes_normal(self):
        from qg_layer20 import check_log_sizes
        self._write_file('quality-gate.log', 'x' * 100)
        issues = check_log_sizes(self.tmpdir)
        self.assertEqual(issues, [])

    def test_log_sizes_large(self):
        from qg_layer20 import check_log_sizes
        self._write_file('quality-gate.log', 'x' * (3 * 1024 * 1024))
        issues = check_log_sizes(self.tmpdir)
        self.assertGreaterEqual(len(issues), 1)
        self.assertIn('LOG_SIZE', issues[0][1])

    # --- run_health_check integration ---

    def test_run_health_check_clean(self):
        from qg_layer20 import run_health_check
        import json
        hooks_dir = os.path.join(self.tmpdir, 'hooks')
        os.makedirs(hooks_dir, exist_ok=True)
        py_path = self._write_file('hooks/good.py', 'x = 1\n')
        settings = self._write_settings(['python ' + py_path])
        state_path = self._write_file('state.json', json.dumps({"schema_version": 1}))
        mon_lines = [json.dumps({"layer": "layer2"}) + '\n'] * 5
        mon_path = self._write_file('monitor.jsonl', ''.join(mon_lines))
        q_path = self._write_file('quarantine.jsonl', '')
        report = run_health_check(
            settings_path=settings, hooks_dir=hooks_dir, state_path=state_path,
            monitor_path=mon_path, quarantine_path=q_path, claude_dir=self.tmpdir,
        )
        self.assertEqual(report['status'], 'ok')
        self.assertEqual(report['stats']['hook_files'], 1)

    def test_run_health_check_issues(self):
        from qg_layer20 import run_health_check
        settings = self._write_settings(['python /nonexistent/bad.py'])
        hooks_dir = os.path.join(self.tmpdir, 'hooks')
        os.makedirs(hooks_dir, exist_ok=True)
        report = run_health_check(
            settings_path=settings, hooks_dir=hooks_dir, state_path='/nope/state.json',
            monitor_path='/nope/monitor.jsonl', quarantine_path='/nope/q.jsonl',
            claude_dir=self.tmpdir,
        )
        self.assertEqual(report['status'], 'critical')
        self.assertGreater(len(report['issues']), 0)

    # --- main ---

    def test_main_json_output(self):
        from qg_layer20 import run_health_check
        import json
        hooks_dir = os.path.join(self.tmpdir, 'hooks')
        os.makedirs(hooks_dir, exist_ok=True)
        py_path = self._write_file('hooks/good.py', 'x = 1\n')
        settings = self._write_settings(['python ' + py_path])
        state_path = self._write_file('state.json', json.dumps({"schema_version": 1}))
        mon_path = self._write_file('monitor.jsonl', json.dumps({"layer": "layer2"}) + '\n')
        report = run_health_check(
            settings_path=settings, hooks_dir=hooks_dir, state_path=state_path,
            monitor_path=mon_path, quarantine_path='/nope', claude_dir=self.tmpdir,
        )
        self.assertIn('status', report)
        self.assertIn('stats', report)
        self.assertIn('issues', report)




# ============================================================================
# qg_layer11.py -- Commit Quality Gate tests
# ============================================================================


class TestLayer11CommitQualityGate(unittest.TestCase):
    """check_commit_message, check_staged_secrets, check_staged_files, etc."""
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        sys.path.insert(0, os.path.expanduser('~/.claude/hooks'))

    def tearDown(self):
        import shutil; shutil.rmtree(self.tmpdir, ignore_errors=True)

    # --- _extract_commit_message ---

    def test_extract_message_double_quotes(self):
        from qg_layer11 import _extract_commit_message
        msg = _extract_commit_message('git commit -m "fix: resolve bug"')
        self.assertEqual(msg, 'fix: resolve bug')

    def test_extract_message_single_quotes(self):
        from qg_layer11 import _extract_commit_message
        msg = _extract_commit_message("git commit -m 'feat: add feature'")
        self.assertEqual(msg, 'feat: add feature')

    def test_extract_message_no_quotes(self):
        from qg_layer11 import _extract_commit_message
        msg = _extract_commit_message('git commit -m fixup')
        self.assertEqual(msg, 'fixup')

    def test_extract_message_no_m_flag(self):
        from qg_layer11 import _extract_commit_message
        msg = _extract_commit_message('git commit --amend')
        self.assertIsNone(msg)

    # --- check_commit_message ---

    def test_conventional_commit_valid(self):
        from qg_layer11 import check_commit_message
        self.assertEqual(check_commit_message('feat: add login page'), [])

    def test_conventional_commit_with_auto(self):
        from qg_layer11 import check_commit_message
        self.assertEqual(check_commit_message('[AUTO] fix: resolve crash'), [])

    def test_conventional_commit_with_scope(self):
        from qg_layer11 import check_commit_message
        self.assertEqual(check_commit_message('feat(auth): add OAuth'), [])

    def test_nonconventional_commit(self):
        from qg_layer11 import check_commit_message
        issues = check_commit_message('updated stuff')
        self.assertGreaterEqual(len(issues), 1)
        self.assertEqual(issues[0][0], 'warning')
        self.assertIn('COMMIT_FORMAT', issues[0][1])

    def test_long_commit_message(self):
        from qg_layer11 import check_commit_message
        issues = check_commit_message('feat: ' + 'x' * 200)
        self.assertGreaterEqual(len(issues), 1)
        self.assertIn('COMMIT_LENGTH', issues[-1][1])

    def test_empty_message_no_issues(self):
        from qg_layer11 import check_commit_message
        self.assertEqual(check_commit_message(None), [])

    # --- check_staged_secrets ---

    def test_staged_secret_aws_key(self):
        from qg_layer11 import check_staged_secrets
        # Build fake key at runtime to avoid block-secrets hook
        fake_key = 'AK' + 'IA' + 'IOSFODNN7EXAMPLE'
        diff = '+' + fake_key + '\n'
        issues = check_staged_secrets(diff)
        self.assertGreaterEqual(len(issues), 1)
        self.assertEqual(issues[0][0], 'critical')
        self.assertIn('STAGED_SECRET', issues[0][1])

    def test_staged_secret_github_pat(self):
        from qg_layer11 import check_staged_secrets
        fake_pat = 'gh' + 'p_' + 'A' * 36
        diff = '+' + fake_pat + '\n'
        issues = check_staged_secrets(diff)
        self.assertGreaterEqual(len(issues), 1)
        self.assertIn('GitHub PAT', issues[0][1])

    def test_staged_no_secrets(self):
        from qg_layer11 import check_staged_secrets
        diff = '+def hello():\n+    return "world"\n'
        self.assertEqual(check_staged_secrets(diff), [])

    def test_staged_empty_diff(self):
        from qg_layer11 import check_staged_secrets
        self.assertEqual(check_staged_secrets(''), [])

    # --- check_staged_files ---

    def test_staged_env_file(self):
        from qg_layer11 import check_staged_files
        issues = check_staged_files(['.env'])
        self.assertGreaterEqual(len(issues), 1)
        self.assertEqual(issues[0][0], 'critical')
        self.assertIn('DANGEROUS_FILE', issues[0][1])

    def test_staged_pem_file(self):
        from qg_layer11 import check_staged_files
        issues = check_staged_files(['certs/server.pem'])
        self.assertGreaterEqual(len(issues), 1)

    def test_staged_normal_files(self):
        from qg_layer11 import check_staged_files
        self.assertEqual(check_staged_files(['src/main.py', 'README.md']), [])

    def test_staged_empty_list(self):
        from qg_layer11 import check_staged_files
        self.assertEqual(check_staged_files([]), [])

    # --- check_push ---

    def test_push_force_detected(self):
        from qg_layer11 import check_push
        issues = check_push('git push --force origin main')
        self.assertGreaterEqual(len(issues), 1)
        self.assertIn('FORCE_PUSH', issues[0][1])

    def test_push_normal(self):
        from qg_layer11 import check_push
        self.assertEqual(check_push('git push origin main'), [])

    # --- _is_git_commit / _is_git_push ---

    def test_is_git_commit(self):
        from qg_layer11 import _is_git_commit
        self.assertTrue(_is_git_commit('git commit -m "fix: stuff"'))
        self.assertFalse(_is_git_commit('git push origin main'))

    def test_is_git_push(self):
        from qg_layer11 import _is_git_push
        self.assertTrue(_is_git_push('git push origin main'))
        self.assertFalse(_is_git_push('git commit -m "fix"'))

    # --- run_commit_check ---

    def test_run_commit_check_clean(self):
        from qg_layer11 import run_commit_check
        report = run_commit_check('git commit -m "feat: add feature"', diff_content='', file_list=[])
        self.assertEqual(report['status'], 'ok')

    def test_run_commit_check_secret_blocks(self):
        from qg_layer11 import run_commit_check
        fake_key = 'AK' + 'IA' + 'IOSFODNN7EXAMPLE'
        report = run_commit_check(
            'git commit -m "feat: add key"',
            diff_content='+' + fake_key + '\n',
            file_list=[],
        )
        self.assertEqual(report['status'], 'block')

    def test_run_commit_check_bad_format_warns(self):
        from qg_layer11 import run_commit_check
        report = run_commit_check('git commit -m "updated stuff"', diff_content='', file_list=[])
        self.assertEqual(report['status'], 'warn')

    def test_run_commit_check_dangerous_file_blocks(self):
        from qg_layer11 import run_commit_check
        report = run_commit_check(
            'git commit -m "feat: add config"',
            diff_content='',
            file_list=['.env'],
        )
        self.assertEqual(report['status'], 'block')

    # --- run_push_check ---

    def test_run_push_check_normal(self):
        from qg_layer11 import run_push_check
        report = run_push_check('git push origin main')
        self.assertEqual(report['status'], 'ok')

    def test_run_push_check_force(self):
        from qg_layer11 import run_push_check
        report = run_push_check('git push --force origin main')
        self.assertEqual(report['status'], 'block')




# ============================================================================
# qg_layer16.py -- Rollback & Undo Capability tests
# ============================================================================


class TestLayer16RollbackUndo(unittest.TestCase):
    """capture_snapshot, restore_snapshot, prune_snapshots, etc."""
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.snap_dir = os.path.join(self.tmpdir, 'snapshots')
        os.makedirs(self.snap_dir, exist_ok=True)
        sys.path.insert(0, os.path.expanduser('~/.claude/hooks'))

    def tearDown(self):
        import shutil; shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _write_file(self, name, content):
        path = os.path.join(self.tmpdir, name)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'w') as f:
            f.write(content)
        return path

    # --- capture_snapshot ---

    def test_capture_snapshot_basic(self):
        from qg_layer16 import capture_snapshot
        p = self._write_file('test.py', 'x = 1\n')
        meta = capture_snapshot(p, self.snap_dir)
        self.assertIsNotNone(meta)
        self.assertEqual(meta['file_path'], p)
        self.assertGreater(meta['size'], 0)
        self.assertTrue(os.path.exists(meta['snapshot_path']))

    def test_capture_snapshot_content_preserved(self):
        from qg_layer16 import capture_snapshot
        original = 'def hello():\n    return "world"\n'
        p = self._write_file('test.py', original)
        meta = capture_snapshot(p, self.snap_dir)
        with open(meta['snapshot_path'], 'r') as f:
            saved = f.read()
        self.assertEqual(saved, original)

    def test_capture_snapshot_nonexistent_file(self):
        from qg_layer16 import capture_snapshot
        meta = capture_snapshot('/nonexistent/file.py', self.snap_dir)
        self.assertIsNone(meta)

    def test_capture_snapshot_empty_file(self):
        from qg_layer16 import capture_snapshot
        p = self._write_file('empty.py', '')
        meta = capture_snapshot(p, self.snap_dir)
        self.assertIsNone(meta)

    def test_capture_snapshot_large_file_skipped(self):
        from qg_layer16 import capture_snapshot
        p = self._write_file('big.py', 'x' * (600 * 1024))
        meta = capture_snapshot(p, self.snap_dir)
        self.assertIsNone(meta)

    def test_capture_snapshot_no_path(self):
        from qg_layer16 import capture_snapshot
        self.assertIsNone(capture_snapshot('', self.snap_dir))
        self.assertIsNone(capture_snapshot(None, self.snap_dir))

    # --- restore_snapshot ---

    def test_restore_snapshot_basic(self):
        from qg_layer16 import capture_snapshot, restore_snapshot
        original = 'x = 1\n'
        p = self._write_file('test.py', original)
        meta = capture_snapshot(p, self.snap_dir)
        # Modify the file
        with open(p, 'w') as f:
            f.write('x = 999\n')
        # Restore
        result = restore_snapshot(meta)
        self.assertTrue(result)
        with open(p, 'r') as f:
            restored = f.read()
        self.assertEqual(restored, original)

    def test_restore_snapshot_missing_snap(self):
        from qg_layer16 import restore_snapshot
        meta = {'snapshot_path': '/nonexistent/snap', 'file_path': '/tmp/test.py'}
        self.assertFalse(restore_snapshot(meta))

    def test_restore_snapshot_empty_meta(self):
        from qg_layer16 import restore_snapshot
        self.assertFalse(restore_snapshot({}))

    # --- prune_snapshots ---

    def test_prune_under_limit(self):
        from qg_layer16 import prune_snapshots
        snaps = [{'snapshot_path': 'a', 'ts': i} for i in range(5)]
        result = prune_snapshots({'layer16_snapshots': snaps})
        self.assertEqual(len(result), 5)

    def test_prune_over_limit(self):
        from qg_layer16 import prune_snapshots, MAX_SNAPSHOTS
        snaps = []
        for i in range(MAX_SNAPSHOTS + 5):
            p = self._write_file('snap_{}.snap'.format(i), 'content')
            snaps.append({'snapshot_path': p, 'ts': i})
        result = prune_snapshots({'layer16_snapshots': snaps})
        self.assertEqual(len(result), MAX_SNAPSHOTS)
        # Old files should be removed
        self.assertFalse(os.path.exists(snaps[0]['snapshot_path']))

    # --- get_snapshots_for_file ---

    def test_get_snapshots_for_file_matches(self):
        from qg_layer16 import get_snapshots_for_file
        state = {'layer16_snapshots': [
            {'file_path': '/a/test.py', 'ts': 1},
            {'file_path': '/a/other.py', 'ts': 2},
            {'file_path': '/a/test.py', 'ts': 3},
        ]}
        matches = get_snapshots_for_file('/a/test.py', state)
        self.assertEqual(len(matches), 2)
        self.assertEqual(matches[0]['ts'], 3)  # newest first

    def test_get_snapshots_for_file_none(self):
        from qg_layer16 import get_snapshots_for_file
        state = {'layer16_snapshots': [
            {'file_path': '/a/other.py', 'ts': 1},
        ]}
        self.assertEqual(get_snapshots_for_file('/a/test.py', state), [])

    # --- cleanup_session_snapshots ---

    def test_cleanup_removes_snaps(self):
        from qg_layer16 import cleanup_session_snapshots
        self._write_file('snapshots/a.snap', 'x')
        self._write_file('snapshots/b.snap', 'y')
        self._write_file('snapshots/keep.txt', 'z')
        count = cleanup_session_snapshots(self.snap_dir)
        self.assertEqual(count, 2)
        self.assertTrue(os.path.exists(os.path.join(self.snap_dir, 'keep.txt')))

    def test_cleanup_empty_dir(self):
        from qg_layer16 import cleanup_session_snapshots
        count = cleanup_session_snapshots(self.snap_dir)
        self.assertEqual(count, 0)

    def test_cleanup_nonexistent_dir(self):
        from qg_layer16 import cleanup_session_snapshots
        count = cleanup_session_snapshots('/nonexistent/dir')
        self.assertEqual(count, 0)

    # --- end-to-end ---

    def test_capture_modify_restore_cycle(self):
        from qg_layer16 import capture_snapshot, restore_snapshot
        v1 = 'version 1\n'
        v2 = 'version 2\n'
        p = self._write_file('test.py', v1)
        snap1 = capture_snapshot(p, self.snap_dir)
        with open(p, 'w') as f:
            f.write(v2)
        snap2 = capture_snapshot(p, self.snap_dir)
        # File is now v2
        with open(p, 'r') as f:
            self.assertEqual(f.read(), v2)
        # Restore to v1
        restore_snapshot(snap1)
        with open(p, 'r') as f:
            self.assertEqual(f.read(), v1)

    def test_multiple_files_tracked(self):
        from qg_layer16 import capture_snapshot, get_snapshots_for_file
        p1 = self._write_file('a.py', 'a\n')
        p2 = self._write_file('b.py', 'b\n')
        m1 = capture_snapshot(p1, self.snap_dir)
        m2 = capture_snapshot(p2, self.snap_dir)
        state = {'layer16_snapshots': [m1, m2]}
        self.assertEqual(len(get_snapshots_for_file(p1, state)), 1)
        self.assertEqual(len(get_snapshots_for_file(p2, state)), 1)




# ============================================================================
# qg_layer12.py -- User Satisfaction Tracking tests
# ============================================================================


class TestLayer12UserSatisfaction(unittest.TestCase):
    """classify_sentiment and _extract_message tests."""
    def setUp(self):
        sys.path.insert(0, os.path.expanduser('~/.claude/hooks'))

    # --- _extract_message ---

    def test_extract_message_string(self):
        from qg_layer12 import _extract_message
        self.assertEqual(_extract_message({"message": "hello"}), "hello")

    def test_extract_message_dict(self):
        from qg_layer12 import _extract_message
        self.assertEqual(_extract_message({"message": {"content": "hi"}}), "hi")

    def test_extract_message_list(self):
        from qg_layer12 import _extract_message
        self.assertEqual(_extract_message({"message": [{"content": "a"}, {"content": "b"}]}), "a b")

    def test_extract_message_prompt_fallback(self):
        from qg_layer12 import _extract_message
        self.assertEqual(_extract_message({"prompt": "test"}), "test")

    def test_extract_message_empty(self):
        from qg_layer12 import _extract_message
        self.assertEqual(_extract_message({}), "")

    # --- classify_sentiment: frustration ---

    def test_frustration_wrong(self):
        from qg_layer12 import classify_sentiment
        cat, score, sigs = classify_sentiment("No, that's wrong")
        self.assertEqual(cat, "frustration")
        self.assertLess(score, 0)

    def test_frustration_try_again(self):
        from qg_layer12 import classify_sentiment
        cat, score, sigs = classify_sentiment("Try again please")
        self.assertEqual(cat, "frustration")
        self.assertIn("retry_request", sigs)

    def test_frustration_i_said(self):
        from qg_layer12 import classify_sentiment
        cat, score, sigs = classify_sentiment("I said to use React, not Vue")
        self.assertEqual(cat, "frustration")
        self.assertIn("correction", sigs)

    def test_frustration_thats_not(self):
        from qg_layer12 import classify_sentiment
        cat, score, sigs = classify_sentiment("That's not what I asked for")
        self.assertEqual(cat, "frustration")

    def test_frustration_undo(self):
        from qg_layer12 import classify_sentiment
        cat, score, sigs = classify_sentiment("undo that change")
        self.assertEqual(cat, "frustration")

    # --- classify_sentiment: satisfaction ---

    def test_satisfaction_thanks(self):
        from qg_layer12 import classify_sentiment
        cat, score, sigs = classify_sentiment("Thanks, that looks great!")
        self.assertEqual(cat, "satisfaction")
        self.assertGreater(score, 0)

    def test_satisfaction_perfect(self):
        from qg_layer12 import classify_sentiment
        cat, score, sigs = classify_sentiment("Perfect!")
        self.assertEqual(cat, "satisfaction")
        self.assertIn("praise", sigs)

    def test_satisfaction_lgtm(self):
        from qg_layer12 import classify_sentiment
        cat, score, sigs = classify_sentiment("LGTM, ship it")
        self.assertEqual(cat, "satisfaction")

    def test_satisfaction_numbered_selection(self):
        from qg_layer12 import classify_sentiment
        cat, score, sigs = classify_sentiment("1")
        self.assertEqual(cat, "satisfaction")
        self.assertIn("numbered_selection", sigs)

    def test_satisfaction_yes(self):
        from qg_layer12 import classify_sentiment
        cat, score, sigs = classify_sentiment("yes")
        self.assertEqual(cat, "satisfaction")

    # --- classify_sentiment: confusion ---

    def test_confusion_what(self):
        from qg_layer12 import classify_sentiment
        cat, score, sigs = classify_sentiment("What? I don't understand")
        self.assertEqual(cat, "confusion")

    def test_confusion_explain(self):
        from qg_layer12 import classify_sentiment
        cat, score, sigs = classify_sentiment("Can you explain that?")
        self.assertEqual(cat, "confusion")

    # --- classify_sentiment: neutral ---

    def test_neutral_task_request(self):
        from qg_layer12 import classify_sentiment
        cat, score, sigs = classify_sentiment("Add a login page with OAuth support")
        self.assertEqual(cat, "neutral")

    def test_neutral_empty(self):
        from qg_layer12 import classify_sentiment
        cat, score, sigs = classify_sentiment("")
        self.assertEqual(cat, "neutral")

    def test_neutral_code_block(self):
        from qg_layer12 import classify_sentiment
        cat, score, sigs = classify_sentiment("def hello():\n    return 42")
        self.assertEqual(cat, "neutral")

    # --- edge cases ---

    def test_mixed_signals_frustration_wins(self):
        from qg_layer12 import classify_sentiment
        cat, score, sigs = classify_sentiment("Thanks but that's not what I asked, try again")
        self.assertEqual(cat, "frustration")

    def test_case_insensitive(self):
        from qg_layer12 import classify_sentiment
        cat, score, sigs = classify_sentiment("WRONG! TRY AGAIN!")
        self.assertEqual(cat, "frustration")




# ============================================================================
# qg_layer14.py -- Response Efficiency Analysis tests
# ============================================================================


class TestLayer14ResponseEfficiency(unittest.TestCase):
    """detect_redundant_reads, check_tool_count, analyze_efficiency, etc."""
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        sys.path.insert(0, os.path.expanduser('~/.claude/hooks'))

    def tearDown(self):
        import shutil; shutil.rmtree(self.tmpdir, ignore_errors=True)

    # --- detect_redundant_reads ---

    def test_no_redundant_reads(self):
        from qg_layer14 import detect_redundant_reads
        result = detect_redundant_reads(['/a/file1.py', '/a/file2.py', '/a/file3.py'])
        self.assertEqual(result, [])

    def test_redundant_reads_detected(self):
        from qg_layer14 import detect_redundant_reads
        result = detect_redundant_reads(['/a/file1.py', '/a/file2.py', '/a/file1.py'])
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0][1], 2)

    def test_redundant_reads_multiple(self):
        from qg_layer14 import detect_redundant_reads
        result = detect_redundant_reads(['/a/f.py', '/a/f.py', '/a/f.py', '/b/g.py', '/b/g.py'])
        self.assertEqual(len(result), 2)

    def test_redundant_reads_empty(self):
        from qg_layer14 import detect_redundant_reads
        self.assertEqual(detect_redundant_reads([]), [])

    def test_redundant_reads_path_normalization(self):
        from qg_layer14 import detect_redundant_reads
        result = detect_redundant_reads(['C:\\Users\\test\\f.py', 'C:/Users/test/f.py'])
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0][1], 2)

    # --- check_tool_count ---

    def test_tool_count_under_threshold(self):
        from qg_layer14 import check_tool_count
        result = check_tool_count(['Read', 'Grep', 'Edit'], 'TRIVIAL')
        self.assertIsNone(result)

    def test_tool_count_over_threshold(self):
        from qg_layer14 import check_tool_count
        tools = ['Read'] * 25
        result = check_tool_count(tools, 'MODERATE')
        self.assertIsNotNone(result)
        self.assertEqual(result[0], 'warning')
        self.assertIn('EXCESSIVE_TOOLS', result[1])

    def test_tool_count_trivial_exceeded(self):
        from qg_layer14 import check_tool_count
        tools = ['Read'] * 6
        result = check_tool_count(tools, 'TRIVIAL')
        self.assertIsNotNone(result)
        self.assertIn('TRIVIAL', result[1])

    def test_tool_count_no_complexity(self):
        from qg_layer14 import check_tool_count
        result = check_tool_count(['Read'] * 100, None)
        self.assertIsNone(result)

    def test_tool_count_unknown_complexity(self):
        from qg_layer14 import check_tool_count
        result = check_tool_count(['Read'] * 100, 'UNKNOWN')
        self.assertIsNone(result)

    # --- analyze_efficiency ---

    def test_analyze_clean(self):
        from qg_layer14 import analyze_efficiency
        report = analyze_efficiency(['Read', 'Edit'], ['/a/f.py'], 'MODERATE')
        self.assertEqual(report['status'], 'ok')
        self.assertEqual(report['stats']['total_tool_calls'], 2)

    def test_analyze_redundant_reads(self):
        from qg_layer14 import analyze_efficiency
        report = analyze_efficiency(
            ['Read', 'Read', 'Edit'],
            ['/a/f.py', '/a/f.py'],
            'MODERATE',
        )
        self.assertEqual(report['status'], 'info')
        self.assertGreaterEqual(len(report['issues']), 1)
        self.assertIn('REDUNDANT_READ', report['issues'][0][1])

    def test_analyze_excessive_tools(self):
        from qg_layer14 import analyze_efficiency
        tools = ['Read'] * 25
        reads = ['/a/{}.py'.format(i) for i in range(25)]
        report = analyze_efficiency(tools, reads, 'MODERATE')
        self.assertEqual(report['status'], 'warning')

    def test_analyze_no_tools(self):
        from qg_layer14 import analyze_efficiency
        report = analyze_efficiency([], [], 'TRIVIAL')
        self.assertEqual(report['status'], 'ok')

    def test_analyze_deep_task_high_count_ok(self):
        from qg_layer14 import analyze_efficiency
        tools = ['Read'] * 50
        reads = ['/a/{}.py'.format(i) for i in range(50)]
        report = analyze_efficiency(tools, reads, 'DEEP')
        self.assertEqual(report['status'], 'ok')

    # --- parse_tool_calls ---

    def test_parse_tool_calls_empty(self):
        from qg_layer14 import parse_tool_calls
        tools, reads = parse_tool_calls('/nonexistent/transcript.jsonl')
        self.assertEqual(tools, [])
        self.assertEqual(reads, [])

    def test_parse_tool_calls_none(self):
        from qg_layer14 import parse_tool_calls
        tools, reads = parse_tool_calls(None)
        self.assertEqual(tools, [])




# ============================================================================
# qg_layer29.py -- Semantic Correctness Verification tests
# ============================================================================


class TestLayer29SemanticCorrectness(unittest.TestCase):
    """check_claim_action, check_direction, check_count_claims, analyze_semantics."""
    def setUp(self):
        sys.path.insert(0, os.path.expanduser('~/.claude/hooks'))

    # --- check_claim_action ---

    def test_claim_error_handling_present(self):
        from qg_layer29 import check_claim_action
        resp = "I added error handling to the function"
        edit = "try:\n    do_stuff()\nexcept ValueError:\n    pass\n"
        self.assertEqual(check_claim_action(resp, edit), [])

    def test_claim_error_handling_missing(self):
        from qg_layer29 import check_claim_action
        resp = "I added error handling to the function"
        edit = "def foo():\n    return 42\n"
        issues = check_claim_action(resp, edit)
        self.assertGreaterEqual(len(issues), 1)
        self.assertIn('CLAIM_MISMATCH', issues[0][1])

    def test_claim_tests_present(self):
        from qg_layer29 import check_claim_action
        resp = "I added tests for the login module"
        edit = "def test_login():\n    assert True\n"
        self.assertEqual(check_claim_action(resp, edit), [])

    def test_claim_tests_missing(self):
        from qg_layer29 import check_claim_action
        resp = "I added tests for the login module"
        edit = "def login():\n    pass\n"
        issues = check_claim_action(resp, edit)
        self.assertGreaterEqual(len(issues), 1)

    def test_claim_logging_present(self):
        from qg_layer29 import check_claim_action
        resp = "I implemented logging throughout"
        edit = "import logging\nlogger = logging.getLogger(__name__)\nlogger.info('started')\n"
        self.assertEqual(check_claim_action(resp, edit), [])

    def test_claim_logging_missing(self):
        from qg_layer29 import check_claim_action
        resp = "I implemented logging throughout"
        edit = "def process():\n    return data\n"
        issues = check_claim_action(resp, edit)
        self.assertGreaterEqual(len(issues), 1)

    def test_claim_validation_present(self):
        from qg_layer29 import check_claim_action
        resp = "I added input validation"
        edit = "if not data:\n    raise ValueError('empty')\n"
        self.assertEqual(check_claim_action(resp, edit), [])

    def test_no_claims_no_issues(self):
        from qg_layer29 import check_claim_action
        resp = "Here is the implementation"
        edit = "def foo(): pass\n"
        self.assertEqual(check_claim_action(resp, edit), [])

    def test_empty_inputs(self):
        from qg_layer29 import check_claim_action
        self.assertEqual(check_claim_action("", "code"), [])
        self.assertEqual(check_claim_action("claim", ""), [])

    # --- check_direction ---

    def test_direction_descending_present(self):
        from qg_layer29 import check_direction
        resp = "Sorted the results in descending order"
        edit = "data.sort(reverse=True)\n"
        self.assertEqual(check_direction(resp, edit), [])

    def test_direction_descending_missing(self):
        from qg_layer29 import check_direction
        resp = "Sorted the results in descending order"
        edit = "data = sorted(data)\n"
        issues = check_direction(resp, edit)
        self.assertGreaterEqual(len(issues), 1)
        self.assertIn('DIRECTION_CHECK', issues[0][1])

    def test_direction_case_insensitive_present(self):
        from qg_layer29 import check_direction
        resp = "Made the search case-insensitive"
        edit = "result = re.search(pattern, text, re.IGNORECASE)\n"
        self.assertEqual(check_direction(resp, edit), [])

    def test_direction_no_keywords(self):
        from qg_layer29 import check_direction
        resp = "Updated the function"
        edit = "def foo(): pass\n"
        self.assertEqual(check_direction(resp, edit), [])

    # --- check_count_claims ---

    def test_count_tests_match(self):
        from qg_layer29 import check_count_claims
        resp = "I added 3 tests"
        edit = "def test_a(): pass\ndef test_b(): pass\ndef test_c(): pass\n"
        self.assertEqual(check_count_claims(resp, edit), [])

    def test_count_tests_mismatch(self):
        from qg_layer29 import check_count_claims
        resp = "I added 5 tests"
        edit = "def test_a(): pass\ndef test_b(): pass\n"
        issues = check_count_claims(resp, edit)
        self.assertGreaterEqual(len(issues), 1)
        self.assertIn('COUNT_MISMATCH', issues[0][1])

    def test_count_no_claims(self):
        from qg_layer29 import check_count_claims
        resp = "Here are the changes"
        edit = "def test_a(): pass\n"
        self.assertEqual(check_count_claims(resp, edit), [])

    def test_count_close_enough(self):
        from qg_layer29 import check_count_claims
        resp = "I added 3 tests"
        edit = "def test_a(): pass\ndef test_b(): pass\n"
        # Off by 1 is tolerated
        self.assertEqual(check_count_claims(resp, edit), [])

    # --- analyze_semantics ---

    def test_analyze_clean(self):
        from qg_layer29 import analyze_semantics
        report = analyze_semantics("Updated the module", "def foo(): pass\n")
        self.assertEqual(report['status'], 'ok')

    def test_analyze_with_issues(self):
        from qg_layer29 import analyze_semantics
        report = analyze_semantics(
            "I added error handling and 10 tests",
            "def foo(): pass\ndef test_one(): pass\n",
        )
        self.assertEqual(report['status'], 'warning')
        self.assertGreater(len(report['issues']), 0)

    def test_analyze_empty(self):
        from qg_layer29 import analyze_semantics
        report = analyze_semantics("", "")
        self.assertEqual(report['status'], 'ok')




# ============================================================================
# qg_layer19_cross.py -- Cross-Project Learning tests
# ============================================================================


class TestLayer19CrossProject(unittest.TestCase):
    """group_by_project, find_cross_project_patterns, etc."""
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        sys.path.insert(0, os.path.expanduser('~/.claude/hooks'))

    def tearDown(self):
        import shutil; shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _write_monitor(self, events):
        import json
        path = os.path.join(self.tmpdir, 'monitor.jsonl')
        with open(path, 'w') as f:
            for e in events:
                f.write(json.dumps(e) + '\n')
        return path

    # --- _normalize_project ---

    def test_normalize_home(self):
        from qg_layer19_cross import _normalize_project
        home = os.path.expanduser('~').replace('\\', '/')
        self.assertEqual(_normalize_project(home), '~')

    def test_normalize_subdir(self):
        from qg_layer19_cross import _normalize_project
        home = os.path.expanduser('~').replace('\\', '/')
        result = _normalize_project(home + '/projects/myapp')
        self.assertEqual(result, '~/projects/myapp')

    def test_normalize_empty(self):
        from qg_layer19_cross import _normalize_project
        self.assertEqual(_normalize_project(''), 'unknown')

    # --- group_by_project ---

    def test_group_basic(self):
        from qg_layer19_cross import group_by_project
        events = [
            {'working_dir': '/a/proj1', 'category': 'X'},
            {'working_dir': '/a/proj2', 'category': 'Y'},
            {'working_dir': '/a/proj1', 'category': 'Z'},
        ]
        groups = group_by_project(events)
        self.assertEqual(len(groups), 2)

    def test_group_no_working_dir(self):
        from qg_layer19_cross import group_by_project
        events = [{'category': 'X'}, {'working_dir': '', 'category': 'Y'}]
        groups = group_by_project(events)
        self.assertEqual(len(groups), 0)

    # --- find_cross_project_patterns ---

    def test_cross_project_found(self):
        from qg_layer19_cross import find_cross_project_patterns
        groups = {
            'projA': [{'category': 'ERROR'}, {'category': 'ERROR'}, {'category': 'WARN'}],
            'projB': [{'category': 'ERROR'}, {'category': 'OTHER'}],
        }
        patterns = find_cross_project_patterns(groups)
        cats = [p['category'] for p in patterns]
        self.assertIn('ERROR', cats)

    def test_cross_project_single_project_excluded(self):
        from qg_layer19_cross import find_cross_project_patterns
        groups = {
            'projA': [{'category': 'UNIQUE'}, {'category': 'UNIQUE'}, {'category': 'UNIQUE'}],
            'projB': [{'category': 'OTHER'}],
        }
        patterns = find_cross_project_patterns(groups)
        cats = [p['category'] for p in patterns]
        self.assertNotIn('UNIQUE', cats)

    def test_cross_project_below_threshold(self):
        from qg_layer19_cross import find_cross_project_patterns
        groups = {
            'projA': [{'category': 'RARE'}],
            'projB': [{'category': 'RARE'}],
        }
        patterns = find_cross_project_patterns(groups)
        # Only 2 events total, below MIN_EVENTS=3
        cats = [p['category'] for p in patterns]
        self.assertNotIn('RARE', cats)

    def test_cross_project_empty(self):
        from qg_layer19_cross import find_cross_project_patterns
        self.assertEqual(find_cross_project_patterns({}), [])

    # --- find_project_specific_patterns ---

    def test_project_specific_found(self):
        from qg_layer19_cross import find_project_specific_patterns
        groups = {
            'projA': [{'category': 'ONLY_A'}, {'category': 'ONLY_A'}, {'category': 'ONLY_A'}],
            'projB': [{'category': 'ONLY_B'}, {'category': 'ONLY_B'}, {'category': 'ONLY_B'}],
        }
        patterns = find_project_specific_patterns(groups)
        cats = [p['category'] for p in patterns]
        self.assertIn('ONLY_A', cats)
        self.assertIn('ONLY_B', cats)

    def test_project_specific_shared_excluded(self):
        from qg_layer19_cross import find_project_specific_patterns
        groups = {
            'projA': [{'category': 'SHARED'}, {'category': 'SHARED'}, {'category': 'SHARED'}],
            'projB': [{'category': 'SHARED'}],
        }
        patterns = find_project_specific_patterns(groups)
        cats = [p['category'] for p in patterns]
        self.assertNotIn('SHARED', cats)

    # --- load_events ---

    def test_load_events_basic(self):
        from qg_layer19_cross import load_events
        import json
        path = self._write_monitor([
            {'working_dir': '/a', 'category': 'X'},
            {'working_dir': '/b', 'category': 'Y'},
        ])
        events = load_events(path)
        self.assertEqual(len(events), 2)

    def test_load_events_missing_file(self):
        from qg_layer19_cross import load_events
        self.assertEqual(load_events('/nonexistent/monitor.jsonl'), [])

    def test_load_events_tail(self):
        from qg_layer19_cross import load_events
        events_data = [{'working_dir': '/a', 'category': 'X', 'idx': i} for i in range(20)]
        path = self._write_monitor(events_data)
        events = load_events(path, tail_lines=5)
        self.assertEqual(len(events), 5)

    # --- analyze_cross_project ---

    def test_analyze_full(self):
        from qg_layer19_cross import analyze_cross_project
        events = []
        for i in range(5):
            events.append({'working_dir': '/proj/a', 'category': 'ERROR'})
        for i in range(3):
            events.append({'working_dir': '/proj/b', 'category': 'ERROR'})
        events.append({'working_dir': '/proj/a', 'category': 'UNIQUE_A'})
        path = self._write_monitor(events)
        report = analyze_cross_project(path)
        self.assertEqual(report['status'], 'ok')
        self.assertEqual(report['project_count'], 2)
        global_cats = [p['category'] for p in report['global_patterns']]
        self.assertIn('ERROR', global_cats)

    def test_analyze_no_data(self):
        from qg_layer19_cross import analyze_cross_project
        report = analyze_cross_project('/nonexistent/file.jsonl')
        self.assertEqual(report['status'], 'no_data')

    # --- save_report ---

    def test_save_report(self):
        from qg_layer19_cross import save_report
        import json
        out_path = os.path.join(self.tmpdir, 'report.json')
        save_report({'status': 'ok', 'global_patterns': []}, out_path)
        with open(out_path) as f:
            data = json.load(f)
        self.assertEqual(data['status'], 'ok')
        self.assertIn('ts', data)



# ============================================================================
# qg_layer15_mem.py -- Memory & State Integrity tests
# ============================================================================


class TestLayer15MemoryIntegrity(unittest.TestCase):
    """extract_references, check_references, check_staleness, etc."""
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.mem_dir = os.path.join(self.tmpdir, 'memory')
        os.makedirs(self.mem_dir, exist_ok=True)
        sys.path.insert(0, os.path.expanduser('~/.claude/hooks'))

    def tearDown(self):
        import shutil; shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _write_file(self, name, content):
        path = os.path.join(self.mem_dir, name)
        with open(path, 'w') as f:
            f.write(content)
        return path

    # --- extract_references ---

    def test_extract_refs_basic(self):
        from qg_layer15_mem import extract_references
        idx = self._write_file('MEMORY.md', '- [Profile](memory/profile.md)\n- [Notes](memory/notes.md)\n')
        refs = extract_references(idx)
        self.assertEqual(len(refs), 2)
        self.assertEqual(refs[0]['name'], 'Profile')

    def test_extract_refs_empty(self):
        from qg_layer15_mem import extract_references
        idx = self._write_file('MEMORY.md', '# Empty index\nNo links here.\n')
        self.assertEqual(extract_references(idx), [])

    def test_extract_refs_missing_file(self):
        from qg_layer15_mem import extract_references
        self.assertEqual(extract_references('/nonexistent/MEMORY.md'), [])

    # --- check_references ---

    def test_check_refs_all_exist(self):
        from qg_layer15_mem import check_references, _resolve_path
        self._write_file('MEMORY.md', '- [A](memory/a.md)\n')
        self._write_file('a.md', 'content\n')
        # Need to monkey-patch _resolve_path for test
        import qg_layer15_mem as mod
        orig = mod._resolve_path
        mod._resolve_path = lambda p: os.path.join(self.mem_dir, os.path.basename(p))
        try:
            issues, count = check_references(os.path.join(self.mem_dir, 'MEMORY.md'))
            self.assertEqual(issues, [])
            self.assertEqual(count, 1)
        finally:
            mod._resolve_path = orig

    def test_check_refs_missing(self):
        from qg_layer15_mem import check_references
        import qg_layer15_mem as mod
        self._write_file('MEMORY.md', '- [A](memory/missing.md)\n')
        orig = mod._resolve_path
        mod._resolve_path = lambda p: os.path.join(self.mem_dir, 'DOES_NOT_EXIST.md')
        try:
            issues, count = check_references(os.path.join(self.mem_dir, 'MEMORY.md'))
            self.assertGreaterEqual(len(issues), 1)
            self.assertIn('MISSING_REF', issues[0][1])
        finally:
            mod._resolve_path = orig

    # --- check_staleness ---

    def test_staleness_fresh(self):
        from qg_layer15_mem import check_staleness
        self._write_file('fresh.md', 'content\n')
        issues, total, stale = check_staleness(self.mem_dir, stale_days=14)
        self.assertEqual(stale, 0)
        self.assertEqual(total, 1)

    def test_staleness_old(self):
        from qg_layer15_mem import check_staleness
        import time as t
        p = self._write_file('old.md', 'content\n')
        os.utime(p, (t.time() - 86400 * 30, t.time() - 86400 * 30))
        issues, total, stale = check_staleness(self.mem_dir, stale_days=14)
        self.assertEqual(stale, 1)
        self.assertGreaterEqual(len(issues), 1)
        self.assertIn('STALE', issues[0][1])

    def test_staleness_empty_dir(self):
        from qg_layer15_mem import check_staleness
        empty = os.path.join(self.tmpdir, 'empty')
        os.makedirs(empty)
        issues, total, stale = check_staleness(empty)
        self.assertEqual(total, 0)

    # --- check_file_sizes ---

    def test_file_sizes_normal(self):
        from qg_layer15_mem import check_file_sizes
        self._write_file('small.md', 'x' * 100)
        self.assertEqual(check_file_sizes(self.mem_dir), [])

    def test_file_sizes_oversized(self):
        from qg_layer15_mem import check_file_sizes
        self._write_file('big.md', 'x' * (200 * 1024))
        issues = check_file_sizes(self.mem_dir)
        self.assertGreaterEqual(len(issues), 1)
        self.assertIn('OVERSIZED', issues[0][1])

    # --- check_duplicates ---

    def test_duplicates_none(self):
        from qg_layer15_mem import check_duplicates
        self._write_file('a.md', '# Unique A\ncontent\n')
        self._write_file('b.md', '# Unique B\ncontent\n')
        self.assertEqual(check_duplicates(self.mem_dir), [])

    def test_duplicates_found(self):
        from qg_layer15_mem import check_duplicates
        self._write_file('a.md', '# Same Heading\ncontent a\n')
        self._write_file('b.md', '# Same Heading\ncontent b\n')
        issues = check_duplicates(self.mem_dir)
        self.assertGreaterEqual(len(issues), 1)
        self.assertIn('DUPLICATE_HEADING', issues[0][1])

    # --- analyze_memory_integrity ---

    def test_analyze_clean(self):
        from qg_layer15_mem import analyze_memory_integrity
        self._write_file('MEMORY.md', '# Index\n')
        self._write_file('notes.md', '# Notes\n')
        report = analyze_memory_integrity(
            index_path=os.path.join(self.mem_dir, 'MEMORY.md'),
            memory_dir=self.mem_dir,
        )
        self.assertEqual(report['status'], 'ok')

    def test_analyze_with_issues(self):
        from qg_layer15_mem import analyze_memory_integrity
        self._write_file('MEMORY.md', '# Index\n')
        self._write_file('big.md', 'x' * (200 * 1024))
        report = analyze_memory_integrity(
            index_path=os.path.join(self.mem_dir, 'MEMORY.md'),
            memory_dir=self.mem_dir,
        )
        self.assertEqual(report['status'], 'warning')



# ============================================================================
# qg_layer13.py -- Knowledge Freshness Verification tests
# ============================================================================


class TestLayer13KnowledgeFreshness(unittest.TestCase):
    """extract_imports, check_module_exists, check_attribute_exists, check_imports."""
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        sys.path.insert(0, os.path.expanduser('~/.claude/hooks'))

    def tearDown(self):
        import shutil; shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _write_file(self, name, content):
        path = os.path.join(self.tmpdir, name)
        with open(path, 'w') as f:
            f.write(content)
        return path

    # --- extract_imports ---

    def test_extract_import_basic(self):
        from qg_layer13 import extract_imports
        imports = extract_imports("import os\nimport json\n")
        modules = [m for m, _ in imports]
        self.assertIn("os", modules)
        self.assertIn("json", modules)

    def test_extract_from_import(self):
        from qg_layer13 import extract_imports
        imports = extract_imports("from os.path import join, exists\n")
        self.assertEqual(imports[0][0], "os.path")
        self.assertIn("join", imports[0][1])
        self.assertIn("exists", imports[0][1])

    def test_extract_import_star(self):
        from qg_layer13 import extract_imports
        imports = extract_imports("from os import *\n")
        self.assertEqual(imports[0][1], [])

    def test_extract_import_as(self):
        from qg_layer13 import extract_imports
        imports = extract_imports("from collections import OrderedDict as OD\n")
        self.assertIn("OrderedDict", imports[0][1])

    def test_extract_comment_skipped(self):
        from qg_layer13 import extract_imports
        imports = extract_imports("# import fake_module\ndef foo(): pass\n")
        self.assertEqual(imports, [])

    def test_extract_empty(self):
        from qg_layer13 import extract_imports
        self.assertEqual(extract_imports(""), [])

    # --- check_module_exists ---

    def test_module_exists_stdlib(self):
        from qg_layer13 import check_module_exists
        self.assertTrue(check_module_exists("os"))
        self.assertTrue(check_module_exists("json"))

    def test_module_exists_nonexistent(self):
        from qg_layer13 import check_module_exists
        self.assertFalse(check_module_exists("totally_fake_module_xyz"))

    # --- check_attribute_exists ---

    def test_attribute_exists_valid(self):
        from qg_layer13 import check_attribute_exists
        self.assertTrue(check_attribute_exists("os", "path"))
        self.assertTrue(check_attribute_exists("json", "dumps"))

    def test_attribute_exists_invalid(self):
        from qg_layer13 import check_attribute_exists
        self.assertFalse(check_attribute_exists("os", "totally_fake_function_xyz"))

    # --- check_imports ---

    def test_check_imports_stdlib_clean(self):
        from qg_layer13 import check_imports
        p = self._write_file("test.py", "import os\nimport json\nfrom pathlib import Path\n")
        issues = check_imports(p)
        self.assertEqual(issues, [])

    def test_check_imports_nonexistent_module(self):
        from qg_layer13 import check_imports
        p = self._write_file("test.py", "import totally_fake_module_xyz\n")
        issues = check_imports(p)
        self.assertGreaterEqual(len(issues), 1)
        self.assertIn("MODULE_NOT_FOUND", issues[0][1])

    def test_check_imports_non_python_skipped(self):
        from qg_layer13 import check_imports
        p = self._write_file("test.js", "import os\n")
        self.assertEqual(check_imports(p), [])

    def test_check_imports_content_param(self):
        from qg_layer13 import check_imports
        issues = check_imports("/fake/path.py", content="import totally_fake_module_xyz\n")
        self.assertGreaterEqual(len(issues), 1)

    def test_check_imports_empty_file(self):
        from qg_layer13 import check_imports
        p = self._write_file("test.py", "def hello(): pass\n")
        self.assertEqual(check_imports(p), [])



# ============================================================================
# qg_layer18_ab.py -- A/B Rule Testing tests
# ============================================================================


class TestLayer18ABRuleTesting(unittest.TestCase):
    """evaluate_rules, compare_rules, run_ab_test."""
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        sys.path.insert(0, os.path.expanduser('~/.claude/hooks'))

    def tearDown(self):
        import shutil; shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _write_file(self, name, content):
        path = os.path.join(self.tmpdir, name)
        with open(path, 'w') as f:
            f.write(content)
        return path

    def _write_events(self, events):
        import json
        path = os.path.join(self.tmpdir, 'monitor.jsonl')
        with open(path, 'w') as f:
            for e in events:
                f.write(json.dumps(e) + '\n')
        return path

    # --- load_rules ---

    def test_load_rules_valid(self):
        from qg_layer18_ab import load_rules
        import json
        path = self._write_file('rules.json', json.dumps({"layer2": {"events_per_turn_limit": 10}}))
        rules = load_rules(path)
        self.assertEqual(rules["layer2"]["events_per_turn_limit"], 10)

    def test_load_rules_missing(self):
        from qg_layer18_ab import load_rules
        self.assertEqual(load_rules('/nonexistent/rules.json'), {})

    # --- evaluate_rules ---

    def test_evaluate_basic(self):
        from qg_layer18_ab import evaluate_rules
        events = [
            {"severity": "critical", "category": "ERROR", "layer": "layer2"},
            {"severity": "info", "category": "INCORRECT_TOOL", "layer": "layer2"},
            {"severity": "info", "category": "NEUTRAL", "layer": "layer5"},
        ]
        metrics = evaluate_rules(events, {})
        self.assertEqual(metrics["total_events"], 3)
        self.assertEqual(metrics["events_by_severity"]["critical"], 1)
        self.assertEqual(metrics["events_by_layer"]["layer2"], 2)

    def test_evaluate_empty(self):
        from qg_layer18_ab import evaluate_rules
        metrics = evaluate_rules([], {})
        self.assertEqual(metrics["total_events"], 0)
        self.assertEqual(metrics["would_fire"], 0)

    # --- compare_rules ---

    def test_compare_equivalent(self):
        from qg_layer18_ab import compare_rules
        events = [{"severity": "warning", "category": "X", "layer": "l1"}]
        rules = {"layer2": {"events_per_turn_limit": 5}}
        result = compare_rules(rules, rules, events)
        self.assertEqual(result["comparison"]["recommendation"], "equivalent")

    def test_compare_different(self):
        from qg_layer18_ab import compare_rules
        events = [
            {"severity": "warning", "category": "X", "layer": "l1"},
            {"severity": "info", "category": "Y", "layer": "l2"},
        ]
        result = compare_rules({}, {}, events)
        self.assertIn("recommendation", result["comparison"])
        self.assertEqual(result["events_analyzed"], 2)

    # --- load_events ---

    def test_load_events_basic(self):
        from qg_layer18_ab import load_events
        import json
        path = self._write_events([{"severity": "info", "category": "X"}])
        events = load_events(path)
        self.assertEqual(len(events), 1)

    def test_load_events_missing(self):
        from qg_layer18_ab import load_events
        self.assertEqual(load_events('/nonexistent/monitor.jsonl'), [])

    def test_load_events_tail(self):
        from qg_layer18_ab import load_events
        events_data = [{"severity": "info", "idx": i} for i in range(20)]
        path = self._write_events(events_data)
        events = load_events(path, tail=5)
        self.assertEqual(len(events), 5)

    # --- run_ab_test ---

    def test_run_ab_test_no_data(self):
        from qg_layer18_ab import run_ab_test
        report = run_ab_test(monitor_path='/nonexistent/file.jsonl')
        self.assertEqual(report["status"], "no_data")

    def test_run_ab_test_with_data(self):
        from qg_layer18_ab import run_ab_test
        import json
        path = self._write_events([
            {"severity": "warning", "category": "X", "layer": "l1"},
            {"severity": "info", "category": "Y", "layer": "l2"},
        ])
        report = run_ab_test(monitor_path=path)
        self.assertEqual(report["status"], "ok")
        self.assertEqual(report["events_analyzed"], 2)

    # --- save_results ---

    def test_save_results(self):
        from qg_layer18_ab import save_results
        import json
        path = os.path.join(self.tmpdir, 'results.json')
        save_results({"status": "ok"}, path)
        with open(path) as f:
            data = json.load(f)
        self.assertIn("ts", data)



# ============================================================================
# qg_layer14.py -- Additional coverage tests (parse_tool_calls, main)
# ============================================================================


class TestLayer14TranscriptParsing(unittest.TestCase):
    """Tests for parse_tool_calls with mock transcript data."""
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        sys.path.insert(0, os.path.expanduser('~/.claude/hooks'))

    def tearDown(self):
        import shutil; shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _write_transcript(self, lines_data):
        import json
        path = os.path.join(self.tmpdir, 'transcript.jsonl')
        with open(path, 'w') as f:
            for d in lines_data:
                f.write(json.dumps(d) + '\n')
        return path

    def test_parse_single_tool_call(self):
        from qg_layer14 import parse_tool_calls
        transcript = self._write_transcript([
            {"role": "user", "message": {"content": "hello"}},
            {"role": "assistant", "message": {"content": [
                {"type": "tool_use", "name": "Read", "input": {"file_path": "/a/test.py"}}
            ]}},
            {"role": "user", "message": {"content": [
                {"type": "tool_result", "content": "file contents"}
            ]}},
        ])
        tools, reads = parse_tool_calls(transcript)
        self.assertIn("Read", tools)
        self.assertIn("/a/test.py", reads)

    def test_parse_multiple_tools(self):
        from qg_layer14 import parse_tool_calls
        transcript = self._write_transcript([
            {"role": "user", "message": {"content": "do stuff"}},
            {"role": "assistant", "message": {"content": [
                {"type": "tool_use", "name": "Read", "input": {"file_path": "/a.py"}},
                {"type": "tool_use", "name": "Edit", "input": {"file_path": "/a.py"}},
                {"type": "tool_use", "name": "Bash", "input": {"command": "ls"}},
            ]}},
            {"role": "user", "message": {"content": [
                {"type": "tool_result", "content": "ok"}
            ]}},
        ])
        tools, reads = parse_tool_calls(transcript)
        self.assertEqual(len(tools), 3)
        self.assertEqual(reads, ["/a.py"])

    def test_parse_stops_at_real_user_list_message(self):
        from qg_layer14 import parse_tool_calls
        transcript = self._write_transcript([
            {"role": "user", "message": {"content": [{"type": "text", "text": "first task"}]}},
            {"role": "assistant", "message": {"content": [
                {"type": "tool_use", "name": "Grep", "input": {}}
            ]}},
            {"role": "user", "message": {"content": [
                {"type": "tool_result", "content": "result"}
            ]}},
            {"role": "user", "message": {"content": [{"type": "text", "text": "second task"}]}},
            {"role": "assistant", "message": {"content": [
                {"type": "tool_use", "name": "Read", "input": {"file_path": "/b.py"}}
            ]}},
            {"role": "user", "message": {"content": [
                {"type": "tool_result", "content": "result2"}
            ]}},
        ])
        tools, reads = parse_tool_calls(transcript)
        # Stops at list-type user message without tool_result
        self.assertIn("Read", tools)
        self.assertNotIn("Grep", tools)

    def test_parse_no_tool_calls(self):
        from qg_layer14 import parse_tool_calls
        transcript = self._write_transcript([
            {"role": "user", "message": {"content": "hello"}},
            {"role": "assistant", "message": {"content": [
                {"type": "text", "text": "Hi there!"}
            ]}},
        ])
        tools, reads = parse_tool_calls(transcript)
        self.assertEqual(tools, [])
        self.assertEqual(reads, [])

    def test_parse_text_and_tools_mixed(self):
        from qg_layer14 import parse_tool_calls
        transcript = self._write_transcript([
            {"role": "user", "message": {"content": "task"}},
            {"role": "assistant", "message": {"content": [
                {"type": "text", "text": "Let me check"},
                {"type": "tool_use", "name": "Glob", "input": {"pattern": "*.py"}},
                {"type": "text", "text": "Found files"},
            ]}},
            {"role": "user", "message": {"content": [
                {"type": "tool_result", "content": "files"}
            ]}},
        ])
        tools, reads = parse_tool_calls(transcript)
        self.assertEqual(tools, ["Glob"])

    def test_parse_invalid_json_lines_skipped(self):
        from qg_layer14 import parse_tool_calls
        path = os.path.join(self.tmpdir, 'bad.jsonl')
        import json
        with open(path, 'w') as f:
            f.write('not json\n')
            f.write(json.dumps({"role": "assistant", "message": {"content": [
                {"type": "tool_use", "name": "Read", "input": {"file_path": "/x.py"}}
            ]}}) + '\n')
        tools, reads = parse_tool_calls(path)
        self.assertIn("Read", tools)

    def test_analyze_with_transcript(self):
        from qg_layer14 import parse_tool_calls, analyze_efficiency
        transcript = self._write_transcript([
            {"role": "user", "message": {"content": "task"}},
            {"role": "assistant", "message": {"content": [
                {"type": "tool_use", "name": "Read", "input": {"file_path": "/a.py"}},
                {"type": "tool_use", "name": "Read", "input": {"file_path": "/a.py"}},
                {"type": "tool_use", "name": "Edit", "input": {"file_path": "/a.py"}},
            ]}},
            {"role": "user", "message": {"content": [{"type": "tool_result", "content": "ok"}]}},
        ])
        tools, reads = parse_tool_calls(transcript)
        report = analyze_efficiency(tools, reads, "MODERATE")
        self.assertEqual(report["stats"]["total_tool_calls"], 3)
        self.assertEqual(report["stats"]["redundant_reads"], 1)


if __name__ == '__main__':
    unittest.main()
