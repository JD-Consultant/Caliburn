# 公版參考工具驗證紀錄

日期：2026-10-05。範圍是已授權、尚未註冊顧問的工具／state 切片；[施工計畫](../../2026-10-05-occupation-reference-tools.md)及[責任契約](../../../specs/2026-10-04-public-reference-completion-design.md#工具與保存契約2026-10-05未接模型)。使用合成訪談與 HTTP fixture，沒有模型請求／付費外送。沿用其他工作仍在使用的 checkout，未 commit／push。

## 可重現反例與設計選擇

| 問題 | 驗證及落點 |
|---|---|
| 搜尋失敗被當沒有工作，或只回命中片段漏掉同公版其他任務 | adapter 分開合法空結果與服務／結構錯誤；完整 parsed catalog 保留。47 項 MockTransport cases，stub 先出現 `NotImplementedError`，實作後通過。 |
| 已選、未選與未選擇混淆，或重新選擇清掉確認來源 | state 純函式 12 項 Red → Green；`None`／空 tuple 分開，選擇只替換選用欄，相同 subject 合併去重來源。 |
| 操作重送套用兩次、回復後舊命令再次提交 | 7 項真 PostgreSQL state cases 從 stub 的 7 failed → 通過；原結果不可變，revision／generation 核對，同 Turn 可達祖先回復。 |
| 取消輪次／顧問問題／其他檔案被當員工依據 | workflow 先觀察 `start` stub 失敗；目前 11 項真 PostgreSQL cases，含 formal + completed 雙資格、fixed frontier、employee role、pending／foreign source、替代 writer、restore、跨中間空白輪次接續。 |
| 只測 fake workflow，無法確認工具與實際保存相容 | 一項真 HTTP MockTransport → adapter → tools → workflow → PostgreSQL 旅程，含保存命令 JSON 往返、服務下線後重播原結果、新 Turn 來源投影及失敗不清資料。不是 Graph／模型旅程。 |
| 主搜尋最多五份，被誤變成永久只能選五份 | 對照已確認規格移除 selection 的 maxItems5；unit／PG 均測兩批可選六份，搜尋 limit 仍五份。 |

沿用現行 completed execution 與正式 exchange 作可見性資格，比另外保存 adopted／completed 旗標少一份 authority；因此不用修改正式完成流程。feature 只保存自己的候選及原操作結果，跨 feature 資格由 workflow 協調。沒有引入新套件、另套排程或完成評分引擎。

## 執行方式與結果

直接使用已鎖定且存在的 `apps/api/.venv/Scripts/python.exe`；`uv` 的使用者 cache 與 sandbox 的 Windows 暫存 ACL 曾阻擋測試／生成。完整 unit/contracts 首次為 **1247 passed、21 fixture setup errors**，均為 `PermissionError`；改 workspace basetemp 仍遭 ACL，未因此修改測試期待或產品程式。以核准的本機權限執行相同完整命令後為 **1268 passed**。後續 checkpoint 修正的最後結果記於下方。

```powershell
apps/api/.venv/Scripts/python.exe -m pytest apps/api/tests/unit apps/api/tests/contracts -q -p no:cacheprovider --tb=short
apps/api/.venv/Scripts/python.exe -m ruff check apps/api
apps/api/.venv/Scripts/python.exe -m ruff format --check apps/api
apps/api/.venv/Scripts/python.exe -m mypy --config-file apps/api/pyproject.toml apps/api/src/caliburn
pnpm build
```

Ruff／格式及完整後端 Mypy 通過；`pnpm build` 的全量 codegen drift、TypeScript 與 Vite build 通過，Vite 有 chunk 大小提示。生成由正式工具完成，沒有手改生成物。

真資料庫使用既有 `caliburn-jd-docker-test-postgres-1`、loopback `127.0.0.1:55441` 的 `caliburn_docker_test`。本目錄 [run_tests.py](run_tests.py) 只私下讀取指定容器的帳密供子程序使用，fixture 建立／清除專屬隨機 schema；沒有讀寫正式 App 資料庫、重建 volume 或停止其他程序。

```powershell
apps/api/.venv/Scripts/python.exe docs/plans/evidence/2026-10-05-occupation-reference-tools/run_tests.py apps/api/tests/integration/test_occupation_reference_state.py apps/api/tests/integration/test_occupation_reference_workflow.py apps/api/tests/integration/test_occupation_reference_tool_journey.py apps/api/tests/integration/test_database_migrations.py apps/api/tests/integration/test_consultant_completion.py -m postgres -q --tb=short
```

結果：**36 passed**。包含新切片 19 項、migration 5 項及既有 consultant completion 12 項；驗證 migration/model metadata 相符、保存與既有完成路徑回歸。

## 獨立審查與修正

1. workflow 測試缺少 `postgres` marker，正式 `-m postgres` 命令會略過 11 項。已補上，以上 36 項命令確實納入。
2. checkpoint 解析沿用 domain 初始值，缺失 `confirmations`／`selected_reference_ids` 可能默默補成空值。審查以保存一筆確認後刪除欄位重現；兩份 state 各缺兩欄先取得 **4 failed**，確認物件缺 `subject`／`answer_refs` 的兩項原本已拒絕。修正以 prepare 使用的同一 TypeAdapter 還原／再序列化，要求 JSON 結構完整相等，拒絕補預設值造成的意圖變化，不改 domain 的正常初始值。

修正後工具 **40 passed**；完整後端 unit/contracts **1274 passed（13.70 秒）**；上述真 PostgreSQL 回歸 **36 passed（24.08 秒）**。全後端 Ruff check／format（470 檔）與 Mypy（313 來源檔）通過。獨立審查重驗原反例已拋出 `ValueError`、workflow 呼叫數為 0，完整命令仍可往返，無剩餘實質 finding。這些耗時只屬本機測試執行，不是產品延遲或效益比較。

## 未驗範圍與操作界線

- 未註冊顧問或改 Prompt、runner、bootstrap；沒有正式 App HTTP endpoint。`0024` 只在隔離 schema 驗證，更新正式安裝仍依既有 migration 流程。
- 未呼叫實際 RAG server／embedding／reranker；其品質與參數仍沿既有檢索實驗。此次只驗服務契約與資料流。
- 未驗模型能否忠實抽取正向主要工作、選中適合公版、理解否認、更正與未知、避免重問或判斷 JD 收尾。
- 未證明 token／耗時下降。正式接模型還須把 reference position 納入既有 checkpoint 回復範圍，補接續／取消競爭及模型旅程；不把獨立 tools 的資料庫接續測試冒充正式 Agent 旅程。
