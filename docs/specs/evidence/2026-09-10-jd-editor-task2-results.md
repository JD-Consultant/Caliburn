# JD 編輯核心 Task 2：保存、版本與回執結果

2026-09-10。**完成：Spec PASS／quality APPROVED；T2-R1 CLOSED。** 原完整驗收130 PASS（34新測試含24真PG＋96既有回歸），修正後另14focused PASS；不是宣稱重新跑過144項全套。實作後獨立review與窄複核見[審查紀錄](jd-editor-task2/review.md)。本結果僅限隔離原生／真PG／既有離線顧問接線，不代表DOM、自然模型、production或成品完成。

完整測試輸出與本批scoped PG普通JSON保留在相鄰jd-editor-task2目錄；首次relation分類失敗、初審T2-R1與後續修正均保留。零付費模型，沒有資料庫重建／清空或production/root lock變更。T2-N1既有Starlette deprecation為非阻擋維護事項，未盲升本切片外依賴。

後续Task5仍須持有並核對實際程序停止證據；服務返回或查無receipt不代表writer已停止。此風險已交有限設計，不提前宣稱取消安全。

以下保留implementer原報告及round1（其初次「待review」是當時狀態，以本頁首及獨立審查closure為最終結果；scratch證據連結改為本目錄路徑）。

---
# Task 2 implementation report

日期：2026-09-10。Topic：JD-R002/C03。Stage：隔離 G7，Task 2 實作與本地驗收完成，交 controller 作獨立 review；不代称整體產品／production authority gate 完成。

## 範圍與基線

- 唯一工作區 `S:/caliburn/.worktrees/analysis-only-agent`，branch `codex/analysis-only-agent`。
- BASE `88eda48086f4b211b066069d59f607b0dd19dd07`，Task 1 tag `jd-editor-core-task1-20260910`。
- 先讀 task-2-brief、AGENTS、current register 頂部、decision-process、contract-strategy，以及 DB/ER closure。使用 executing-plans、TDD、systematic-debugging、verification-before-completion 流程；未 spawn 子 agent，未 git add/commit/tag/reset/gc。
- Binding：同 PG 唯一 JD 工作稿；revision/receipt/head 短交易；mapper 唯一 generated DTO 邊界；原 Memory/Saver/Store authority 不變。原 Task 1 native/schema/lock 未改。
- 本輪 blocking question：能否在固定原生運算與真 PG 保存之間，保留精確一次發布、receipt-first 重開及已知未改/結果未知的區別。以以下真測試閉合，下一 gate 是獨立 review。

## 最後驗證

從 `experiments/analysis-agent`，私下由 root compose db 設定建立 loopback libpq `Q019_TEST_DATABASE_URL`；不打印帳密、不讀模型 keys。實際指令（環境設定省略敏感值）：

```text
uv run pytest -q -s tests/test_jd_engine.py tests/test_jd_store.py tests/test_jd_postgres.py tests/test_service.py tests/test_publication.py tests/test_conversation_lookup.py tests/test_conversation_lifecycle.py tests/test_api.py --basetemp <verified-new-workspace-directory>
130 passed, 1 warning in 79.69s (0:01:19)
```

完整原始輸出：[完整測試輸出](jd-editor-task2/final-tests.txt)。新增 **34 項**：8 engine、2 mapper/store、24 real PG；另 93 既有顧問/Memory離線與 3 API 回歸。沒有 skip、沒有真模型呼叫。唯一 warning 為 Starlette TestClient 使用 anyio deprecated BlockingPortal alias，不是本次邏輯失敗。controller 另獨立跑同四組 93 項，15.79s PASS；訊息交錯造成一次重覆，之後不再重跑。

`git diff --check` exit 0；只有既存 Windows LF→CRLF 提醒。Task 1 依賴未修改，沒有重跑已通過且無新反證的 native/build/codegen suite。

## RED → GREEN 真紀錄

1. 首次授權 sandbox 執行 `uv run pytest -q tests/test_jd_engine.py tests/test_jd_store.py tests/test_jd_postgres.py` 被 uv cache `sdists-v9/.git` access denied 擋下；未改測試避開環境。使用既有授權 escalation 重跑後，**3 failed, 2 errors in 0.69s**：`analysis_agent.jd_engine`／`jd_contract`／`jd_store` 尚未存在。這是指定接點的實際 RED，不是把 SQLite 或 SKIP 當 PG 結果。
2. 固定 Node/mapper 最小接線後，同指令 **3 passed, 9 errors in 1.60s**：9 個交易測試因 `jd_store` 尚未實作而失敗。
3. SQL/服務接線後，真專用 PG **12 passed in 8.33s**；擴到必要 Node 故障／跨程序／歷史驗收後 **24 passed in 33.69s**。
4. 補明確故障邊界時，focused 指令 `-k 'digest or failed_receipt or read_failed or single_direction or two_no_change or sql_total or array_order'` **3 failed, 5 passed, 15 deselected in 6.83s**：內部 intent 未核 exact digest；已知失敗 receipt 的 commit reply lost 被誤映射 outcome_unknown；typed read failure mapper 缺少。定位並修正後，同 focused **8 passed, 15 deselected in 6.83s**。
5. 初始化總 budget 與 scope fixture `-k 'initial_create_uses or missing_catalog_unbound'` **2 failed, 21 deselected in 1.62s**：initial create 未用 SQL 總 deadline；不存在 catalog 的結果仍帶 operation。修正後連同 rollback/commit/lock 接點 **8 passed, 15 deselected in 6.33s**。
6. 完整 format2 `-k format2_links` 首輪 **1 failed, 23 deselected in 22.24s**：native `referenced_item` 細分錯誤被映射為 engine_failed，雖然實際零發布。讀原生 schema.ts 確認四種有限 grammar/relation code，mapper 明確映射 invalid_input；重跑 **1 passed, 23 deselected in 21.73s**。首轮 failure snapshot [首輪 relation failure snapshot](jd-editor-task2/first-relation-failure-pg.jsonl) 保留，沒有改判／覆寫。
7. 最後 necessary suite 130 PASS 如上，之後只有 README/report 與只讀 diff 核對，沒有再改 executable code。

## PG 與故障證據

[final PG snapshot](jd-editor-task2/final-pg.jsonl) 為 final suite 完整 evidence（102,674 bytes）。24 個 test 記錄，包含本批 scoped 24 heads、42 revisions、28 receipts 的完整欄位/普通 JSON；另保留 unique catalog-only absence 與初始化 rollback 的 assertions。不讀取其他文件正文、不清空／drop既有 DB。

實際查得：PostgreSQL **16.14 (Debian 16.14-1.pgdg13+1)**；`fsync=on`、`synchronous_commit=on`；三表 `relpersistence=p`。DSN guard 精確要求 `q019_jd_app_20260910`、localhost/127.0.0.1、connect_timeout 1–5。沒有放寬原 Memory `q019_agent_test` guard。

- 初始 catalog/revision/head 同交易；head 插入前故障與超過總 budget 均無半成品。
- 兩個真 driver connections 在 head `FOR UPDATE` 前 barrier，同 base 不同 operation：恰一 committed、一 stale_base，1 head/2 revisions/2 receipts；逐一核原 receipt。
- revision insert 後、receipt insert 後（head 前）、head update 後分點 exception，均回到 1 head/1 initial revision/0 receipt。沒有 partial publication。
- 真 COMMIT 成功後故意失去 acknowledgement：當次 outcome_unknown，後續同 operation receipt 查到原 committed。失敗 receipt 的 acknowledgement 遺失則保留原 engine_failed/unchanged/unconfirmed/reconcile。
- 子程序完成 COMMIT，尚未回應即 `os._exit(73)`；另一全新程序接相同 request key/payload，只讀原 receipt，Node 被禁止執行；得到原 committed 完整 JSON，沒有多版本。final raw log 有完整 recovered receipt。
- 真 head lock 等待及 `pg_sleep` 驗取消/總 budget，沒有自動 transaction replay；failure receipt 無法取得 lock 時為 save_failed/unconfirmed，正文/receipt 零發布。
- 同鍵不同 digest conflict 不覆寫；saved no_change/engine_failed/stale_base 精確重播。digest 包含 document/base/profile/origin/完整 payload，不含候選隨機新 ID。
- immediate FK、origin/parent/profile、單一 initial/successor/producer 與 receipt CHECK 負例拒絕；兩個 no_change 可共同指向同一 base。mapper 另核 opaque refs 的 scope/UUID/確切 before-after pair。
- JSONB `=` 為唯一 no_change 判準。marks、重覆文字段落、array 順序、完整 r2 Task/K/S links 均按全值保存；淨零原生操作不發布暫時 changes。invalid relation 只留 failure receipt，head不改。
- manual committed 的 operations=null、affected=[]；保存前後完整 snapshot仍不同。manual→manual改回→AI 混合鏈 counts 3、manual 2、AI 1；只由 direct parent反查producer，非祖先拒絕，initial/no_change不算建立事件。

## Node 實測

Final 原始測量：r2 value 18,460 bytes；100 commands 的 request 27,853 bytes；200 原生 operations；result value 18,296 bytes；validate 8.343s、transform 8.875s，兩個獨立階段合計 17.218s。它們是含 Python schema、Node啟動/運算/JSON/輸出驗證的端到端階段耗時，不冒稱單獨原生 transform CPU 耗時。

100 是明示 stress 規模，沒有核准的 schema最大 commands。controller已同步計畫措辭，不新增 maxItems。

固定 argv、無shell、OS環境allowlist、一次attempt；hang、截斷JSON、stdout超界、stderr超界、active cancel 均 typed failure，子程序確認reap，無自動重播。正文從未截短後當成功。預設30秒監督預算，terminate/reap及kill/reap各5秒；16MiB input/stdout、8KiB stderr。

## Changed paths（Task 2 自己的改動）

新增：

- `experiments/analysis-agent/src/analysis_agent/jd_types.py`
- `experiments/analysis-agent/src/analysis_agent/jd_contract.py`
- `experiments/analysis-agent/src/analysis_agent/jd_engine.py`
- `experiments/analysis-agent/src/analysis_agent/jd_store.py`
- `experiments/analysis-agent/src/analysis_agent/jd_service.py`
- `experiments/analysis-agent/tests/test_jd_engine.py`
- `experiments/analysis-agent/tests/test_jd_store.py`
- `experiments/analysis-agent/tests/test_jd_postgres.py`
- `experiments/analysis-agent/tests/jd_process_worker.py`

修改：`experiments/analysis-agent/src/analysis_agent/api.py`、`catalog.py`、`service.py`；`experiments/analysis-agent/README.md` 只追加 Task 2 段落，保留既有 dirty edits。scratch report/raw evidence不混入runtime。其他既有dirty文件由controller/先前工作擁有。

## Self-review 與限制

- 同engine composition、generated DTO唯一mapper、三表單向FK、不可變receipt/no_change、人工快照、scope、失敗分類及後續有限history ports，逐項按brief/DB/ER closure核對。沒有新Memory／source store、通用command/retry/rebase/diff engine、production/RAG imports、root lock修改或付費請求。
- Task 3 才把真 source owner/引用binding接上；本Task來源fixture只有synthetic，不能宣稱來源truth已驗。Task 4/5才交HTTP/DOM、writer gate、取消run closure與明確resume；receipt查無row本身不是安全重送證明。
- Node OS spawn與同步JSON/schema計算不可中途preempt；timer是控制預算而非硬性30秒牆鐘。SQL沿共享engine connect_timeout=5，driver cancel/rollback收尾另據真實結果，不宣稱所有OS/網路故障都可在同一30秒內返回。
- 本輪測到實際 Windows terminate/reap；無法reap分支保留quiescent=false與unconfirmed，不可据此解除後續writer gate。未執行主機crash/斷電測試，也不把設定核對與commit後process exit冒稱電源故障驗收。
- 證據只覆蓋固定離線provider/原生/PG；自然模型工具選擇、專業JD品質、費用／延遲產品驗收、真人交付與production adoption均未完成。
- 獨立review尚待controller；implementer未提交或打tag。

## Fix round 1：T2-R1（2026-09-10，待窄複核）

上方原始實作與130項驗收紀錄保持不變；獨立 `task-2-review.md` 發現唯一 blocking T2-R1：selection 的已知 `JdEngineFailure` 會漏出 `read` typed port。讀過 review 與實際 `native/src/read-selection.ts`／既有 service 後，採 receiving-code-review/TDD，僅修此項。

先加 focused 真服務＋現有 wire mapper 測試，再執行：

```text
uv run pytest -q tests/test_jd_store.py -k selection_read
RED:   11 failed, 3 passed, 2 deselected in 1.02s
GREEN: 14 passed, 2 deselected in 0.42s
```

RED 的11種可識別錯誤全部以 `JdEngineFailure` 漏出；3項取消／unknown code／RuntimeError保留既有傳遞行為已通過。GREEN 原始輸出存 [R1 focused測試輸出](jd-editor-task2/r1-focused-tests.txt)。本輪無PG、無Node子程序、無模型請求；沒有重跑已通過的130項或真PG全套。

`JdService.read` 現在只捕捉並明確分類已知 Node failure：

- `invalid_input`／`invalid_selection`／`invalid_span` → invalid_input／correct_arguments。
- `target_missing` → target_missing／reread_current。
- `unsupported_content`／`noncanonical_value`／`duplicate_id`／`referenced_item`／`invalid_relation_kind` → unsupported_content／stop；不要求呼叫者修改選取參數去修復既有保存內容。
- `engine_failed`／`engine_timeout` → read_failed／stop。
- `cancelled`、未列出的code與普通程式RuntimeError原樣向外傳遞；沒有catch-all、沒有重試。每個可分類case都經原 `read_failure_to_wire` 的SSOT＋generated DTO驗證，確保 effect=unchanged、durability=unconfirmed、error.command_index=null，且不附虛構revision／fragment。

此次相對原review snapshot，僅變更：

1. `experiments/analysis-agent/src/analysis_agent/jd_service.py`（有限read例外分類）。
2. `experiments/analysis-agent/tests/test_jd_store.py`（14項focused cases）。
3. 本 `task-2-report.md` 追加round1紀錄；新增scratch [R1 focused測試輸出](jd-editor-task2/r1-focused-tests.txt) 證據。

focused diff check exit0。T2-N1既有dependency deprecation不升版；Task5 quiescence/process ownership後續風險維持原交接，不在本round擴做writer lifecycle。未git mutation、未spawn agent。T2-R1實作修正已驗，狀態待controller依原snapshot做窄複核。
