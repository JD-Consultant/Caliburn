# 否認範圍簡化：接續驗證

日期：2026-10-05。接續[前版紀錄](verification.md)，不覆寫前版數字。使用者確認目的是避免重問，不保留員工回答來源；明確沒做／不負責的範圍獨立保存，不放 Memory。最新責任見[設計](../../../specs/2026-10-04-public-reference-completion-design.md#最新確認只保留明確否認的工作範圍)。

## 變更與界線

`OccupationReferenceState` 改為 `selected_reference_ids + excluded_work`。移除 `WorkConfirmation`、來源 selector、來源投影、舊工具 `record_work_confirmation` 及其 schema／生成物；改用 `update_excluded_work(add, remove)`，精確去重、未知移除／交集／雙空操作整批拒絕，員工更正可移除或替換範圍。重新選公版不清除排除清單。

保存機制不另造：原 execution／檔案鎖、候選 revision、generation、原操作結果與 completed＋formal 資格保留。`0024` 尚未發布／套用正式資料庫，直接調整未發布 shape；不猜測舊 confirmations 是肯定或否認，不做舊資料轉換。測試 DB 只使用隔離 schema。工具仍未註冊顧問，沒有改 Memory、RAG 排名或模型 Prompt，無模型／付費外送。

## 反例到通過

| 範圍 | Red 與修正 | 最終驗證 |
|---|---|---|
| state 純函式／保存格式 | 15 failed、8 passed：缺新增／更正規則，舊 confirmations 未拒絕。改成精確排除清單及 strict shape | 23 unit passed |
| PostgreSQL state | 1 failed、6 passed：新 excluded_work 經舊 serializer 後變空。同步未發布 DDL、serializer，再補舊格式／額外來源拒絕反例 | 9 PostgreSQL state passed |
| workflow | 新測試先因缺 `prepare_excluded_work` 失敗；移除來源參數／導覽，使用純排除更新 | 10 PostgreSQL workflow passed |
| tools | 新 `update_excluded_work` 呼叫先被舊名稱分派拒絕。schema 生成後切換 transport，保留完整 checkpoint 比對 | 43 tool unit passed |
| 真接縫 | HTTP MockTransport → adapter → tools → workflow → PostgreSQL；JSON 往返、服務下線重播、新輪讀回、解除排除及 503 不清 state | 1 journey passed |

旅程對「新增排除之後再次搜尋」與服務錯誤時的 POST body 做精確比對，仍只有原本正向 `query` 與 `limit:5`；沒有自行拼入 `excluded_work`，沒有把未負責內容當搜尋文字或自動剔除整份公版。

## 完整回歸命令

```powershell
apps/api/.venv/Scripts/python.exe -m pytest apps/api/tests/unit apps/api/tests/contracts -q -p no:cacheprovider --tb=short
apps/api/.venv/Scripts/python.exe docs/experiments/engineering/2026-10-05-occupation-reference-tools/run_tests.py apps/api/tests/integration/test_occupation_reference_state.py apps/api/tests/integration/test_occupation_reference_workflow.py apps/api/tests/integration/test_occupation_reference_tool_journey.py apps/api/tests/integration/test_database_migrations.py apps/api/tests/integration/test_consultant_completion.py -m postgres -q --tb=short
apps/api/.venv/Scripts/python.exe -m ruff check apps/api
apps/api/.venv/Scripts/python.exe -m ruff format --check apps/api
apps/api/.venv/Scripts/python.exe -m mypy --config-file apps/api/pyproject.toml apps/api/src/caliburn
pnpm build
```

結果：**1288 unit/contracts passed（15.68 秒）**、**37 PostgreSQL passed（28.17 秒）**。後者含本切片 20 項、migration 5 項及既有 completion 12 項。Ruff／格式、Mypy、全量契約生成檢查、TypeScript 與 Vite build 全通過；Vite 有既有 chunk 大小提示。測試與生成沿前版方式使用核准的本機權限，避免 Windows sandbox 暫存／Docker pipe ACL，不修改產品來繞過失敗。

獨立審查新版 workflow 與 tool：無實質 finding；確認來源與 Memory 依賴已移除、正式資格與操作回復仍在、解除範圍保留選用公版、搜尋請求不混排除清單，沒有顧問／bootstrap 註冊。語意上什麼算明確否認仍由未來顧問判斷，不能從離線通過推定模型不再重問。

## 尚未驗證

模型是否正確區分明確否認、未知、拒答及部分負責；是否在追問前讀取 state；員工更正時是否正確解除；整份 JD 的收尾品質及 token／耗時收益。正式模型接線、runner/checkpoint 位置回復整合及正式資料庫 migration 均未執行。
