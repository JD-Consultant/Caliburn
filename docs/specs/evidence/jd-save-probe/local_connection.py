"""Probe-only connection; credentials stay in memory and are never printed."""
import json
import subprocess
from psycopg.conninfo import make_conninfo

DATABASE = 'jd_editor_probe_p01_20260909'
CONTAINER = 'caliburn-q019-postgres'

def load_probe_dsn(*, control=False):
    result = subprocess.run(
        ['docker', 'inspect', '--format', '{{json .Config.Env}}', CONTAINER],
        capture_output=True, text=True, timeout=10, check=False,
    )
    if result.returncode:
        raise RuntimeError('Cannot inspect the known local PostgreSQL container; no credentials emitted')
    config = dict(item.split('=', 1) for item in json.loads(result.stdout) if '=' in item)
    user = config.get('POSTGRES_USER')
    password = config.get('POSTGRES_PASSWORD')
    if user != 'q019' or not password:
        raise RuntimeError('Unexpected local database configuration')
    return make_conninfo(host='127.0.0.1', port=55433, user=user, password=password,
                         dbname='postgres' if control else DATABASE, connect_timeout=5)
