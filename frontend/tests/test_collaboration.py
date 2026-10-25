import json
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from hub.core import Store, Conflict
from hub import workspace as ws
from hub.exchange import export_packet, import_packet

class CollaborationTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.a=Store(Path(self.tmp.name)/'a.db');self.b=Store(Path(self.tmp.name)/'b.db')
        self.ha=ws.local_host(self.a);self.hb=ws.local_host(self.b)
        ws.save(self.a,'hosts',self.hb);ws.save(self.b,'hosts',self.ha)
    def tearDown(self):
        self.a.db.close();self.b.db.close();self.tmp.cleanup()
    def task(self):
        t=self.a.create(dict(title='协作核查',executor='agent-handoff',collaboration_mode='joint',responsibilities='A 推导；B 核查；用户验收',execution_host_id=self.hb['id']))
        self.a.change(t['id'],dict(action='dispatch',revision=t['revision']))
        t=self.a.claim();return self.a.finish(t['id'],t['run_id'],'waiting_external','handoff')
    def packet(self,t):return export_packet(self.a,dict(task_id=t['id'],target_host_id=self.hb['id']))
    def test_registration_liveness_and_identity(self):
        a=ws.agent_action(self.a,dict(action='register',name='Codex',registration_key='codex-main'))
        b=ws.agent_action(self.a,dict(action='register',name='Codex',registration_key='codex-main'))
        self.assertEqual(a['id'],b['id']);self.assertEqual(len(ws.records(self.a,'agents')),1)
        self.assertEqual(ws.connection_status(b),'online')
        b['last_seen']=(datetime.now(timezone.utc)-timedelta(seconds=91)).isoformat()
        self.assertEqual(ws.connection_status(b),'offline')
        self.assertEqual(ws.agent_action(self.a,dict(action='offline',agent_id=a['id']))['connection_status'],'offline')
        self.assertEqual(ws.local_host(self.a)['id'],self.ha['id'])
        remote=ws.save(self.a,'agents',dict(name='Windows agent',host_id=self.hb['id']))
        with self.assertRaises(ValueError):ws.agent_action(self.a,dict(action='heartbeat',agent_id=remote['id']))
    def test_joint_requires_responsibilities_and_conflict(self):
        with self.assertRaises(ValueError):self.a.create(dict(title='x',collaboration_mode='joint'))
        t=self.task();run=t['run_id']
        changed=self.a.change(t['id'],dict(action='collaboration',revision=t['revision'],collaboration_mode='led',lead_host_id=self.ha['id']))
        self.assertEqual(changed['run_id'],run);self.assertEqual(changed['state'],'waiting_external')
        self.assertEqual(len(changed['collaboration_history']),1)
        with self.assertRaises(Conflict):self.a.change(t['id'],dict(action='collaboration',revision=t['revision']))
    def test_roundtrip_and_duplicate(self):
        t=self.task();p=self.packet(t)
        received=import_packet(self.b,p)['task'];self.assertEqual(received['state'],'draft')
        self.assertTrue(import_packet(self.b,p)['duplicate']);self.assertEqual(len(self.b.list()),1)
        received=self.b.change(received['id'],dict(action='result',revision=received['revision'],result='核查完成，附证据'))
        reply=export_packet(self.b,dict(task_id=received['id'],packet_kind='result'))
        done=import_packet(self.a,reply)['task'];self.assertEqual(done['state'],'review')
        self.assertTrue(import_packet(self.a,reply)['duplicate'])
        self.assertEqual(done['run_id'],t['run_id'])
    def test_wrong_target_changed_packet_and_stale_result(self):
        t=self.task();p=self.packet(t)
        with self.assertRaises(ValueError):import_packet(self.a,p)
        received=import_packet(self.b,p)['task']
        p['payload']['title']='changed'
        with self.assertRaises(Conflict):import_packet(self.b,p)
        self.b.change(received['id'],dict(action='result',revision=received['revision'],result='result'))
        reply=export_packet(self.b,dict(task_id=received['id'],packet_kind='result'))
        self.a.change(t['id'],dict(action='collaboration',revision=t['revision'],responsibilities='changed'))
        with self.assertRaises(Conflict):import_packet(self.a,reply)
        self.assertEqual(self.a.get(t['id'])['state'],'waiting_external')
    def test_remote_never_marked_online_by_files(self):
        import_packet(self.b,self.packet(self.task()))
        snap=ws.snapshot(self.b)
        self.assertEqual(next(h for h in snap['hosts'] if h['id']==self.ha['id'])['connection_status'],'unknown')

if __name__=='__main__':unittest.main()
