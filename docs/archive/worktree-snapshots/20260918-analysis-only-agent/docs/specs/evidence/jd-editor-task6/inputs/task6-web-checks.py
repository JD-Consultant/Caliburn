"""Fixed isolated Web/native checks with individual raw logs and receipts."""
import json
import os
import subprocess
import sys
from pathlib import Path
from time import monotonic

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
NODE = HERE / 'task4-runtime/node-v22.23.2-win-x64'
env = {**os.environ, 'PATH': str(NODE)+os.pathsep+os.environ['PATH'],
       'PYTHONUTF8': '1', 'NEXT_TELEMETRY_DISABLED': '1', 'UV_OFFLINE': '1'}
for key in ('Q019_TEST_DATABASE_URL', 'OPENAI_API_KEY', 'OPENROUTER_API_KEY', 'ANTHROPIC_API_KEY', 'LANGSMITH_API_KEY'):
    env.pop(key, None)
checks = [
    ('codegen', ['run', 'check-codegen', '-w', '@caliburn/jd-editor-contract']),
    ('tests', ['run', 'test', '--workspaces', '--if-present']),
    ('build', ['run', 'build', '--workspaces', '--if-present']),
    ('types', ['run', 'typecheck', '-w', '@caliburn/jd-editor-web']),
    ('lint', ['run', 'lint', '-w', '@caliburn/jd-editor-web']),
]
receipts = []
phase = 'web-fix' if '--fix' in sys.argv else 'web'
if '--fix' in sys.argv:
    checks = checks[2:]
for name, args in checks:
    argv = [str(NODE/'node.exe'), str(NODE/'node_modules/npm/bin/npm-cli.js'), *args]
    start = monotonic()
    with (ROOT/f'scratch/task6-{phase}-{name}.log').open('w', encoding='utf8') as out:
        result = subprocess.run(argv, cwd=ROOT/'experiments/jd-editor', env=env, stdout=out,
                                stderr=subprocess.STDOUT, creationflags=subprocess.CREATE_NO_WINDOW)
    receipt = {'check': name, 'argv': argv, 'exit_code': result.returncode, 'elapsed_seconds': round(monotonic()-start, 2)}
    receipts.append(receipt)
    (ROOT/f'scratch/task6-{phase}-checks.json').write_text(json.dumps(receipts, indent=2), encoding='utf8')
    print(json.dumps(receipt), flush=True)
    if result.returncode:
        raise SystemExit(result.returncode)
