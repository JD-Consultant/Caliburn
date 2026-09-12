"""Read-only source inventory from accepted Git blobs, not the dirty checkout."""
import hashlib
import json
from pathlib import Path
import subprocess
import tomllib

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
MAIN = Path('S:/caliburn')
CORE = '54cdfb3420d074d1f4566cb04f12d1fb9a868022'
PRODUCTION = '638ed877'  # Resolve and record the full read-only production reference.
OUT = ROOT/'docs/specs/evidence/jd-accepted-core-inputs'
OUT.mkdir(exist_ok=False)
def git(root,*args):
    return subprocess.check_output(['git',*args],cwd=root)
PRODUCTION=git(MAIN,'rev-parse',PRODUCTION).decode().strip()
assert git(ROOT,'rev-parse','refs/tags/jd-editor-core-isolated-20260910^{commit}').decode().strip()==CORE
def blob(root,ref,path):
    return git(root,'show',ref+':'+path)
paths=git(ROOT,'ls-tree','-r','--name-only',CORE,'experiments/analysis-agent/src','experiments/jd-editor').decode().splitlines()
fixed = ['experiments/analysis-agent/pyproject.toml','experiments/analysis-agent/uv.lock',
         'experiments/jd-editor/package.json','experiments/jd-editor/package-lock.json',
         'experiments/jd-editor/license-inventory.json',
         *['experiments/jd-editor/'+part+'/package.json' for part in ('contract','native','web')],
         'experiments/jd-editor/contract/pyproject.toml','experiments/jd-editor/contract/uv.lock']
selected=[]
for path in paths:
    if path.startswith('experiments/analysis-agent/src/'):
        selected.append(path)
    elif any(path.startswith('experiments/jd-editor/'+part+'/') for part in ('native/src','contract/src','contract/scripts','contract/generated','contract/types','web/src')) and '.test.' not in path:
        selected.append(path)
selected=sorted(set(selected+fixed))
files=[]
for path in selected:
    data=blob(ROOT,CORE,path)
    if path.startswith('experiments/analysis-agent/src/'):
        responsibility='Tested advisor/Memory/JD runtime and methods; formal import, namespace and composition retargeting remains under A2/G6'
    elif '/native/' in path:
        responsibility='Tested native editor adapter; candidate formal packages/jd-editor-native'
    elif '/contract/' in path:
        responsibility='SSOT/generation input; map into formal job-analysis contract under A2, never hand-edit generated output'
    elif '/web/' in path:
        responsibility='Tested employee UI; integrate through the formal Web composition under G6, not copy isolated endpoints blindly'
    else:
        responsibility='Exact accepted dependency/license input; dependency merge and installability remain unproven'
    files.append({'path':path,'git_blob':git(ROOT,'rev-parse',CORE+':'+path).decode().strip(),
                  'sha256_git_bytes':hashlib.sha256(data).hexdigest(),'bytes':len(data),
                  'responsibility':responsibility})

def pydeps(root,ref,prefix):
    project=tomllib.loads(blob(root,ref,prefix+'/pyproject.toml').decode())
    lock=tomllib.loads(blob(root,ref,prefix+'/uv.lock').decode())
    return {'requires_python':project.get('project',{}).get('requires-python'),
            'declared':project.get('project',{}).get('dependencies',[]),
            'groups':project.get('dependency-groups',{}),
            'resolved':{p['name']:p.get('version') for p in lock.get('package',[]) if p.get('version')}}
old=pydeps(MAIN,PRODUCTION,'apps/api')
new=pydeps(ROOT,CORE,'experiments/analysis-agent')
py_diff=[{'name':name,'production':old['resolved'].get(name),'accepted_core':new['resolved'].get(name)}
         for name in sorted(old['resolved'].keys()|new['resolved'].keys()) if old['resolved'].get(name)!=new['resolved'].get(name)]
old_web=json.loads(blob(MAIN,PRODUCTION,'apps/web/package.json'))
new_web=json.loads(blob(ROOT,CORE,'experiments/jd-editor/web/package.json'))
web_diff={}
for group in ('dependencies','devDependencies','engines'):
    left,right=old_web.get(group,{}),new_web.get(group,{})
    web_diff[group]=[{'name':name,'production':left.get(name),'accepted_core':right.get(name)} for name in sorted(left.keys()|right.keys()) if left.get(name)!=right.get(name)]
result={'status':'ACCEPTED SOURCE INPUT BASELINE ONLY; NOT COMPLETE A1 DEPENDENCY MERGE OR G6 AUTHORITY',
        'observed_date':'2026-09-12','core_commit':CORE,'core_tag':'jd-editor-core-isolated-20260910',
        'production_reference':PRODUCTION,'files':files,'python':{'production':old,'accepted_core':new,'resolved_differences':py_diff},
        'web_declaration_differences':web_diff,
        'not_done':['merged dependency resolution/installability','final per-file formal HTTP/composition mapping',
                    'P3 actual trial endpoint/configuration and budget guard','P3 paid natural evaluation',
                    'successor ADR/G6 production adoption'],
        'product_provider_calls':0,'code_copied_to_production':False,'dependencies_installed':False}
(OUT/'baseline.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8')
# Re-read every exact blob independently of the construction loop.
for entry in files:
    assert hashlib.sha256(blob(ROOT,CORE,entry['path'])).hexdigest()==entry['sha256_git_bytes']
(OUT/'verification.json').write_text(json.dumps({'verified_files':len(files),'source':CORE,'tag_matches':True,'all_git_byte_hashes_match':True,
    'python_resolved_differences':len(py_diff),'comparison_is_not_installability_proof':True},indent=2),encoding='utf8')
(OUT/'README.md').write_text(f'''# 已驗收編輯核心：後續測試與採用輸入

2026-09-12。核心 `54cdfb34`／tag `jd-editor-core-isolated-20260910`；主產品對照 `{PRODUCTION}`。

[baseline.json](baseline.json)固定 **{len(files)}項Git原始輸入**，含既有顧問／Memory、JD工具、Skill、SSOT與生成物、native adapter、Web及lock／授權清單。檔案由已接受commit讀取，不取工作區未提交研究；[逐檔再核對](verification.json)全部一致。沒有複製到production或安裝套件。

Python正式與隔離lock有 **{len(py_diff)}項名稱／版本差異**，宣告、Python要求與Web依賴差異列在同檔。差異清單不是合併後可安裝證據：正式依賴仍需A1/A2核對，不能直接用隔離lock覆蓋正式API。這是已接受版本的本地事實，不是最新版本推薦或供應商共識。

這份輸入接續9/10的Task4預覽；原件保留沿革。本份已涵蓋Task5、Task6與整體修正，**不代表A1完整採用manifest、P3 OFF01全部完成或G6已通過**。工具／Skill／格式hash可用作後續凍結起點，實際trial的endpoint／完整配置、預算防護、案例與費用授權仍待具體執行包。P3-B01公開計費上界缺口仍OPEN；未發模型請求。

正式HTTP／composition映射沿已採設計A2完成，不把這份responsibility欄位當新架構裁決。舊writers退役仍依原採用盤點；沒有刪除任何正式入口。
''',encoding='utf8')
(OUT/'build-inventory.py').write_bytes(Path(__file__).read_bytes())
print(json.dumps({'files':len(files),'python_dependency_differences':len(py_diff),'directory':str(OUT)}))
