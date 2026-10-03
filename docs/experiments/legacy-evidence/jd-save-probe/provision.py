"""Create only this probe's dedicated database; never emit credentials."""
import json
from pathlib import Path

import psycopg
from psycopg import sql
from local_connection import load_probe_dsn, DATABASE

TARGET = DATABASE
ROOT = Path(__file__).resolve().parent
control = load_probe_dsn(control=True)
with psycopg.connect(control, autocommit=True) as connection:
    existing = connection.execute('SELECT 1 FROM pg_database WHERE datname = %s', (TARGET,)).fetchone()
    if existing:
        raise RuntimeError('Probe database exists; inspect ownership/evidence instead of overwriting')
    connection.execute(sql.SQL('CREATE DATABASE {}').format(sql.Identifier(TARGET)))
probe_dsn = load_probe_dsn()
with psycopg.connect(probe_dsn) as connection:
    name, version = connection.execute('SELECT current_database(), version()').fetchone()
    tables = connection.execute("SELECT tablename FROM pg_tables WHERE schemaname='public'").fetchall()
    assert name == TARGET and tables == []
report = {'database': TARGET, 'host': '127.0.0.1', 'port': '55433',
          'version': version, 'initial_public_tables': tables,
          'created_by_this_probe': True, 'credential_source': 'existing local configuration; not archived'}
(ROOT / 'results').mkdir(exist_ok=True)
(ROOT / 'results/provision.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps(report, ensure_ascii=False))
