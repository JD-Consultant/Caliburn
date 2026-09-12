"""Start the already-built, isolated Web for a final read/reopen check."""
import json
import os
from pathlib import Path
import socket
import subprocess
from datetime import datetime, timezone

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
NODE = HERE/'task4-runtime/node-v22.23.2-win-x64/node.exe'
with socket.socket() as s:
    if s.connect_ex(('127.0.0.1', 3001)) == 0:
        raise SystemExit('Port occupied; inspect exact owner, do not kill by port')
argv = [str(NODE), str(ROOT/'experiments/jd-editor/node_modules/next/dist/bin/next'),
        'start', '--hostname', '127.0.0.1', '--port', '3001']
env = {**os.environ, 'NEXT_TELEMETRY_DISABLED': '1'}
for key in ('Q019_TEST_DATABASE_URL', 'OPENAI_API_KEY', 'OPENROUTER_API_KEY', 'ANTHROPIC_API_KEY', 'LANGSMITH_API_KEY'):
    env.pop(key, None)
with (ROOT/'scratch/core-final-web.log').open('w', encoding='utf8') as out:
    proc = subprocess.Popen(argv, cwd=ROOT/'experiments/jd-editor/web', env=env, stdout=out,
                            stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL, creationflags=subprocess.CREATE_NO_WINDOW)
result = {'pid': proc.pid, 'argv': argv, 'created_utc': datetime.now(timezone.utc).isoformat()}
(ROOT/'scratch/core-final-web-server.json').write_text(json.dumps(result, indent=2), encoding='utf8')
print(json.dumps(result))
