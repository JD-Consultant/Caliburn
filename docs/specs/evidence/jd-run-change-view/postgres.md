# 整輪變更 API：原生顧問與真 PostgreSQL 驗收

- 日期：2026-09-13。
- 驗收者：`jd_ref_signer_preflight`；本輪未實作 `ChatService.changes`／run-change HTTP／投影。
- 測試：[test_run_change_api_postgres.py](../../../../experiments/jd-relational-app/tests/test_run_change_api_postgres.py)。只新增此檔，沒有修改共用 helper 或產品。
- **首次執行 3 PASS／0 FAIL，14.76 秒。** 沒有為測試結果放寬範圍、schema 或保存規則。

## 實際接線

沿 `test_chat_api_postgres.http_runtime/current_page/wait_terminal` 及 `test_ai_runtime_postgres._offline_model/_runtime/_read/_create/_final`，使用真正的：

- `ManualRuntime`／`AiRuntime` 共同 owner、原生 Agent 工具循環及持久 binding。
- 既有 PostgreSQL `127.0.0.1:55436`／`caliburn_jd_relational_test`，fixture 驗使用者、PG **18.6／180006**、Alembic **20260913_0001**；Saver 使用既有 `jd_runtime_test` 四張原生表。
- 原 `JdStorage`／SQL receipt 與 `PostgresSaver`；沒有 `FakeAuthority`。
- `create_configured_api`、原 Origin／dataset 邊界及 Starlette `TestClient` 的 ASGI HTTP。
- 真模型 SDK＋固定合成 SSE `httpx2.MockTransport`。同步 client 不使用環境 proxy，async client 工廠拒絕；沒有 provider 網路通路。每次已建立的串流 body 都必須 closed。

執行：`JD_RELATIONAL_TEST_DB=1`、`PYTHONUTF8=1`，在隔離 App 跑 `uv run --frozen --offline pytest -q tests/test_run_change_api_postgres.py`。

```text
... [100%]
3 passed, 2 warnings in 14.76s
```

兩個 warning：Starlette TestClient 引用 AnyIO 的 deprecated `BlockingPortal` alias，以及既有 pytest cache 位置 Windows 存取被拒。均未中止案例，沒有 setup error，未因警告更換依賴／權限或重跑。

## 三個通過情境

### 1. AI 新增 → 整輪變更 → 後續人工更正

固定 SDK 依序原生 `jd_read`、`jd_create_task`、完整公開回覆，共 **3 次 SDK 請求**。

- 真 SQL 新增 1 任務、2 成果、1 要求；整輪投影 `continuous`、`settled`、1 個 captured committed operation、4 個淨變更。
- 整輪 `records`／`total_records`／S／E 與原 operation 的既有差異 API 完全相同。
- 當時 `current.revision_ref == E`，初始目前稿 ref 等於 S；capture 中的原 operation UUID 與原 receipt 一致。
- 透過同一 API 的真人工 owner 修改 purpose，current 前進；再讀原輪兩次，完整回傳仍與原先相同，沒有把較晚人工內容混入 S→E。
- 原始 Human 原話與完整原生 messages 保留。資料庫為 3 revisions／2 operations；實際 execute 只有 AI 1 次、manual 1 次，SDK 仍 3 次。

### 2. 純訪談

真原生流程保存原話及完整回覆，**1 次 SDK 請求、0 次 writer execute**。

- 整輪為 `none`／`settled`，captured operation、changes、records 均為 0。
- S／E 為 null，無 cursor；不是假造同版 diff。
- 目前稿 ref 不變，資料庫仍 1 revision／0 operations。
- 重讀整輪不改原生 messages、不重播模型。

### 3. 執行中分頁固定捕捉範圍

固定 SDK 原生流程：read → create 1 → read → create 2 → final，總計 **5 次 SDK 請求、2 次 writer execute**。

- 第二筆 create 回覆在 MockTransport 內以有界 Event 暫停；此時第一筆 SQL 已 committed。
- 首次整輪 GET 使用真 service 的既有 `page_bytes=4096` 參數製造分頁，不替換 records、snapshots、scope、signature 或保存結果。
- 第一頁為 1 個 operation、4 個 changes、`unconfirmed`，E 等於當時 current；確實有 next cursor。
- 釋放第二筆回覆並等真回合 completed 後，使用原 cursor 讀完：全部頁保留原 capture、S、E、1 個 operation 及 `unconfirmed`。頁索引連續且不截斷／混入第二筆。
- 續頁期間把 `runtime.inspect_run` 替換成一旦被呼叫即讓測試失敗的探針，證明續頁沒有重新掃描原生 run；其他查詢／投影仍是真實實作。探針於 `finally` 恢復。
- 新的無 cursor 第一頁才得到 2 個 operations、8 個 changes、`settled` 及新的 E；原 messages、資料庫數量與 SDK／execute 數量不再改動。
- 這個暫停只控制合成 SDK 回覆，不模擬 Future／程序死亡；Event 在 `finally` 釋放，owner 必須實際 close 才能關 Saver。

## 未宣稱範圍

- TestClient 是 ASGI 整合，不是實際 socket server、瀏覽器、AX、IME 或員工試用。
- 合成 SDK 工具序列不等於自然模型自行判斷、訪談專業品質或費用／延遲評估。
- 本次沒有做 Windows 宿主重啟／斷線、未知 SQL 恢復、Memory／來源或整輪撤回；沒有啟動服務、setup、建立／刪除 DB 或讀取正式配置。
- 本輪只跑這三個新真 PG 情境一次；其他 SSOT conditional schema、純投影、游標與既有回歸由主代理及對應責任文件記錄，不合併冒稱本檔驗收。
