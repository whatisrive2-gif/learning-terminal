"""Versioned local configuration and explicit collaboration records; no model calls."""
import json
import uuid
from pathlib import Path
from .core import Conflict, now

DEFAULT = dict(name='默认学习', goal='', tone='耐心、直接', length='默认', depth='正常首轮',
               instructions='', suggestions=False, workflow_summary=False)
KINDS = {'profiles','agents','projects','submissions','channels','messages','hosts'}

def records(store, kind):
    if kind not in KINDS: raise ValueError('未知记录类型')
    with store.lock:
        return [json.loads(r[0]) for r in store.db.execute('SELECT data FROM records WHERE kind=? ORDER BY rowid', (kind,))]

def get(store, kind, rid):
    return next((x for x in records(store, kind) if x['id']==rid), None)

def save(store, kind, data):
    if kind not in KINDS: raise ValueError('未知记录类型')
    with store.lock, store.db:
        rid = data.get('id') or uuid.uuid4().hex
        if not isinstance(rid,str) or len(rid)>100: raise ValueError('无效标识')
        old = get(store,kind,rid)
        if old and data.get('revision') != old['revision']: raise Conflict('记录已更新，请刷新')
        if kind=='hosts':
            value={k:data.get(k,(old or {}).get(k,'')) for k in ('name','platform','endpoint')}
        elif kind=='profiles':
            value={k:data.get(k,v) for k,v in DEFAULT.items()}
            if value['length'] not in {'默认','较长','较短'}: raise ValueError('长度无效')
            if any(type(value[k]) is not bool for k in ('suggestions','workflow_summary')): raise ValueError('开关无效')
        elif kind=='agents':
            value={k:data.get(k,'') for k in ('name','provider','role','parent','quota','background')}
            parent=get(store,'agents',value['parent']) if value['parent'] else None
            if value['parent'] and not parent: raise ValueError('父 Agent 不存在')
            ancestor=parent
            while ancestor:
                if ancestor['id']==rid: raise ValueError('Agent 关系不能循环')
                ancestor=get(store,'agents',ancestor.get('parent'))
            if any(a['name']==value['name'] and a['id']!=rid for a in records(store,kind)): raise ValueError('Agent 名称必须唯一，子 Agent 请明确编号与职责')
            value['host_id']=data.get('host_id',(old or {}).get('host_id',local_host(store)['id']))
            if not get(store,'hosts',value['host_id']): raise ValueError('主机未登记')
            value['registration_key']=data.get('registration_key',(old or {}).get('registration_key',''))
            value['work_status']=(old or {}).get('work_status','idle')
            value['transport']=(old or {}).get('transport','manual')
            if old and old.get('last_seen'): value['last_seen']=old['last_seen']
        elif kind=='projects':
            value={k:data.get(k,'') for k in ('name','goal','lead','mode','background')}
            if not get(store,'agents',value['lead']): raise ValueError('请选择已注册的主 Agent')
            if value['mode'] not in {'项目','讨论','自定义'}: raise ValueError('协作模式无效')
        elif kind=='channels':
            value={k:data.get(k,'') for k in ('name','type','target','credential_env','sender','host')}
            if value['type'] not in {'folder','webhook','email'}: raise ValueError('渠道类型无效')
            if value['type']=='webhook' and not value['target'].startswith('https://'): raise ValueError('提交接口须使用 HTTPS')
            if value['type']=='folder' and not Path(value['target']).is_absolute(): raise ValueError('提交目录须为绝对路径')
            if value['type']=='email' and ('@' not in value['target'] or not value['host'] or '@' not in value['sender']): raise ValueError('请填写 SMTP 主机、发件人与收件人')
        elif kind=='messages':
            value={k:data.get(k,'') for k in ('name','sender','recipient','project','body')}
            if not get(store,'agents',value['recipient']): raise ValueError('接收 Agent 不存在')
        else:
            value={k:data.get(k,'') for k in ('name','path','destination','notes')}
            path=Path(value['path'])
            if not path.is_absolute() or not path.is_file(): raise ValueError('请选择已存在的本地完成文件（绝对路径）')
            channel=get(store,'channels',value['destination'])
            if not channel: raise ValueError('请选择提交渠道')
            if old: raise ValueError('提交条目不可覆盖，请为新版本另建条目')
            import hashlib
            if path.stat().st_size>20*1024*1024: raise ValueError('本版提交文件上限 20 MB')
            value['sha256']=hashlib.sha256(path.read_bytes()).hexdigest()
            value['channel_snapshot']=channel
            value['status']='ready'
            value['receipt']=None
        for k,v in value.items():
            if k in {'suggestions','workflow_summary','receipt','channel_snapshot'}: continue
            if not isinstance(v,str) or len(v)>12000: raise ValueError('字段格式或长度无效')
        if not value['name'].strip(): raise ValueError('名称不能为空')
        value.update(id=rid,revision=(old or {}).get('revision',0)+1,updated=now())
        store.db.execute('INSERT OR REPLACE INTO records VALUES (?,?,?)',(kind,rid,json.dumps(value,ensure_ascii=False)))
        store.db.execute('INSERT INTO events(task,time,kind,detail) VALUES (?,?,?,?)',(rid,now(),kind,'保存：'+value['name']))
        return value

def attach_context(store, task, data):
    attach_collaboration(store,task,data)
    config=data.get('config')
    if config is not None:
        if not isinstance(config,dict): raise ValueError('配置须为对象')
        if set(config)-set(DEFAULT): raise ValueError('未知配置字段')
        for k,v in config.items():
            if k in ('suggestions','workflow_summary'):
                if type(v) is not bool: raise ValueError('配置开关无效')
            elif not isinstance(v,str) or len(v)>12000: raise ValueError('配置字段无效')
        task['config']={**DEFAULT,**config}
    aid=data.get('agent_id')
    pid=data.get('project_id')
    if aid:
        agent=get(store,'agents',aid)
        if not agent: raise ValueError('Agent 不存在')
        task.update(agent_id=aid,agent=agent['name'],agent_snapshot=agent,executor='agent-handoff')
    if pid:
        project=get(store,'projects',pid)
        if not project: raise ValueError('协作项目不存在')
        task.update(project_id=pid,project_snapshot=project,lead_snapshot=get(store,'agents',project['lead']))

def monitor_targets(state):
    """Display-only allowlist; never return the sync service token or credentials."""
    import ast
    targets={}
    try:
        tree=ast.parse((state/'tools'/'homework_crawler.py').read_text(encoding='utf-8-sig'))
        constants={n.targets[0].id:n.value.value for n in tree.body
                   if isinstance(n,ast.Assign) and isinstance(n.targets[0],ast.Name)
                   and isinstance(n.value,ast.Constant) and isinstance(n.value.value,str)}
        origin=constants.get('ORIGIN',''); share=constants.get('TOKEN','')
        if origin.startswith('https://') and share:
            targets['homework-crawler']={'target':origin+'/d/'+share+'/','content':'概率论分享目录中的新增或更新作业文件'}
    except (OSError,SyntaxError,ValueError): pass
    try:
        config=json.loads((state.parent.parent/'协议'/'config.json').read_text(encoding='utf-8-sig'))
        download=config.get('homework',{}).get('downloadDir')
        if isinstance(download,str): targets.setdefault('homework-crawler',{})['download_dir']=download
        watch=config.get('tools',{}).get('dirwatch',{}).get('watchDir')
        if isinstance(watch,str): targets['dirwatch']={'target':watch,'content':'目录内已稳定写入的新文件或变更文件'}
    except (OSError,ValueError,AttributeError): pass
    return targets


def snapshot(store):
    local=local_host(store)
    data={k:records(store,k) for k in KINDS}
    data['local_host_id']=local['id']
    for agent in data['agents']: agent['connection_status']=connection_status(agent)
    for host in data['hosts']:
        host['connection_status']='online' if host['id']==local['id'] else 'unknown'
    data['defaults']=DEFAULT
    from .adapters import STATE
    data['monitor_targets']=monitor_targets(STATE)
    return data

def agent_action(store, data):
    action=data.get('action')
    if action in {'export-packet','import-packet'}:
        from .exchange import export_packet, import_packet
        return export_packet(store,data) if action=='export-packet' else import_packet(store,data.get('packet'))
    if action=='register':
        local=local_host(store)
        if data.get('host_id',local['id'])!=local['id']: raise ValueError('自动注册只能代表当前主机；远端资料请手动登记')
        key=data.get('registration_key','')
        if not isinstance(key,str) or len(key)>100: raise ValueError('注册键无效')
        with store.lock:
            existing=next((a for a in records(store,'agents') if key and a.get('registration_key')==key and a.get('host_id')==local['id']),None)
            if existing:
                return heartbeat(store,existing,data)
            agent=save(store,'agents',data)
        with store.lock,store.db:
            agent.update(transport='polling',last_seen=now())
            store.db.execute('UPDATE records SET data=? WHERE kind=? AND id=?',(json.dumps(agent,ensure_ascii=False),'agents',agent['id']))
        return agent
    agent=get(store,'agents',data.get('agent_id'))
    if not agent: raise ValueError('Agent 未注册')
    if action in {'heartbeat','offline'}:
        return heartbeat(store,agent,data,offline=action=='offline')
    if action=='inbox':
        heartbeat(store,agent,data)
        return dict(tasks=[t for t in store.list() if t.get('agent_id')==agent['id'] and t['state']=='waiting_external'],messages=[m for m in records(store,'messages') if m['recipient']==agent['id']])
    if action=='result':
        task=store.get(data.get('task_id'))
        if task.get('agent_id')!=agent['id'] or task['run_id']!=data.get('run_id'): raise ValueError('任务接收方或运行版本不匹配')
        return store.change(task['id'],dict(action='result',revision=data.get('revision'),result=data.get('result')))
    if action=='assign':
        project=get(store,'projects',data.get('project_id'))
        if not project or project['lead']!=agent['id']: raise ValueError('仅项目主 Agent 可通过分派接口安排项目任务')
        target=data.get('target_agent_id')
        if not get(store,'agents',target): raise ValueError('目标 Agent 未注册')
        task=store.create({**data,'agent_id':target,'executor':'agent-handoff'})
        return store.change(task['id'],dict(action='dispatch',revision=task['revision']))
    if action=='message': return save(store,'messages',{**data,'sender':agent['id']})
    raise ValueError('未知 Agent 操作')


# Machine identities and liveness are local observations, never inferred from file presence.
def local_host(store):
    import platform
    with store.lock:
        row=store.db.execute("SELECT data FROM records WHERE kind='local_identity' AND id='host'").fetchone()
        if row: return get(store,'hosts',json.loads(row[0])['host_id'])
        host=save(store,'hosts',dict(name=platform.node() or platform.system(),platform=platform.system()))
        with store.db:
            store.db.execute('INSERT INTO records VALUES (?,?,?)',('local_identity','host',json.dumps({'host_id':host['id']})))
        return host


def connection_status(agent):
    from datetime import datetime, timezone
    if agent.get('work_status')=='offline': return 'offline'
    if agent.get('transport')!='polling' or not agent.get('last_seen'): return 'unknown'
    try:
        age=(datetime.now(timezone.utc)-datetime.fromisoformat(agent['last_seen'])).total_seconds()
        return 'online' if 0<=age<=90 else 'offline'
    except (ValueError,TypeError): return 'unknown'


def heartbeat(store,agent,data,offline=False):
    with store.lock,store.db:
        agent=get(store,'agents',agent['id'])
        if agent.get('host_id')!=local_host(store)['id']: raise ValueError('不能用本机心跳证明远端在线')
        status='offline' if offline else data.get('work_status','idle')
        if status not in {'idle','busy','paused','offline'}: raise ValueError('工作状态无效')
        agent.update(transport='polling',last_seen=now(),work_status=status)
        store.db.execute('UPDATE records SET data=? WHERE kind=? AND id=?',(json.dumps(agent,ensure_ascii=False),'agents',agent['id']))
        return {**agent,'connection_status':connection_status(agent)}


def attach_collaboration(store,task,data):
    old=task.get('collaboration',{})
    keys=('collaboration_mode','lead_host_id','execution_host_id','integrator_agent_id','responsibilities')
    if not any(k in data for k in keys) and old: return
    local=local_host(store)['id']
    values={k:data.get(k,old.get(k,'')) for k in keys}
    if not old and not data.get('collaboration_mode'):
        values.update(collaboration_mode='led',lead_host_id=local,execution_host_id=local)
    if any(not isinstance(v,str) or len(v)>12000 for v in values.values()): raise ValueError('协作字段格式无效')
    if values['collaboration_mode'] not in {'led','joint'}: raise ValueError('请选择单端主导或共同协作')
    if values['collaboration_mode']=='joint':
        values['lead_host_id']=''
        if not values['responsibilities'].strip(): raise ValueError('共同协作请填写双方分工与汇总约定')
    elif not get(store,'hosts',values['lead_host_id']): raise ValueError('请选择主导主机')
    for key in ('execution_host_id',):
        if values[key] and not get(store,'hosts',values[key]): raise ValueError('执行主机未登记')
    if values['integrator_agent_id'] and not get(store,'agents',values['integrator_agent_id']): raise ValueError('汇总 Agent 未登记')
    task['collaboration']=values
