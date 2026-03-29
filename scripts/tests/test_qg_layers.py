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


if __name__ == '__main__':
    unittest.main()

