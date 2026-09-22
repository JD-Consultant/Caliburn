"""Only Task4 review fix1 affected checks, launched by task4-run.py."""
import json, os, shutil, subprocess, time, sys
from pathlib import Path
here = Path(__file__).parent
root = here.parents[2]
j = root / 'experiments/jd-editor'
w = j / 'web'
a = root / 'experiments/analysis-agent'
node = shutil.which('node')
npm = str(Path(node).with_name('npm.cmd'))
jobs = [
    ('api', a, ['uv', 'run', 'pytest', '-q', 'tests/test_jd_api.py', '-k', 'manual_rejection or routes_manual']),
    ('web-tests', w, [node, '../node_modules/vitest/vitest.mjs', 'run', 'src/jd/useJdSession.test.tsx', 'src/documents/DocumentList.test.tsx']),
    ('codegen-check', j, ['cmd.exe', '/d', '/c', npm, 'run', 'check-codegen', '-w', '@caliburn/jd-editor-contract']),
    ('types', w, ['cmd.exe', '/d', '/c', npm, 'run', 'typecheck']),
    ('lint', w, ['cmd.exe', '/d', '/c', npm, 'run', 'lint']),
    ('build', w, ['cmd.exe', '/d', '/c', npm, 'run', 'build']),
]
if len(sys.argv) > 1:
    jobs = [job for job in jobs if job[0] in sys.argv[1:]]
summary = {'node': node, 'PYTHONUTF8': os.environ.get('PYTHONUTF8'), 'runs': []}
try:
    for name, cwd, command in jobs:
        start = time.perf_counter()
        result = subprocess.run(command, cwd=cwd, capture_output=True, encoding='utf-8', errors='replace')
        (here / f'task4-fix1-final-{name}.log').write_text(result.stdout + result.stderr, encoding='utf-8')
        summary['runs'].append({'name': name, 'cwd': str(cwd), 'command': command, 'exit_code': result.returncode, 'seconds': time.perf_counter()-start})
        print(name, 'exit', result.returncode, flush=True)
        if result.returncode:
            print((result.stdout+result.stderr)[-5000:], flush=True)
            raise SystemExit(result.returncode)
finally:
    (here / 'task4-fix1-verification.json').write_text(json.dumps(summary, indent=2), encoding='utf-8')
