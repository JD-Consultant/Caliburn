"""Archive reviewed core closure and prepare a precise, reviewable stage list."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
OUT = ROOT/'docs/specs/evidence/jd-editor-core-review'
OUT.mkdir(exist_ok=False)
BASE = '3d0445ae2d4b3bb2ef3493f703ea18f0108b0eef'
assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT).decode().strip() == BASE
paths = [
    'experiments/analysis-agent/src/analysis_agent/service.py',
    'experiments/analysis-agent/tests/test_jd_shutdown_isolation.py',
    'experiments/jd-editor/web/src/jd/useJdSession.ts',
    'experiments/jd-editor/web/src/jd/JdWorkspace.tsx',
    'experiments/jd-editor/web/src/jd/JdNode.tsx',
    'experiments/jd-editor/web/src/jd/JdStaleCandidate.test.tsx',
    'experiments/jd-editor/web/src/jd/JdStaleWorkspace.test.tsx',
    'experiments/jd-editor/web/browser/core-stale-recovery.mjs',
]
minor = json.loads((HERE/'claude-core-minor/manifest.json').read_text(encoding='utf8'))
overrides = {item['path']:item['sha256'] for item in minor}
closure = json.loads((HERE/'claude-core-closure/manifest.json').read_text(encoding='utf8'))
expected = {item['file'].removeprefix('source/'):item['sha256'] for item in closure['files'] if item['file'].startswith('source/')}
expected.update(overrides)
for path in paths:
    assert hashlib.sha256((ROOT/path).read_bytes()).hexdigest() == expected[path], path
    target = OUT/'source'/path
    target.parent.mkdir(parents=True,exist_ok=True)
    shutil.copyfile(ROOT/path,target)

reviews = {}
for phase,folder in [('initial','claude-core-final'),('closure','claude-core-closure'),('minor','claude-core-minor')]:
    packet = HERE/folder
    events = [json.loads(line) for line in (packet/'response.jsonl').read_text(encoding='utf8').splitlines() if line.strip()]
    result = next(e for e in reversed(events) if e.get('type')=='result')
    assert not result['is_error'], phase
    if phase != 'initial': assert 'APPROVED' in result['result'] and 'CHANGES REQUIRED' not in result['result']
    review = OUT/'reviews'/phase
    review.mkdir(parents=True)
    (review/'original.md').write_text(result['result'],encoding='utf8')
    kept = {k:result.get(k) for k in ('is_error','subtype','num_turns','total_cost_usd','modelUsage','permission_denials','duration_ms','stop_reason')}
    (review/'result.json').write_text(json.dumps(kept,indent=2),encoding='utf8')
    reviews[phase] = kept
    for name in ('manifest.json','prompt.txt','invocation.json'):
        shutil.copyfile(packet/name,review/name)
    if phase == 'initial':
        shutil.copytree(packet/'requirements',review/'requirements')
    else:
        for child in packet.iterdir():
            if child.name in ('manifest.json','prompt.txt','invocation.json','response.jsonl','stderr.log'): continue
            if child.is_dir(): shutil.copytree(child,review/child.name)
            else: shutil.copyfile(child,review/child.name)

evidence_names = [
    'core-stale-red.log','core-stale-red2.log','core-close-red.log','core-close-red2.log',
    'core-web-green1.log','core-fix-python.log','core-fix-pg.log','core-fix-python-results.json',
    'core-fix-test.log','core-fix-build.log','core-fix-typecheck.log','core-fix-lint.log','core-fix-web-results.json',
    'core-minor-test.log','core-minor-build.log','core-minor-typecheck.log','core-minor-lint.log','core-minor-web-results.json',
    'core-stale-browser-before-minor.log','core-stale-browser-before-minor.json','core-stale-browser-before-minor.png',
    'core-stale-browser.log','core-stale-browser.json','core-stale-browser.png','core-servers.json','core-final-web-server.json',
]
for name in evidence_names:
    shutil.copyfile(ROOT/'scratch'/name, OUT/name)
final_browser = json.loads((OUT/'core-stale-browser.json').read_text(encoding='utf8'))
assert final_browser['status'] == 'PASS'
assert not [r for r in final_browser['requests'] if r['method']=='POST' and r['url'].endswith('/runs')]
for filename,expected_summary in [('core-fix-python.log','86 passed'),('core-fix-pg.log','19 passed'),('core-minor-test.log','47 passed')]:
    assert expected_summary in (OUT/filename).read_text(encoding='utf8')
assert all(x['exit_code']==0 for x in json.loads((OUT/'core-minor-web-results.json').read_text(encoding='utf8')))
for name in ('core-fix-checks.py','core-minor-checks.py','core-start-servers.py','core-final-web.py','run-claude-core-review.py','run-claude-core-closure.py','run-claude-core-minor.py','core-archive.py'):
    target=OUT/'inputs'/name
    target.parent.mkdir(parents=True,exist_ok=True)
    shutil.copyfile(HERE/name,target)

report = (HERE/'core-fix-report.md').read_text(encoding='utf8').replace('以下待窄closure。','F1–3與最後R1/R2均已獨立APPROVED，root核對hash／實際結果後接受核心隔離範圍。')
report = report.replace('原RED與最後測試兩份分別保留。','原RED輸出與最後測試保留；原RED測試檔未另凍結，不主張前後逐byte相同。')
report += f'''
## 最後窄複核與主代理處置

F1/F2/F3 CLOSED後，另接受R1/R2小修：已知終局結果不再重送原key；候選文案區分未知與未保存。最後47 Web、build/types/lint及真瀏覽器再PASS，文件`{final_browser['document']}`，前次原件保留於before-minor。minor reviewer未讀web.log（檔案實在其packet內）且在瀏覽器重跑完成前回覆，最後實測由root獨立核對，不補稱它已看過。

minor review把no_pending說成「寫入從未發生」不正確，root明確不採：它只表示查詢沒有pending／receipt，不能由absence證明未執行。既有原key完整候選出口、跨版本及server終局裁決未變。Reviewer供給的base相等條件亦未採，避免封死原有未知恢復。

R3保留至P5：明示載入與背景revalidate競速時可能只取消動作、缺再按一次的提示；generation仍保護內容。R4保留至P5：既有busy呈現可受重疊操作影響，server gate與active-run鎖仍守資料；原review的停止按鈕情境還依賴之後run狀態改變，並非一般idle載入即可觸發。兩項無已觀測內容遺失／假保存，不為文案與呈現另造並行引擎。

原review與closure各自讀取範圍明列；root完成來源hash與raw summary核對。初始化helper的產品provider為固定transport，瀏覽器0 POST /runs可直接核；helper常數product_provider_calls本身不是獨立證據。這不是自然品質、正式採用或日常可用成品。
'''
(OUT/'review.md').write_text(report,encoding='utf8')
(OUT/'README.md').write_text('''# JD編輯核心整體交接

2026-09-12：六個隔離切片及整體跨切片review已通過，F1–3／R1–2 CLOSED；[修正、證據與限制](review.md)。Task6基底3d0445ae，整體修正以本次提交與本地tag `jd-editor-core-isolated-20260910` 定位。此tag名稱沿原9/10計畫，實際驗收日期9/12。

初審為FAIL，不能只引用最後PASS。reviews/initial保留原結果與需求快照，其source/diff可依manifest指定Git BASE/HEAD重建；closure／minor保留精確獨立封包及當時結論。source是最後8檔原始bytes，artifact-manifest列全部檔案hash；不包含manifest本身。子目錄不放生效的.gitattributes。Chrome截圖為修復短流程，Task6完整六章證據仍在相鄰jd-editor-task6。

下一工作：P3離線費用防護及可審執行包、A1正式採用清單；P3-B01公開計費上界缺口仍OPEN，不呼叫付費模型、不默改US$1硬上限。G6正式接合、P5日常維護及兩項呈現Minor、P6真人／長訪談、P7交付未通過。資料與舊production保持原權責。
''',encoding='utf8')

plan = ROOT/'docs/plans/2026-09-10-jd-editor-core-implementation.md'
plan_text = plan.read_text(encoding='utf8')
for n in range(1,7):
    plan_text=plan_text.replace(f'- [ ] **6.{n}',f'- [x] **6.{n}')
plan.write_text(plan_text,encoding='utf8')
shutil.copyfile(plan,OUT/'inputs/completed-core-plan.md')

attributes = ROOT/'.gitattributes'
attributes.write_text(attributes.read_text(encoding='utf8')+'\n# Preserve integrated core review captures and exact source snapshots.\ndocs/specs/evidence/jd-editor-core-review/** -text\n',encoding='utf8')
integration=ROOT/'docs/specs/evidence/2026-09-10-jd-editor-core-integration.md'
integration.write_text(integration.read_text(encoding='utf8')+'\n## 2026-09-12：核心整體交接\n\nTask6已保存於`3d0445ae2d4b3bb2ef3493f703ea18f0108b0eef`。其後[整體review與有限修正](jd-editor-core-review/review.md)完成，F1–3及R1–2 CLOSED；最後47 Web／86受影響Python／19真PG、build/types/lint與真Chrome短恢復流程通過。R3/R4呈現Minor列P5，原Task6未驗界線不變。六切片隔離核心已接受；自然品質與正式產品未交付。\n',encoding='utf8')
for rel in ('experiments/jd-editor/README.md','experiments/jd-editor/ACCEPTANCE.md'):
    target=ROOT/rel
    target.write_text(target.read_text(encoding='utf8')+'\n## 2026-09-12 核心整體審查收尾\n\n六切片與整體review已通過；[修正與實測](../../docs/specs/evidence/jd-editor-core-review/review.md)保存舊版手改同頁出口、逐文件關閉、已知失敗不重送，以及真Chrome／PG結果。僅隔離核心；自然模型、正式接合、日常維護與真人驗收仍待完成。\n',encoding='utf8')

note='**JD-R002／隔離編輯核心通過（2026-09-12，G7）：**Task6已保存3d0445ae；[整體審查及有限修正](specs/evidence/jd-editor-core-review/review.md)F1–3／R1–2 CLOSED，root接受。最後47 Web／86受影響Python／19真JD PG及build/types/lint、真Chrome恢復PASS，原Task6完整旅程證據保留、不累加。當前完成六切片核心交接／本地tag；**下一工作為P3離線費用防護與執行包、A1採用清單**。P3-B01仍OPEN／0產品provider；G6、P5日常維護（含R3/R4呈現Minor）、P6真人與自然品質、P7成品未通過。未merge／push。'
register=ROOT/'docs/current-decisions.md'
raw=register.read_bytes(); pos=raw.index(b'\n')+1
newline=b'\r\n' if raw[:pos].endswith(b'\r\n') else b'\n'
register.write_bytes(raw[:pos]+note.encode()+newline+raw[pos:])
index=subprocess.check_output(['git','show','HEAD:docs/current-decisions.md'],cwd=ROOT)
pos=index.index(b'\n')+1
nl=b'\r\n' if index[:pos].endswith(b'\r\n') else b'\n'
(HERE/'core-register-index.md').write_bytes(index[:pos]+note.encode()+nl+index[pos:])

artifacts=[]
for file in sorted(OUT.rglob('*')):
    if file.is_file():
        data=file.read_bytes()
        artifacts.append({'path':file.relative_to(OUT).as_posix(),'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()})
(OUT/'artifact-manifest.json').write_text(json.dumps(artifacts,indent=2),encoding='utf8')
stage=paths+['.gitattributes','docs/specs/evidence/2026-09-10-jd-editor-core-integration.md','experiments/jd-editor/README.md','experiments/jd-editor/ACCEPTANCE.md']
stage += [p.relative_to(ROOT).as_posix() for p in sorted(OUT.rglob('*')) if p.is_file()]
(HERE/'core-stage-files.json').write_text(json.dumps(stage,indent=2),encoding='utf8')
(HERE/'core-stage-paths.txt').write_bytes(b'\0'.join(p.encode() for p in stage)+b'\0')
print(json.dumps({'stage_files':len(stage),'raw_artifacts':len(artifacts),'final_browser':final_browser['document'],'review_list_estimates':{k:v['total_cost_usd'] for k,v in reviews.items()}}))
