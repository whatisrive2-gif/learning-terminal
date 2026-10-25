"""Double-click launcher: loopback service in a standalone Edge app window."""
import json
import os
from pathlib import Path
import subprocess
import sys
import urllib.request
import webbrowser
from hub.server import serve, ROOT


def open_window(url):
    edge = Path(os.environ.get('PROGRAMFILES(X86)', 'C:/Program Files (x86)')) / 'Microsoft/Edge/Application/msedge.exe'
    if edge.is_file():
        from window_state import windows
        previous=windows()
        subprocess.Popen([str(edge), '--app=' + url, '--new-window'], creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        subprocess.Popen([sys.executable, str(ROOT/'window_state.py'), *map(str,previous)],
                         creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    else:
        webbrowser.open(url)


def main():
    runtime = ROOT / 'data' / 'runtime.json'
    # Reuse only this workbench's authenticated loopback server.
    if runtime.is_file():
        try:
            old = json.loads(runtime.read_text(encoding='utf-8'))
            req = urllib.request.Request('http://127.0.0.1:8790/api/state', headers={'X-Hub-Token':old['token']})
            with urllib.request.urlopen(req, timeout=2) as response:
                if response.status == 200:
                    open_window('http://127.0.0.1:8790/#' + old['token'])
                    return
        except (OSError, ValueError, KeyError):
            pass
    server, hub, token = serve()
    runtime.parent.mkdir(parents=True, exist_ok=True)
    runtime.write_text(json.dumps({'token':token, 'pid':os.getpid()}), encoding='utf-8')
    if '--no-open' not in sys.argv:
        open_window('http://127.0.0.1:8790/#' + token)
    try:
        server.serve_forever()
    finally:
        hub.stop.set()
        server.server_close()
        runtime.unlink(missing_ok=True)


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        (ROOT / 'startup-error.txt').write_text(str(exc), encoding='utf-8')
        if sys.stderr:
            print('启动失败：' + str(exc), file=sys.stderr)
        sys.exit(1)
