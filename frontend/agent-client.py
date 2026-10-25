"""Load this client from any local Agent. Credentials never appear in output."""
import argparse
import json
from pathlib import Path
import urllib.request

ROOT=Path(__file__).resolve().parent
def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('command',choices=['register','inbox','result','assign','message','create-task','heartbeat','offline','workspace','set-collaboration','export-packet','import-packet','register-host'])
    parser.add_argument('--file',help='UTF-8 JSON request file')
    parser.add_argument('--agent-id')
    args=parser.parse_args()
    data=json.loads(Path(args.file).read_text(encoding='utf-8-sig')) if args.file else {}
    if args.agent_id: data['agent_id']=args.agent_id
    data['action']=args.command
    runtime=json.loads((ROOT/'data/runtime.json').read_text(encoding='utf-8'))
    route='tasks' if args.command=='create-task' else 'agent'
    if args.command=='workspace': route='workspace'
    if args.command=='register-host': route='workspace/hosts'
    if args.command=='set-collaboration':
        route='tasks/'+data.pop('task_id')
        data['action']='collaboration'
    req=urllib.request.Request('http://127.0.0.1:8790/api/'+route,data=None if args.command=='workspace' else json.dumps(data).encode(),headers={'X-Hub-Token':runtime['token'],'Content-Type':'application/json'})
    try:
        with urllib.request.build_opener(urllib.request.ProxyHandler({})).open(req,timeout=30) as response:
            print(json.dumps(json.load(response),ensure_ascii=False,indent=2))
    except urllib.error.HTTPError as exc:
        print(exc.read().decode('utf-8'));raise SystemExit(1)

if __name__=='__main__': main()
