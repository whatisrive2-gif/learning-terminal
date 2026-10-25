"""Qoder-owned tool service adapter. Fixed loopback target; never retries POST."""
import json
import re
import socket
import urllib.error
import urllib.request
from datetime import datetime, timezone

BASE_URL = 'http://127.0.0.1:8787'
TOOLS = {'homework-crawler', 'dirwatch', 'material-transfer'}


class ServiceError(ValueError):
    pass


class SubmissionUnknown(ServiceError):
    pass


class MissingRun(ServiceError):
    pass


def request(path, body=None):
    req = urllib.request.Request(BASE_URL + path, headers={'Content-Type':'application/json'},
        data=json.dumps(body).encode() if body is not None else None)
    # Explicitly bypass system proxies for the fixed local service; disallow redirects.
    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, *args, **kwargs): return None
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
    try:
        with opener.open(req, timeout=5) as response:
            data = json.loads(response.read(4_000_001))
            if not isinstance(data, dict): raise ValueError('接口返回结构无效')
            return data
    except urllib.error.HTTPError as exc:
        if 400 <= exc.code < 500:
            if exc.code == 404 and path.startswith('/api/runs/'):
                raise MissingRun('远端运行记录已不存在，不能据此判断执行失败或重新执行') from None
            raise ServiceError(f'工具服务拒绝请求（HTTP {exc.code}）；409 表示该工具可能正在执行') from None
        error = SubmissionUnknown if body is not None else ServiceError
        raise error(f'工具服务返回 HTTP {exc.code}；请核对服务状态') from None
    except (OSError, ValueError, socket.timeout, urllib.error.URLError):
        error = SubmissionUnknown if body is not None else ServiceError
        raise error('无法连接工具服务或响应不完整；写入请求可能已受理，禁止自动重发' if body is not None
                    else '工具服务离线或响应不可读，请启动协议目录中的同步服务') from None


def validate(tool, action, data):
    if tool not in TOOLS: raise ValueError('工具不在允许清单中')
    if action not in {'run', 'enable', 'disable', 'backfill', 'configure'}: raise ValueError('不支持的工具操作')
    if action == 'configure':
        if tool != 'dirwatch': raise ValueError('目前仅目录监听支持配置')
        from pathlib import Path
        watch=data.get('watchDir')
        interval=data.get('intervalMinutes')
        if not isinstance(watch,str) or not Path(watch).is_absolute() or not Path(watch).is_dir(): raise ValueError('请选择存在的绝对目录')
        if type(interval) is not int or not 1 <= interval <= 1440: raise ValueError('检查间隔须为 1—1440 分钟')
        return {'watchDir':watch,'intervalMinutes':interval}
    if tool == 'material-transfer' and action != 'backfill': raise ValueError('材料收发是服务类工具，仅支持查询与显式补发')
    if action == 'backfill':
        if tool != 'material-transfer': raise ValueError('补发仅由材料收发工具执行')
        sha = data.get('sha256', '')
        if not isinstance(sha, str) or not re.fullmatch(r'[0-9a-f]{64}', sha):
            raise ValueError('请选择单条材料补发；不默认补发所有历史材料')
        return {'sha256':sha}
    if action == 'run':
        dry = data.get('dryRun', False)
        if not isinstance(dry, bool): raise ValueError('dryRun 必须是布尔值')
        return {'input':{'dryRun':dry}}
    return {}


def catalog():
    try:
        result = request('/api/tools')
        if not isinstance(result.get('tools'), list): raise ServiceError('工具清单结构无效')
        return {'online':True, 'tools':result['tools'], 'sampledAt':datetime.now(timezone.utc).isoformat()}
    except ServiceError as exc:
        return {'online':False, 'tools':[], 'error':str(exc), 'sampledAt':datetime.now(timezone.utc).isoformat()}


def detail(tool):
    if tool not in TOOLS: raise ValueError('未知工具')
    return {'tool':request('/api/tools/'+tool),
            'runs':request('/api/tools/'+tool+'/runs?limit=20').get('runs', []),
            'items':request('/api/tools/'+tool+'/items').get('items', []),
            'sampledAt':datetime.now(timezone.utc).isoformat()}


def submit(task):
    body = validate(task['tool_id'], task['tool_action'], task['tool_input'])
    result = request('/api/tools/'+task['tool_id']+'/'+task['tool_action'], body)
    if task['tool_action'] == 'run':
        rid = result.get('runId')
        if result.get('status') != 'accepted' or not isinstance(rid, str) or not re.fullmatch(r'[\w-]{1,100}', rid):
            raise SubmissionUnknown('提交响应缺少有效 runId；请查远端历史，不自动重发')
    return result


def run_status(run_id):
    if not re.fullmatch(r'[\w-]{1,100}', run_id): raise ValueError('运行标识无效')
    result = request('/api/runs/'+run_id)
    if result.get('id') != run_id or result.get('status') not in {'accepted','running','completed','failed'}:
        raise ServiceError('运行返回的标识或状态不匹配')
    return result
