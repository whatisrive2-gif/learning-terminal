import argparse
import hmac
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import secrets
import threading
import time
from urllib.parse import urlparse

from .core import Store, Conflict
from . import adapters, toolcenter

ROOT = Path(__file__).resolve().parent.parent


class Hub:
    def __init__(self, db):
        self.store = Store(db)
        self.stop = threading.Event()
        self.worker = threading.Thread(target=self.run, daemon=True)
        self.tool_worker = threading.Thread(target=self.poll_tools, daemon=True)

    def poll_tools(self):
        while not self.stop.is_set():
            for task in self.store.list():
                if self.stop.is_set(): break
                if task['state'] != 'waiting_tool': continue
                try:
                    run = toolcenter.run_status(task['remote_run_id'])
                    if run.get('toolId') != task['tool_id']: raise toolcenter.ServiceError('工具身份不匹配')
                    state = {'completed':'review', 'failed':'failed'}.get(run['status'], 'waiting_tool')
                    self.store.tool_update(task['id'], task['run_id'], state,
                        json.dumps(run, ensure_ascii=False, indent=2), tool_run=run, poll_error=None)
                except toolcenter.MissingRun as exc:
                    self.store.tool_update(task['id'], task['run_id'], 'unknown', str(exc), poll_error=str(exc))
                except toolcenter.ServiceError as exc:
                    # Preserve the accepted ID and keep querying; never repeat submission.
                    self.store.tool_update(task['id'], task['run_id'], 'waiting_tool', task['result'], poll_error=str(exc))
                except Exception as exc:
                    self.store.tool_update(task['id'], task['run_id'], 'unknown', str(exc)[:500])
            self.stop.wait(3)

    def run(self):
        while not self.stop.is_set():
            task = self.store.claim()
            if task:
                try:
                    if task['executor'] == 'qoder-tool':
                        result = toolcenter.submit(task)
                        if task['tool_action'] == 'run':
                            self.store.tool_update(task['id'], task['run_id'], 'waiting_tool',
                                json.dumps(result, ensure_ascii=False), remote_run_id=result['runId'])
                        else:
                            failures = [r for r in result.get('results', []) if not r.get('ok')]
                            self.store.tool_update(task['id'], task['run_id'], 'failed' if failures else 'review',
                                json.dumps(result, ensure_ascii=False, indent=2))
                        continue
                    state, result = adapters.execute(task, lambda: self.stop.is_set() or self.store.get(task['id'])['state'] == 'cancelled')
                except toolcenter.SubmissionUnknown as exc:
                    state, result = 'unknown', str(exc)
                except adapters.OutcomeUnknown as exc:
                    state, result = 'unknown', str(exc)[:3000]
                except Exception as exc:
                    state, result = 'failed', str(exc)[:3000]
                self.store.finish(task['id'], task['run_id'], state, result)
            else:
                self.stop.wait(0.5)


def serve(port=8790, db=None):
    hub = Hub(db or ROOT / 'data' / 'hub.sqlite3')
    token = secrets.token_urlsafe(32)
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass

        def send(self, code, data, content_type='application/json; charset=utf-8'):
            raw = data if isinstance(data, bytes) else json.dumps(data, ensure_ascii=False).encode('utf-8')
            self.send_response(code)
            self.send_header('Content-Type', content_type)
            self.send_header('Content-Length', str(len(raw)))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.send_header('Referrer-Policy', 'no-referrer')
            self.send_header('Content-Security-Policy', "default-src 'self'; style-src 'self'; script-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'")
            self.end_headers()
            self.wfile.write(raw)

        def guard(self):
            host = f'127.0.0.1:{self.server.server_port}'
            if self.headers.get('Host') != host:
                self.send(403, {'error':'仅允许本机地址'})
                return False
            origin = self.headers.get('Origin')
            if origin and origin != 'http://' + host:
                self.send(403, {'error':'来源不受信任'})
                return False
            return True

        def auth(self):
            if not hmac.compare_digest(self.headers.get('X-Hub-Token', '').encode(), token.encode()):
                self.send(401, {'error':'请从启动入口重新打开工作台'})
                return False
            return True

        def do_GET(self):
            if not self.guard(): return
            path = urlparse(self.path).path
            if path in {'/', '/app.js', '/tool-ui.js', '/style.css'}:
                name, mime = {'/':('index.html','text/html'), '/app.js':('app.js','text/javascript'), '/tool-ui.js':('tool-ui.js','text/javascript'), '/style.css':('style.css','text/css')}[path]
                return self.send(200, (ROOT / 'web' / name).read_bytes(), mime + '; charset=utf-8')
            if not self.auth(): return
            try:
                if path == '/api/state':
                    tasks = hub.store.list()
                    for task in tasks: task['blocked_by'] = hub.store.blocked(task)
                    data = dict(tasks=tasks, events=hub.store.events(), model_calls=0)
                elif path == '/api/sessions': data = adapters.sessions()
                elif path == '/api/inventory': data = adapters.inventory()
                elif path == '/api/export': data = hub.store.export()
                elif path == '/api/tools': data = toolcenter.catalog()
                elif path.startswith('/api/tools/'): data = toolcenter.detail(path.split('/')[-1])
                else: return self.send(404, {'error':'没有此接口'})
                self.send(200, data)
            except Exception as exc:
                self.send(400, {'error':str(exc)})

        def do_POST(self):
            if not self.guard() or not self.auth(): return
            try:
                if self.headers.get('Content-Type', '').split(';')[0] != 'application/json':
                    raise ValueError('仅接受 JSON')
                length = int(self.headers.get('Content-Length', '0'))
                if not 0 < length <= 100000: raise ValueError('请求大小无效')
                data = json.loads(self.rfile.read(length))
                if not isinstance(data, dict): raise ValueError('请求必须为对象')
                path = urlparse(self.path).path
                if path == '/api/tasks': result = hub.store.create(data)
                elif path == '/api/tool-actions': result = hub.store.create_tool(data)
                elif path.startswith('/api/tasks/'):
                    result = hub.store.change(path.split('/')[-1], data)
                elif path == '/api/shutdown':
                    self.send(200, {'ok':True})
                    hub.stop.set()
                    threading.Thread(target=self.server.shutdown, daemon=True).start()
                    return
                else: return self.send(404, {'error':'没有此接口'})
                self.send(200, result)
            except Conflict as exc: self.send(409, {'error':str(exc)})
            except (ValueError, TypeError, KeyError) as exc: self.send(400, {'error':str(exc)})

    server = ThreadingHTTPServer(('127.0.0.1', port), Handler)
    server.daemon_threads = True
    hub.worker.start()
    hub.tool_worker.start()
    return server, hub, token


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', type=int, default=8790)
    args = parser.parse_args()
    server, hub, token = serve(args.port)
    # CLI use only; desktop launcher never emits this token to logs.
    print(f'http://127.0.0.1:{server.server_port}/#{token}', flush=True)
    try: server.serve_forever()
    finally:
        hub.stop.set()
        server.server_close()
