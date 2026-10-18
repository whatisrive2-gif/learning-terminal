import json
from pathlib import Path
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from hub.core import Store, Conflict
from hub.server import serve
ARTIFACTS = Path(__file__).resolve().parent / 'artifacts'
ARTIFACTS.mkdir(exist_ok=True)


class CoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(dir=ARTIFACTS)
        self.path = Path(self.tmp.name) / 'hub.db'
        self.s = Store(self.path)

    def tearDown(self):
        self.s.db.close()
        self.tmp.cleanup()

    def make(self, **kw):
        return self.s.create({'title':'测试任务', **kw})

    def act(self, t, action, **kw):
        return self.s.change(t['id'], {'revision':t['revision'], 'action':action, **kw})

    def test_dependency_requires_review_and_approval(self):
        a = self.make()
        b = self.make(executor='local-inventory', dependencies=[a['id']])
        b = self.act(b, 'dispatch')
        self.assertIsNone(self.s.claim())
        a = self.act(a, 'result', result='已完成本地处理')
        self.assertIsNone(self.s.claim())
        self.act(a, 'approve', evidence='已核对产物')
        self.assertEqual(self.s.claim()['id'], b['id'])
        self.assertIsNone(self.s.claim())

    def test_conflict_and_cycle(self):
        a = self.make()
        b = self.make(dependencies=[a['id']])
        with self.assertRaises(ValueError): self.act(a, 'edit', dependencies=[b['id']])
        self.act(a, 'edit', title='新标题')
        with self.assertRaises(Conflict): self.act(a, 'edit', title='旧请求')

    def test_crash_does_not_replay(self):
        a = self.act(self.make(executor='local-inventory'), 'dispatch')
        self.s.claim()
        b = self.act(self.make(executor='local-inventory'), 'dispatch')
        self.s.db.close()
        self.s = Store(self.path)
        self.assertEqual(self.s.get(a['id'])['state'], 'unknown')
        self.assertEqual(self.s.get(b['id'])['state'], 'paused')
        self.assertIsNone(self.s.claim())

    def test_cancel_rejects_late_result(self):
        t = self.act(self.make(executor='local-inventory'), 'dispatch')
        t = self.s.claim()
        self.act(t, 'cancel')
        self.s.finish(t['id'], t['run_id'], 'review', '晚到结果')
        self.assertEqual(self.s.get(t['id'])['state'], 'cancelled')

    def test_manual_evidence_and_reopen(self):
        t = self.make()
        with self.assertRaises(ValueError): self.act(t, 'approve', evidence='不能直接完成')
        t = self.act(t, 'result', result='产物位置与说明')
        with self.assertRaises(ValueError): self.act(t, 'approve', evidence='')
        t = self.act(t, 'approve', evidence='人工核对')
        t = self.act(t, 'reopen')
        self.assertEqual(t['state'], 'draft')
        self.assertEqual(len(self.s.export()['events']), 4)

    def test_invalid_executor_and_missing_dependency(self):
        with self.assertRaises(ValueError): self.make(executor='shell')
        with self.assertRaises(ValueError): self.make(dependencies=['missing'])

    def test_reopen_dependency_blocks_approval(self):
        a = self.act(self.make(), 'result', result='完成')
        a = self.act(a, 'approve', evidence='核对')
        b = self.make(dependencies=[a['id']])
        b = self.act(b, 'result', result='完成')
        self.act(a, 'reopen')
        with self.assertRaises(ValueError): self.act(b, 'approve', evidence='核对')


class HttpTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(dir=ARTIFACTS)
        self.server, self.hub, self.token = serve(0, Path(self.tmp.name) / 'hub.db')
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.url = f'http://127.0.0.1:{self.server.server_port}'

    def tearDown(self):
        self.hub.stop.set()
        self.server.shutdown()
        self.thread.join()
        self.hub.worker.join(timeout=5)
        self.hub.tool_worker.join(timeout=5)
        self.server.server_close()
        self.hub.store.db.close()
        self.tmp.cleanup()

    def test_api_auth_origin_and_host(self):
        for headers in [{}, {'X-Hub-Token':self.token, 'Origin':'https://evil.example'},
                        {'X-Hub-Token':self.token, 'Host':'evil.example'}]:
            with self.assertRaises(urllib.error.HTTPError):
                urllib.request.urlopen(urllib.request.Request(self.url+'/api/state', headers=headers))
        req = urllib.request.Request(self.url+'/api/state', headers={'X-Hub-Token':self.token})
        with urllib.request.urlopen(req) as response:
            self.assertEqual(json.load(response)['tasks'], [])

    def test_persistent_create_and_conflict_http(self):
        headers = {'X-Hub-Token':self.token, 'Content-Type':'application/json'}
        req = urllib.request.Request(self.url+'/api/tasks', data=json.dumps({'title':'中文任务'}).encode(), headers=headers)
        with urllib.request.urlopen(req) as response: task = json.load(response)
        req = urllib.request.Request(self.url+'/api/tasks/'+task['id'], data=b'{"revision":0,"action":"edit","title":"stale"}', headers=headers)
        with self.assertRaises(urllib.error.HTTPError) as e: urllib.request.urlopen(req)
        self.assertEqual(e.exception.code, 409)


if __name__ == '__main__': unittest.main()
