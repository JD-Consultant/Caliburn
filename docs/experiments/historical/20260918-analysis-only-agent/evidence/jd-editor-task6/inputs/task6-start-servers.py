"""Start only the explicitly isolated offline API and JD Web for acceptance."""
import json
import os
import socket
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from psycopg.conninfo import make_conninfo

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
NODE = HERE/'task4-runtime/node-v22.23.2-win-x64'
api_only = '--api-only' in sys.argv
for port in ([8091] if api_only else [8091, 3001]):
    with socket.socket() as s:
        if s.connect_ex(('127.0.0.1', port)) == 0:
            raise SystemExit(f'Port {port} already occupied; inspect owner before any action')
env = {**os.environ, 'PATH': str(NODE)+os.pathsep+os.environ['PATH'], 'PYTHONUTF8': '1',
       'Q019_LIFECYCLE_INSTALLATION': 'jd-task6-offline-20260911',
       'Q019_TEST_RECORD_PATH': str(ROOT/'scratch/task6-browser-wire.jsonl'),
       'PYTHONPATH': os.pathsep.join([str(ROOT/'experiments/analysis-agent/src'), str(ROOT/'experiments/jd-editor/contract/src')]),
       'NEXT_TELEMETRY_DISABLED': '1'}
config = json.loads(subprocess.check_output(['docker','compose','-f',str(ROOT/'docker-compose.yml'),'config','--format','json'],text=True))
db = config['services']['db']['environment']
env['Q019_TEST_DATABASE_URL'] = make_conninfo(host='127.0.0.1',port='5432',user=db['POSTGRES_USER'],password=db['POSTGRES_PASSWORD'],dbname='q019_jd_app_20260910',connect_timeout=5)
phase = 'restarted' if api_only else 'initial'
commands = [('api', [str(ROOT/'experiments/analysis-agent/.venv/Scripts/python.exe'),'-m','uvicorn','jd_offline_service:create_app','--factory','--app-dir','tests','--host','127.0.0.1','--port','8091','--workers','1','--no-proxy-headers'], ROOT/'experiments/analysis-agent')]
if not api_only:
    commands.append(('web', [str(NODE/'node.exe'),str(NODE/'node_modules/npm/bin/npm-cli.js'),'run','dev','-w','@caliburn/jd-editor-web'],ROOT/'experiments/jd-editor'))
launched = []
for name, argv, cwd in commands:
    with (ROOT/f'scratch/task6-{phase}-{name}.log').open('w',encoding='utf8') as out:
        proc = subprocess.Popen(argv,cwd=cwd,env=env,stdout=out,stderr=subprocess.STDOUT,stdin=subprocess.DEVNULL,creationflags=subprocess.CREATE_NO_WINDOW)
    launched.append({'name':name,'pid':proc.pid,'argv':argv,'cwd':str(cwd)})
result = {'observed_utc':datetime.now(timezone.utc).isoformat(),'phase':phase,'processes':launched,'provider':'httpx.MockTransport only'}
(ROOT/f'scratch/task6-{phase}-servers.json').write_text(json.dumps(result,indent=2),encoding='utf8')
print(json.dumps(result))
