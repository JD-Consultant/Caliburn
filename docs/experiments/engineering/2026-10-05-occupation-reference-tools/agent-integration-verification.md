# 公版工具接入 A／B1／B2：驗證紀錄

日期：2026-10-05。依 [ADR0080](../../../adr/0080-opt-in-public-reference-agent-tools.md) 完成可選角色接線；本頁保留接線範圍、反例與結果，前輪未接模型的工具與保存證據保留原樣。現行契約與其他驗證見[工程驗證索引](../README.md#角色接線)。

## 交付行為

- 明示 `CALIBURN_OCCUPATION_REFERENCE_URL` 才建立公版 client 並讓新 A 請求取得五工具；B1／B2 只取得 `read_excluded_work`。未配置時維持原工具組，不建立 reference candidate／HTTP client。
- 顧問可搜尋主要職位參考、按需讀任務、選用多份公版、保存或解除員工明確否認的工作。否認不自動併入搜尋 query，亦不複製到 Memory。
- bootstrap 沿既有 AsyncExitStack 管理 client；URL 只接受明示 HTTP(S) origin，timeout 預設 30 秒且須有限、正值。client 不使用系統代理或跟隨重導。
- 已開始的工作由自己的 preparation／context／Step 保留原工具、提示及操作。正常恢復直接重播原 JSON command／result，不倒帶 candidate，不另寫恢復引擎。原 A 請求需要 client 而目前缺少配置時，在模型請求前拒絕。

## 反例與結果

| 範圍 | 驗證行為 |
|---|---|
| 設定及組裝 | URL 未設、非法 origin／port／timeout 拒絕；bootstrap 建立、注入、關閉同一 client；停用不建立 client；兩個 Memory runner 僅獲唯讀資格 |
| 真 runner 旅程 | 合成 Responses 指示 A 搜尋→讀任務→選用→寫入否認→讀 state→正式完成；下一 A 及 B1／B2 讀回。工具 HTTP request 核對原正向 query，未拼入否認 |
| 權限 | B1／B2 不取得公版搜尋、選用或排除寫入；即使合成模型要求寫入，也回 `scope_not_allowed` |
| 寫入中斷 | DB 已保存否認後故意中斷；缺 client 先拒絕且沒有模型請求；恢復 client 後沿原 command 重播，公版 transport 即使不可用也不重送已保存寫入 |
| 正式資格 | 取消／失敗候選不進下一 A 的正式 state；同一批 B1／B2 沿原 binding／F 讀取，後輪更正不回流 |
| 原模板 | preparation 保存後 adoption 中斷、adopt 後尚未 capture、最早 `__start__` checkpoint 均保留原提示／工具；新開關不改舊訪談。跨 execution／role／window 或不同 request ID／snapshot 的 held 被拒絕 |
| 合法 held | count／compaction 結果保存失敗時，原 request 仍在 saver。恢復使用該原件，不重算 count 或重送 compaction |

### 獨立審查的修正

審查找到「沒有本輪 saver 邊界卻採用 held 模板」的反例：若本輪重用前輪取消後的 prepared base，後續 preparation 可直接返回，繞過原 snapshot 核對。修正前，以 fresh／reused base × count／compaction 的四項反例得到 **4 failed、11 passed**；修正後，缺少原 saver 邊界且提供 held 一律拒絕。合法 held 本來就在保存原 request 後才會產生，因此沒有新增替代保存或恢復機制。

實作者的相關 PostgreSQL 回歸 **23 passed**；獨立複審另跑七項離線邊界檢查，未發現未解的可重現問題。最終擴大回歸如下。

原角色提示測試另出現六個 `Mock cannot be awaited`，原因是新增原模板唯讀查詢需要 async saver；僅將 fixture 換成 `InMemorySaver`，保留原提示斷言。該檔 **19 passed**，再納入完整 unit/contracts。

## 最終檢查

| 指令範圍 | 結果 |
|---|---|
| 完整 API unit／contracts | **1,377 passed，14.12 秒** |
| 角色、公版、Memory 及恢復 PostgreSQL 回歸 | **70 passed，60.54 秒** |
| Ruff check `src tests` | 通過 |
| Ruff format `src tests` | **469 files already formatted** |
| Mypy `src/caliburn` | **318 source files，無錯誤** |
| 文件／差異 | 15 份相關文件的 422 個本地連結目標存在；本次受影響範圍 `git diff --check` 通過 |

從 repository root 執行：

```powershell
apps/api/.venv/Scripts/python.exe -m pytest apps/api/tests/unit apps/api/tests/contracts -q -p no:cacheprovider --tb=short
apps/api/.venv/Scripts/python.exe docs/experiments/engineering/2026-10-05-occupation-reference-tools/run_tests.py apps/api/tests/integration/test_occupation_reference_runners.py apps/api/tests/integration/test_reference_template_reentry.py apps/api/tests/integration/test_consultant_runner.py apps/api/tests/integration/test_consultant_runner_recovery.py apps/api/tests/integration/test_memory_analysis_runners.py apps/api/tests/integration/test_role_context_history.py apps/api/tests/integration/test_consultant_context_binding.py apps/api/tests/integration/test_excluded_work_reads.py apps/api/tests/integration/test_occupation_reference_workflow.py -m postgres -q --tb=short
```

從 `apps/api` 執行：

```powershell
.venv/Scripts/python.exe -m ruff check src tests
.venv/Scripts/python.exe -m ruff format --check src tests
.venv/Scripts/python.exe -m mypy src/caliburn
```

## 服務隔離與驗證層級

執行前唯讀核對共用後端沒有 reload 參數、既有 PostgreSQL 容器正在運作。沿現有本機測試 DB `caliburn_docker_test`、loopback port 55441，每項 fixture 僅建立／移除自己的隨機 schema。DB 憑證由既有測試 runner 私下取得，不輸出、不保存至報告。

本次沒有重啟或停止服務、修改現有環境檔、對正式 DB 套用 migration、執行 RAG／GPU 搜尋或付費模型。保留其他工作正在修改的 A／B2 instructions，公版指引另置可選檔案；未 commit／push。

這輪驗證實際 runner、工具分派、持久化及原生恢復，模型與公版 HTTP 使用合成 transport。顧問選用公版、否認判讀、避免重問與 JD 收尾的品質比較另行實驗；本輪不新增這些效果數字。實際啟用依 [API 操作說明](../../../../apps/api/README.md#公版參考工具的可選啟用)，在其他測試結束後對欲啟用的程序設定及啟動。
