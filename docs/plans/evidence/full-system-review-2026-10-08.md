# 全系統審查與重構證據

計畫與授權見[主計畫](../2026-10-08-full-system-review-and-refactoring.md)。本頁保存實際基準、發現、修正及驗證；產品權責沿架構文件，不由測試結果反推新契約。

## 1. 工作區及基準

- 起始 HEAD：`6ec52822ee475876ed20e57d818c8db298c42928`，分支 `consultant-jd-analysis`，完整 dirty 工作區包含前期 Plan／Prompt 與文件工作。
- 後端離線基準：`uv run --project apps/api --locked pytest apps/api/tests/unit apps/api/tests/contracts -q -p no:cacheprovider`：**1491 passed，19.78s**。
- 後端靜態基準：`ruff check apps/api` 通過；`ruff format --check apps/api`：507 files already formatted；`mypy --config-file apps/api/pyproject.toml apps/api/src/caliburn`：340 source files 通過。均從根目錄以 `uv run --project apps/api --locked` 執行。
- 初次 sandbox 執行因 uv interpreter cache 寫入遭拒，未開始產品檢查；以工具核准的 sandbox 外執行重跑後取得以上結果。環境拒絕不計為產品測試失敗。
- 前端起始基準：48 檔、301 tests；typecheck、lint 通過。
- 真 PG 使用本次建立的 `caliburn-review-20261008-postgres`，PostgreSQL 18.6 鎖定映像，loopback 55448、`caliburn_review_test`；各測例建立獨立隨機 schema，未清理現有產品資料。
- 最終瀏覽器、交付與後端整合結果見 §4；各次受測版本與重驗分開記錄。

## 2. 審查覆蓋

| 責任範圍 | 第一輪審查者 | 進度 |
|---|---|---|
| 資料表、約束、交易、領域責任、migration | `experiment_design_research` | D1／D2 已實作；D2 獨立審查的原意圖完整性反例已修正及重驗 |
| 前端模組、狀態、契約、安全呈現、測試 | `frontend_delivery_research` | F1 已實作及獨立審查；完整瀏覽器 35／35 通過 |
| Log、diagnostics、對照入口、測試配置、交付腳本 | `observability_research` | O1／E1／L1 已修正並獨立審查 |
| Agent runtime、模型／工具接線、取消恢復、權限與整合 | 主代理 | 核對原 captured 配置、checkpoint／正式保存分責、Host／Origin、工具 scope、SDK／saver 關閉；驗證結果見 §4 |
| 架構文件與圖面語意、現行／候選及單一來源 | 主代理整合 | 保存圖逐一對照資料約束；29 張主文件及 4 張報告圖完成渲染與視覺複核 |

除上述修改外，核對以下現有責任及測試接縫；沒有為覆蓋面向而另造框架：

- **邊界與權限：** 本機 Host／Origin／Fetch Metadata、開發代理轉送、逐檔工具 scope 及 A／B 寫入能力；沿 `test_local_http_security`、`test_credential_containment`、工具及跨檔案整合測試。App 已知 ID／版本仍由後端提供，沒有改由模型決定。
- **網路、恢復與資源：** SDK 重試設為 0，由既有工作政策管理有限重試；原始請求、未知結果、取消及正式採用分責。lifespan 的 AsyncExitStack 按建立者關閉 client／saver／supervisor；沿 app composition、outbound retry、response recovery、程序恢復與控制反例核對。
- **契約、UI 與匯出：** Schema 生成檢查、Python／TS 型別及 import 邊界；Markdown 的連結／圖片維持惰性文字呈現，PDF 關閉 JS、離線並拒絕網路請求。前端單元與 E2E 分別驗狀態競爭、鍵盤、對話框、保存、預覽與 PDF；不據此宣稱完整 WCAG 認證。
- **資料與交付：** migration／ORM parity、同檔複合 FK、交易原子性及原操作恢復沿真 PG；鎖定依賴、非 root 容器及 loopback 發布沿既有交付與 Compose 測試。本輪沒有重新建置或部署 Docker 映像，沒有量測正式容量或跨作業系統效能。

## 3. 已確認發現與修正

### O1 Log 欄位與未完成執行的診斷資訊

反例：實際 Uvicorn LOGGING_CONFIG 下安全 `extra` 不出現在輸出；已保存 request 搭配空 response 的 checkpoint 產生空診斷列表；`initial_context.binding` 中的 Memory／Plan 版本未納入既有診斷 view。

已集中 stdlib logging 的 JSONL 配置、contextvars、有界佇列與輸出生命週期；診斷保留 request-only、原始 binding 及工具配置，CLI `--show` 可直接查同一份副本。migration 0027 只擴診斷投影；saved response 與 request-only 分別計數，未擷取為 null。正式保存仍沿原 owner，沒有新日誌資料庫或背景雙寫。

實作者：23 項單元、11 項真 PG 診斷、1 項 migration／ORM parity，Ruff／mypy 通過。主代理新增執行 scope 與 HTTP correlation 的 RED，再取得 7 passed。獨立審查後另修兩個反例：

- 未處理例外的 500 在外層 ServerErrorMiddleware 產生，漏 X-Request-ID。由同一 scope ID 的 500 handler 接回，真 HTTP 測試 1 failed／2 passed → 3 passed；已開始的串流維持原 200，不重送 500。
- stdout PIPE 不讀取時，daemon 持全域 buffered stdout 鎖，使 close 已返回仍卡 interpreter shutdown。真子程序 4000 筆 RED 超時並出 `_enter_buffered_busy`；改 listener 持自有不可繼承 descriptor、`os.write` 後正常 exit 0，close 未排完仍回 False。獨立原反例重跑 0.368 秒 exit 0；另核 broken pipe、partial write、建置失敗釋放 dup。沒有把關閉有界宣稱成 Log 全保存。

logging／launcher／execution 合計 24 tests 通過。獨立 sandbox 同步集有 11 passed／2 failed，後兩個是 Python launcher 前置警告使測試 stderr 非純 JSON；子程序均正常退出，與產品缺陷分開記錄。最終整合結果見 §4。

後續補查發現 supervisor 的監督錯誤只存在物件欄位，正式啟動器沒有消費者，可能安靜停止。新增 `supervisor.monitor_failed`／`supervisor.release_failed`，只記角色、操作與例外類名，保留原失敗／釋放語意；正常取消安靜。六個反例先 4 failed／2 passed，再全部通過；獨立 reviewer 連同匯入邊界及 reference fixture 重跑 65 tests 通過，未發現新問題。

研究：[Python logging cookbook](https://docs.python.org/3/howto/logging-cookbook.html)、[I/O 執行緒限制](https://docs.python.org/3/library/io.html#multi-threading)、[os.dup](https://docs.python.org/3/library/os.html#os.dup)、[Starlette middleware](https://starlette.dev/middleware/)。選 stdlib 有界接線，沒有引進尚無必要消費者的 processor 平台。

### F1 本機查詢、完成刷新與編輯基準

反例分別為：離線時 localhost query／mutation 被框架暫停；完成時 invalidate 沿用較早的首次 GET；編輯器 draft／revision 固定、dirty 比較文字卻隨背景資料更新。新測試依序 RED 2、3、2，修正使用正式 QueryClient factory、完成後先 cancel 再 await refetch，以及同一開啟基準。

`frontend_refactor` 全套 50 檔／309 tests、typecheck、lint、format、build 通過。13 個原有檔案另做 Prettier 換行正規化，word diff 無實質改動。`frontend_delivery_research` 獨立 review 無新 finding，重跑 4 檔／56 tests 通過；尚非 E2E 證據。build 保留 >500 kB chunk 提示，未將其誤列為建置失敗。

依據：[TanStack network mode](https://tanstack.com/query/latest/docs/framework/react/guides/network-mode)、[取消](https://tanstack.com/query/latest/docs/framework/react/guides/query-cancellation)、[QueryClient](https://tanstack.com/query/latest/docs/framework/react/reference/classes/QueryClient)及鎖定 5.104 原碼。

### D1 Memory／Plan 有界讀取

單一 Memory 讀取與來源標頭原先載入全 position，K 個引用反覆搬運 N 個成員；Plan 每輪將有效歷史全部搬出 Python，再以 VALUES 傳回取一筆。重構使用 owner 的指定成員投影、同次來源概覽按 snapshot 批次讀，以及具名跨域 SELECT 組合，不新增快取或 Plan head。

真 PG RED 4 failed；第一輪 GREEN 43 passed。批次概覽另先重現 4 次 member query 超過應有 3 次；最終來源／HTTP／工具／Memory 30 passed、storage 26 passed，17 source mypy 與 28 import boundary checks 通過。`experiment_design_research` 獨立核 scope、sealed、固定來源及 Plan 最新 null／空不回退，無需修正；未重跑相同整套。這證明結果與查詢範圍，未量測大量資料的延遲改善。

研究：[SQLAlchemy 2.1 SELECT／JOIN](https://docs.sqlalchemy.org/en/21/tutorial/data_select.html)、[PostgreSQL 18 LIMIT](https://www.postgresql.org/docs/18/queries-limit.html)。保留資料 owner 的具名公開投影，workflow 不取得私有表寫入權。

### L1 啟動與停止

舊 `run-app` 同步第二次 spawn 失敗或子程序 error 時會跳過先前程序清理；兩個 Node RED 失敗已重現。抽出具體程序生命週期後，共用 finally 收尾、等待 close、清理失敗仍處理其他程序、訊號及超時 force：11 tests 通過。

獨立 review 的有界 probe 另重現：Windows 正式 uv wrapper 被外部終止後，launcher 約 204 ms 返回，但合成 Python 服務仍活著。probe 有 5 秒自退並以自有 PID 回收，沒有殘留；已裝 pnpm 同測沒有留下 Node。修正為短命 uv 完成原有鎖定同步及 interpreter 定位，再直接啟動後端，保留自訂專案環境，不硬編碼 `.venv`。

最終 16 個 launcher 單元反例與 3 個真子程序測試通過，獨立 reviewer 重跑 19／19。真程序涵蓋後端退出、向啟動器注入 SIGTERM／SIGINT 後 Python 與兄弟 Node 程序皆結束；沒有宣稱測到鍵盤 Ctrl+C 的實際 console broadcast、所有任意孫程序或其他作業系統。三個程序測試已加入根 `pnpm test`；整合另與 Docker 組裝契約合跑 25／25。

[Node child process](https://r2.nodejs.org/docs/latest-v24.x/api/child_process.html)、[Windows taskkill](https://learn.microsoft.com/en-us/windows-server/administration/windows-commands/taskkill)支持本次已持有 PID 的清理方式；[Execa termination](https://github.com/sindresorhus/execa/blob/main/docs/termination.md#killing-descendant-processes)也明示 Windows wrapper 退出後的限制，因此未僅為換套件增加依賴。

### E1 明示候選與正式 App 組裝

新增不可變 ConsultantConfiguration、AppComposition，正式 runner／SDK／checkpointer 接線可明示替換。新比較入口使用相同 App／HTTP，產生有效配置、原始診斷及正式成品；不 import 歷史 runner 或修改 module-global。既有 JD 讀取容量可作實際回傳變因，於原始捕捉後固定；舊 snapshot 缺值沿既有預設。

實作者回報 83 focused unit、30 PG 恢復／並行、13 診斷／比較 PG 通過；兩個候選零付費 CLI smoke 各 2 個模型 Step、1 個正式工具，實際保存職稱。第一版診斷漏 cap channel，已補反例與第二版 smoke，原第一版保留。真 provider 入口是要求已授權 guard factory 的程式化範例，CLI 目前只 dry-run／scripted，未搬遷歷史整批費用 guard。

獨立審查另重現 mutable DTO 在 manifest 與 await 後組裝之間被改，導致記錄 A、實際 B。四個 Red 分別覆蓋 live 首次等待、manifest 後改動、scripted 改動及 CLI 重讀規格導致 hash 漂移；修正為一次固定整批候選、解析與 hash 使用同份 bytes。17 單元及 2 真 PG 測試通過；原 reviewer 獨立重跑 17 tests、靜態複核無剩餘 finding。

第二版 CLI smoke [原件封存](full-system-review-2026-10-08-e1-smoke.zip)包含 manifest、兩個候選 result／runtime 及其受測 source.zip；整包 SHA256 為 `911a15edd24ca4a04f8ee0150ce68ecccee25a96cd85420b464201883cfdb214`。它支持兩組正式流程與診斷的合成實跑，不包含後加的 DTO 變動反例或 D2；這些沿各自測試判讀。

### 圖面與文件

依 [C4 notation](https://c4model.com/diagrams/notation)及 [Mermaid 圖種文件](https://mermaid.js.org/intro/)區分元件、活動、資料流、時序、狀態及 ER 語意；中央規範只在架構設計取捨維護。獨立 reviewer 對照實際 key／FK／nullability，核了 JD、Memory、訪談及執行的 20 張保存圖，修正其中 19 張的線型、判斷節點或先後語意；其他總圖另核責任、協定及依賴方向。

九份主文件的 29 張 Mermaid 均已渲染並逐張視覺核對。報告 04、07 修正多工具迴圈及 Memory 固定選用；10、11 移除手抄 `.mmd`，直接由正式 JD 保存文件生成。四組報告 SVG／PNG 重新渲染，獨立視覺審查先發現數字開頭 render ID 使 CSS 失效，修正為合法 identifier 後主代理逐張確認箭線、中文及關係表完整。SVG 經 XML 解析與獨立圖片載入，PNG 為兩倍解析度；產圖方式寫入原圖稿 README，不加產品依賴。

### D2 JD 完整操作由領域一次保存

四類模型編輯原先由 workflow 多次呼叫局部寫入、複製選用集合，再用前後 ID 集合差猜新物件。新增具名 compound commands／results，由 JD feature 計算完整內容與依據後至多寫一個修訂；workflow 保留跨域資格、固定來源解析與外層短交易。migration 0028 在既有 `jd_operations` 增加必要結果 payload，沒有第二份操作台帳。代表任務操作由 5 個中間修訂降為 1 個，另一含能力案例由 6 個降為 1 個；未量測大量資料的整體延遲。

實作者受影響 PG 93 項、純規則 36 項及 checkpoint 4 項通過；測到末段失敗全回滾、真正 COMMIT 後回覆丟失的原結果重放、正式撤回與原來源核對基底。獨立審查另發現舊鏈重放只核 incoming 前綴：原 profile 有兩來源，省略第二組仍回成功及中間修訂，資料數量與 head 雖未變，卻不是原完整意圖。

五個真 PG Red 覆蓋四類命令的尾段省略及 profile no-op 尾段；修正按舊固定衍生名稱與原內容的有限範圍證明完整性，另驗稀疏來源索引及 source-only no-op 改首步。不以時間戳／transaction ID 猜測，不掃全歷史，不補寫殘缺舊鏈。最終 recovery **29 passed，`-W error`**，compound／checkpoint／邊界單元 34 passed；原 reviewer 獨立重驗 14 項 `-W error` 通過，未發現新重要問題。合法原 checkpoint 仍回原結果與新增 ID，異意圖拒絕且不倒退 head。

### 整合測試本身的修正

完整 PG collection 原先因 unit／integration 的同名測試模組相撞而中止。依 [pytest good practices](https://docs.pytest.org/en/stable/explanation/goodpractices.html)切換 `--import-mode=importlib`，不再把各測試目錄插入 import path；既有共用 `tests.*` 匯入仍可使用。獨立 collection 2,572 項無匯入錯誤。reference 恢復測試原先用只供同步呼叫的 Mock 代替 saver；改用空的官方 InMemorySaver，仍驗缺 client 時在 history／model 工作前拒絕，沒有改產品分支。

## 4. 驗證與限制

| 層級 | 本輪整合命令／範圍 | 結果 |
|---|---|---|
| 後端單元／契約 | `uv run --project apps/api --locked pytest apps/api/tests/unit apps/api/tests/contracts -q -p no:cacheprovider` | 1,551 passed，19.29 秒 |
| 完整 PostgreSQL | 同一 uv 入口，`pytest apps/api/tests -m postgres -q -p no:cacheprovider`，明示本次隔離測試資料庫 | 初跑 1,010 passed／7 failed，19 分 2.72 秒；七項修正後連同整份 outbound retry 及三份日誌單元，53／53 通過；D2 最後修改另驗 29／29 |
| 後端靜態／生成 | Ruff check／format、mypy、`generate_contracts.py --check` | D2 最後修正後全數通過；540 檔格式、354 個 source files 型別通過 |
| 前端單元與建置 | 前端 `test`、`typecheck`、`lint`、`format:check`、`build`、`test:proxy` | 50 檔／309 tests 與 4 個 proxy tests 通過，其餘命令退出碼 0 |
| 真瀏覽器旅程 | 真 API／PostgreSQL、同源建置 Web、Playwright Chromium 153.0.8010.12；scripted provider | 最後完整 35／35，1.6 分鐘；鍵盤反例另外重複 3／3 |
| 交付／程序 | `node --test scripts/docker-compose.test.mjs scripts/run-app.test.mjs scripts/run-app.process.test.mjs` | 25／25，包含三個真子程序情境；Compose 缺必要 collection 的錯誤輸出為預期負例 |
| 文件／圖面 | 本輪責任文件相對連結、Mermaid 解析／渲染、圖面視覺檢查 | 最終 27 檔 832 個本機檔案連結皆存在；圖面 33 張通過，`git diff --check` 通過 |

前端 build 仍有既存 >500 kB chunk 提示。sandbox pnpm 無法讀取工作目錄，經工具核准後在標準本機環境執行；該環境錯誤不當產品失敗。

瀏覽器初跑 31／35，其後修正定位過廣、合成 hold 標記混入職稱、失敗測例遺留請求，以及保存尚未結束就讀取／reload 的測試競爭。中途數次 34／35 分別暴露對話框 `aria-hidden` 被誤當刪除完成、鍵盤入口尚 `aria-disabled` 卻已送 Enter；先查 trace，再掃同類入口。七份 E2E 檔改為等待可觀察的保存／可操作狀態，每例只取消自己檔案的工作；保留 exactly-one request、正式資料、reload／PDF 與原文取回斷言，沒有加入 sleep 或修改產品。最終 35／35，收尾 scripted `waiting=0`，自有 8168 後端已停止，資料保留。

PG 整合的四個 SQLAlchemy 未歸還連線 warning 來自 collection 時仍使用舊 `after_commit` 例外注入的 D2 測試。後續已改成真正提交且正常關閉 session 後才模擬回覆丟失；獨立 23 項 `-W error` 通過，舊 run 仍照實保留 warning，不宣稱原整批無警告。

七個 Log 失敗全部位於 `test_outbound_retry.py` 的四處舊 `getMessage()` 字串斷言；實際事件已改為固定名稱及 `extra` 欄位。測試改為解析正式 `SafeJsonFormatter` 輸出，核對 event、level、HTTP 狀態、provider code、request／attempt／execution ID、null 與正文不洩漏，原重試／預算／不明結果斷言保留。相應 53 項於 20.62 秒通過；這是有界重驗，沒有把原全套結果改寫成一次全綠。

本輪已確認問題均完成相應修正與重驗。未執行付費模型、資料清除或部署切換；工程通過不代表 JD 品質已全面達標。真 provider CLI、通用工具插件、外送觀測平台、正式容量／效能量測及跨作業系統驗證並未實作或宣稱完成；目前的可替換接縫與本機查閱足以支持下一次有限對照。

收尾只停止已核對 PID／命令的自有 E2E 後端，以及任務標籤吻合的專用 PostgreSQL 容器；容器與合成資料保留，其他既有服務不動。沒有 commit、push、merge 或改用本輪隔離資料取代原資料庫。正式環境採用新程式時仍沿 runbook 明確 migration／重啟。
