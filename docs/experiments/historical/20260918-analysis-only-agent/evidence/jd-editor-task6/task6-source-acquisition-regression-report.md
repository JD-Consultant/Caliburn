# Task6 source acquisition focused regression

2026-09-11；BASE `444416722190fd48c14f4423d101f36b25831de1`，cwd `S:/caliburn/.worktrees/analysis-only-agent`。

唯一新增的產品測試檔：`experiments/analysis-agent/tests/test_jd_current_source_acquisition.py`。未修改 src、既有測試、docs、README，未 commit。

## 三個最小情境

1. 真 `read_conversation` 讀已發配的 current-input exact ref，後續 actual `jd_edit` 保存 source_refs；binding 同時保留 current_input 與 tool_call。
2. 沿既有 run_calls 建立前一輪；同 checkpoint／同本次 Human answer 的 ref 擴大至前一 Human，形成沒有發配的較寬 window。actual reader 可讀，但 `_extraction_range` 證實該 checkpoint 未閉合，後續 jd_edit 必須 invalid_input，無 current_input 權，JD head 不變。沒有清空既有 issuance 或修改 reader／validator。
3. 相同 wider ref 的替換工具先真正呼叫 owner reader，卻更改返回原話；既有 owner-result guard 拋錯，不發配該 ref，JD head 不變。

使用原 `seed`／`run_calls`、Memory read tool factory、ConversationReader、build_conversation、InMemorySaver、SDK MockTransport 及 dedicated JD PG fixture；沒有重造 graph 或 SQL／source validator。

## RED／GREEN

- RED：`scratch/task6-source-acquisition-red.log`＝**1 FAIL／2 PASS／2 warnings，9.15s**。僅正向 current-input 案例在預期 committed 得到 invalid_input，確實重現覆寫 binding 的原缺口。另兩項既有防線保持通過。
- RED overlay：`scratch/task6-source-acquisition-red-run.py` 先確認 accepted git object 與原 frozen jd_tools（僅 CRLF／LF 正規化）相同，再僅在此新 Python 程序的 import module 載原 frozen 檔；從未替換工作樹 src。Git object hash `34426d29be0ebbadb68587fd22b85d02dd9969b5112015be953a39a543a97c00`；原 frozen bytes hash `de497f516f12f1d13e262ef191a5e10957e3f395d1fcee760f89fad6a4d68f5e`。overlay 先 import 模組產生兩個 pytest assert-rewrite warning（anyio／langsmith），沒有隱藏。
- GREEN：`scratch/task6-source-acquisition-green.log`＝**3 PASS，7.46s**，直接使用目前 source 與原 acceptance runner。
- managed launcher 在 RED 外層仍顯示 exit=0；以 pytest 原 raw 的 FAIL 作結論，不把 wrapper exit 當綠燈。GREEN 原 raw 為三項通過。
- 未重跑主 E2E／舊 source 五項、整套 API 或 Web。0 產品 provider／0 費用；專用 `q019_jd_app_20260910`，實際 Windows bootstrap；fixture 每次 UUID 文件及既有 PG evidence 行為不變，沒有清全 DB 或干擾 root browser API。

## 精確命令

下列從上述 cwd 執行；task4-run 只在子程序注入既有專用測試 DB，不輸出 credential。

```powershell
$env:Q019_LIFECYCLE_INSTALLATION='jd-task6-source-red-20260911'
& 'experiments/analysis-agent/.venv/Scripts/python.exe' '.superpowers/sdd/2026-09-10-jd-editor-core-implementation/task4-run.py' 'S:/caliburn/.worktrees/analysis-only-agent/experiments/analysis-agent/.venv/Scripts/python.exe' 'S:/caliburn/.worktrees/analysis-only-agent/scratch/task6-source-acquisition-red-run.py' '-q' 'tests/test_jd_current_source_acquisition.py' *> 'scratch/task6-source-acquisition-red.log'

$env:Q019_LIFECYCLE_INSTALLATION='jd-task6-source-green-20260911'
& 'experiments/analysis-agent/.venv/Scripts/python.exe' '.superpowers/sdd/2026-09-10-jd-editor-core-implementation/task4-run.py' 'S:/caliburn/.worktrees/analysis-only-agent/experiments/analysis-agent/.venv/Scripts/python.exe' 'tests/task5_acceptance_runner.py' '-q' 'tests/test_jd_current_source_acquisition.py' *> 'scratch/task6-source-acquisition-green.log'
```

## 最終 SHA256

| 檔案 | SHA256 |
| --- | --- |
| 新 test | `35f1b759d5d8844b23f618b8f9db8d12e8fe891072d6922a4e6a845379c622e0` |
| GREEN current jd_tools.py | `9e85aae99d9bd5a133a099bd6544f91eba7d963b0390cb0623705669ab83bff5` |
| RED overlay runner | `0bfe217359865981cced2fedba7c1053abfa2b50825d12954365e2567a36692c` |
| RED log | `3c3949a2d993f65298981dc53bdea781c4bf2171a18202e35df8d38413f4af71` |
| GREEN log | `65f782b22f6367d2127942dfd34d1c60a590dca599ccb6cbf5928af0d14bd72e` |

這是來源取得修正的有限回歸，不是完整 Task6 審查、真模型品質或成品驗收。
