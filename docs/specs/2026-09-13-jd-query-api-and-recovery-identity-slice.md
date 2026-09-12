# JD：查詢 API、確切差異與可恢復操作身分

- 日期：2026-09-13；JD-R002，RS-1／2→RS-3 的隔離接合。
- 承接[同版讀取切片](2026-09-13-jd-read-change-implementation.md)與[新版計畫](../plans/2026-09-13-jd-relational-app-implementation.md)。本單位隔離施工、實測與獨立審查完成；整體 App／G4／G6 尚未完成。
- 框架維持工程選擇；沒有變更六章、關聯式正文、十三表、原話／Memory 責任、Excel 延後或 G6。沒有付費產品模型呼叫。

## 1. 本單位要交付的效果

1. 將同版 `jd_read` 與原操作 `jd_change_read` 接為實際 HTTP 查詢，供管理畫面取得資料；人與模型仍讀同一套服務材料。
2. 差異完整保留前後欄位、結構、來源變動與受影響任務；變更多時可續讀，不把一整個大型事件當不可分頁單位。
3. 真正的唯讀資料庫服務不需要注入假 writer。恢復已發配操作時，不應被迫重建過時 refs、來源或 `CommandContext`；只用已持久化身分核對原結果，未發布時只閉合失敗。

這不是完整手動 App；本輪不註冊 mutation HTTP。已有八操作及真保存不因此被刪除，實際 writer／持久 runtime owner 接好後即承接寫入。唯讀 API、取消 HTTP request、PG session 結束都不是 writer stopped proof。

## 2. 邊界與框架責任

| 範圍 | 接法與限制 |
|---|---|
| HTTP／生命週期 | FastAPI 原生路由、generated DTO、同步 endpoint threadpool、lifespan。宿主提供資源，API 不讀環境金鑰、不自動 migration、不建 writer。 |
| 有界輸入 | 明示掛 Starlette `RequestBodyLimitMiddleware`，16 KiB 為兩個查詢參數的本案上限，不是 JD 正文字數上限；查 Content-Length 及累計 chunks。FastAPI 0.141.1 的 constructor 不會將 `max_body_size` 傳给 Starlette，不能只填一個無效選項。 |
| 本機 HTTP | 保持 `strict_content_type=True`；原生 TrustedHost 只接受 127.0.0.1／localhost，CORS 只用宿主明列 origin。CORS 只管瀏覽器讀取，不是寫入 admission／ACL。正式 BFF／寫入 Origin 檢查另按接合閉合。 |
| 錯誤／診斷 | 讀取業務錯誤用獨立 RFC 9457 `QueryProblem`，包含既有 `ReadFailure`，沒有 mutation receipt／durability。驗證失敗不輸出 body／errors()/ctx。純 ASGI 窄邊界記 request ID、固定 route、status、耗時，不記正文、refs、query 或 raw exception；diagnostic sink 壞掉不遮蓋結果。 |
| 原生傳輸拒絕 | Host／body limiter 的 400／413 保留框架簡短錯誤，不假裝是 JD 保存結果。測所有內容不含原輸入；查詢回應統一 no-store／request ID。 |
| OpenAPI | request／response schema 仍由生成 DTO 推得；以 FastAPI 公開 OpenAPI hook 將四個業務失敗的已生成 media entry 移到 application/problem+json，不手寫另一套正文 schema。 |

FastAPI 的安全 500 handler 不足以保證 server log 安全：Starlette 的 `ServerErrorMiddleware` 會在回應後重拋原 exception。本案的查詢邊界在送出回應前將未知故障轉成固定讀取失敗，消耗原例外；已送出後的傳輸故障只拋固定不含原因的中斷錯誤，不能再送第二份回應。

獨立審查另外發現 lifespan 啟動／關閉原 cause 仍會進 server traceback，已修正為固定 `jd_query_startup_failed`／`jd_query_shutdown_failed` 並保留原生 `async with` 清理。非 `Exception` 取消照原生語意傳遞；沒有以所有錯誤皆吞掉的方式隱藏宿主啟動失敗。

## 3. 差異讀取的精確契約

模型只填 `change_ref`、`cursor`。由原 operation 取 base/result，不回查目前 head 推定原結果。只有 committed 有可發配 change ref；no_change／失敗不偽造差異。

公開輸出沿 read SSOT 生成 `ChangeReadInput`／`ChangeReadPage`：原 operation、change、base/result refs、origin，及有界 flat records。每個淨變更有 `change_index`；header、前後完整 field／結構、來源 metadata、排序上下文及受影響任務可跨頁，單一允許欄位仍完整交付。所有舊稿 refs 都保持只讀，不能因 result 等於 head 升成可寫。

重用既有六章欄位／來源投影及固定 byte packing，不另建通用 diff 引擎。原 source basis digest／position 在 change 專用記錄中保留，與來源是否可回讀分開；UI 可選擇不預設展示技術 metadata，但不能抹去實際改動。排序前後鄰居只說明兩版順序，不宣稱是使用者當時拖動的動作。

## 4. 恢復身分與真正 writer 的未完接點

原 `reconcile_stopped` 要完整 `BoundEdit`，且新增失敗回執讀 command tool；跨重啟若只保存必要操作 descriptor，便會被迫重建 command/context。現已抽出嚴格、固定 `AdmittedIdentity`，只含文件／原 operation／base／digest／origin／run／command kind；由原 BoundEdit 發配，不重算意圖。停止後的 failure-only closure 使用該身分，不執行原 command，也不回讀來源。真回執仍優先，身分不符拒絕；完整 stopped proof 仍來自實際 owner，不能由外部 boolean 代填。

後續持久 runtime 必須在 JD SQL 前保存 admitted descriptor；AI 綁原 tool call，人工不假裝成對話。正式採用同一 Saver／所選 runtime 的持久 API，不新增平行 run/binding 表。不同文件用各自的 gate；同一文件在未解操作或 writer 還能執行時不開新 writer。

舊 runtime 的 `q019_document`／RunRow FK 與新 `jd_document` 不可雙寫。要接新文件 owner 及同一 thread identity，不照搬舊 catalog；新純 Python JD 也不需要舊 Plate／Node transform 的程序義務。跨 App 重啟仍需 OS 層確認舊 App 組終止，再跨 PG 原寫入邊界查回全部 descriptor。這部分未完成，不能用本輪唯讀 server 新程序測試代替。

## 5. 有界官方依據

查閱日 2026-09-13；精確版本、授權與相容性依[宿主前置](evidence/2026-09-13-jd-http-host-preflight.md)。本輪新增 FastAPI 0.141.1（MIT）、Starlette 1.6.0／Uvicorn 0.52.4（BSD-3-Clause），沿既有 Python 3.12.13、Pydantic 2.13.5、SQLAlchemy 2.0.52、Psycopg 3.3.5；不升級無關依賴。

- [FastAPI error handlers](https://fastapi.tiangolo.com/tutorial/handling-errors/)、[OpenAPI extension](https://fastapi.tiangolo.com/how-to/extending-openapi/)及[additional responses](https://fastapi.tiangolo.com/advanced/additional-responses/)支持明示 handler、生成式契約及有限媒體型別接合；不保證本案所有 middleware 自動輸出同一 shape。
- [LangGraph checkpointers](https://docs.langchain.com/oss/python/langgraph/checkpointers)的 sync durability／update_state 提供持久接點；replay 可能重跑外部操作，不是本案未知 JD 寫入的重試權限。實際 runtime 組合尚待接合。
- [Python Future](https://docs.python.org/3.12/library/concurrent.futures.html)、[asyncio task](https://docs.python.org/3.12/library/asyncio-task.html)及[PG18 locks](https://www.postgresql.org/docs/18/explicit-locking.html)限制停止推論：等待超時、Future.cancel 失敗、session lock 释放都不等於原 worker 已退出。
- [OpenAI function calling](https://developers.openai.com/api/docs/guides/function-calling)與[Anthropic tool use](https://platform.claude.com/docs/en/agents-and-tools/tool-use/overview)提供模型提出工具／App 真正執行及回真實結果的契約；兩家未規定本案 schema、表數、signer 或 writer owner。這些細節是本案需求映射，不標成跨廠統一實作。

已有依據與可重現反例後停止同層品牌廣搜；以固定 ASGI、真 PG、真 Uvicorn 新程序分層驗證，零付費模型。完整 browser CRUD、自然訪談及員工驗收仍依成品計畫。

## 6. 實測結果與首敗

| 證據 | 最後結果與範圍 |
|---|---|
| 整體離線 | `pytest -q -p no:cacheprovider`：**871 PASS／89 真 PG SKIP**。合成正文、原版差異、typed refs、八操作、生成契約、SDK 程序內序列化、錯誤與新查詢 ASGI；不需要模型金鑰。 |
| 真資料庫接合 | 同一指令執行 `test_storage_service.py`、`test_query_postgres.py`、`test_read_storage_integration.py`、`test_storage_history.py`：**69 PASS**，其中 13 個離線歷史反例、56 個真 PG 案例；56.06 秒。含原 identity 新程序查回、原回執逐值不變／未執行只記失敗、完整六章查詢與原操作差異。 |
| 真 HTTP 新程序 | 上列 `test_query_postgres.py` 五案例包含真 Uvicorn loopback。查 current／history／change、保留原 producer、全部十三表該文件值與筆數不變；SQL 限 SELECT／SET／SHOW。自己的 stdin STOP 關閉且 exit 0，保存 launcher/server/parent PID；不是產品宿主或 writer 停止證明。 |
| 差異專項與 SDK | `test_change_reads.py`、`test_change_transport.py`、既有兩個 read 測試檔：**88 PASS**；兩家 SDK 的成功／讀取失敗共四例、八次 POST 全由 MockTransport 攔截，不是 provider／自然模型驗收。 |
| Query API 修正 | `test_query_api.py`＋`test_query_http.py`：**34 PASS**。原生 routing／OpenAPI／limiter、固定錯誤、CORS、同步 reader thread、清理／隱私／壞診斷 sink。已包含在整體離線，不另累加。 |
| 生成與型別 | 六份 JSON Schema 的十二個 Python／TS 生成檔 `--check` 通過，TypeScript 通過；既有八份非 read 生成物未變。 |

真 PG 固定使用本機 55436 的專用 PostgreSQL 18.6／合成資料；沒有 migration、清資料、正式 DB 或 provider 請求。重現指令見 [README](../../experiments/jd-relational-app/README.md)。Starlette 1.6.0 TestClient 的 `anyio.abc.BlockingPortal` alias 有一個第三方 DeprecationWarning；未改 vendor 或將它靜默隱藏。

保留首敗及修正：

- Change/API/recovery 新測試先因缺 module／identity／reader 失敗；補實作後通過。差異測試曾誤認 escaped lone surrogate 可通過 DTO，實際安全拒絕，改正測試預期。
- 真 HTTP 測試首次猜錯 `storage.reader` 模組位置，改為實際 `storage.service.JdReader`。pytest mode-0700 temp factory 在本機權限失敗，測試改用 repo 下唯一目錄保存程序證據；沒有放寬產品權限或刪除未知目錄。
- Windows venv launcher PID 與 Python server PID 不同，首個 server 測試過嚴斷言失敗；修正為父子身分核對、STOP／EOF 清理後通過。只處理本測試持有的程序，不按端口 kill。
- Query lifespan 私因外洩由獨立合成反例證實；兩階段修正、6 項窄測及原反例複測均通過。

投影重複發配相同 ref 的反例先紅（兩次簽發）後綠（一次）。只用單次投影內 cache，沒有跨請求或跨文件 retention。固定 62 任務／64 KiB 欄位案例有 733 records：同頁簽發數 1163→427，32 KiB 首頁三次約 0.146–0.175 秒→0.077–0.111 秒；4 KiB 受局部負載沒有一致改善，不能宣稱所有頁面都加速。這只是局部 CPU 量測，不是整體員工等待時間門檻。

## 7. 獨立審查與下一施工

- 查詢 API 審查：原生媒體／DTO、threadpool、敏感例外、CORS／limiter順序；lifespan finding 已關閉。額外 ASGI chunks／response-start 反例通過。
- 差異審查：原 operation material、唯讀 cursor／refs、完整欄位與來源 basis、排序鄰项、實際序列化 bytes。另六個記憶體反例共 25 頁／69 records，20 個歷史 field 寫入皆拒；無阻擋 finding。
- 主代理核實身分／資料讀寫差異與上述整體測試；審查及不同證據種類不合併成「完整 App 通過」。
- 文件交叉審查抓到保存契約 §9 及計畫頁首仍把公開差異／所有 HTTP 列為未完成；已同步為查詢已驗、寫入／完整 App 未完，沒有擴大驗收宣稱。

**唯一下一工作：**接一套實際持久 runtime 的 admitted descriptor／per-document owner、真 writer 完成／停止與重開恢復，再開共同編輯 HTTP 與六章管理畫面。沿已研究的顧問／Memory 能力與責任選原生接点，不 import 舊研究模組、不雙寫文件 catalog、不以 fake authority 暫代真接線。

尚需來源 owner／選區、人工改動通知、autosave、還原／整輪 JD 撤回、日常設定與啟停，及後續真模型／員工驗收。沒有因框架選定而改掉 CRUD 產品目的；Excel 仍延後，production authority 不變。
