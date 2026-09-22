"""Fresh fixed-provider API and built Web for the one core regression."""
import json
import os
from pathlib import Path
import socket
import subprocess
from datetime import datetime, timezone
from psycopg.conninfo import make_conninfo

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
NODE = HERE / 'task4-runtime/node-v22.23.2-win-x64'
for port in (8091, 3001):
    with socket.socket() as sock:
        if sock.connect_ex(('127.0.0.1', port)) == 0:
            raise SystemExit('Port occupied; inspect its owner before acting')
env = {**os.environ, 'PATH': str(NODE) + os.pathsep + os.environ['PATH'], 'PYTHONUTF8': '1',
       'NEXT_TELEMETRY_DISABLED': '1', 'Q019_LIFECYCLE_INSTALLATION': 'jd-task6-offline-20260911',
       'Q019_TEST_RECORD_PATH': str(ROOT/'scratch/core-browser-wire.jsonl'),
       'PYTHONPATH': os.pathsep.join([str(ROOT/'experiments/analysis-agent/src'), str(ROOT/'experiments/jd-editor/contract/src')])}
for key in ('OPENAI_API_KEY', 'OPENROUTER_API_KEY', 'ANTHROPIC_API_KEY', 'LANGSMITH_API_KEY'):
    env.pop(key, None)
config = json.loads(subprocess.check_output(['docker', 'compose', '-f', str(ROOT/'docker-compose.yml'), 'config', '--format', 'json'], text=True))
db = config['services']['db']['environment']
env['Q019_TEST_DATABASE_URL'] = make_conninfo(host='127.0.0.1', port='5432', user=db['POSTGRES_USER'], password=db['POSTGRES_PASSWORD'], dbname='q019_jd_app_20260910', connect_timeout=5)
commands = [
    ('api', [str(ROOT/'experiments/analysis-agent/.venv/Scripts/python.exe'), '-m', 'uvicorn', 'jd_offline_service:create_app', '--factory', '--app-dir', 'tests', '--host', '127.0.0.1', '--port', '8091', '--workers', '1', '--no-proxy-headers'], ROOT/'experiments/analysis-agent'),
    ('web', [str(NODE/'node.exe'), str(ROOT/'experiments/jd-editor/node_modules/next/dist/bin/next'), 'start', '--hostname', '127.0.0.1', '--port', '3001'], ROOT/'experiments/jd-editor/web'),
]
launched = []
for name, argv, cwd in commands:
    with (ROOT/f'scratch/core-{name}.log').open('w', encoding='utf8') as out:
        proc = subprocess.Popen(argv, cwd=cwd, env=env, stdout=out, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL, creationflags=subprocess.CREATE_NO_WINDOW)
    launched.append({'name': name, 'pid': proc.pid, 'argv': argv, 'cwd': str(cwd)})
result = {'created_utc': datetime.now(timezone.utc).isoformat(), 'processes': launched, 'provider': 'fixed offline transport only'}
(ROOT/'scratch/core-servers.json').write_text(json.dumps(result, indent=2), encoding='utf8')
print(json.dumps(result))
