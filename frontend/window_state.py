"""Remember this application's native window placement, including maximization."""
import ctypes
from ctypes import wintypes as W
import json
import os
from pathlib import Path
import sys
import time

STATE = Path(__file__).resolve().parent / 'data' / 'window-placement.json'
TITLE = '学习终端 · 工作台'

class Placement(ctypes.Structure):
    _fields_ = [('length',W.UINT),('flags',W.UINT),('showCmd',W.UINT),
                ('ptMinPosition',W.POINT),('ptMaxPosition',W.POINT),('rcNormalPosition',W.RECT)]

def api():
    user = ctypes.WinDLL('user32', use_last_error=True)
    user.GetWindowPlacement.argtypes=[W.HWND,ctypes.POINTER(Placement)]
    user.SetWindowPlacement.argtypes=[W.HWND,ctypes.POINTER(Placement)]
    user.GetWindowTextLengthW.argtypes=[W.HWND]
    user.GetWindowTextW.argtypes=[W.HWND,W.LPWSTR,ctypes.c_int]
    user.IsWindow.argtypes=[W.HWND]
    user.IsWindowVisible.argtypes=[W.HWND]
    user.IsIconic.argtypes=[W.HWND]
    return user

def windows():
    if os.name!='nt': return []
    user=api();found=[]
    callback=ctypes.WINFUNCTYPE(W.BOOL,W.HWND,W.LPARAM)
    @callback
    def visit(hwnd,_):
        text=ctypes.create_unicode_buffer(user.GetWindowTextLengthW(hwnd)+1)
        user.GetWindowTextW(hwnd,text,len(text))
        if user.IsWindowVisible(hwnd) and text.value.startswith(TITLE): found.append(int(hwnd))
        return True
    user.EnumWindows.argtypes=[callback,W.LPARAM]
    user.EnumWindows(visit,0)
    return found

def read_state(path=STATE):
    try:
        data=json.loads(path.read_text(encoding='utf-8'))
        if not all(type(data.get(k)) is int for k in ('left','top','right','bottom')): return None
        if not (320<=data['right']-data['left']<=20000 and 240<=data['bottom']-data['top']<=20000): return None
        return data
    except (OSError,ValueError): return None

def capture(hwnd):
    user=api()
    if not user.IsWindow(hwnd) or user.IsIconic(hwnd): return None
    p=Placement();p.length=ctypes.sizeof(p)
    if not user.GetWindowPlacement(hwnd,ctypes.byref(p)): return None
    r=p.rcNormalPosition
    return dict(left=r.left,top=r.top,right=r.right,bottom=r.bottom,maximized=p.showCmd==3)

def restore(hwnd,data):
    if not data: return
    p=Placement();p.length=ctypes.sizeof(p)
    p.showCmd=3 if data.get('maximized') else 1
    p.rcNormalPosition=W.RECT(data['left'],data['top'],data['right'],data['bottom'])
    # Windows relocates a saved placement when the original monitor is unavailable.
    if not api().SetWindowPlacement(hwnd,ctypes.byref(p)): raise ctypes.WinError(ctypes.get_last_error())

def watch(previous):
    saved=read_state();deadline=time.monotonic()+30
    hwnd=None
    while time.monotonic()<deadline:
        fresh=[h for h in windows() if h not in previous]
        if fresh: hwnd=fresh[0];break
        time.sleep(.2)
    if not hwnd: return
    time.sleep(.5)
    restore(hwnd,saved)
    last=None
    while api().IsWindow(hwnd):
        current=capture(hwnd)
        if current and current!=last:
            STATE.parent.mkdir(parents=True,exist_ok=True)
            tmp=STATE.with_suffix('.'+str(os.getpid())+'.tmp')
            tmp.write_text(json.dumps(current),encoding='utf-8');tmp.replace(STATE)
            last=current
        time.sleep(.4)

if __name__=='__main__':
    watch({int(x) for x in sys.argv[1:]})
