"""Explicit, versioned task envelopes. No credentials, databases or automatic execution."""
import json
import uuid
import hashlib
from .core import now, Conflict
from . import workspace as ws


def export_packet(store,data):
    task=store.get(data.get('task_id'))
    local=ws.local_host(store)
    kind=data.get('packet_kind','handoff')
    if kind=='handoff':
        if task['executor']!='agent-handoff' or task['state']!='waiting_external':
            raise ValueError('请先派发 Agent 任务，等待交接后导出')
        if task.get('origin'): raise ValueError('接收的任务不能再次转包；请回传结果')
        target=ws.get(store,'hosts',data.get('target_host_id'))
        if not target or target['id']==local['id']: raise ValueError('请选择另一台已登记主机')
        if task.get('collaboration',{}).get('execution_host_id')!=target['id']: raise ValueError('交接目标须与任务执行主机一致')
        payload={k:task.get(k) for k in ('id','revision','run_id','title','notes','config','collaboration')}
    elif kind=='result':
        if not task.get('origin') or task['state'] not in {'review','done'} or not task.get('result'):
            raise ValueError('接收任务登记结果后才能回传')
        target={'id':task['origin']['host_id']}
        payload={**task['origin'],'result':task['result']}
    else: raise ValueError('未知交接包类型')
    return dict(schema='lt-collaboration/1',packet_id=uuid.uuid4().hex,kind=kind,created=now(),
                sender={k:local[k] for k in ('id','name','platform')},target_host_id=target['id'],payload=payload)


def import_packet(store,packet):
    if not isinstance(packet,dict) or packet.get('schema')!='lt-collaboration/1': raise ValueError('不支持的交接包')
    raw=json.dumps(packet,ensure_ascii=False,sort_keys=True)
    if len(raw.encode())>90000: raise ValueError('交接包过大')
    pid=packet.get('packet_id');sender=packet.get('sender');body=packet.get('payload')
    if not isinstance(pid,str) or not 1<=len(pid)<=100 or not isinstance(sender,dict) or not isinstance(body,dict): raise ValueError('交接包格式错误')
    if any(not isinstance(sender.get(k),str) or not 1<=len(sender[k])<=200 for k in ('id','name','platform')): raise ValueError('来源主机格式错误')
    with store.lock,store.db:
        local=ws.local_host(store)
        if packet.get('target_host_id')!=local['id']: raise ValueError('交接包目标不是本机，请核对双方主机 ID')
        if sender['id']==local['id']: raise ValueError('来源与目标主机不能相同')
        digest=hashlib.sha256(raw.encode()).hexdigest()
        prior=store.db.execute("SELECT data FROM records WHERE kind='exchange_receipts' AND id=?",(pid,)).fetchone()
        if prior:
            receipt=json.loads(prior[0])
            if receipt['digest']!=digest: raise Conflict('同一交接包标识对应不同内容')
            return dict(task=store.get(receipt['task_id']),duplicate=True)
        # Peers must be explicitly registered locally before their packets are accepted.
        if not ws.get(store,'hosts',sender['id']): raise ValueError('请先登记来源主机的真实 ID')
        if packet.get('kind')=='handoff':
            for k in ('id','run_id','title','notes'):
                if not isinstance(body.get(k),str): raise ValueError('任务字段缺失')
            if not body['run_id'] or type(body.get('revision')) is not int: raise ValueError('任务运行版本无效')
            origin=dict(host_id=sender['id'],id=body['id'],run_id=body['run_id'],revision=body['revision'])
            existing=next((t for t in store.list() if t.get('origin')==origin),None)
            if existing: task=existing
            else:
                # Remote metadata is evidence; local scheduling remains an explicit choice.
                cooperation=body.get('collaboration')
                if not isinstance(cooperation,dict): raise ValueError('缺少协作约定')
                validated={}
                ws.attach_collaboration(store,validated,{**cooperation,'integrator_agent_id':''})
                task=store.create(dict(title=body['title'],notes=body['notes'],config=body.get('config'),executor='agent-handoff',**validated['collaboration']))
                task['origin']=origin
                task['remote_collaboration']=body.get('collaboration')
                task=store._save(task,'received','收到远端交接；待本机安排，不自动执行')
        elif packet.get('kind')=='result':
            task=store.get(body.get('id'))
            if body.get('host_id')!=local['id'] or task['run_id']!=body.get('run_id'): raise Conflict('任务运行版本不匹配')
            if task['state']!='waiting_external': raise Conflict('任务已不处于等待交接状态')
            expected=task.get('collaboration',{}).get('execution_host_id')
            if expected!=sender['id']: raise ValueError('回传主机与任务执行主机不匹配')
            task=store.change(task['id'],dict(action='result',revision=body.get('revision'),result=body.get('result')))
        else: raise ValueError('未知交接包类型')
        receipt=dict(digest=digest,task_id=task['id'],time=now())
        store.db.execute('INSERT INTO records VALUES (?,?,?)',('exchange_receipts',pid,json.dumps(receipt)))
        return dict(task=task,duplicate=False)
