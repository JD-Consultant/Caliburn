"""Inject the existing dedicated Memory test DB only in this process's child env."""
import json
import os
import subprocess
import sys
from psycopg.conninfo import make_conninfo

container=json.loads(subprocess.check_output(['docker','inspect','caliburn-q019-postgres'],text=True))[0]
assert container['Id']=='68b894059353f5f9c068070dfd9b539430e7f61be27c5dd6845051d3fc6b2a65'
assert container['State']['Running'] and container['Config']['Image']=='postgres:16'
assert any(p['HostIp']=='127.0.0.1' and p['HostPort']=='55433' for p in container['NetworkSettings']['Ports']['5432/tcp'])
config=dict(v.split('=',1) for v in container['Config']['Env'] if '=' in v)
assert config['POSTGRES_USER']=='q019' and config['POSTGRES_DB']=='q019_agent_test'
env={**os.environ,'Q019_TEST_DATABASE_URL':make_conninfo(host='127.0.0.1',port=55433,
    user=config['POSTGRES_USER'],password=config['POSTGRES_PASSWORD'],dbname=config['POSTGRES_DB'],connect_timeout=5)}
result=subprocess.run([sys.executable,'tests/task5_acceptance_runner.py',*sys.argv[1:]],env=env,
    capture_output=True,text=True,encoding='utf-8',creationflags=subprocess.CREATE_NO_WINDOW)
sys.stdout.write(result.stdout)
sys.stderr.write(result.stderr)
raise SystemExit(result.returncode)
