# 關聯式 JD：隔離編輯核心

**目前狀態（2026-09-14）：**C 的 App 接合／停止收尾／新程序查回已完成；source 與 B1 核心／OpenAI adapter 固定接合。[H4 runtime執行計畫](../../docs/plans/2026-09-14-jd-h4-runtime-integration.md) **R1 已完成**：source owner 發固定 target 並切有界批次（[結果](../../docs/specs/evidence/jd-b1-adoption/fixed-target-batch-results.md)），一批 B1 在真 PostgresSaver／PostgresStore 上保存、故障後關閉重建資源續作、重抽與查回（[結果](../../docs/specs/evidence/jd-b1-adoption/r1-postgres-batch-results.md)）。**R2 也已完成**：B2 已採用，B1→B2→publication 兩批有序交接、B2 pending 重建資源續作、發布回覆遺失查回與 C 較晚更正都在真 PG 上驗過（[結果](../../docs/specs/evidence/jd-b1-adoption/r2-consolidation-handover-results.md)）。**R3 進行中**（[結果](../../docs/specs/evidence/jd-b1-adoption/r3-notification-and-background-results.md)）：純通知工具已註冊並有自己的結果分類（不借用 JD operation）；「B2 未發布不得開始下一批」已由 `require_handed_over` 以 publication head 關閉；背景准入列 `jd_memory_admission` 已依 [ADR0076](../../docs/adr/0076-jd-background-admission-record.md) 建立並在真 PG 驗過保存、對帳、重複喚醒、受阻與封存。**宿主生命週期、有界背景 worker 與真新 Windows 程序恢復尚未做；顧問指引／Skills／BackgroundAvailability 與 JD 編輯器共用 writer 的接合也未做。**日常 AI 未啟用。既有非JD顧問有CT49／50限定真模型成果；新App日常AI未啟用，不等於顧問從未做好。下文早期切片保留當時結果，不能把當時「下一步」當目前待辦。

此目錄承接[新版施工計畫](../../docs/plans/2026-09-13-jd-relational-app-implementation.md)的 RS-1／2、RS-3 第一段及 RS-4 通知／模型保存接點。已驗證八個編輯操作、完整任務建立、相依內容更正、員工／模型共用規則及真實保存；框架選擇可替換，產品效果以既有六章 JD 研究為準。

**最新：[同頁整輪改動](../../docs/specs/2026-09-13-jd-run-change-view-slice.md)承接聊天與原話保護。**整輪保存內容、完整前後對照、刪除原文與目前欄位提示沿同一歷史來源；只讀 GET 使用原生確認的固定範圍，Web 不計算業務差異。實測層级及獨審結果見結果稿；新畫面真瀏覽器互動未驗，先前 Fetch 原因仍 OPEN。未完成事項集中在[收尾清單](../../docs/specs/2026-09-13-jd-app-open-issues.md)；Memory／來源、還原撤回、日常 AI 與自然品質仍未完成，`enable_chat=False` 不因測試而改變。下文各切片較早「下一接 Web」為沿革。

**已有可開啟的[六章手動管理畫面](web/README.md)，透過共用 service／人工 HTTP 保存到獨立 PostgreSQL 的十三表。**已接讀取／差異查詢、人工 writer、原生 PG Saver、Windows 宿主互斥／跨重啟對帳，以及文件建立／列表／更名／封存恢復。`build_candidate` 仍只回保存前候選，`JdStorage` 在完整交易確認後才回已保存結果。[持久配置與一般開啟](../../docs/specs/2026-09-13-jd-managed-configuration-slice.md)已接同一服務；[本次 UI 結果](../../docs/specs/2026-09-13-jd-manual-ui-and-browser-drafts-slice.md)包含自動保存、未完成表單重開及歷史。完整 AI 生命週期、来源回查、歷史還原與圖形啟動器尚未完成。此目錄不啟動模型、不接正式產品或舊實驗模組；原話保留以合成 native messages 驗證，沒有正式訪談／Memory 整合。

**[RS-4 通知與模型保存](../../docs/specs/2026-09-13-jd-consultant-context-slice.md)已用真 SDK／原生 Agent／PG Saver 及固定離線串流接合。**人工改動投影不改原始對話；完整回覆與通知邊界成對保存，缺結束事件不前進，重開只讀不重播。74 項受影響測試通過（含 13 真 PG），獨立審查缺口已修。日常入口仍未啟用 AI；本輪前景回合與工具接合見下段。

**後續[本程序 AI 回合與工具](../../docs/specs/2026-09-13-jd-ai-runtime-and-tools-slice.md)已接共同 owner／JdStorage。**原生 Agent 用 App 注入的身分及真 read 結果編輯；固定 SDK／真 PG 驗 AI→手改→AI、纯訪談不改及保存 ACK 遺失原結果恢復。同 owner 只允許一個 `AiRuntime`；`start` 同原請求回同 handle，App 自動收尾，`wait` 只觀察，`recover` 明示對帳且不重播模型或命令。最後253核心測試及14真PG通過，範圍重疊以結果稿為準。日常入口尚無聊天AI；新宿主AI恢復、Memory／source、選區、聊天HTTP／Web接合仍待完成。

**[新宿主 AI 恢復](../../docs/specs/2026-09-13-jd-ai-restart-recovery-slice.md)已完成。**一般 App 啟動先由同 owner 查原 AI／人工 pending；相同 Agent 結構的檢視模式不開 provider、不重播工具。真新程序／PG四組及既有PG八組通過，最後相關離線293項通過；獨審互斥pending缺口已修。上一段的新宿主待辦由此成果取代；聊天HTTP／Web、Memory／source等仍待完成。

## 結構

**顧問 Memory 讀取已接：**[固定選版／導覽／原話工具](../../docs/specs/2026-09-13-jd-memory-read-integration-slice.md)以正常 `build_consultant_tools()` 提供十個 JD 工具與四個只讀工具。`open_managed_app` 注入同宿主 Memory engine／原生 Store，前景入圖前固定讀取版本，native START／root／child／close 保留選版；中斷只核原结果不重播。原生 ToolRuntime 提供文件與回合身分，模型只填所需路徑／引用及讀取參數。真 SDK／PG 固定回覆與新宿主回歸通過；C／B1B2 寫入、完整顧問指引／日常 AI／自然品質仍待接，以下較早「模型工具未接」以此段及結果稿為準。

**Memory 更正核心已可採用：**[C 六節點與原結果查回](../../docs/specs/2026-09-13-jd-memory-repair-core-slice.md)位於正常 `caliburn_memory` 套件，使用官方 patch／原生 staging／既有 publication；App 的來源 adapter 同步區分可修地址錯誤與服務故障。核心真PG驗兩檔更正、回覆遺失與新連線查回，JD／原話保留。後續已新增`repair_memory`接線；十五工具的WIP與恢復缺口見頁首，不把核心完成等同App全部完成。

**Memory 核心接合：**[獨立套件與結果](../../docs/specs/2026-09-13-jd-memory-core-adoption-slice.md)已驗保存／發布、固定版本讀取、後續修正与真 PG 重開；使用 `packages/consultant-memory` 正常依賴。`memory_sources.py` 只把同一原話 owner 綁到文件；新來源有 `conversation:` 前綴，既有裸 signed v1 原樣可讀。原話及 JD 不雙寫。[宿主 Memory 接合](../../docs/specs/2026-09-13-jd-memory-host-integration-slice.md)已完成一般 host 的獨立Store連線、原生Runtime.store、schema-mapped publication view、明示初始化及登記讀取排空；同設定新程序讀回原話／Memory通過。模型工具與背景整理／即時修補尚未接，不冒稱完整顧問可用。

一般 host 現要求既有 `checkpoint_schema` 的八張表（四Saver＋兩Store＋兩publication）；public 是**十三張 JD 內容表＋一張 runtime 背景准入表（`jd_memory_admission`，[ADR0076](../../docs/adr/0076-jd-background-admission-record.md)）＋Alembic**，內容表本身未增減欄位。原ready實驗資料庫缺Memory時明示拒絕，不自動升級或清資料；新配置只明示初始化fresh DB。本機合成 fixture 的舊host區可由下方專用腳本補齊，不是產品更新流程。

**最新[聊天HTTP與原修改結果](../../docs/specs/2026-09-13-jd-chat-http-slice.md)已接。**`ChatService` 共用 `AiRuntime`／人工write state，原話、實際執行與JD效果分開回報；`chat_history.py`固定原root/source分頁，只公開原話及AI正文。生成契約／TS、完整離線2211 PASS／209 SKIP、三個真PG HTTP情境與獨審通過。`open_managed_app`預設`enable_chat=False`，日常仍不開provider；新run回`ai_unavailable`，保存對話／原結果可查。下一接Web，不宣稱自然AI或完整App完成。

- `contracts/jd-chat-http.schema.json`／`chat_service.py`／`chat_api.py`：原請求送出、原狀態、取消／恢復與已保存對話；原`BoundResult`及人工狀態直接external ref，不增加run／聊天表。所有同步查讀由同owner排空。
- `chat_history.py`：同現有設定key/dataset、不同用途salt的固定native位置；初頁取最新公開文字、頁內正序，cursor 固定同 anchor 向前取較早頁，`anchor_run_id` 是該 snapshot 的 run。私有 token v2 明確拒絕舊 forward token；原生歷史不改寫。輸出頁有界，底層仍讀完整messages。不是另一份對話保存或LLM context壓縮。

**最新[聊天版次准入與原回合查回](../../docs/specs/2026-09-13-jd-chat-admission-and-original-run-slice.md)已接核心。**新 `start` 必填 canonical `expected_revision_id: UUID`，原請求查回優先；`lookup` 可在後續回合後讀原結果，無模型重播。V1原樣讀取恢復、V2保存起始版次；同owner讀取也納關閉排空。完整離線1961 PASS／201 SKIP，真PG4及新程序PG4通過，獨審缺口已修。尚未接聊天HTTP／Web；歷史256祖先位置上限／缺鏈明示待查回，不能當不存在重送。

- `ai_records.py`／`ai_history.py`：原生 tagged union 讀保存格式、有效父鏈原回合查回；不建立另一份對話或操作權威。新增模型上下文壓縮前，須先維持原始對話與原請求身分可查，不能以摘要沒有 ID 推定新請求。

- `ai_runtime.py`／`consultant_tools.py`／`ai_checkpoints.py`：本機前景回合、generated 具名工具、原生固定 root／child 收尾；與人工共用 writer owner，不新增另一組業務規則或資料庫。原始輸入只在 START checkpoint 時仍查原 Saver payload；未保存必須明示，不以缺 run 當停止證據。
- `inspection_model.py`：透過同一 Agent 工廠建立相容檢視結構；model／tool wraps 與原 after_model hook 明確停用執行。只讀 checkpoint，不構造供應商 SDK；不是任意 invoke 無副作用的沙盒。

[回覆遺失驗收](../../docs/specs/2026-09-13-jd-browser-reply-loss-slice.md)已用真瀏覽器／PG確認：提交成功但回覆未到，重開查回原operation後恢復，沒有新POST／重複任務。重現入口是[測試專用說明](tests/support/ui_response_gate_notes.md)，不將回覆閘門加入產品。人工通知與AI回合接點沿[下一步前置](../../docs/specs/evidence/2026-09-13-jd-consultant-context-preflight.md)；仍未啟用模型。

- `web/`：React／Next／MUI 六章管理、IndexedDB 候選及 Web Locks；從正式 Schema／generated 型別接同一 API，不另存正式 JD。

- `contracts/jd-work.schema.json`：八個編輯工具輸入的唯一 JSON Schema。
- `contracts/jd-result.schema.json`／`jd-http.schema.json`：合法結果組合與 HTTP Problem，和輸入一樣使用標準產生器。
- `contracts/jd-snapshot.schema.json`／`snapshots.py`：v3 完整歷史格式、嚴格轉換及 canonical digest；關聯 rows 仍是 current 權威。
- `contracts/jd-read.schema.json`／`reads.py`／`read_transport.py`：生成式讀取契約、六章完整可續讀投影與兩家模型工具外殼；分頁與實際工具輸出共用 UTF-8 序列化。
- `change_reads.py`／`change_transport.py`：共用 read SSOT，將原 operation 的完整前後差異投影為唯讀、可續讀 records；兩家 SDK 離線驗工具與結果外殼。
- `contracts/jd-query-http.schema.json`／`query_http.py`／`query_api.py`：generated 查詢錯誤與 FastAPI 查詢路由；宿主注入資源，原生 lifespan／threadpool／輸入限制，沒有 mutation 路由或假的 writer owner。
- `contracts/jd-manual-http.schema.json`／`manual_service.py`／`manual_api.py`：generated 人工保存／狀態／原操作查回；人工 App 由原 query app 增加四個具名路由，仍使用同一 domain／保存 owner。mandatory configured Origin 在 unsafe POST body／admission 前檢查，回覆遺失不取消 writer。
- `contracts/jd-catalog-http.schema.json`／`catalog_service.py`／`catalog_api.py`：在同一宿主新增文件建立／列表／查回／metadata；create 依原 key 與 dataset，metadata 以 ETag＋CAS 更新單一欄位。目錄更新不增加正文 revision，不新增目錄資料庫。
- `local_configuration.py`／`config_file.py`：固定 Known Folder 的 DPAPI 設定；永久空 guard、防重複初始化、原設定 CAS。普通開啟不讀環境補值、不重配 key／UUID。
- `configured_host.py`／`storage_setup.py`：明示初始化及原身分續作，普通開啟共用唯讀 schema 核對；`initialization_pending → initializing → ready`。固定 migration、Saver 原生 setup、不自動修復未知 schema。
- `configured_api.py`／`managed_app.py`／`__main__.py`：真配置與 lifecycle 組合，unsafe HTTP 另需單一正確 `X-JD-Dataset`；先同 host startup 恢復才受理寫入。CLI 的 init／resume 與一般 serve 分開，無模型啟動。
- `src/jd_relational/generated`：標準工具生成 Python DTO／TS 型別，禁止手改。
- `transport.py`：人工與模型轉入同一 command；兩家工具外殼不同。
- `application.py`：同一準備入口，保留候選／原錯誤，發出固定安全診斷；沒有重試或保存。
- `domain.py`：同文件／同 base refs、完整候選、正文／引用／排序／来源規則，沒有 SQL 或 SDK。
- `selection.py`：根據 App 捕捉資料作精確 UTF-16 選區替換；模型不填 offset，不猜相同文字的位置。
- `intents.py`：固定 App 配發的操作身分、可信讀取材料與意圖摘要；`AdmittedIdentity` 保存恢復必要原身分，不含候選／refs／來源內容，不取得 writer 資格。
- `runtime_checkpoints.py`：原生 LangGraph root／直接 child，共用 Saver；只用公開 state API 保存 manual 操作身分，不 invoke 顧問或重寫對話。
- `notice_history.py`：同版唯讀取得確切變更計數與有限事件；不新增歷史表或讀完整 snapshot。
- `consultant_context.py`：原生 model middleware 投影通知、綁定完整回覆與通知邊界；固定 root checkpoint 查回。此觀察不授予 writer 資格。
- `conversation_sources.py`：同一 Saver 的固定當輪原話／前 AI 上下文與來源驗證；同持久 key 的獨立來源用途。AI 真 request 仍含完整原話才供 metadata，原文不複製到 system；人工與 AI 共用 resolver，人工準備使用既有讀取排空。來源服務故障停止回合，操作查回不重建引用。這是[當輪來源接合](../../docs/specs/2026-09-13-jd-consultant-source-integration-slice.md)，較早 Memory 來源、專業指引及來源 UI 仍待接合。
- `consultant_model.py`：固定相容的 Anthropic 原生 adapter；有限補 terminal 與 response 清理，private seams 升級須重驗，沒有自製 Agent loop／SSE parser。
- `manual_runtime.py`：每文件實際 writer／Future、保存與收尾確認；有 native lease 時先掃全 catalog 關閉原 pending 才開新修改。foreign pending 不把空本地 Future 當死亡證明。
- `windows_host.py`／`host_runtime.py`：固定安裝 mutex、舊 Job 退出、新 Job membership 及程序終身 lease；成功後才開 DB／Saver，startup 完成才 ready。只供專用 App 程序，不在目前 Python shell／pytest 主程序直接 bootstrap。
- `result_transport.py`／`http_results.py`：驗證觀察結果並投影；不執行寫入或自動重試，不把候選當保存完成。
- `storage/schema.py`／`migrations`：十三張關聯內容表、一張 runtime 背景准入表與固定 Alembic migration（目前 head `20260914_0002`）；沒有連線自動初始化或通用 repository。
- `storage/rows.py`：九組 current 資料增量讀寫；由 caller 控制交易。
- `storage/receipts.py`／`storage/service.py`：永久回執、`JdReader` 同版唯讀及 `JdStorage` 共同保存；`reconcile_stopped` 只接受原 `AdmittedIdentity`，沒有候選重建或自動重播。
- `references.py`：ItsDangerous 2.2.0 標準 signer，固定型別、文件／版本／用途與資料集檢查；沒有自建簽章或 token registry。
- `storage/history.py`／`changes.py`：短唯讀交易取得原版或原 operation 的 base/result；另有[固定 AI 操作集合的比較材料](../../docs/specs/2026-09-13-jd-run-change-material-slice.md)，按版次核連續、只讀首末完整版本，不混入人工／別輪。內部讀取不證原生 run 全集；由 `ChatService` 首讀取得原生確認集合再交 `run_change_reads.py` 投影，公開續頁不擴張原捕捉。穩定 IDs 比較完整欄位／關係，不用目前稿重建過去、不重播事件。
- `run_change_reads.py`：原整輪材料與 `change_reads.py` 共用完整差異投影；生成 chat DTO，原 `jsonschema` registry 從固定 `contracts` 補出站條件。正式封裝須攜帶相同來源，不能將 generated DTO 當成來源条件已全部生成。
- `observation_projection.py`：只從原保存觀察發配結果 refs；投影故障不把已成功保存改判失敗，也不重跑操作。
- `tests`：合成工作、格式正反例、共同操作流程、真 SDK 的離線請求捕捉。未完整任務不強迫補欄；多成果和多要求不配對。

## 重現

本單位驗證 Python 3.12.13、Node 24.19.0。使用此目錄的 lock；不修改正式 App 依賴。安裝公開套件後，測試可以全程離線且不需要模型金鑰：

```powershell
uv sync --frozen
npm ci --ignore-scripts --no-audit --no-fund
uv run --frozen --offline python scripts/generate_contract.py --check
uv run --frozen --offline pytest -q -p no:cacheprovider
node node_modules/typescript/bin/tsc -p tsconfig.json
```

若工具預設暫存目錄不可寫，將 uv 的 `--cache-dir` 指到可寫位置。`NODE_BINARY` 可指到正確的 Node 執行檔；在本機不要依賴全機舊版 npm wrapper 選中的 Node。產生器只用標準 CLI stdout，`--check` 不寫生成物。

SDK 測試使用 `httpx2.MockTransport`、固定假 key 與 `offline.invalid`，封鎖 sockets 及環境／本地帳號探索；16 個編輯 wire、4 個讀取 wire 與 4 個差異 wire 測試各兩次 POST 都在程序內攔截。這只證明 SDK 序列化，未證明 provider 接受或模型自然選用。

### 獨立 PostgreSQL 實測

`compose.test.yaml` 僅供合成資料，固定在本機 55436；測試帳密是公開 fixture，不能用於產品。新 PG18 volume 使用 `/var/lib/postgresql`，不接舊 volume。明示建立／驗證：

```powershell
docker compose -f compose.test.yaml up -d --wait --wait-timeout 45
$env:PYTHONUTF8='1'
$env:PYTHONPATH='src'
uv run --frozen --offline python scripts/init_test_database.py
uv run --frozen --offline python scripts/init_test_runtime.py
uv run --frozen --offline python scripts/init_test_runtime.py --schema jd_host_test
uv run --frozen --offline python scripts/init_test_runtime.py --schema jd_ai_host_test
uv run --frozen --offline python scripts/init_test_memory.py
$env:JD_RELATIONAL_TEST_DB='1'
uv run --frozen --offline pytest -q -p no:cacheprovider tests/test_storage_postgres.py
uv run --frozen --offline pytest -q -p no:cacheprovider tests/test_storage_rows.py tests/test_storage_service.py
uv run --frozen --offline pytest -q -p no:cacheprovider tests/test_storage_history.py tests/test_read_storage_integration.py
uv run --frozen --offline pytest -q -p no:cacheprovider tests/test_query_postgres.py
uv run --frozen --offline pytest -q -p no:cacheprovider tests/test_operation_lookup.py tests/test_manual_runtime_postgres.py
uv run --frozen --offline pytest -q -p no:cacheprovider tests/test_host_recovery_postgres.py
uv run --frozen --offline pytest -q -p no:cacheprovider tests/test_manual_service_postgres.py tests/test_manual_http_postgres.py
uv run --frozen --offline pytest -q -p no:cacheprovider tests/test_catalog_storage.py tests/test_catalog_service_postgres.py tests/test_catalog_native_http.py
Remove-Item Env:JD_RELATIONAL_TEST_DB
```

initializer 先核固定測試 DB／user／PG18.6 與表集合，再明示 migration；不清資料、不讀產品設定。真 PG tests 預設跳過；明示啟用後無法連線即失敗，不會假 PASS。直接 SQL／mapper 一般案例回滾；service 與新程序回讀案例保留合成已提交文件，不清空 volume。停止測試容器用 `docker compose -f compose.test.yaml stop`，保留 volume。

`init_test_runtime.py` 只允許 `jd_runtime_test`／`jd_host_test` 兩個固定測試 schema；各明示執行官方 `PostgresSaver.setup()` 的四張 checkpoint 表，不計入十三 JD 表，public JD/Alembic 不變。第二組供真宿主重啟，第一組保留 native busy 等反例，不互相清資料。普通 runtime 建立及 fixture 都不初始化資料庫，缺 schema 直接失敗。這些 schema／帳密只供合成驗收。

Windows-only `pywin32==312` 使用 creator token 的 default DACL、不繼承 handle、不允許 breakaway；successful self-job／mutex 的 handles 由 OS process exit 清理。`test_windows_host.py` 只在新隱藏 helpers 作 native assignment，`test_host_recovery_postgres.py` 再接真 DB。新程序先自行 bootstrap／恢復，父測試不提供 proof；STDIN STOP／CRASH 只為驗收，不是產品 API。所有產物及已確認自有 PID／退出證據保留在 `.research-tmp/jd-host-recovery-*`。

查詢新程序案例只啟動該測試自己的 loopback server，以 STOP／EOF 關閉，保存 PID／退出紀錄於 repo `.research-tmp/jd-query-http-<uuid>`；不是日常產品啟動器。Windows venv launcher 與 Python server 可能不同 PID，依父子身分核對，不能按端口停止別人程序。Starlette TestClient 目前有一個第三方 AnyIO alias 棄用警告，結果稿保留此限制。

人工 HTTP 新程序情境以真 `open_manual_host`／Uvicorn／PG 執行，原始連線在 admission 後不接收回覆直接關閉；原操作查回、後續改稿後重送及新程序重開仍保持相同結果。測試沿 `jd_host_test`，證據於 `.research-tmp/jd-manual-http-*`；合成固定 Origin／signing key／dataset 僅屬 fixture，不能用於日常配置。日常組合改用受保護配置及 `open_managed_app`，保留上述 fixture 的實證邊界。

文件目錄真程序情境使用同一 helper／host，在建立已提交後刻意不接收 HTTP 回覆；原 key 查回、後續更名封存與新程序重開仍對應同一文件。證據於 `.research-tmp/jd-catalog-http-*`。一般服務只能經 runtime 建立／改目錄；storage 無 guard 建立只保留內部 fixture 相容，不可直接暴露為 App endpoint。

### 本機維運入口

在此目錄、固定 lock 環境執行。這是目前人工 API 的維運入口；六章管理畫面已接，圖形啟停尚在施工：

```powershell
$env:PYTHONUTF8='1'
$env:PYTHONPATH='src'
uv run --offline --frozen python -m jd_relational status
# 只有首次明示初始化才執行；需先有空的本機 PG18.6 資料庫。
uv run --offline --frozen python -m jd_relational init
# 前次初始化中斷時沿原設定接續，不重新輸入資料庫或分配身分。
uv run --offline --frozen python -m jd_relational resume-init
uv run --offline --frozen python -m jd_relational serve
```

`status` 只讀設定階段，不能證明 DB 已就緒；`serve` 才核同版 schema、取得原 OS 所有權並恢復 pending。使用完在原服務程序以 Ctrl+C 正常停止；不要按端口終止未知程序。沒有 override config path／DSN／installation 參數。init 只在互動終端取得設定、密碼不顯示；不經環境或命令參數傳秘密。若設定缺損或已有初始化 guard，保留原檔／backup／candidate／guard，不手動清掉當作新安裝。

測試只用 repo 下合成 DPAPI 路徑及55436新 `caliburn_jd_setup_test_<uuid>` 資料庫。`test_config_file.py` 是真 Windows；`test_storage_setup_postgres.py` 用真PG與明標lease分支；`test_configured_host_native.py` 用真 Win32／DPAPI／PG／HTTP 新程序。native ReplaceFileW 在受限 token 下可能因保留原 ACL 所需權限失敗；測試記錄這個執行邊界，不為通過而改 ACL 或忽略錯誤。不碰日常 Known Folder 或正式 DB，不自動刪測試資料。

## 待接責任

目前／歷史 item、field、container、section 與觀察 refs 已發配／驗證，`command_context` 用同版讀取材料重核可寫用途、存在性與欄位摘要。來源查核仍是注入 callback，未接實際 source owner；讀取回 `readability=not_checked`。瀏覽器選區發配仍未完成，此接點明示拒絕 selection，不把 field ref 當選區。

`WriterAuthority` 已由實際 writer 提供；同安裝 Windows 程序互斥／退出證據、PG 屏障及全 catalog 人工 pending 恢復已驗。支持範圍是所有寫入入口共用固定安裝 key／同 session，不能覆蓋繞過宿主的程序。query／manual／catalog 組合由宿主注入同一 `ManualRuntime`。固定設定與手動管理畫面已接，日常 configured API 包含無 refs recover 的資料集門閘；備份還原世代流程、人工通知及實際顧問回合尚待接線。

文字自動保存、管理表單與原請求暫存已接，真瀏覽器重開可找回未完成內容；原生故障注入、實體 IME 及 AI 交接仍待驗。正文歷史還原／整輪撤回與維護尚未完成。保存 service 能提供真 DB 觀察；外部結果／HTTP mapper 必須由接線層以該觀察投影，不能自行宣稱 COMMIT。正式格式沿十三表、v3 snapshot 與永久回執，沒有另一份文件權威。

原兩工具及來源 digest 見[首切片](../../docs/specs/2026-09-13-jd-relational-command-slice.md)；目前八工具、分層與錯誤／診斷、289 項結果及通過界線見[本次設計與結果](../../docs/specs/2026-09-13-jd-management-operations-slice.md)。

歷史[结果與資料庫基礎](../../docs/specs/2026-09-13-jd-result-and-storage-foundation.md)、[共同保存交易](../../docs/specs/2026-09-13-jd-transaction-service-slice.md)、[同版讀取](../../docs/specs/2026-09-13-jd-read-change-implementation.md)、[查詢接合](../../docs/specs/2026-09-13-jd-query-api-and-recovery-identity-slice.md)、[人工 writer](../../docs/specs/2026-09-13-jd-manual-runtime-slice.md)、[宿主重啟恢復](../../docs/specs/2026-09-13-jd-host-restart-recovery-slice.md)、[人工 HTTP](../../docs/specs/2026-09-13-jd-manual-http-slice.md)、[文件目錄](../../docs/specs/2026-09-13-jd-catalog-http-slice.md)及[配置與初始化](../../docs/specs/2026-09-13-jd-managed-configuration-slice.md)保留當時結果。最新測試、首敗、獨立審查及下一工作見[六章手動管理與恢復切片](../../docs/specs/2026-09-13-jd-manual-ui-and-browser-drafts-slice.md)；各批數字不累加。
