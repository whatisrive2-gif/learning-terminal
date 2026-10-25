import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from hub.core import Store, Conflict
from hub import workspace, submission

class RedesignTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(dir=Path(__file__).parent/'artifacts')
        self.root=Path(self.tmp.name);self.store=Store(self.root/'test.db')
    def tearDown(self): self.store.db.close();self.tmp.cleanup()
    def test_quick_complete_and_protected_delete(self):
        a=self.store.create({'title':'待办'})
        b=self.store.create({'title':'后续','dependencies':[a['id']]})
        with self.assertRaises(ValueError): self.store.change(b['id'],{'action':'complete','revision':b['revision']})
        a=self.store.change(a['id'],{'action':'complete','revision':a['revision']})
        with self.assertRaises(ValueError): self.store.change(a['id'],{'action':'delete','revision':a['revision']})
        self.assertEqual(a['state'],'done')
    def test_config_snapshot_and_revision(self):
        p=workspace.save(self.store,'profiles',{'name':'长讲解','length':'较长'})
        t=self.store.create({'title':'学习','config':{k:p[k] for k in workspace.DEFAULT}})
        workspace.save(self.store,'profiles',{**p,'length':'较短'})
        self.assertEqual(t['config']['length'],'较长')
        with self.assertRaises(Conflict): workspace.save(self.store,'profiles',p)
    def test_agent_assignment_result_and_stale_response(self):
        lead=workspace.agent_action(self.store,dict(action='register',name='主',role='调度'))
        child=workspace.agent_action(self.store,dict(action='register',name='子-01',role='核查',parent=lead['id']))
        p=workspace.save(self.store,'projects',dict(name='项目',lead=lead['id'],mode='项目'))
        t=workspace.agent_action(self.store,dict(action='assign',agent_id=lead['id'],project_id=p['id'],target_agent_id=child['id'],title='核查'))
        t=self.store.claim();self.store.finish(t['id'],t['run_id'],'waiting_external','交接')
        tasks=workspace.agent_action(self.store,dict(action='inbox',agent_id=child['id']))['tasks'];self.assertEqual(len(tasks),1)
        reply=dict(action='result',agent_id=child['id'],task_id=t['id'],run_id=t['run_id'],revision=tasks[0]['revision'],result='已核查')
        self.assertEqual(workspace.agent_action(self.store,reply)['state'],'review')
        with self.assertRaises(Conflict): workspace.agent_action(self.store,reply)
    def submission_fixture(self):
        f=self.root/'answer.txt';f.write_text('answer');dest=self.root/'out';dest.mkdir()
        c=workspace.save(self.store,'channels',dict(name='交付目录',type='folder',target=str(dest)))
        return workspace.save(self.store,'submissions',dict(name='作业',path=str(f),destination=c['id'])),f,dest
    def test_submission_snapshot_and_no_repeat(self):
        s,f,dest=self.submission_fixture();result=submission.send(self.store,s)
        self.assertEqual(result['status'],'submitted');self.assertEqual(len(list(dest.iterdir())),1)
        with self.assertRaises(ValueError): submission.send(self.store,result)
    def test_submission_changed_file_rejected(self):
        s,f,_=self.submission_fixture();f.write_text('changed')
        with self.assertRaises(ValueError): submission.send(self.store,s)
    def test_interrupted_submission_becomes_unknown(self):
        import json
        s,_,_=self.submission_fixture();s['status']='sending'
        with self.store.db: self.store.db.execute("UPDATE records SET data=? WHERE kind='submissions' AND id=?",(json.dumps(s),s['id']))
        self.store.db.close();self.store=Store(self.root/'test.db')
        self.assertEqual(workspace.get(self.store,'submissions',s['id'])['status'],'unknown')
    def test_network_uncertainty_not_success(self):
        f=self.root/'answer.txt';f.write_text('answer')
        c=workspace.save(self.store,'channels',dict(name='接口',type='webhook',target='https://example.invalid/submit'))
        s=workspace.save(self.store,'submissions',dict(name='作业',path=str(f),destination=c['id']))
        with patch('urllib.request.OpenerDirector.open',side_effect=TimeoutError):
            result=submission.send(self.store,s)
        self.assertEqual(result['status'],'unknown')
        with self.assertRaises(ValueError): submission.send(self.store,result)

if __name__=='__main__': unittest.main()
