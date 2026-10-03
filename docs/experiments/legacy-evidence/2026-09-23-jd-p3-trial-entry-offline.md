# P3 自然縱切測試入口：離線接線證據

2026-09-23；程式只涉及 `experiments/jd-relational-app/tests/support/` 與對應測試。**未執行 P3、未呼叫真模型、未取得付費授權。** 正式產品仍以 ADR0077 的新 JD App 為唯一權責；本入口不在 `pnpm dev/start` 中。

## 現在接好的部分

- `p3_trial_server.py` 沿用既有隔離 PostgreSQL／DPAPI `prepare`、`initialize`、正式 `open_managed_app(enable_chat=True)`、正式 `build_consultant` 與 `create_role_models`。A／B1／B2 共用同一組 caller-owned guarded sync／async clients 和 durable spend ledger。沒有接回舊 `apps/api` 或 `apps/web`。
- `serve` 在讀 Windows Credential Manager 金鑰或開啟 App 之前，要求後續 Owner 授權形成的本地 unlock、C-W 卡包 manifest hash、指定 Git commit 以及乾淨工作樹。現在沒有 unlock，因此入口拒絕啟動真模型。檔案本身只是操作保險，不能代替 Owner 的對話授權。
- 在正式 chat HTTP 路徑前，對實際 `POST /chat/runs` 嘗試持久計數；第 13 次拒絕，重開沿用已計數值，狀態寫入失敗後拒絕繼續聊天。GET 查回不計為新員工回合。此為保守的請求次數上限，失敗 POST 也佔名額。
- 沿用既有測試觀測器，只記 HTTP route／status、JD operation／receipt 與 spend ledger 的模型 attempt／費用；不記金鑰、prompt、工具內容或內部 reasoning。完整原始訪談及來源仍由正式 App／DB 保存，判讀者於 trial 再按結果模板核對。
- 結果模板需要的實際 provider／model／tier、generation ID 與可用的 token／cache 數字，原本雖經 spend gate 驗證卻未在成功後持久保存；新增反例先得到 `KeyError: actual_model`，然後只在同一 test-only ledger 的 settled attempt 保存這些白名單 metadata。缺席的可選 usage 欄位不推測成 0；不記 response choices、prompt、工具內容或 reasoning。這不改正式模型 adapter／Domain。

採用依據（2026-09-23 查閱）：[OpenRouter Chat Completions 回應](https://openrouter.ai/docs/api/api-reference/chat/create-a-chat-completion)含模型與 usage；[Service Tiers](https://openrouter.ai/docs/guides/features/service-tiers)說明本路徑 tier 在回應頂層；[Prompt Caching](https://openrouter.ai/docs/guides/best-practices/prompt-caching)說明 `usage.prompt_tokens_details` 的 cache 欄位。本案僅記出現且型別符合的數字，不把官方可選欄位假設成每次必有。

## 首次離線失敗與處理

第一輪 pytest 被 Windows 暫存目錄 ACL 擋住；改用 repository 內隔離暫存位置並在可讀取該位置的執行環境重跑，未改測試語意。新增反例先發現 32 位大寫 UUID 路徑不會被原測試正則計數，以及持久計數寫入失敗後需要拒絕後續聊天；已改為涵蓋正式 chat 路徑的保守比對並保留停止狀態。

另一個反例證實 httpx 若跟隨重新導向，會在同一次 send 內向新目標外送多筆請求，後續請求繞過 test-only GuardedClient 的逐請求 admission。P3 caller-owned clients 已關閉自動重新導向；provider 回 3xx 會按既有非 200 規則保留未知費用並停止。正式產品 client 未修改。

另發現 C-W v2 `manifest.json` 的五個 raw-byte SHA／bytes 與 Git checkout 不相等。這是準備時混合 LF／CRLF、Git `core.autocrlf=true` 將 index 正規化、Windows 再 checkout 為 CRLF 所致：employee-card、release-protocol、oracle 以「最後一行 CRLF」可重建原 SHA；README 與 results-template 依保存的 `operator-adoption` 精確 diff 重建後，轉為 LF 的正文亦與目前 checkout 一致。沒有發現 W／M／Q 語意差異。舊 manifest 保留歷史原值；付費前以**核准的 manifest 實際 hash + 乾淨的 exact commit**約束可執行內容，不能把舊 raw-byte hash 當成 Windows checkout 驗證。v2 舊模板的全角色 8192 記錄由新增的 results-template-v3.md 承接並修正為 A 8192、B1／B2 32768；付費 unlock 同時核對這份 v3 模板的 SHA256。

## 2026-09-23 隔離 PostgreSQL／正式 App 零付費預檢

- Docker Desktop Engine 可讀，既有 `postgres:18.6-bookworm` 測試容器健康；只以既有 helper `prepare → initialize` 建立新的 `caliburn_jd_setup_test_0b342f3e8e39467aa2cb51fa27190d30`，沒有清理任何舊容器／volume／DB。初始化記錄 `phase=ready`，唯讀 SQL 回報 PostgreSQL `server_version_num=180006`、`public` 15 表、`jd_runtime` 8 表。
- 初始與正式 App 預檢關閉後，唯讀查詢的 `jd_document`、`jd_revision`、`jd_operation`、Memory publication head、Saver checkpoints、Store 業務筆數皆為 **0**。安裝用 migration 記錄不當成訪談／JD 資料。
- 用該隔離 DB、正式 `open_managed_app(enable_chat=True)`、正式 A／B1／B2 graph／model factory 和既有 P3 spend gate 的**未授權**模式，透過 ASGI `TestClient` 啟動與關閉完整 App lifespan；`GET /api/documents` 為 200、空清單，Saver 連線已關，provider attempt **0**。沒有打開 HTTP listener、沒有讀真金鑰、沒有送付費模型。
- 首次一次性預檢命令少了 `tests` 模組搜尋路徑，匯入即失敗（未進 App／DB）；補正命令後同一目標通過。這不是產品失敗，也不抹除首敗。先前 Docker pipe 的一般 sandbox `permission denied` 是工具權限；在允許唯讀查詢的執行環境中 Engine／容器均正常。
- 此結果僅是正式新 App 的隔離 PG／ASGI 啟停預檢，**不是 production Web build 或真 Browser，更不是 P3 自然訪談 PASS**。前次 Stable Chrome 固定模型旅程依原證據保留，但不能替代同批真模型 Browser 結果。

## 驗證與界線

`uv run --frozen --offline pytest tests/test_p3_trial_server.py tests/test_p3_spend_gate.py tests/test_ui_chat_server.py -q -p no:cacheprovider`：**49 passed**（pytest `--basetemp` 指向 repository 隔離目錄）；0 provider network／US$0。覆蓋未授權時不讀金鑰或開 host、正式三角色共用 guarded clients、12 次上限與重開、帳本故障、正式 managed App composition seam、支出閘門、成功回應 metadata 的持久白名單及沿用的觀測器。

這完成測試入口的離線接線與隔離 PG／正式 App ASGI 啟停預檢。尚未有可提交的 exact revision、同批 production Web／Browser 預檢、完整逐輪 trace、Owner 付費授權、自然模型與真 Browser 品質結果；不能標 P3 PASS。下一步先核對同批 Web build／現有 Browser 證據的適用界線，再交可審的凍結版本和費用界線請 Owner 裁決是否執行真模型。

## 2026-09-23 正式新 App Web 零付費複核與 trace 盤點

- 在同一未凍結工作樹執行正式 `@caliburn/jd-relational-web`：`test` **310 passed／0 failed**、`typecheck` 成功、`build` 成功；正式 `@caliburn/jd-relational-app codegen:check` 顯示 Python／TypeScript 生成契約一致。首次一般 sandbox 的 Node 測試／build 子程序為 `spawn EPERM`，uv 預設快取為存取遭拒；在允許子程序的環境及專案隔離 uv 快取用**同一檢查命令**重跑通過。未修改產品程式，亦未送 provider request。
- 既有 test-only `Evidence` 只記 HTTP route／status／elapsed 與 JD writer receipt；正式 AiRunCheckpoints／ChatHistory 的 canonical messages 保存 Human／AI／Tool，背景 admission 與 Memory publication 另有既有 owner。這些能作逐輪內容及副作用查回，不能把 Web unit PASS 或單一 HTTP 計數當成自然模型 trace。
- P3 spend ledger 已保存 provider attempt、實際 provider／model／可用 usage 與費用，但**沒有每筆 attempt 的 A／B1／B2 角色、觸發事件或起訖時間**。A 的 8192 output 上限可與 B1／B2 的 32768 區分，B1 與 B2 不能只靠上限區分；不可在結果模板憑推測填角色或時間。下一個零付費接點僅需核對現有模型 metadata／native checkpoint 能否精確對帳，若不能，再於既有 test-only HTTP gate 補最小白名單觀測；不建立第二套 production trace authority。
- 此複核**沒有**啟動 production Web＋API 同批真 Browser、沒有自然 Luna 訪談，也尚未產生可供付費入口核對的乾淨 exact commit。Chrome 固定模型旅程沿既有證據保留，但不能代替 P3 真模型 Browser。P3 仍 `NOT RUN／NOT AUTHORIZED`。

## 2026-09-23 P3 逐請求角色與時間：零付費接線

- 在鎖定的正式 `create_role_models` 上，以 `httpx.MockTransport` 核對 LangChain `on_chat_model_start` callback：既有 `caliburn_component` metadata 在 A、B1、B2 的 sync invoke、工具綁定後 invoke、B1／B2 非同步交錯請求都能到達同一次 HTTP 送出；成功後 callback 清除角色，不讓下一次請求沿用。正式 OpenRouter adapter 也把 synthetic response ID 保留在 `AIMessage.response_metadata.id`，可與既有 spend ledger 的 `generation_id` 作後續對帳。這是本機合成 probe，不是自然 Agent／真 Saver 完整往返。
- 只在既有 P3 test-only guarded client／spend ledger 補角色與 UTC 起訖時間、HTTP status。正式三角色模型本身的 metadata 為來源；缺角色或角色與正式 max output 不符時，在 provider network 前拒絕。成功／HTTP 異常／transport unknown 均沿同一帳本記錄已知事實，未知終點不偽造。沒有新 production trace、資料表、Agent、Prompt 或模型設定。
- 先寫的兩個反例在原程式得到 `KeyError: role` 與真正打到 synthetic transport 的錯誤，證明原本無法保存角色且缺角色不會 fail closed；最小補線後再加角色／輸出額度不符及模型錯誤後清除角色兩個邊界檢查。`test_p3_trial_server.py`、`test_p3_spend_gate.py`、`test_ui_chat_server.py` 合計 **53 passed／0 failed**。全程只用 MockTransport、合成輸入與合成 cost，**0 外部 provider request／US$0**；帳本測試另確認員工輸入與 synthetic key 不落盤。
- 逐請求的角色、起訖、HTTP、generation ID、費用現在有 test-only 保存接點；**觸發哪個員工／背景事件，以及 generation ID 如何穿過真 PostgreSQL Saver 與 B1／B2 checkpoint 對到正式結果，尚未在同批整合旅程核實**。不能因此把完整逐輪 trace 或 P3 標成 PASS。下一步只沿既有 App/Saver/Store 與結果模板做離線查回，不增第二套追蹤權威；付費與真 Browser 仍需獨立 gate。

框架依據（2026-09-23 查閱）：[LangChain `on_chat_model_start` 參考](https://reference.langchain.com/python/langchain-core/callbacks/base/CallbackManagerMixin/on_chat_model_start)明列 model run 的 `metadata`、`run_id` 與 `tags`；本案實際鎖定環境為 `langchain-core 1.6.3`、`langchain-openrouter 0.2.8`、`openrouter 0.10.8`，只採本地已實測的 `caliburn_component`，不把最新文件的簽章當成本地版本已驗證的替代品。

## 2026-09-23 正式新 App／Saver 單回合零付費對帳

- 沿用已初始化的隔離資料庫 `caliburn_jd_setup_test_0b342f3e8e39467aa2cb51fa27190d30`、正式 `open_managed_app(enable_chat=True)`、A／B1／B2 factory、正式 Chat HTTP 與 `AiRunCheckpoints.observe`；只替換 OpenRouter HTTP 為 `httpx.MockTransport`，回傳一個固定合成 A 回覆及合成費用，沒有使用真金鑰或外送 provider。
- 首次執行把 `create_document` 放在 ASGI lifespan 啟動之前，正式 owner 回報 `startup_pending`；未建立文件、未送模型。依既有 App 生命週期把建文件移至 `TestClient` 啟動後重跑，同一隔離 fixture 通過。未為測試放寬 startup 權責。
- 成功回合由 HTTP 保存合成員工輸入，回合查回為 `run_status=completed`、`input_state=saved`。P3 spend ledger 僅有一筆 `role=consultant` 的 synthetic attempt，其 `generation_id=gen-p3-pg-a-1` 與正式 PostgreSQL Saver 觀察到的 AIMessage `response_metadata.id` 相等；App／Saver 正常關閉。這是合成 provider 回覆的資料關聯測試，不是自然品質或付費模型能力證據。
- 本次在該專用測試 DB 留下一份合成文件與回合，沒有刪除既有資料、重建 DB 或變更正式產品；零外部 provider request／US$0。B1／B2 尚未在正式背景工作中驗證 checkpoint／觸發關聯，不能把 A 的單回合對帳外推；P3 仍 **NOT RUN／NOT AUTHORIZED**。

## 2026-09-23 B1／B2 正式背景 checkpoint 與 publication 零付費對帳

- 採用目前新 App 的 `build_background_memory_workflow`、`BackgroundDispatcher`、`BackgroundAdmissions` 與正式 `create_role_models`；一份合成 canonical 訪談及已保存的合成整理通知是本次固定輸入。B1／B2 皆走相同 P3 guarded clients／durable spend ledger，僅 OpenRouter HTTP 由 `MockTransport` 回覆固定工具呼叫；沒有改 package Agent、Prompt、Domain、publication 或 production App。
- 真 PostgreSQL 18.6 的 Saver／Store／admission／publication 上，dispatcher `wake()` 接受一批；外層 workflow terminal `completed`，publication `revision=1` 的 `processed_source` 等於固定 job source，admission 回 `idle`，目前 bundle 有一個案例與一份工作理解。B1、B2 的各個 AIMessage `response_metadata.id` 分別等於同一 spend ledger 中對應角色的 `generation_id`，所有帳本 attempt 均 settled。這證明 request→正式背景 checkpoint→publication 可在固定合成流程對帳，沒有額外 trace authority。
- 首次一般 sandbox 在 pytest 暫存目錄得到 Windows `WinError 5`，未取得產品結果；於可存取隔離測試環境執行同一測試 **1 passed**。再執行 `test_p3_trial_background_postgres.py`、`test_p3_trial_server.py`、`test_p3_spend_gate.py`、`test_ui_chat_server.py` 及既有 `test_layered_background_dispatch_postgres.py`：**57 passed／0 failed**。只使用合成輸入與 `MockTransport`，0 外部 provider request／US$0；測試資料保留於既有隔離測試 DB，不清理其他資料。
- 本測試的通知與模型回覆刻意固定，沒有驗證 A 自主決定通知時機、B1／B2 自然整理品質，也不是與上一段 A 單回合同一文件的自然縱切。真正逐輪事件、真 Luna、同批 Browser 及最終 JD 品質仍待 P3；P3 仍 **NOT RUN／NOT AUTHORIZED**。

## 既有同文件旅程證據的沿用界線

- [2026-09-22 元件與完整 App 驗收](2026-09-22-jd-component-first-acceptance.md#完整-app-旅程接續)已在正式新 JD App、同一隔離 PostgreSQL 與真 Luna 路徑走過 A 非等待式整理通知、B1／B2 publication、A 下一輪按需回讀、JD 修改、真 Browser 來源查看與本輪 JD 撤回。這是現有同文件整合證據，**不再另造一套固定 A→B1→B2 接線測試**；上節新增的 P3 離線 B1／B2 測試只補當時缺的逐角色 spend ledger ↔ Saver checkpoint 對帳。
- 9/22 旅程使用合成訪談資料，不是 C-W 依自然追問逐步揭露的長訪談，也未使用本次 P3 的同批付費閘門與逐輪結果模板。因此不能把那次整合 PASS 換算成 P3 自然品質、C-W 當輪觸發、完整專業 JD 或本批 Browser PASS；這些仍須在獲核准的凍結版本上實測。

## 2026-09-23 P3 逐次外送的重新導向覆寫邊界

- 審核 test-only guarded client 時發現：雖然 trial runtime 建構 `httpx 0.28.1` client 時設 `follow_redirects=False`，每次 `send(follow_redirects=True)` 仍可覆寫。兩個先寫的同步／非同步反例在原實作各得到 `TooManyRedirects`，證明一筆 spend-ledger admission 可實際送出多次 307 請求；原先只測 client 預設不跟隨，未覆蓋逐次覆寫。
- 修正只在 P3 `GuardedClient`／`GuardedAsyncClient` 的 `send`：明示 `follow_redirects=True` 於 admission／network 前拒絕，其他呼叫也一律向 httpx 傳 `follow_redirects=False`。不改正式產品 HTTP client、Provider、Agent、重試或費用語意。先跑 P3 集合 **42 passed／1 skipped**（PG opt-in 未啟用）；再啟用既有隔離 PG fixture，跑 spend gate、trial server、正式背景與相鄰 chat／dispatcher 集合 **59 passed／0 failed**。全程 `MockTransport`／離線，0 外部 provider request／US$0。
- 這只修補 P3 驗收入口的請求數護欄；C-W 自然 Luna、同批 Browser、乾淨 exact revision 與 Owner 付費裁決仍未完成。

## 同批真 Browser 的既有接線邊界（靜態核對，未執行）

- 正式根目錄 `pnpm start` 會由 `scripts/run-jd-app.mjs` 讀取**一般受保護 App 設定**的 API origin，並一起啟動一般 API 與 Web；它不是隔離 P3 trial API 的入口。不能用該啟動器開啟 P3 Web，否則畫面可能連到另一份文件／資料庫。
- P3 `serve.ready.json` 才提供隔離 trial 的 `api_origin`，並記錄預期 `ui_origin=http://127.0.0.1:3002`。正式 Web 的 `page.tsx` 是動態頁，從執行時 `JD_API_ORIGIN` 傳入既有 `Workspace`／`JdApi`；因此待 trial 獲准且 API ready 後，應以**同一凍結 revision 的既有 Web `start` 腳本**單獨啟動，將該 ready 檔的 `api_origin` 設為 Web 程序的 `JD_API_ORIGIN`。不修改根啟動器、Web 程式或另建 P3 專用前端。
- 開始員工輸入前，須在真 Browser 核對文件列表請求的實際 API origin 等於 ready 檔的 `api_origin`，並核對回覆的 dataset 身分屬於隔離 trial；不能只看空白列表便推定連線正確。已有的 production Web build 與 9/22 Chrome 合成旅程只能沿用為各自層級的證據，**不能代替這個同批核對**。目前沒有啟動本輪 P3 API／Web 或真 Browser，仍 `NOT RUN／NOT AUTHORIZED`。

## 2026-09-23 目前工作樹的 P3 入口窄回歸

- 只重跑 `test_p3_spend_gate.py` 與 `test_p3_trial_server.py`。第一次在預設 uv cache 得到 Windows `WinError 5`；改用專案 cache 後，pytest 預設暫存根仍存取拒絕；指定全新、已確認位於專案內的 basetemp，在受限執行環境仍存取拒絕。三次都沒有取得完整產品測試結果，沒有修改產品或測試語意。
- 同一程式與測試，在可讀寫該全新暫存目錄的執行環境，使用 `uv run --frozen --offline`、專案 cache 與 `-p no:cacheprovider` 得到 **42 passed／0 failed**。測試只用合成回應與 `MockTransport`，沒有讀正式 key 或外送 provider request；這只確認目前工作樹的 P3 入口與支出閘門離線回歸，**不代表自然 Luna、同批 Browser 或 JD 品質通過**。

## 2026-09-23 正式 Web 的隔離 API origin 預檢（無 provider）

- 沿目前已建置的正式 `@caliburn/jd-relational-web`，只對 Web 程序設定測試用 `JD_API_ORIGIN=http://127.0.0.1:8769`，以既有 `start` 腳本在 `127.0.0.1:3002` 啟動。`GET /` 回 HTTP 200；回傳頁面含指定的 `8769` API origin，未出現「尚未連接本機資料服務」。這實測了動態頁可從獨立 Web 程序承接 API 位址，不需修改根啟動器或新增 P3 前端。
- 本次**沒有啟動 8769 API、沒有建立文件、沒有 Browser 操作，也沒有呼叫模型**；它不證明 Web 能查到隔離 trial 的 dataset，更不算同批 Browser 或自然 Luna PASS。Web 程序已正常停止，3002 listener 已不存在。下一輪仍須在獲准的 trial API ready 後，從真 Browser 核對實際請求 origin 與 dataset 身分，再開始員工輸入。
