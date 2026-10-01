"""Final scoped Python checks, with JD and Memory DB groups kept separate."""
import json
import os
import subprocess
import sys
from pathlib import Path
from time import monotonic
from uuid import uuid4

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
A = ROOT/'experiments/analysis-agent'
env = {**os.environ, 'PYTHONUTF8': '1', 'Q019_LIFECYCLE_INSTALLATION': 'task6-final-'+sys.argv[1],
       'PATH': str(HERE/'task4-runtime/node-v22.23.2-win-x64')+os.pathsep+os.environ['PATH'],
       'PYTHONPATH': os.pathsep.join([str(A/'src'),str(ROOT/'experiments/jd-editor/contract/src')])}
for key in ('Q019_TEST_DATABASE_URL','OPENAI_API_KEY','OPENROUTER_API_KEY','ANTHROPIC_API_KEY','LANGSMITH_API_KEY'):
    env.pop(key,None)
kind = sys.argv[1]
if kind == 'all':
    argv = [sys.executable,'tests/task5_acceptance_runner.py','-q','-ra','--basetemp=../../scratch/task6-final-all-temp']
elif kind == 'jd':
    files = [str(p.relative_to(A)) for p in sorted((A/'tests').glob('test_jd*.py'))]
    argv = [sys.executable,str(HERE/'task4-run.py'),sys.executable,'tests/task5_acceptance_runner.py','-q','-ra',*files,'--basetemp=../../scratch/task6-final-jd-temp']
elif kind == 'memory':
    files = [str(p.relative_to(A)) for p in sorted((A/'tests').glob('test_postgres_*.py'))]
    argv = [sys.executable,'tests/task5_memory_runner.py','-q','-ra',*files,'tests/test_extraction_role.py::test_real_factory_routes_models_through_same_budget_and_lifetime','--basetemp=../../scratch/task6-final-memory-temp']
else:
    raise SystemExit('Unknown group')
# Each run owns a fresh temp tree; keep failed evidence without pytest cleanup.
argv[-1] = f'--basetemp=../../scratch/task6-{kind}-{uuid4().hex[:12]}'
start = monotonic()
with (ROOT/f'scratch/task6-final-{kind}.log').open('w',encoding='utf8') as out:
    result = subprocess.run(argv,cwd=A,env=env,stdout=out,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW)
receipt = {'group':kind,'argv':argv,'cwd':str(A),'exit_code':result.returncode,'elapsed_seconds':round(monotonic()-start,2),'provider':'offline fixtures only'}
(ROOT/f'scratch/task6-final-{kind}.json').write_text(json.dumps(receipt,indent=2),encoding='utf8')
print(json.dumps(receipt))
raise SystemExit(result.returncode)
