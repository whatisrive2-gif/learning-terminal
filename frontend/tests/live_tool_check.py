"""One explicit dry-run against the real tool service; isolated workbench DB."""
from pathlib import Path
import json
import sys
import time
import uuid
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from hub.server import Hub
from hub import toolcenter

root=Path(__file__).parent/'artifacts'/('live-tools-'+uuid.uuid4().hex[:8])
root.mkdir(parents=True)
catalog=toolcenter.catalog()
if not catalog['online']: raise RuntimeError(catalog['error'])
print(json.dumps({'online':True,'tools':[t['id'] for t in catalog['tools']]}),flush=True)
if any(t['id']=='homework-crawler' and t['running'] for t in catalog['tools']):
    for _ in range(60):
        time.sleep(1)
        if not any(t['id']=='homework-crawler' and t['running'] for t in toolcenter.catalog()['tools']): break
h=Hub(root/'hub.db')
task=h.store.create_tool({'requestId':uuid.uuid4().hex,'tool_id':'homework-crawler','tool_action':'run','tool_input':{'dryRun':True}})
h.worker.start();h.tool_worker.start()
try:
    for _ in range(120):
        task=h.store.get(task['id'])
        if task['state'] in {'review','failed','unknown'}:break
        time.sleep(1)
    details=toolcenter.detail('material-transfer')
    evidence={'task':task,'item_status_counts':{s:sum(i['status']==s for i in details['items']) for s in ['held','pending','served','acked']}}
    (root/'result.json').write_text(json.dumps(evidence,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'state':task['state'],'remote_run_id':task.get('remote_run_id'),
        'remote_status':(task.get('tool_run') or {}).get('status'),
        'summary':(task.get('tool_run') or {}).get('summary'),
        'error':(task.get('tool_run') or {}).get('error'),
        'evidence':str(root/'result.json')},ensure_ascii=False),flush=True)
    if task['state']!='review':sys.exit(1)
finally:
    h.stop.set();h.worker.join(7);h.tool_worker.join(7);h.store.db.close()
