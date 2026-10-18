"""In-process deterministic tool service simulation for browser tests only."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from hub import toolcenter
from hub.server import serve

tools=[dict(id=i,title=t,description='隔离测试数据',type=kind,capabilities=['run','dry-run'] if kind=='periodic' else ['list-items','backfill'],enabled=True,running=False,intervalMinutes=30) for i,t,kind in [('homework-crawler','概率论作业抓取','periodic'),('dirwatch','目录监听','periodic'),('material-transfer','材料收发','service')]]
runs={};ticks={};items=[{'title':'材料 '+s,'sha256':str(n)*64,'status':s} for n,s in enumerate(['held','pending','served','acked'],1)]
def fake(path,body=None):
    if path=='/api/tools':return {'tools':tools}
    if path.startswith('/api/runs/'):
        rid=path.split('/')[-1];ticks[rid]+=1
        if ticks[rid]>3:runs[rid]['status']='completed';runs[rid]['finishedAt']='2026-10-17T01:01:00Z'
        return runs[rid]
    parts=path.split('/');tool=next(t for t in tools if t['id']==parts[3])
    if len(parts)==4:return tool
    action=parts[4].split('?')[0]
    if action=='items':return {'items':items}
    if action=='runs':return {'runs':[r for r in runs.values() if r['toolId']==tool['id']]}
    if action in {'enable','disable'}:tool['enabled']=action=='enable';return {'id':tool['id'],'enabled':tool['enabled']}
    if action=='backfill':
        for i in items:
            if i['sha256']==body['sha256']:i['status']='pending'
        return {'results':[{'ok':True,'sha256':body['sha256']}]}
    rid='fixture-'+str(len(runs)+1);ticks[rid]=0
    runs[rid]={'id':rid,'toolId':tool['id'],'status':'running','input':body['input'],'acceptedAt':'2026-10-17T01:00:00Z','summary':'模拟试运行结果','outputs':[]}
    return {'runId':rid,'status':'accepted'}
toolcenter.request=fake
s,h,t=serve(0,sys.argv[1]);print(f'http://127.0.0.1:{s.server_port}/#{t}',flush=True);s.serve_forever()
