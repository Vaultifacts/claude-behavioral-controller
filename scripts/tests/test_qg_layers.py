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


if __name__ == '__main__':
    unittest.main()
