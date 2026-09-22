"""Affected checks for the integrated core review findings; no providers."""
import json
import os
from pathlib import Path
import subprocess
import sys
from time import monotonic

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
NODE = HERE / 'task4-runtime/node-v22.23.2-win-x64'
A = ROOT / 'experiments/analysis-agent'
J = ROOT / 'experiments/jd-editor'
env = {**os.environ, 'PATH': str(NODE) + os.pathsep + os.environ['PATH'], 'PYTHONUTF8': '1',
       'NEXT_TELEMETRY_DISABLED': '1', 'UV_OFFLINE': '1', 'Q019_LIFECYCLE_INSTALLATION': 'jd-core-review-fix',
       'PYTHONPATH': os.pathsep.join([str(A/'src'), str(J/'contract/src')])}
for key in ('OPENAI_API_KEY', 'OPENROUTER_API_KEY', 'ANTHROPIC_API_KEY', 'LANGSMITH_API_KEY', 'Q019_TEST_DATABASE_URL'):
    env.pop(key, None)
kind = sys.argv[1]
if kind == 'python':
    checks = [('python', [sys.executable, 'tests/task5_acceptance_runner.py', '-q', 'tests/test_jd_shutdown_isolation.py', 'tests/test_service.py', 'tests/test_conversation_lifecycle.py', 'tests/test_read_recovery.py', '--basetemp=../../scratch/core-minor-python-temp'], A),
              ('pg', [sys.executable, str(HERE/'task4-run.py'), sys.executable, 'tests/task5_acceptance_runner.py', '-q', 'tests/test_jd_close_reconcile.py', 'tests/test_jd_admission.py', 'tests/test_jd_postgres_recovery.py', '--basetemp=../../scratch/core-minor-pg-temp'], A)]
else:
    npm = [str(NODE/'node.exe'), str(NODE/'node_modules/npm/bin/npm-cli.js')]
    checks = [(name, [*npm, 'run', name, '-w', '@caliburn/jd-editor-web'], J) for name in ('test', 'build', 'typecheck', 'lint')]
results = []
for name, argv, cwd in checks:
    started = monotonic()
    with (ROOT/f'scratch/core-minor-{name}.log').open('w', encoding='utf8') as out:
        result = subprocess.run(argv, cwd=cwd, env=env, stdout=out, stderr=subprocess.STDOUT, creationflags=subprocess.CREATE_NO_WINDOW)
    item = {'check': name, 'argv': argv, 'cwd': str(cwd), 'exit_code': result.returncode, 'seconds': round(monotonic()-started, 2)}
    results.append(item)
    (ROOT/f'scratch/core-minor-{kind}-results.json').write_text(json.dumps(results, indent=2), encoding='utf8')
    print(json.dumps(item), flush=True)
    if result.returncode:
        raise SystemExit(result.returncode)
