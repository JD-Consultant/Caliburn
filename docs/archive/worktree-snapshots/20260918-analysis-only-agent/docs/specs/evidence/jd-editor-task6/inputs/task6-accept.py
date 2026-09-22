"""Record independent review closure and prepare exact task-only commit inputs."""
import difflib
import hashlib
import json
from pathlib import Path
import subprocess
import sys

HERE=Path(__file__).resolve().parent; ROOT=HERE.parents[2]
DEST=ROOT/'docs/specs/evidence/jd-editor-task6'
packet=HERE/'claude-task6-final'
events=[json.loads(line) for line in (packet/'response.jsonl').read_text(encoding='utf8').splitlines()]
final=next(e for e in reversed(events) if e.get('type')=='result')
assert final['subtype']=='success' and '**Spec：PASS**' in final['result'] and 'APPROVED' in final['result']
for item in json.loads((HERE/'task-6-review-manifest.json').read_text(encoding='utf8')):
    assert hashlib.sha256((ROOT/item['path']).read_bytes()).hexdigest()==item['sha256'],item['path']
out=DEST/'reviews/final'; out.mkdir(parents=True,exist_ok=True)
(out/'review-original.md').write_text(final['result']+'\n',encoding='utf8')
diff=(packet/'change.diff').read_text(encoding='utf8')
assert diff.count('diff --git ')==30 and 'Explicit files: 32' in diff
corrected=diff.replace('Explicit files: 32','Explicit files: 30 (Claude-authorized subset of the 32-file root review; excludes .gitattributes and analysis-agent/README.md)',1)
(out/'change-corrected.diff').write_text(corrected,encoding='utf8')
for name in ('manifest.json','prompt.txt','invocation.json'):
    (out/name).write_bytes((packet/name).read_bytes())
init=next(e for e in events if e.get('type')=='system' and e.get('subtype')=='init')
metadata={'init':{k:init.get(k) for k in ('model','tools','mcp_servers')},
          'result':{k:final.get(k) for k in ('subtype','is_error','duration_ms','num_turns','total_cost_usd','modelUsage')},
          'review_original_sha256':hashlib.sha256((out/'review-original.md').read_bytes()).hexdigest()}
(out/'metadata.json').write_text(json.dumps(metadata,indent=2),encoding='utf8')
closure='''# Task6 主代理接受與審查閉合

2026-09-12。獨立 Claude Opus5：Spec PASS／quality APPROVED，無產品 Critical；F5 手改覆蓋問題明確 CLOSED。root核對 raw結果、現碼及凍結hash後接受Task6隔離範圍。未表示整體跨切片review或成品已通過。

## I1：審查封包表頭計數 — CLOSED

root原始凍結確為32檔，`inputs/task-6-review.diff`與manifest逐一相符。對外Claude包依已授權資料範圍排除根 `.gitattributes` 及 `experiments/analysis-agent/README.md`，剩30個source/doc項及30個diff段；原表頭未隨篩選更新，造成誤解，並非2個未揭露產品程式。

保留原review和原32檔diff，另提供 `reviews/final/change-corrected.diff`（30檔，明示2個排除項）。root逐段數量／path核對通過。排除的前者只延用既有raw evidence換行規則，後者只有本Task6文檔段且既有11行被精確排除；已由root核對。這兩個低風險文件不需要外傳；helper原件作技術驗收輸入封存，不是遺漏的產品runtime。

## Minor處置

- M1採納說明：dirty RED是同一情境的原inline fixture；GREEN改成完整生成型別helper以修TS2352，guard／預期未放寬。原RED原樣保留，不冒稱與最後測試逐byte相同。
- M2不改：本切片明定A工作目錄且managed runner固定cwd。累積wire保存所有嘗試，當例`task6-e2e-result.json`另有完整requests。改成每次覆寫反會丟首敗；不將helper當日常使用入口。
- M3範圍保留：Task6核三工具頂層schema／description與SSOT、不動其$defs；既有Task3契約／provider-binding測試另保留，codegen一致性通過。沒有觀察到$defs變更，不新增第二套golden。
- M4空行風格不影響行為與已要求檢查，保留原樣，避免無意義重凍結。
- M5交整體review核跨切片，現有原base遇新版被拒仍保留候選；不讓本次dirty保護自動rebase或覆寫。OS真人IME仍未驗。

## 完成界線

620離線／156真JD PG／45真Memory PG各組實際PASS，68原生、最後41 Web與codegen／build／types／lint PASS；群組不累加。真瀏覽器完整旅程及新API／新瀏覽器恢復PASS，最後guard另有反例與built Web重開。方法／固定工具驗收不等於自然職位品質；0產品模型呼叫。Claude CLI工程審查依持續授權使用，不冒稱所有AI資源免費。

後續：精確本地保存Task6，再執行整體跨切片review；P3自然試驗、G6正式採用、P5維護與P6真人等門檻保持。
'''
(DEST/'review.md').write_text(closure,encoding='utf8')
replacements={
 'docs/specs/evidence/2026-09-10-jd-editor-core-integration.md':[
 ('**工程檢查完成，Task6 最終獨立審查中；未提交／未正式採用。**','**Task6 工程驗收與獨立審查已通過，root已接受；準備精確本地保存，未正式採用。**'),
 ('下一gate：Task6凍結包独立審查→精確本地commit→整體跨切片審查／tag。','[獨立審查與root closure](jd-editor-task6/review.md)已通過，I1文件計數更正、F5 CLOSED。下一gate：精確本地commit→整體跨切片審查／tag。'),
 ('最後 **41 Web PASS**；新增 fixture','RED保留同情境原inline fixture，最後 **41 Web PASS**；新增 fixture')],
 'experiments/jd-editor/ACCEPTANCE.md': [('Task6 工程驗收完成、獨立審查中','Task6 工程驗收與獨立審查通過')],
 'experiments/jd-editor/README.md': [('Task6 仍待獨立審查閉合','Task6 獨立審查已閉合，整體跨切片審查接續進行')],
 'docs/specs/evidence/jd-editor-task6/README.md': [('最終獨立審查中','最終獨立審查已通過，見[closure](review.md)'),('../../../..//experiments','../../../../experiments')],
}
for rel,pairs in replacements.items():
    path=ROOT/rel; text=path.read_text(encoding='utf8')
    for old,new in pairs:
        assert text.count(old)==1,(rel,old)
        text=text.replace(old,new,1)
    path.write_text(text,encoding='utf8')
for item in json.loads((HERE/'task-6-method-input-manifest.json').read_text(encoding='utf8')):
    data=(ROOT/item['path']).read_bytes()
    assert hashlib.sha256(data).hexdigest()==item['sha256'],item['path']
    target=DEST/'inputs/methods'/item['path'];target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(data)
for name in ('task6-freeze.py','task6-accept.py','run-claude-task6-final-review.py'):
    (DEST/'inputs'/name).write_bytes((HERE/name).read_bytes())
official='docs/specs/2026-09-11-jd-skill-current-official-preflight.md'
(DEST/'inputs/official-skill-preflight.md').write_bytes((ROOT/official).read_bytes())
subprocess.run([sys.executable,str(HERE/'prepare-readme-index.py'),'--task','task-6','--base','444416722190fd48c14f4423d101f36b25831de1','--baseline','task-6-readme-baseline.md'],check=True)
note='**JD-R002／Task6已接受（2026-09-12，隔離G7）：**[完整固定旅程與結果](specs/evidence/2026-09-10-jd-editor-core-integration.md)及[獨立審查closure](specs/evidence/jd-editor-task6/review.md)通過；來源metadata、JSONB相等、終態讀取及途中手改保護已修正。620離線／156真JD PG／45真Memory PG、68原生／41 Web與建置檢查通過，真瀏覽器及API重開全值一致；不累加重疊案例。**當前gate：精確保存Task6，接整體跨切片review／tag。**0產品provider；Claude工程審查已獲持續授權，非P3自然測試授權。自然品質、G6正式接合、日常維護及真人驗收仍未完成。\n'
relative='docs/current-decisions.md'; path=ROOT/relative
current=path.read_text(encoding='utf8'); heading='# Caliburn Current Decision Register\n'
assert current.startswith(heading);path.write_text(heading+note+current[len(heading):],encoding='utf8')
base=subprocess.check_output(['git','show','HEAD:'+relative],cwd=ROOT).decode('utf8').replace('\r\n','\n')
assert base.startswith(heading)
index=heading+note+base[len(heading):]
patch='diff --git a/'+relative+' b/'+relative+'\n'+''.join(difflib.unified_diff(base.splitlines(keepends=True),index.splitlines(keepends=True),fromfile='a/'+relative,tofile='b/'+relative))
(HERE/'task-6-register.patch').write_text(patch,encoding='utf8')
(HERE/'task-6-register-index.md').write_text(index,encoding='utf8')
records=[{'path':str(p.relative_to(DEST)).replace('\\','/'),'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'bytes':p.stat().st_size}
         for p in sorted(DEST.rglob('*')) if p.is_file() and p.name!='artifact-manifest.json']
(DEST/'artifact-manifest.json').write_text(json.dumps(records,indent=2),encoding='utf8')
selected=[p for p in json.loads((HERE/'task-6-files.json').read_text(encoding='utf8')) if p!='experiments/analysis-agent/README.md']
selected += [str(p.relative_to(ROOT)).replace('\\','/') for p in DEST.rglob('*') if p.is_file()]
selected += [official]
assert len(selected)==len(set(selected))
(HERE/'task-6-stage-files.json').write_text(json.dumps(selected,indent=2),encoding='utf8')
print(json.dumps({'review':'accepted; F5/I1 closed','stage_files':len(selected),'partial_patches':['README','register']}))
