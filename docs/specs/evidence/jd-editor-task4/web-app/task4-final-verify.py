"""Bounded final Task4 suite with actual scoped runtime and raw outputs."""
import json, os, shutil, subprocess, time
from pathlib import Path
HERE=Path(__file__).parent;ROOT=HERE.parents[2]
J=ROOT/'experiments/jd-editor';A=ROOT/'experiments/analysis-agent';C=J/'contract'
node=shutil.which('node');npm=str(Path(node).with_name('npm.cmd'))
jobs=[
 ('codegen-check',J,['cmd.exe','/d','/c',npm,'run','check-codegen','-w','@caliburn/jd-editor-contract']),
 ('contract',C,['uv','run','pytest','-q','tests/test_schema_contract.py']),
 ('native',J,['cmd.exe','/d','/c',npm,'run','test','-w','@caliburn/jd-editor-native']),
 ('web-tests',J,['cmd.exe','/d','/c',npm,'run','test','-w','@caliburn/jd-editor-web']),
 ('web-types',J,['cmd.exe','/d','/c',npm,'run','typecheck','-w','@caliburn/jd-editor-web']),
 ('web-lint',J,['cmd.exe','/d','/c',npm,'run','lint','-w','@caliburn/jd-editor-web']),
 ('web-build',J,['cmd.exe','/d','/c',npm,'run','build','-w','@caliburn/jd-editor-web']),
 ('api-and-affected-owner-regression',A,['uv','run','pytest','-q','tests/test_jd_api.py','tests/test_api.py','tests/test_jd_engine.py','tests/test_jd_tools.py','tests/test_jd_sources.py','tests/test_jd_fix1.py','tests/test_jd_fix2.py']),
]
summary={'node':node,'node_version':subprocess.check_output([node,'--version'],text=True).strip(),'PYTHONUTF8':os.environ.get('PYTHONUTF8'),'runs':[]}
try:
 for name,cwd,command in jobs:
  start=time.perf_counter();result=subprocess.run(command,cwd=cwd,capture_output=True,encoding='utf-8',errors='replace')
  (HERE/('task4-final-'+name+'.log')).write_text(result.stdout+result.stderr,encoding='utf-8')
  summary['runs'].append({'name':name,'cwd':str(cwd),'command':command,'exit_code':result.returncode,'seconds':time.perf_counter()-start})
  print(name,'exit',result.returncode,flush=True)
  if result.returncode:print((result.stdout+result.stderr)[-7000:],flush=True);raise SystemExit(result.returncode)
finally:(HERE/'task4-final-verification.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
