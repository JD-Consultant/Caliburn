"""Capture explicit Task6 sources and synthetic acceptance evidence, no secrets."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
DEST = ROOT/'docs/specs/evidence/jd-editor-task6'
DEST.mkdir(exist_ok=True)
files = [
    '.gitattributes',
    *('experiments/analysis-agent/src/analysis_agent/'+name for name in (
        'api.py', 'jd_tools.py', 'skills.py', 'skills/compare-work-patterns/SKILL.md',
        'skills/outcomes-and-expertise/SKILL.md', 'skills/work-scope-interview/SKILL.md',
        'skills/write-customized-jd/SKILL.md',
        'skills/write-customized-jd/references/complete-work-guide.md',
        'skills/write-customized-jd/references/writing-and-correction.md')),
    *('experiments/analysis-agent/tests/'+name for name in (
        'test_context_budget.py','test_native_context_budget.py','test_extraction_role.py',
        'test_postgres_service.py','test_memory_prompt_contract.py','test_read_recovery.py',
        'test_jd_skill_contract.py','test_jd_end_to_end.py','test_jd_current_source_acquisition.py',
        'jd_offline_service.py','fixtures/jd-task6-prompt-delta.json')),
    *('experiments/jd-editor/'+name for name in (
        'fixtures/core-scenario.json','web/src/jd/JdEditor.tsx','web/src/jd/useJdSession.ts',
        'web/src/jd/JdSavedProjection.test.tsx','web/browser/task6-journey.mjs',
        'web/package.json','package-lock.json','README.md','ACCEPTANCE.md')),
    'experiments/analysis-agent/README.md',
    'docs/specs/evidence/2026-09-10-jd-editor-core-integration.md',
]
(HERE/'task-6-files.json').write_text(json.dumps(files,indent=2),encoding='utf8')
subprocess.run([sys.executable,str(HERE/'capture-task-review.py'),'--base','444416722190fd48c14f4423d101f36b25831de1',
                '--name','task-6','--files',str(HERE/'task-6-files.json'),'--overrides',str(HERE/'task-6-review-overrides.json')],check=True)
records = []
def copy(source, relative):
    data = source.read_bytes()
    target = DEST/relative
    target.parent.mkdir(parents=True,exist_ok=True)
    if target.exists(): raise RuntimeError(f'Existing evidence: {target}')
    target.write_bytes(data)
    records.append({'path':relative,'sha256':hashlib.sha256(data).hexdigest(),'bytes':len(data)})
for source in sorted((ROOT/'scratch').glob('task6-*')):
    if source.is_file() and source.suffix in ('.log','.json','.png','.md'):
        copy(source,source.name)
for name in ('task6-python-regression.py','task6-web-checks.py','task6-start-servers.py',
             'task6-start-built-web.py','task4-run.py','task-6-method-preflight.md',
             'task-6-method-input-manifest.json','task-6-readme-baseline.md',
             'task-6-review-manifest.json','task-6-review.diff'):
    copy(HERE/name,'inputs/'+name)
for item in json.loads((HERE/'task-6-review-manifest.json').read_text(encoding='utf8')):
    copy(HERE/'task-6-snapshot'/item['path'],'source/'+item['path'])
for name in ('claude-source-review','claude-web-review','claude-regression-review','claude-task6-check'):
    packet=HERE/name
    events=[json.loads(line) for line in (packet/'response.jsonl').read_text(encoding='utf8').splitlines() if line.strip()]
    init=next(e for e in events if e.get('type')=='system' and e.get('subtype')=='init')
    final=next(e for e in reversed(events) if e.get('type')=='result')
    result={'init':{k:init.get(k) for k in ('model','tools','mcp_servers')},
            'result':{k:final.get(k) for k in ('subtype','is_error','result','duration_ms','num_turns','total_cost_usd','modelUsage')}}
    out=DEST/'reviews'/name
    out.mkdir(parents=True,exist_ok=True)
    (out/'result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8')
    for filename in ('manifest.json','prompt.txt','invocation.json'):
        copy(packet/filename,f'reviews/{name}/{filename}')
(DEST/'artifact-manifest.json').write_text(json.dumps(records,indent=2),encoding='utf8')
print(json.dumps({'source_files':len(files),'captured_artifacts':len(records)}))
