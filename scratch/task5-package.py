"""Capture only this task's declared implementation and immutable review evidence."""
from pathlib import Path
import hashlib,json,shutil,difflib,subprocess

root=Path(__file__).resolve().parents[1]
plan=root/'.superpowers/sdd/2026-09-10-jd-editor-core-implementation'
delivery=root/'docs/specs/evidence/jd-editor-task5/implementation'
delivery.mkdir(parents=True,exist_ok=True)
api='experiments/analysis-agent/'
web='experiments/jd-editor/web/'
source=[api+p for p in ['README.md','pyproject.toml','uv.lock','scripts/export_web_contract.py',
    *['src/analysis_agent/'+p+'.py' for p in ['api','conversation','jd_engine','jd_reconcile','jd_routes','jd_service','jd_store','jd_tools','service','windows_lifecycle']],
    *['tests/'+p+'.py' for p in ['jd_browser_server','jd_lifecycle_process_worker','task5_acceptance_runner','task5_memory_runner',
        'test_jd_admission','test_jd_close_reconcile','test_jd_manual_recovery','test_jd_native_lifecycle','test_jd_postgres_recovery',
        'test_jd_process_lifecycle','test_windows_lifecycle','windows_lifecycle_worker']]]]
source += [web+p for p in ['src/generated/analysis-api.ts','src/jd/api.ts','src/jd/useJdSession.ts','src/jd/useJdSession.test.tsx','src/jd/JdWorkspace.tsx']]
def record(path):
    data=path.read_bytes()
    return {'path':path.relative_to(root).as_posix(),'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()}
records=[record(root/p) for p in source]
baseline=(plan/'task-5-readme-baseline.md').read_text(encoding='utf-8')
current=(root/api/'README.md').read_text(encoding='utf-8')
assert current.startswith(baseline),'Task5 must preserve the complete prior README including its 11 research lines'
patch=''.join(difflib.unified_diff(baseline.splitlines(True),current.splitlines(True),fromfile='a/'+api+'README.md',tofile='b/'+api+'README.md'))
(delivery/'readme-task5-only.patch').write_text(patch,encoding='utf-8')
(delivery/'source-files.json').write_text(json.dumps({'base':'8eec072d51e97735b22c5f0df598b67101fe570b','branch':'codex/analysis-only-agent',
    'readme_baseline':record(plan/'task-5-readme-baseline.md'),'source_files':records},ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
raw=sorted((root/'scratch').glob('task5-*.log'))+sorted(p for p in (root/'scratch').glob('task5-*.json')
    if p.name not in {'task5-source-files.json','task5-delivery-files.json'})
start=min(p.stat().st_mtime for p in raw)
raw += sorted(p for p in plan.glob('task-2-pg-*.jsonl') if p.stat().st_mtime>=start)
raw += [plan/'task5-browser-server.json',plan/'task5-browser-provider.jsonl']
mapping=[]
for path in raw:
    target=delivery/'raw'/path.name
    target.parent.mkdir(exist_ok=True)
    shutil.copyfile(path,target)
    mapping.append({'original':path.relative_to(root).as_posix(),**record(target)})
(delivery/'raw-files.json').write_text(json.dumps(mapping,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
diff=subprocess.check_output(['git','diff','--',*source],cwd=root)
(delivery/'tracked-source-with-prior-readme.diff').write_bytes(diff)
shutil.copyfile(root/'scratch/task-5-report.md',delivery/'report.md')
(root/'scratch/task5-source-files.json').write_text(json.dumps(records,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
(root/'scratch/task5-delivery-files.json').write_text(json.dumps([record(p) for p in sorted(delivery.rglob('*')) if p.is_file()],ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'source_files':len(records),'raw_files':len(mapping),'readme_preserved':True,'delivery':str(delivery)}))
