"""Local orchestration: isolated storage, dependencies, explicit dispatch and review."""
import json
import sqlite3
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path


def now():
    return datetime.now(timezone.utc).isoformat()


class Conflict(ValueError):
    pass


EXECUTORS = {'manual', 'agent-handoff', 'local-inventory', 'taber', 'qoder-tool'}
EDITABLE = {'draft', 'paused', 'failed', 'cancelled'}


class Store:
    def __init__(self, path):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.lock = threading.RLock()
        self.db = sqlite3.connect(path, check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        self.db.execute('PRAGMA journal_mode=WAL')
        self.db.executescript('''
          CREATE TABLE IF NOT EXISTS tasks(id TEXT PRIMARY KEY, data TEXT NOT NULL);
          CREATE TABLE IF NOT EXISTS events(seq INTEGER PRIMARY KEY, task TEXT, time TEXT, kind TEXT, detail TEXT);
          PRAGMA user_version=1;
        ''')
        with self.lock, self.db:
            for task in self.list():
                if task['state'] == 'running':
                    task['state'] = 'unknown'
                    self._save(task, 'interrupted', '服务重启；上次执行结果未知，请核对后处理。')
                elif task['state'] == 'queued':
                    task['state'] = 'paused'
                    self._save(task, 'recovered', '服务重启；队列已暂停，需重新派发。')

    def list(self):
        with self.lock:
            return [json.loads(r['data']) for r in self.db.execute('SELECT data FROM tasks ORDER BY rowid DESC')]

    def get(self, tid):
        with self.lock:
            row = self.db.execute('SELECT data FROM tasks WHERE id=?', (tid,)).fetchone()
            if not row:
                raise ValueError('任务不存在')
            return json.loads(row['data'])

    def _save(self, task, kind, detail=''):
        task['revision'] = task.get('revision', 0) + 1
        task['updated'] = now()
        self.db.execute('INSERT OR REPLACE INTO tasks VALUES (?,?)', (task['id'], json.dumps(task, ensure_ascii=False)))
        self.db.execute('INSERT INTO events(task,time,kind,detail) VALUES (?,?,?,?)',
                        (task['id'], now(), kind, detail))
        return task

    def _fields(self, task, data):
        for k, limit in [('title', 200), ('notes', 12000), ('category', 80), ('due', 10), ('session', 100), ('agent', 100)]:
            if k in data:
                if not isinstance(data[k], str) or len(data[k]) > limit:
                    raise ValueError(f'{k} 格式或长度无效')
                task[k] = data[k].strip()
        if not task.get('title'):
            raise ValueError('请填写任务标题')
        if task.get('due'):
            datetime.strptime(task['due'], '%Y-%m-%d')
        executor = data.get('executor', task.get('executor', 'manual'))
        if executor not in EXECUTORS:
            raise ValueError('执行者不受支持')
        task['executor'] = executor
        if executor == 'qoder-tool':
            from .toolcenter import validate
            tool = data.get('tool_id', task.get('tool_id'))
            action = data.get('tool_action', task.get('tool_action'))
            inputs = data.get('tool_input', task.get('tool_input', {}))
            if not isinstance(inputs, dict): raise ValueError('工具参数格式无效')
            validate(tool, action, inputs)
            task.update(tool_id=tool, tool_action=action, tool_input=inputs)
        priority = data.get('priority', task.get('priority', 'normal'))
        if priority not in {'normal', 'high', 'low'}:
            raise ValueError('优先级无效')
        task['priority'] = priority
        deps = data.get('dependencies', task.get('dependencies', []))
        if not isinstance(deps, list) or len(deps) > 50 or not all(isinstance(x, str) for x in deps):
            raise ValueError('依赖格式无效')
        task['dependencies'] = list(dict.fromkeys(deps))
        def visit(tid, seen):
            if tid == task['id']:
                raise ValueError('任务依赖不能形成循环')
            if tid in seen:
                return
            seen.add(tid)
            for parent in self.get(tid)['dependencies']:
                visit(parent, seen)
        for dep in task['dependencies']:
            visit(dep, set())

    def create(self, data):
        with self.lock, self.db:
            task = dict(id=uuid.uuid4().hex, state='draft', created=now(), revision=0,
                        notes='', category='学习', due='', session='', agent='', result='', evidence='', run_id='')
            self._fields(task, data)
            return self._save(task, 'created', '任务已记录')

    def blocked(self, task):
        return [self.get(d)['title'] for d in task['dependencies'] if self.get(d)['state'] != 'done']

    def change(self, tid, data):
        with self.lock, self.db:
            task = self.get(tid)
            if data.get('revision') != task['revision']:
                raise Conflict('任务已被其他操作更新，请刷新后重试')
            action = data.get('action', 'edit')
            state = task['state']
            if action == 'edit':
                if state not in EDITABLE:
                    raise ValueError('请先暂停或重新打开任务再编辑')
                self._fields(task, data)
            elif action == 'dispatch':
                if state not in EDITABLE:
                    raise ValueError('当前状态不可派发')
                if task['executor'] == 'manual':
                    raise ValueError('本人处理的任务请直接登记结果')
                if task.get('remote_run_id'):
                    task.setdefault('tool_history', []).append({'remote_run_id':task['remote_run_id'],
                        'tool_run':task.get('tool_run'), 'result':task.get('result'), 'evidence':task.get('evidence')})
                task.update(state='queued', result='', evidence='', run_id=uuid.uuid4().hex,
                            remote_run_id=None, tool_run=None, poll_error=None)
            elif action == 'pause':
                if state != 'queued':
                    raise ValueError('只有排队任务可暂停；执行中请取消')
                task['state'] = 'paused'
            elif action == 'cancel':
                if task['executor'] == 'qoder-tool' and state == 'running':
                    raise ValueError('提交中的远端操作不能取消；工具服务没有取消接口')
                if state not in {'queued', 'running', 'waiting_external', 'paused'}:
                    raise ValueError('当前状态不可取消')
                task['state'] = 'cancelled'
            elif action == 'result':
                if state not in {'draft', 'waiting_external', 'unknown'}:
                    raise ValueError('当前状态不可登记结果')
                result = data.get('result', '')
                if not isinstance(result, str) or not result.strip() or len(result) > 50000:
                    raise ValueError('请填写有效结果（最多 50000 字）')
                task.update(state='review', result=result.strip())
            elif action == 'approve':
                if state != 'review':
                    raise ValueError('请先执行或登记结果')
                if self.blocked(task):
                    raise ValueError('前置任务尚未完成，不能验收')
                evidence = data.get('evidence', '')
                if not isinstance(evidence, str) or not evidence.strip() or len(evidence) > 4000:
                    raise ValueError('请填写验收依据')
                task.update(state='done', evidence=evidence.strip())
            elif action == 'reopen':
                if state not in {'review', 'done', 'failed', 'cancelled', 'paused'}:
                    raise ValueError('当前状态不可重新打开；结果未知需先核对并登记结果')
                task['state'] = 'draft'
            else:
                raise ValueError('未知操作')
            return self._save(task, action, {'dispatch':'明确派发', 'approve':'用户验收', 'result':'登记结果'}.get(action, action))

    def claim(self):
        with self.lock, self.db:
            for task in reversed(self.list()):
                if task['state'] == 'queued' and not self.blocked(task):
                    task['state'] = 'running'
                    return self._save(task, 'started', task['executor'])

    def finish(self, tid, run_id, state, result):
        with self.lock, self.db:
            task = self.get(tid)
            if task['state'] != 'running' or task['run_id'] != run_id:
                return task
            task.update(state=state, result=result)
            return self._save(task, state, '执行结果已保存，完成须另行验收' if state == 'review' else state)

    def events(self, tid=None):
        with self.lock:
            query = 'SELECT * FROM events' + (' WHERE task=?' if tid else '') + ' ORDER BY seq DESC LIMIT 200'
            return [dict(r) for r in self.db.execute(query, (tid,) if tid else ())]

    def create_tool(self, data):
        """Atomically create+queue, deduplicating the UI intent, not remote execution."""
        from .toolcenter import validate
        key = data.get('requestId')
        if not isinstance(key, str) or not 8 <= len(key) <= 100: raise ValueError('需要有效 requestId')
        tool, action, inputs = data.get('tool_id'), data.get('tool_action'), data.get('tool_input', {})
        if not isinstance(inputs, dict): raise ValueError('工具参数格式无效')
        validate(tool, action, inputs)
        intent = {'tool_id':tool, 'tool_action':action, 'tool_input':inputs}
        with self.lock, self.db:
            for old in self.list():
                if old.get('request_key') == key:
                    if any(old.get(k) != v for k,v in intent.items()): raise Conflict('同一请求标识不能提交不同操作')
                    return old
            task = dict(id=uuid.uuid4().hex, state='queued', created=now(), revision=0,
                        title=f'{tool} · {action}' + (' · 试运行' if inputs.get('dryRun') else ''),
                        notes='由工具中心明确派发。执行完成与手机保存确认分别记录。',
                        category='工具', due='', session='', agent='', result='', evidence='',
                        run_id=uuid.uuid4().hex, executor='qoder-tool', request_key=key, **intent)
            self._fields(task, {})
            return self._save(task, 'tool-dispatch', '工具操作已排队，尚未等同远端受理')

    def tool_update(self, tid, run_id, state, result, **extra):
        with self.lock, self.db:
            task = self.get(tid)
            if task['state'] not in {'running','waiting_tool'} or task['run_id'] != run_id: return task
            if all(task.get(k) == v for k,v in {'state':state,'result':result,**extra}.items()): return task
            task.update(state=state, result=result, **extra)
            return self._save(task, 'tool-status', '工具状态：'+state)

    def export(self):
        with self.lock:
            return dict(schema_version=1, exported=now(), tasks=self.list(),
                        events=[dict(r) for r in self.db.execute('SELECT * FROM events ORDER BY seq')])
