"""Allowlisted adapters. No arbitrary shell commands and no model calls."""
import json
import os
from pathlib import Path
import shutil
import sqlite3
import subprocess
import time

STATE = Path(os.environ.get('LEARNING_TERMINAL_WORKSPACE', str(Path(__file__).resolve().parents[2] / '.learning-terminal'))).resolve()
PROJECT = STATE.parent
TABER = Path(os.environ.get('TABER_BRIDGE_SCRIPT', str(PROJECT.parent / 'taber' / 'scripts' / 'taber.mjs'))).resolve()


class OutcomeUnknown(ValueError):
    pass


def sessions(state=STATE):
    path = state / 'learning.sqlite3'
    if not path.is_file():
        raise ValueError('学习数据库不存在，未创建替代库')
    with sqlite3.connect(path.as_uri() + '?mode=ro', uri=True) as db:
        db.row_factory = sqlite3.Row
        return [dict(r) for r in db.execute('''SELECT s.id,s.title,s.goal,s.created,
            COALESCE(r.id,0) AS revision, COALESCE(r.created,s.created) AS updated,
            COALESCE(length(r.content),0) AS content_length
            FROM sessions s LEFT JOIN revisions r ON r.id=(SELECT max(id) FROM revisions WHERE session=s.id)
            ORDER BY updated DESC''')]


def inventory():
    records = sessions()
    return dict(workspace=str(STATE), session_count=len(records),
                published_count=sum(r['content_length'] > 0 for r in records),
                taber_available=TABER.is_file(), node_available=bool(shutil.which('node')),
                tool_integration='已接入 127.0.0.1:8787；在线状态请查看工具中心；未启动额外监听',
                agents=[dict(name='Codex', mode='人工交接', quota=None),
                        dict(name='Qoder CN', mode='人工交接', quota=None)])


def handoff(task):
    return ('任务：' + task['title'] + '\n执行方：' + (task['agent'] or '待用户选择') +
            '\n任务 ID：' + task['id'] + '\n运行 ID：' + task['run_id'] +
            '\n目标与上下文：\n' + task['notes'] +
            '\n关联学习会话：' + (task['session'] or '无') +
            '\n本轮配置（仅此任务快照）：\n' + json.dumps(task.get('config', {}),ensure_ascii=False) +
            '\n协作项目与主 Agent：\n' + json.dumps({'project':task.get('project_snapshot'),'lead':task.get('lead_snapshot'),'assignment':task.get('agent_snapshot')},ensure_ascii=False) +
            '\n请返回实际结果、产物路径、验证证据和未完成项。不要把收到任务视为完成。')


def command(args, cancelled, timeout=25):
    proc = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            encoding='utf-8', errors='replace', creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0),
                            env={**os.environ, 'PYTHONIOENCODING':'utf-8'})
    deadline = time.monotonic() + timeout
    while True:
        try:
            out, err = proc.communicate(timeout=0.2)
            break
        except subprocess.TimeoutExpired:
            if cancelled() or time.monotonic() > deadline:
                proc.kill()
                proc.communicate()
                raise OutcomeUnknown('桥接已中断或超时；Taber 可能已打开，请检查窗口再决定是否重试')
    if proc.returncode:
        raise ValueError((err or out or '桥接执行失败')[-2000:])
    return json.loads(out)


def execute(task, cancelled):
    if task['executor'] == 'agent-handoff':
        return 'waiting_external', handoff(task)
    if task['executor'] == 'local-inventory':
        return 'review', json.dumps(inventory(), ensure_ascii=False, indent=2)
    if task['executor'] == 'taber':
        session = next((s for s in sessions() if s['id'] == task['session']), None)
        if not session or not session['content_length']:
            raise ValueError('关联会话不存在或尚无已提交讲解')
        node = shutil.which('node')
        if not node or not TABER.is_file():
            raise ValueError('缺少 Node 或 Taber 桥接脚本')
        binding = command([node, str(TABER), 'open', '--workspace', str(STATE), '--session', session['id']], cancelled)
        context = None
        for _ in range(10):
            if cancelled():
                raise OutcomeUnknown('已取消；请核对已打开的 Taber 窗口')
            context = command([node, str(TABER), 'context'], cancelled)
            document = (context or {}).get('document') or {}
            if document.get('id') == 'learning:' + binding['id'] and document.get('version') == f"revision:{binding['revision']}":
                break
            time.sleep(0.4)
        else:
            raise OutcomeUnknown('桥接已返回，但当前阅读文档或版本尚未匹配；请检查 Taber 窗口')
        return 'review', json.dumps({'session':binding['session'], 'revision':binding['revision'],
            'document_id':document['id'], 'document_version':document['version'],
            'assistant_connected':binding.get('connected'), 'assistant_error':binding.get('error'),
            'note':'当前文档及版本已读回匹配，请检查窗口排版后验收。阅读不代表掌握。'}, ensure_ascii=False, indent=2)
    raise ValueError('没有此执行适配器')


_base_handoff = handoff
def handoff(task):
    return _base_handoff(task) + '\n\n任务协作约定（主机地位平等；离线不自动移交）：\n' + json.dumps(task.get('collaboration',{}),ensure_ascii=False,indent=2)
