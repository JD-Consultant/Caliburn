# 真瀏覽器聊天 helper

日期：2026-09-13；2026-09-15 wire 更新。本 helper 僅存在於 tests，production 不 import。原文下方保存當時 Anthropic fixture 的歷史結果；目前 helper 已改用正式前景相同的 LangChain／LangGraph＋OpenRouter adapter、OpenAI-only Luna route 與 sync／async `httpx.MockTransport`，仍是四次固定合成回覆、0 provider。更新後相關模型／runtime／managed App／helper 38 passed，完整離線回歸 2930 passed／315 skipped；未重跑本頁舊的真瀏覽器 fixture，也未把歷史數字改寫成新結果。

## 已交付與證據界線

- `ui_chat_server.py` 重用 `ui_response_gate_server.py` 的 `directory`、`prepare`、`initialize`、`manifest`、`fixture_file`、port/socket 檢查；目錄名沿原安全邊界 `jd-ui-gate-<32個小寫 UUID hex>`，本輪必須是全新 fixture。
- `serve` 用真 `open_managed_app(..., enable_chat=True)`，真原生 `build_consultant_node`、`AiToolMiddleware`、JD 工具、host owner、SQL 與 PostgreSQL Saver。只替換 SDK 的 HTTP transport，使用明示合成 key、`trust_env=False`、同步 MockTransport；非同步 client 拒絕建立，tracing 關閉。模型 retry 保持原生 factory 的 0。
- 固定四次 SDK 請求：第一輪 `jd_read` → 依實際 read 回傳的 container ref `jd_create_task` → final；第二輪只有 final。任務含兩項成果及一項執行要求。這是接線驗收，不是自然模型判斷、訪談品質或 Memory 整合驗收。
- 不使用舊的 response gate，不包含取消、回覆遺失或新程序恢復故障注入。超過四次 SDK 請求會明確失敗；同 fixture 不再開第二次 serve，避免重播固定腳本。

## 本輪實際 fixture／操作

主代理已經完成以下 fixture 的 prepare 及 initialize；**不要再執行這兩步**：

```text
S:/caliburn/.research-tmp/jd-ui-gate-89efc61691f442b9bffd5e16ee6d57a9
API http://127.0.0.1:8767
UI  http://127.0.0.1:3002
```

主代理在 `experiments/jd-relational-app` 使用本 App frozen venv，設定 `PYTHONUTF8=1`、`JD_RELATIONAL_TEST_DB=1`，以 Hidden 背景視窗啟動並保存自有 PID／stdout／stderr：

```text
uv run --offline --frozen --no-sync --cache-dir S:/caliburn/.research-tmp/uv-cache python tests/support/ui_chat_server.py serve S:/caliburn/.research-tmp/jd-ui-gate-89efc61691f442b9bffd5e16ee6d57a9
```

`serve.ready.json` 只在真 ASGI lifespan 完成後寫入。它包含 PID、dataset、installation、DB 名稱及固定 endpoint，不含密碼或 signing key。一般 serve 只開既有配置，不做 setup。此代理沒有啟動 server；啟動及瀏覽器操作由主代理決定。

建議合成旅程：

1. 瀏覽器從空白建立一份文件。第一輪輸入：「我收到通知後檢查設備，先確認隔離，留下檢查記錄並交接異常。」
2. 待原回合完成，核對同頁 JD 新任務、兩成果、一要求，以及可見原話與顧問文字。第一輪新增一筆業務操作，revision 由初版前進一次。
3. 第二輪輸入：「這輪先確認目前的說明，沒有新的工作要補充。」待完成；應顯示第二次顧問文字，JD revision 不再前進。
4. 關頁重開，核原對話與 JD，原模型 HTTP count 仍為 4、writer execute 為 1、chat start POST 為 2。另用唯讀 SQL／Saver 核對原始 HumanMessage、ToolMessage 與 receipt；不以模型 final 文字替代保存證據。
5. 下列 stop 僅在固定 fixture 建立控制檔，不 kill 程序；等 `serve.finished.json` 並另核所保存原生 PID 真退出：

```text
uv run --offline --frozen --no-sync --cache-dir S:/caliburn/.research-tmp/uv-cache python tests/support/ui_chat_server.py stop S:/caliburn/.research-tmp/jd-ui-gate-89efc61691f442b9bffd5e16ee6d57a9
```

若另建全新 fixture，CLI 保留 `prepare <新目錄> --api-port <空閒測試埠>`、`initialize <同目錄>`；它們直接沿原 helper 查明固定 127.0.0.1:55436／合成 admin DB／jd_test／PG180006 後才建立新命名 DB。不 DROP、不共用 production、不猜設定；本輪無需再使用。

## 紀錄與離線驗證

`chat.observations.json` 只記模型請求次數、payload byte 數、工具名稱、合成 response 狀態、已關閉 body 數、HTTP 路由分類計數，以及實際 writer 的文件／run／operation／revision ID 與確認狀態。不寫員工文字、工具參數、reference、key、query string 或例外正文。`provider_network=false` 表示 transport 固定為 MockTransport，沒有付費 provider；不代表沒有本機 API／PG 網路。

首敗：新 helper 尚不存在，測試收集 `ImportError`，1 error／0.26 秒。首次實作後 3 FAIL／3 PASS／3.60 秒：單測直接 bind tools 未帶原 middleware 正式使用的 strict 選項，且誤把 SDK 包裝後的錯誤期待成裸 `ValueError`。只修正測試為 `strict=True` 及原生 `AnthropicConnectionError`，未放寬 helper 的工具、位置或請求次數檢查；隨後 6 PASS／2.23 秒。

最後補路由／writer 元資料不讀正文的反例後，窄跑新 helper 7 案及被重用 helper 的既有 23 案：**30 PASS／0 FAIL，3.06 秒**。命令：`uv run --offline --frozen --no-sync --cache-dir S:/caliburn/.research-tmp/uv-cache pytest -q -p no:cacheprovider tests/test_ui_chat_server.py tests/test_ui_response_gate.py`。

離線測試執行真正 SDK／adapter，但工具結果是單測合成的 fixture；交易、Saver、宿主及瀏覽器尚不能據此宣稱通過。主代理真瀏覽器之後另記實際結果。

## 首輪瀏覽器查詢故障後的有限觀察補充

主代理在上述 fixture 的第一次真瀏覽器訪談，已取得 3 次完整合成 SDK 回覆及 1 次 confirmed writer；原 POST 取得 running 後，Web 的後續讀稿／狀態 `fresh()` 有一個 fetch 拋 `response_unknown`，停止觀察。明示「重新查看」後讀回原完整顧問文字、JD 及差異，沒有重送。此首敗保留，不能列為首次流程無故障。

靜態核對只能把故障限定在 fetch 本身：15 秒 timeout、CORS／網路／redirect 等瀏覽器拒絕均可能；正常 API Problem、JSON／schema 檢查有其他錯誤碼。原紀錄只有 HTTP 入口計數，沒有耗時與 send 狀態，**尚不能確認根因**。active owner 的 status 不須讀 Saver，讀稿為獨立唯讀交易，也沒有因此證明所有查詢皆準時送達。

本次僅修改測試 helper，新增 `http_observations`：

| 欄位 | 確切含義 |
|---|---|
| `ordinal`、`method`、`route` | 本 helper 收到的 HTTP 次序、固定方法集合、分類名稱；`jd_read`／`jd_state` 分開。沒有 raw URL/path、文件 ID、query 或 body。 |
| `status` | App 嘗試送出的 response.start 狀態；未見 start 為 null。它不表示瀏覽器接到 HTTP 回覆。 |
| `response_start_forwarded` | 原 ASGI send 對 start 正常返回後才為 true。原 send 拋錯則保持 false；不代表沒有部分位元組傳出。 |
| `response_body_end_forwarded` | 原 send 對最後一段 body 正常返回後才為 true，不讀取 body。Uvicorn 可能在連線已斷後仍正常返回，因此不是接收端 ACK。 |
| `cors_origin_matches` | 僅比較 response 的單一 ACAO 是否等於 request 的單一 Origin；不保存兩者值。缺少、不等或重複為 false；這不是完整 CORS／preflight 合規判定。 |
| `elapsed_ms` | helper 進入至 App 返回／拋錯的耗時；尚未返回為 null。不是瀏覽器收到或解析完畢的時間。 |

send 前後均不持有記錄鎖跨 await；不改原 message、不讀原 request body、不吞原 send 例外，記錄失敗只設 `evidence_failed`。既有活程序不 reload、不重啟；新紀錄僅用於主代理另開的全新 fixture，最多重現首輪一次（3 次固定合成 SDK 回覆），本輪不擴故障閘門或改產品錯誤／logging 架構。

新增觀察反例先 **5 FAIL／7 deselected，2.02 秒**（原 helper 無 `http_observations`）。實作後新 helper 12 案＋既有 helper 23 案，**35 PASS／0 FAIL，3.15 秒**；涵蓋讀稿／狀態分類、CORS 比較、真正 await send 後才設旗標、start 前／start send／body send 失敗，以及資料不外漏。這仍是離線 ASGI／SDK 證據。若新 fixture 未重現，保留首敗未知及已實測原 run 恢復，不將原錯誤改寫為 PASS。
