# JD 隔離 API 宿主：官方接點前置核實

- 查閱日：2026-09-13；Topic：JD-R002／RS-F、RS-1–2；性質：有界官方研究與接線建議。
- 本稿記錄施工前的有界研究，未自行建立宿主或測試。後續[查詢 API／恢復身分結果](../2026-09-13-jd-query-api-and-recovery-identity-slice.md)已核實依賴與原生接點，包含真 PG／Uvicorn；本稿的寫入、停止／重開及來源測試清單仍是後續責任，不能把查詢 PASS 延伸成完整 host。
- 基線：[目前決策](../../current-decisions.md)、[決策流程](../../decision-process.md)、[框架方向 §4–5](../2026-09-13-jd-app-stack-selection.md#4-後端選擇)、[錯誤與紀錄證據](2026-09-13-jd-app-boundaries-errors-logging-evidence.md)、[保存契約 §6／9](../2026-09-12-jd-relational-schema-and-write-contract.md#6-寫入交易)。
- 不重選品牌，不變更六章欄位、十三表、來源／Memory、永久 receipt 或 writer authority；不增加登入／ACL、通用 server、背景 DB writer 或 production 入口。

## 1. 可採方案與效力

沿已選 FastAPI 方向，用生成的 Pydantic DTO 接 HTTP，將已存在的同步 SQLAlchemy／Psycopg service 作一次完整呼叫。宿主負責生命週期、傳輸限制、安全錯誤出口及既有 owner 的接合；正文、operation、snapshot 與 receipt 仍由原共同 service 決定。

精確驗證候選為 **FastAPI 0.141.1＋Starlette 1.6.0＋Uvicorn 0.52.4**。版本 metadata 與現有 Python 3.12／Pydantic 2.13.5 沒有已見相依衝突；不能由此宣稱整組 runtime 已驗證。研究結束時，主代理已把三項寫入隔離 [pyproject](../../../experiments/jd-relational-app/pyproject.toml)／[lock](../../../experiments/jd-relational-app/uv.lock)；本研究未自行安裝或核驗宿主啟動。

三項立即影響施工的發現：

1. Starlette 有原生 request body limiter；FastAPI 的同名 constructor 額外參數不會自動啟用它，且原生超限出口未全部使用本案 problem JSON。
2. async 取消或 HTTP 斷線不能證明同步 DB worker 停止；原 operation 的身分與未確認狀態必須保留。
3. 自訂安全 500 回應仍可能讓 Starlette 重拋原 exception 給 Uvicorn；回應安全與實際紀錄安全須一起驗。

## 2. 官方版本、授權與相容性依據

所有官方頁面均於 2026-09-13 查閱。以下「正式發布」指有正式版號的發行，不是 LTS 或整組穩定性保證。

| 元件 | 官方發行／授權 | 與本案直接相關的發布 metadata |
|---|---|---|
| FastAPI 0.141.1 | [發布紀錄](https://fastapi.tiangolo.com/release-notes/)：2026-07-29；[該 tag metadata](https://raw.githubusercontent.com/fastapi/fastapi/0.141.1/pyproject.toml)：MIT | Python ≥3.10；Starlette ≥0.46.0、Pydantic ≥2.9.0，這個 tag 未設兩者上限。development classifier 為 Beta；[版本政策](https://fastapi.tiangolo.com/deployment/versions/)要求鎖版並測試升級，不能假稱多年 LTS。 |
| Starlette 1.6.0 | [發布紀錄](https://starlette.dev/release-notes/)：2026-08-08；[該 tag metadata](https://raw.githubusercontent.com/Kludex/starlette/1.6.0/pyproject.toml)：BSD-3-Clause | Python ≥3.10；AnyIO ≥3.6.2、<5。development classifier 仍為 Alpha；不得因版號為 1.x 改寫該標示。1.6.0 加入 app／route 的 `max_body_size`。 |
| Uvicorn 0.52.4 | [發布紀錄](https://uvicorn.dev/release-notes/)：2026-08-18；[該 tag metadata](https://raw.githubusercontent.com/encode/uvicorn/0.52.4/pyproject.toml)：BSD-3-Clause | Python ≥3.10；核心使用 Click、h11，development classifier 為 Beta。lock 中套件上傳 UTC 日為 2026-08-19，與 release note 日分開記。0.52.0 新增的 zttp backend 明列 experimental，本案不需採用。 |

保留已鎖 SQLAlchemy 2.0.52、Psycopg 3.3.5、Pydantic 2.13.5 與 Python 3.12 線；資料層能力／授權沿[DB 前置](2026-09-13-jd-relational-db-preflight.md)。FastAPI／Uvicorn 基本套件已提供所需接點，無必要直接安裝整個 `[standard]` extra；其額外 CLI、表單／模板、檔案監看、可選 event loop 等不是本案必要功能。Windows 可明示 `loop=asyncio`、`http=h11`，精確組合在 §5 核驗。

上表以官方 tag 原碼及發布紀錄為依據。研究中的 PowerShell 公開 PyPI 查詢曾連線失敗，沒有把空輸出當成版本結果；未因此讀取私人 registry 或任何認證資料。

## 3. 必要宿主接點

### H-01：lifespan 只組裝與關閉資源，不接管保存

**官方事實：**FastAPI 建議 `lifespan` context manager，舊 startup／shutdown events 是替代路線，不應混用。Starlette 在 lifespan 啟動完成前不提供請求；測試須以 `TestClient` context manager 進出 lifespan。[FastAPI lifespan](https://fastapi.tiangolo.com/advanced/events/)、[Starlette lifespan](https://starlette.dev/lifespan/)

**本案映射：**使用可注入設定／資源的 app factory，在 lifespan 建立 process-scoped Engine、既有讀取與保存 service、refs 所需已核資料集／key 接點。啟動先核必要設定；migration 仍是明示初始化，不能隨啟動重建表或清資料。關閉先停止新 admission、讓實際 writer owner 完成既定 drain／恢復責任，再釋放 Engine；不能把執行到 lifespan teardown 本身當成 stopped proof。引用 key／dataset 的持久化仍由既定宿主設計提供，本稿不另生一份 authority。

### H-02：同步交易留在同一 worker 呼叫

**官方事實：**FastAPI 的一般 `def` endpoint 由外部 thread pool 執行；在 `async def` 直接呼叫一般同步 helper 不會自動移出 event loop。Starlette 使用 AnyIO thread pool，預設 40 個 tokens 由同步 endpoints／dependencies 等共用。SQLAlchemy `Connection` 不保證 thread safety。[FastAPI async](https://fastapi.tiangolo.com/async/)、[Starlette thread pool](https://starlette.dev/threadpool/)、[SQLAlchemy Connection](https://docs.sqlalchemy.org/en/20/core/connections.html#sqlalchemy.engine.Connection)

**本案映射：**完成 HTTP body／DTO 驗證後，以同步 endpoint 或單一 awaited `anyio.to_thread.run_sync` 呼叫共同 service；整個取得連線、交易、commit／rollback、關閉連線留在該呼叫內。共享 Engine，不把 request dependency 產出的 Connection／transaction 跨執行緒傳遞，也不在 response 送出後才由 dependency cleanup commit。模型／來源 I/O 留在短 SQL transaction 外；不另建 BackgroundTasks DB writer。是否需要調整 thread tokens 由有限併發測試決定，先不為單人 App 放大預設。

### H-03：取消等待與停止 writer 是兩件事

**官方事實：**AnyIO 預設遮蔽等待 worker 時的取消；若開 `abandon_on_cancel=True`，等待者可取消，但 worker 仍會繼續，其結果被忽略。Python 無法由這個 API 強制中止已執行的 thread。Uvicorn 的 graceful shutdown timeout 是伺服器停止等待的控制，不是 DB 提交／回滾證明。[AnyIO worker threads](https://anyio.readthedocs.io/en/stable/threads.html)、[Uvicorn settings](https://uvicorn.dev/settings/)

**本案映射：**HTTP disconnect、task cancel、SSE 結束或宿主逾時均不能自行解綁、重送 command、產生 `writer_stopped=True`，也不能回報已回滾。已綁定者保留原 operation／digest／descriptor；按真 writer owner 的完成或可信退出證據及[保存契約 §6.2](../2026-09-12-jd-relational-schema-and-write-contract.md#62-人工或-ai-保存)查原 receipt。無已確認 terminal 就沿原 identity 對帳；只有 stopped proof 加上正確 DB barrier／下一 statement 查無結果，才可進 failure-only closure。AnyIO shielding 本身不取代 owner 證明，OS 強停也須走恢復路線。

### H-04：生成 DTO 與安全 exception 出口

**官方事實：**FastAPI 預設 `RequestValidationError` handler 回 `exc.errors()`；該 exception 也可持有原 body。官方示範如何 override，但 debug 回應／例外字串可包含內部資訊。[FastAPI errors](https://fastapi.tiangolo.com/tutorial/handling-errors/)、[0.141.1 handlers 原碼](https://raw.githubusercontent.com/fastapi/fastapi/0.141.1/fastapi/exception_handlers.py)

**本案映射：**HTTP 輸入與公開輸出沿 JSON Schema SSOT 生成 DTO；宿主不手寫另一份 command／result model。解析／DTO 不合先回具名、安全的 HTTP 邊界結果；不能把 `exc.errors()`、`exc.body`、`str(exc)`、不可信 ref、SQL driver 訊息或 exception cause 直接放入 response／logs。保持 `debug=False`。已知 domain／storage failure 沿現有結果 mapper；未確認操作維持原 reconcile 指令；成功查回原失敗 receipt 仍是本次查詢成功，不能再改成寫入失敗狀態。

**必要補充：**Starlette 的 `ServerErrorMiddleware` 在呼叫 custom 500 handler 後仍重拋原 exception，讓 server 可記錄。因此僅換 JSON handler 不能證明紀錄安全。小型宿主邊界應將已分類錯誤映成安全結果，未預期故障以固定安全 metadata 紀錄；實際 Uvicorn error handler 也不得輸出 raw traceback／cause／locals。沿既有標準 logging 配置處理，不另造 logger 平台。[Starlette 1.6.0 errors 原碼](https://raw.githubusercontent.com/Kludex/starlette/1.6.0/starlette/middleware/errors.py)

送出回應或 response DTO projection 失敗不能改寫已提交的原 receipt。前端仍可依原 operation 查回；不能為湊一個 500 而生成新的 mutation terminal。若直接回 `Response`，須在既有 mapper 完成正式 DTO 驗證，不能假定 FastAPI 會再驗回應。[FastAPI direct response](https://fastapi.tiangolo.com/advanced/response-directly/)

### H-05：使用原生 body limit，但驗明接入位置與出口

**官方事實：**Starlette 1.6.0 的 `RequestBodyLimitMiddleware(app, max_body_size=...)` 在讀取時檢查 Content-Length，並累加實際收到的 body bytes；超過上限會產生 413。它部分出口直接使用純文字 413。[官方 body limiter 原碼](https://raw.githubusercontent.com/Kludex/starlette/1.6.0/starlette/middleware/body_limit.py)

**相容性差異：**FastAPI 0.141.1 未宣告 `max_body_size`；`**extra` 只保存、不使用，且 FastAPI 自建 middleware stack。因此不能只寫 `FastAPI(max_body_size=...)` 便宣稱 body 有界；要透過 FastAPI 的 middleware 接點明示掛上官方 limiter。[FastAPI applications 原碼](https://raw.githubusercontent.com/fastapi/fastapi/0.141.1/fastapi/applications.py)、[Starlette applications 原碼](https://raw.githubusercontent.com/Kludex/starlette/1.6.0/starlette/applications.py)

**本案映射：**先用原生 limiter，不另寫通用 chunk 計數器。host 上限要容納正式 envelope 與既有 command 的 1 MiB 界線；依 envelope 的有限欄位決定總上限，不能誤把 1 MiB 的合法 arguments 加 envelope 後拒絕。command／read 既有細限仍由原 parser 維護；HTTP 不重算 JD 商業規則。JSON request 必須完整解析與驗證後才 binding／寫入。驗正常 Content-Length、缺少／不實長度及分塊超限；確認實際 413 是否經預期 problem projection，必要時只補固定出口轉換。

Uvicorn 的 `h11-max-incomplete-event-size` 只限制未完成 parser event buffer，不是總 JSON body 限制；form 的 `max_part_size` 也不能替代 JSON 上限。未提供 request 解壓縮時不新增壓縮 body 支援；不得因 wire bytes 有界就宣稱任意解壓內容也有界。[Uvicorn settings](https://uvicorn.dev/settings/)、[Starlette requests](https://starlette.dev/requests/)

### H-06：loopback、Host／Origin 與 JSON admission

**官方事實：**FastAPI 的 `strict_content_type=True` 為預設；官方明示無登入的本機 JSON API 若寬鬆接受缺 Content-Type 請求，會讓惡意網頁有直接呼叫的機會。保留此預設。[FastAPI strict Content-Type](https://fastapi.tiangolo.com/advanced/strict-content-type/)

Starlette CORS middleware 會處理 preflight，但非 preflight 的 simple request 仍呼叫下游，只在回應決定是否附允許來源的 header；CORS 不是一般寫入 admission。TrustedHostMiddleware 可限制 Host header。[Starlette CORS 原碼](https://raw.githubusercontent.com/Kludex/starlette/1.6.0/starlette/middleware/cors.py)、[Starlette middleware](https://starlette.dev/middleware/)

**本案映射：**本機 Uvicorn 明示 loopback、單 worker、reload 關閉；直接本機連線不信任 forwarded headers。Web 跨 port 直連 API 時，以精確 scheme／host／port 設 CORS；mutating browser request 在 binding 前另核配置的 Origin，拒絕 foreign／null Origin。保留 strict JSON Content-Type，Host 沿原生 allowlist；不用萬用 CORS／Host。無 Origin 的合法本機 client 路徑須由實際 Web 接法明示：第一個純 browser 宿主可要求 Origin，內部工具直接呼叫 application；若採 Next BFF，另核受信的同機轉送邊界，不靠放寬全部缺 Origin 請求解決。這是避免任意網頁呼叫本機服務的傳輸限制，不是新增登入／ACL，也不使可偽造的 header 成為 writer proof。[Uvicorn settings](https://uvicorn.dev/settings/)

## 4. 已知與尚未證明

| 問題 | 本輪可確認 | 仍須局部驗證 |
|---|---|---|
| 發布與相依 | 官方精確 tags、Python 要求與相依範圍可支持這組候選；主代理已落 lock | 安裝／import、完整 lock 與既有 generated DTO、TestClient／httpx2 的實際相容性 |
| transaction owner | 保存契約要求同步短交易與原 operation 對帳；HTTP 不能取得 writer authority | 真宿主的 admission／正常完成／斷線／退出／恢復接合，不能由框架文件推定完成 |
| body 防護 | 官方 limiter 可用，FastAPI 需明示掛入 | 所選 envelope 總上限、middleware 順序、所有超限出口及 JSON parser 交互 |
| 本機請求 | 原生 CORS／TrustedHost、strict Content-Type 能提供部分原件 | Web 直連或 BFF 的精確 Origin 接法與真瀏覽器反例；目前不增加兩套平行入口 |
| 錯誤資料 | default validation／server re-raise 的確存在 | 實際 response、Uvicorn handler、stderr／log rotation 全路徑的合成資料不外露 |
| 功能範圍 | 原共同 service／typed refs／SSOT 沿既有切片 | 此研究沒有實作 source owner、selection issuer、notice baseline、restore、顧問或 Web 畫面 |

## 5. 有限驗證與停止研究條件

以下是相依施工的驗收清單，**不是本輪通過紀錄**；先建立有明確標記的合成反例，再跑受影響測試，不呼叫 provider。

1. **精確組合／lifespan：**沿隔離 lock 安裝，核套件 metadata／生成 DTO import；以 TestClient context manager 驗成功啟動、設定不合停止服務、一次初始化／一次釋放。不自動 migration。
2. **HTTP／SSOT：**所有具名 endpoint 的合法／非法 fixture 經真 ASGI routing；確認 nullable、closed objects、refs 長度、錯誤 code、HTTP status 與原結果一致，無框架預設 validation input 外露。
3. **body 界線：**接近既有 command 最大容量的合法完整 envelope 可用；Content-Length 超限、缺長度的分塊超限、錯 JSON 分別拒絕；確認 binding／DB writer 未呼叫與回應不洩資料。用實際 native limiter，不僅單測常數。
4. **本機 browser 邊界：**合成正確／錯誤／null／缺 Origin、錯 Host、缺／錯 Content-Type、preflight 與非 preflight 直接 POST；所有不允許的寫入在 admission 前被拒絕。此處的純 ASGI 測試不能替代後續真 browser 反例。
5. **同步 worker：**阻塞一個測試 DB transaction 時，獨立唯讀請求仍能處理；核 Connection 在同一完整 service 呼叫內取得與關閉，無跨 thread transaction、response 後 commit 或背景 writer。
6. **真斷線／取消：**真本機 HTTP socket 斷線或取消等待時讓同步 worker 繼續，觀察原 operation 最後結果；不可因此產生 stopped proof、第二次 command 或 known-none。普通 ASGI client 的取消不能代稱 OS／socket 證據。
7. **交易與回覆分離：**真測試 PG 先 commit 再注入回覆遺失／輸出驗證故障，查回原 receipt；原失敗 receipt 的成功查回仍按查詢語意回應，未確認寫入保持 reconcile。
8. **退出／重開：**單一自有程序正常 drain 與強制退出分開驗；新程序沿原 identity 與可信 stopped proof＋DB barrier 對帳，未取得 proof 時保持未閉合。不能只驗 shutdown callback 有跑。
9. **實際紀錄隱私與故障：**在 JSON、DTO、domain、driver／unexpected exception 各注入不同合成 sentinel；捕捉真 handler／stderr／response，均無 raw body／ref／cause；壞 logging sink 不改原 terminal，也不輸出第二次不安全 traceback。

上述接點已有直接官方依據；其餘不確定性是有限組合與行為測試，沒有必要再比較同層 API 框架或建立通用宿主引擎。完成相依驗證後才把版本組合／宿主接線列為實作結果；production authority 仍須沿有效 ADR／G6。
