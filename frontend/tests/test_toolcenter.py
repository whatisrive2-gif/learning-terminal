import json
from pathlib import Path
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from hub.core import Store, Conflict
from hub.server import Hub
from hub import toolcenter

ARTIFACTS = Path(__file__).parent / 'artifacts'
ARTIFACTS.mkdir(exist_ok=True)


class ToolTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(dir=ARTIFACTS)
        self.path = Path(self.tmp.name)/'hub.db'
        self.h = Hub(self.path)

    def tearDown(self):
        self.h.stop.set()
        for thread in [self.h.worker, self.h.tool_worker]:
            if thread.is_alive(): thread.join(8)
        self.h.store.db.close()
        self.tmp.cleanup()

    def create(self, **kw):
        return self.h.store.create_tool(dict(requestId='unique-0001',tool_id='homework-crawler',
            tool_action='run',tool_input={'dryRun':True},**kw))

    def wait(self, tid, state):
        for _ in range(100):
            t = self.h.store.get(tid)
            if t['state'] == state: return t
            time.sleep(.05)
        self.fail(f'Expected {state}, got {t}')

    def test_deduplicate_same_intent(self):
        a = self.create(); b = self.create()
        self.assertEqual(a['id'],b['id'])
        with self.assertRaises(Conflict):
            self.h.store.create_tool(dict(requestId='unique-0001', tool_id='dirwatch',tool_action='run',tool_input={}))

    def test_accepted_is_not_completed_and_polled_once(self):
        calls=[]
        def fake(path, body=None):
            calls.append((path,body))
            if body is not None: return {'runId':'run-1','status':'accepted'}
            return {'id':'run-1','toolId':'homework-crawler','status':'completed','outputs':[], 'input':{'dryRun':True}}
        with patch.object(toolcenter,'request',side_effect=fake):
            a=self.create();self.h.worker.start()
            t=self.wait(a['id'],'waiting_tool')
            self.assertEqual(t['remote_run_id'],'run-1')
            self.assertNotEqual(t['state'],'done')
            self.h.tool_worker.start(); t=self.wait(a['id'],'review')
            self.assertEqual(t['tool_run']['status'],'completed')
            self.assertEqual(sum(body is not None for _,body in calls),1)

    def test_restart_preserves_accepted_id(self):
        a=self.create();t=self.h.store.claim()
        self.h.store.tool_update(t['id'],t['run_id'],'waiting_tool','accepted',remote_run_id='run-2')
        self.h.store.db.close();self.h.store=Store(self.path)
        t=self.h.store.get(a['id'])
        self.assertEqual(t['state'],'waiting_tool');self.assertEqual(t['remote_run_id'],'run-2')
        self.assertIsNone(self.h.store.claim())

    def test_ambiguous_post_does_not_retry(self):
        with patch.object(toolcenter,'request',side_effect=toolcenter.SubmissionUnknown('connection lost')) as mock:
            a=self.create();self.h.worker.start();self.wait(a['id'],'unknown');time.sleep(.6)
            self.assertEqual(mock.call_count,1)

    def test_poll_outage_retains_run(self):
        a=self.create();t=self.h.store.claim()
        self.h.store.tool_update(t['id'],t['run_id'],'waiting_tool','accepted',remote_run_id='run-3')
        with patch.object(toolcenter,'run_status',side_effect=toolcenter.ServiceError('offline')):
            self.h.tool_worker.start()
            for _ in range(50):
                t=self.h.store.get(a['id'])
                if t.get('poll_error'): break
                time.sleep(.05)
            self.assertEqual(t['state'],'waiting_tool');self.assertEqual(t['remote_run_id'],'run-3')
            self.assertEqual(t['poll_error'],'offline')

    def test_missing_run_becomes_unknown(self):
        a=self.create();t=self.h.store.claim()
        self.h.store.tool_update(t['id'],t['run_id'],'waiting_tool','accepted',remote_run_id='gone')
        with patch.object(toolcenter,'run_status',side_effect=toolcenter.MissingRun('gone')):
            self.h.tool_worker.start();self.wait(a['id'],'unknown')

    def test_service_operations_and_sha_restrictions(self):
        for tool,action,data in [('material-transfer','run',{}),('dirwatch','backfill',{}),
                                 ('material-transfer','backfill',{'sha256':'all'}),('dirwatch','run',{'dryRun':'false'})]:
            with self.assertRaises(ValueError):toolcenter.validate(tool,action,data)

    def test_cancel_after_submit_not_supported(self):
        a=self.create();t=self.h.store.claim()
        with self.assertRaises(ValueError):self.h.store.change(a['id'],{'revision':t['revision'],'action':'cancel'})

    def test_backfill_failure_is_not_success(self):
        with patch.object(toolcenter,'request',return_value={'results':[{'ok':False,'reason':'源文件丢失'}]}):
            a=self.h.store.create_tool(dict(requestId='backfill-0001',tool_id='material-transfer',tool_action='backfill',tool_input={'sha256':'a'*64}))
            self.h.worker.start();self.wait(a['id'],'failed')


if __name__=='__main__': unittest.main()
