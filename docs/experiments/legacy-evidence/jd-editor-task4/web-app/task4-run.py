"""Scoped offline test launcher; reads only Compose's db service credentials."""
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[3]
NODE = Path(__file__).parent / 'task4-runtime/node-v22.23.2-win-x64'
env = {**os.environ, 'PATH': str(NODE) + os.pathsep + os.environ['PATH'], 'PYTHONUTF8': '1'}
env['PYTHONPATH'] = os.pathsep.join([str(ROOT/'experiments/analysis-agent/src'), str(ROOT/'experiments/jd-editor/contract/src')])
config = json.loads(subprocess.check_output(['docker', 'compose', '-f', str(ROOT/'docker-compose.yml'), 'config', '--format', 'json'], text=True))
from psycopg.conninfo import make_conninfo
db = config['services']['db']['environment']
env['Q019_TEST_DATABASE_URL'] = make_conninfo(host='127.0.0.1', port='5432', user=db['POSTGRES_USER'], password=db['POSTGRES_PASSWORD'], dbname='q019_jd_app_20260910', connect_timeout=5)
raise SystemExit(subprocess.call(sys.argv[1:], env=env, cwd=ROOT/'experiments/analysis-agent'))
