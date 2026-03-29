import sys, os, time, tempfile, unittest
sys.path.insert(0, os.path.expanduser('~/.claude/hooks'))
import qg_session_state as ss

class TestSessionState(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mktemp(suffix='.json')
        ss.STATE_PATH = self.tmp
        ss.LOCK_PATH = self.tmp + '.lock'
        for p in [self.tmp, self.tmp + '.lock']:
            try: os.unlink(p)
            except FileNotFoundError: pass

    def tearDown(self):
        for p in [self.tmp, self.tmp + '.lock']:
            try: os.unlink(p)
            except FileNotFoundError: pass

    def test_read_returns_empty_when_file_missing(self):
        state = ss.read_state()
        self.assertIsNone(state['session_uuid'])
        self.assertEqual(state['schema_version'], 1)
        self.assertIn('notification_pending_criticals', state)

    def test_write_and_read_roundtrip(self):
        state = ss.read_state()
        state['session_uuid'] = 'test-abc'
        ss.write_state(state)
        result = ss.read_state()
        self.assertEqual(result['session_uuid'], 'test-abc')

    def test_staleness_resets_on_old_file(self):
        state = ss.read_state()
        state['session_uuid'] = 'old-uuid'
        state['session_start_ts'] = time.time() - 90000  # 25h ago
        ss.write_state(state)
        result = ss.read_state()
        self.assertIsNone(result['session_uuid'])

    def test_update_state_partial(self):
        ss.update_state(session_uuid='xyz-789', active_task_id='t1')
        result = ss.read_state()
        self.assertEqual(result['session_uuid'], 'xyz-789')
        self.assertEqual(result['active_task_id'], 't1')

    def test_lock_silently_fails_on_contention(self):
        open(self.tmp + '.lock', 'w').close()  # Pre-create lock
        state = ss.read_state()
        state['session_uuid'] = 'should-not-persist'
        ss.write_state(state)  # Should silently fail — lock is held
        result = ss.read_state()
        self.assertIsNone(result['session_uuid'])  # Not written
        os.unlink(self.tmp + '.lock')

    def test_migration_adds_missing_fields(self):
        import json
        with open(self.tmp, 'w') as f:
            json.dump({'schema_version': 0, 'session_uuid': 'v0',
                       'session_start_ts': time.time()}, f)
        result = ss.read_state()
        self.assertIn('layer2_unresolved_events', result)
        self.assertIn('notification_pending_criticals', result)
        self.assertEqual(result['session_uuid'], 'v0')

if __name__ == '__main__':
    unittest.main()
