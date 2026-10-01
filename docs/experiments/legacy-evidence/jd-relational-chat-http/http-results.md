# 聊天 HTTP 的原回合、保存結果與安全邊界接合

- 日期：2026-09-13；原始基準 `2734b82b`，對同工作單位新 `chat_api`／`chat_service`／`configured_api` 的接合測試。
- 狀態：以下有限案例通過；本份只新增測試與證據，未修改 `src`、契約、依賴或資料表。
- 入口：[離線 HTTP 測試](../../../../experiments/jd-relational-app/tests/test_chat_api.py)、[真 PG HTTP 測試](../../../../experiments/jd-relational-app/tests/test_chat_api_postgres.py)。
- 零 provider；真 SDK 只接 `httpx2.MockTransport` 固定 SSE。沒有真瀏覽器、Uvicorn socket／新程序、自然模型、正式設定或 production DB。

## 1. 被驗證的實際接線

`create_configured_api(..., with_chat=True)` 使用同一 lifespan 注入的 `ChatServices(reads, changes, manual, catalog, chat)`。聊天路由沿既有 Origin、dataset、body limit、安全錯誤／記錄與 no-store 邊界；沒有新增 owner 或另一份 conversation store。

離線案例使用既有 `make_runtime` 的真原生 `InMemorySaver`、root／child graph、`ForegroundFuture` 及 `ManualRuntime`；走實際 `ChatService`、`ManualService`、`ChatHistoryService`。唯一 SQL 回執查詢是明示回空 tuple 的合成 port，child 回覆也是合成，不將此層當真保存證據。

真 PG 案例使用同一 app composition、真 `JdStorage`、`HistoryReader`、PostgreSQL Saver、具名 JD 工具及 `AiRuntime`。模型工廠、SDK create/stream 與工具配對沿[既有 AI runtime PG fixture](../../../../experiments/jd-relational-app/tests/test_ai_runtime_postgres.py)；只有 HTTP transport 回覆被替換。fixture 核每個 SDK request 的 10 工具 strict schema、禁止平行工具及 tracing disabled；synthetic key 直接指定，不讀真金鑰。`MockTransport` 中雖保留 SDK 的官方 host 字串，沒有實際網路連線。

HTTP 用 FastAPI `TestClient` 實際送入 ASGI，包含 request parsing、dependencies、native sync endpoint threadpool 與 response validation；不把它稱作真瀏覽器或 loopback socket server。TestClient lifespan 不代供 native OS ownership proof；owner/Saver 的建立與排空沿既有測試 fixture。

## 2. 離線 HTTP 的 22 個案例

- POST 開始在真正 child Future 尚未完成時回 **202**，`Location` 指向原 run GET。GET 只觀察原 run／SQL port，不另 start 或 invoke；原生 checkpoint 不因 GET 改動。
- cancel 設定停止要求，但 child 尚未退出時仍回 **202/running**、write gate 保持；`handle.wait` 仍 timeout。待真正 Future 完成後，GET 才回 cancelled，並保留已保存的原話及实际完整回覆。
- 已完成原 run 重送相同輸入，即使 head 已前進也回原結果；同 ID 異文字回 run_conflict。下一輪完成後，GET 舊 run 仍可查回，未知 run 只回 not_found／input unconfirmed，不宣稱原話未保存。
- 聊天分頁保留 CRLF、空白與 emoji 原話；拿第一輪 cursor 後開始第二輪，續讀仍固定第一輪 anchor，沒有混入新話。只輸出 user／assistant public text，不複製 tools／system 內容到畫面正文。
- 對 start／cancel／recover，以原生 ASGI `receive` 禁止被呼叫的反例，驗 Origin、dataset 缺少／錯誤先於 body。重複 dataset header 不能觸發只有 UUID 的 recovery。
- 破 JSON、原 JSON 重複 key、未知欄、錯型別、NUL、UTF-8 超過 128 KiB 皆在入 run 前拒絕；原始合成私有 marker 不進 response 或 App log。cancel／recover 僅接受精確空 object。
- driver 合成例外回固定 service_unavailable，不外露原例外；錯誤仍有 CORS、no-store、request ID 及 nosniff。OpenAPI 宣告 dataset header、202 ChatRunState、原 ChatProblem／CatalogProblem 409 union，CORS 可讀 Location。

每個正式成功／聊天錯誤 JSON 以生成 DTO 與其公開 JSON Schema 驗證；沒有手寫成功結果副本。dataset gate 使用其原 CatalogProblem，此錯誤不冒充聊天 run 結果。

## 3. 三個真 PG HTTP 情境

1. **純訪談。** HTTP 先讀 JD current 取得 revision ref，再開始訪談及以 GET 查到 completed／input saved／effects settled empty。原 Human 文字及完整 AI 回覆存在原生 Saver，聊天頁與 response_message_id 一致。重复 GET、未知 run、缺文件都不另呼叫模型。JD 仍是 **1 revision／0 operation**。
2. **AI 新增工作，後來人工更正。** HTTP start 使真 Agent 依次 jd_read → jd_create_task → final；SQL 成為 **2 revisions／1 operation**，任務含兩成果、一要求。GET 的唯一 committed／confirmed result 與原 SavedOperation、base/result revision IDs、change ref 一致，change HTTP 返回同原 AI operation 的四個 create 差異。接著同 app 的 manual HTTP 真保存用途更正，成為 **3 revisions／2 operations**；舊 run GET、原 change、歷史 JD 與原話保持，沒有新模型呼叫。最新聊天頁可以有新 root anchor；此前取得的 cursor 仍沿舊 root 續讀，原消息不變。
3. **JD 已保存，最後模型回覆失敗。** jd_read／jd_create_task 已完成真 COMMIT，第三次 SDK request 的 MockTransport 拋合成 ReadError。HTTP 最終同時呈現 `run_status=failed`、`input_state=saved`、`jd_effects.state=settled`；其中唯一 result 仍是 committed／confirmed／changed，具有原 change ref，error=null。任務及三個 detail 存在，SQL 仍為 **2 revisions／1 operation**。原生 run 已關閉為 failed，聊天頁保留原話；GET 不把保存改判失敗，也不再執行模型或新增操作。

以上三者分開證明回合、原話、JD 效果。第一案只捕獲 1 次固定 SDK request，第二及第三案各 3 次；都不是模型額度或自然回答品質測試。第三案是模型讀取錯誤注入，不是假造 SQL COMMIT 或回執成功。

## 4. 首輪與最後結果

| 執行 | 實際輸出 | 解讀 |
|---|---|---|
| `test_chat_api.py` 首跑 | **22 PASS，2.14s** | 離線 ASGI／native Future；不是 PG |
| 真 PG 原兩案首跑 | **1 PASS／1 FAIL，3.50s** | 純訪談通過；第二案最後錯將「最新聊天 root anchor 必相同」列為測試要求 |
| 修正第二案測試假設後，僅重跑該案 | **1 PASS，2.61s** | manual descriptor／cleanup 原本就會產生新 root checkpoint，最新 anchor 可變；修為核消息原樣，另補舊 cursor 固定頁 |
| 追加第三案首跑 | **1 PASS，2.32s** | 真 SQL 已保存＋模型回覆失敗的三事實情境 |

這些是分別執行的結果，不宣稱曾以一個命令跑過「3 PG PASS」或更大完整 suite。未發現需修改 `src` 的阻擋反例；唯一首敗是測試对新 root anchor 的錯誤假設。

上述 HTTP 執行皆有 **1 項已知 DeprecationWarning**：鎖定 Starlette TestClient 引用 `anyio.abc.BlockingPortal` alias，上游建議改用 `anyio.from_thread.BlockingPortal`。本工作未升級或改 vendor；warning 不是 provider、DB 失敗或測試 skip。

## 5. 可重現與限制

在 `experiments/jd-relational-app`：

```powershell
$env:PYTHONUTF8='1'
uv run --offline --frozen --cache-dir S:/caliburn/.research-tmp/uv-cache pytest tests/test_chat_api.py -q -p no:cacheprovider --tb=short
$env:JD_RELATIONAL_TEST_DB='1'
uv run --offline --frozen --cache-dir S:/caliburn/.research-tmp/uv-cache pytest tests/test_chat_api_postgres.py -q -p no:cacheprovider --tb=short
```

PG 沿[既有專用 engine](../../../../experiments/jd-relational-app/tests/test_storage_postgres.py)，只連 `127.0.0.1:55436/caliburn_jd_relational_test`，實查 PostgreSQL 18.6 與既有 migration。Saver 沿[既有 native 連線](../../../../experiments/jd-relational-app/tests/test_manual_runtime_postgres.py)及 `jd_runtime_test` 四張原生表，不 setup／drop／刪除，合成文件與原話保留。未使用 FakeAuthority 證明 AI 或人工 admission。

版本與官方依據沿既有[HTTP host 前置](../2026-09-13-jd-http-host-preflight.md)、[原生工具前置](../jd-relational-ai-runtime/tool-preflight.md)與[SQL 原操作清單](operation-results.md)，本輪沒有新增套件或品牌研究。FastAPI／Starlette／SQLAlchemy／Psycopg／LangChain 等仍採 app lock，模型與 App／DB 權責未改。

仍未由這些測試涵蓋：managed app 的真 OS startup／跨程序重啟、實際 Uvicorn 傳輸中斷、Web 元件送出／恢復與真瀏覽器、自然模型、Memory/source/selection 接線，以及所有未列出的故障組合。首輪 read-only history 也不等於 SQL 與 Saver 共享一個交易；完整性仍由 runtime 分別核原生 binding 與原 SQL receipts。
