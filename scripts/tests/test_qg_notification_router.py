import sys, os, tempfile, unittest
sys.path.insert(0, os.path.expanduser('~/.claude/hooks'))
import qg_session_state as ss
import qg_notification_router as router

class TestNotificationRouter(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mktemp(suffix='.json')
        ss.STATE_PATH = self.tmp
        ss.LOCK_PATH = self.tmp + '.lock'
        router.ss = ss
        router._turn_critical_count = 0
        for p in [self.tmp, self.tmp + '.lock']:
            try: os.unlink(p)
            except FileNotFoundError: pass

    def tearDown(self):
        for p in [self.tmp, self.tmp + '.lock']:
            try: os.unlink(p)
            except FileNotFoundError: pass

    def test_info_returns_none(self):
        result = router.notify('INFO', 'layer2', 'LAZINESS', 'foo.py', 'msg', 'pretooluse')
        self.assertIsNone(result)

    def test_critical_immediate_in_pretooluse(self):
        result = router.notify('CRITICAL', 'layer2', 'LOOP', 'foo.py', 'looping!', 'pretooluse')
        self.assertIsNotNone(result)
        self.assertIn('additionalContext', result)
        self.assertIn('looping!', result['additionalContext'])

    def test_critical_queued_from_stop(self):
        router.notify('CRITICAL', 'layer3', 'FN', None, 'missed failure', 'stop')
        state = ss.read_state()
        self.assertEqual(len(state['notification_pending_criticals']), 1)
        self.assertEqual(state['notification_pending_criticals'][0]['message'], 'missed failure')

    def test_dedup_within_60s(self):
        router.notify('WARNING', 'layer2', 'LAZINESS', 'foo.py', 'first', 'pretooluse')
        router.notify('WARNING', 'layer2', 'LAZINESS', 'foo.py', 'second', 'pretooluse')
        state = ss.read_state()
        dropped = [d for d in state['notification_delivery'] if d.get('status') == 'dropped']
        self.assertEqual(len(dropped), 1)

    def test_rate_limit_queues_4th_critical(self):
        for i in range(4):
            router.notify('CRITICAL', 'layer2', f'CAT{i}', f'f{i}.py', f'msg{i}', 'pretooluse')
        state = ss.read_state()
        queued = [p for p in state['notification_pending_criticals']]
        self.assertGreaterEqual(len(queued), 1)

    def test_flush_pending_criticals_clears_queue(self):
        router.notify('CRITICAL', 'layer3', 'FN', None, 'alert!', 'stop')
        result = router.flush_pending_criticals()
        self.assertIsNotNone(result)
        self.assertIn('alert!', result)
        state = ss.read_state()
        self.assertEqual(len(state['notification_pending_criticals']), 0)

if __name__ == '__main__':
    unittest.main()
