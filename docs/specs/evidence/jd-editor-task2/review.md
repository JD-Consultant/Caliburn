# Task 2 獨立 review

Spec Compliance：FAIL（T2-R1）。Code Quality：CHANGES REQUIRED。

範圍為 BASE 88eda48086f4b211b066069d59f607b0dd19dd07 後 task-2-review.diff 的 13 檔未提交快照；不是 whole-branch／merge review。依 SDD task-reviewer rubric 審查。README 舊有 11 行 recall dirty hunk 不在本 review，也不要求納入提交。

## Strengths

- 同 engine 與既有 catalog session composition 正確：api.py 新增 JdStore(engine)，service.py 文件建立委派 JdService；jd_store.py:178–194 將 catalog／初版／head 放同交易，Node 位於交易外。
- jd_store.py:211–270 的 head lock 後 receipt 重查、base 核對、JSONB `=`、revision→receipt→head 順序符合 DB closure。receipt 與 revision 不提供 UPDATE/UPSERT port；partial unique 分別約束 initial／successor／committed producer。
- jd_store.py:251–254 保留人工 committed 的 null operations／空定位；history:282–305 以 direct parent 與 committed producer 計事件，人工改回仍有事件，沒有把空 affected IDs 當 no_change。
- jd_contract.py 是唯一 generated DTO import；request digest 包含 scope/base/profile/origin/payload，receipt mapper 核對 scoped refs 與確切 pair。
- 真 PG 測試含不同 connections 競爭、分點 rollback、COMMIT acknowledgement 遺失、新程序 receipt-first，以及完整 format2 歷史／關係負例。不是以 mock 或 skip 充當持久驗收。

## Important

### T2-R1 — read-selection 的可分類 Node 錯誤漏出 typed read port

- 位置：experiments/analysis-agent/src/analysis_agent/jd_service.py:35–41；對照 jd_engine.py:139–142、jd_contract.py:69–73。
- 違反：Task 2 共用介面要求 read(scope, query) 產內部 JdReadView；ER02/ER03 指定可識別輸入問題與依賴不可用分別走 typed read failure，單次讀取不得把依賴故障冒充 target missing。
- 問題：selection 呼叫可丟 JdEngineFailure（invalid_span、target_missing、engine_timeout、Node 不存在／stdout 錯誤等），但 read 只捕捉 JdMissing、DBAPIError、TimeoutError。寫入路徑有有限 mapping，選取讀取卻沒有，因此這些正常可預期情況無法交給 read_failure_to_wire，會直接跳出服務 port。
- 實際反例：以固定 in-memory revision 與 selection engine 丟出 JdEngineFailure('invalid_span') 呼叫 read，實際輸出 `READ_ESCAPES JdEngineFailure invalid_span`，而非 invalid_input view。不開 DB、不呼叫 Node／模型。相同分支也會漏出 engine_timeout。
- 要求：在此既有 read 邊界補有限 JdEngineFailure 分類（輸入/目標錯誤、unsupported existing content、可分類依賴失敗），遵循 ER02 的 stop／correct_arguments，不 catch-all 程序 bug 或吞取消。補 focused 測試證明 invalid span 與 engine timeout 回合法 typed read DTO；不需重跑整套 PG。

## Minor

### T2-N1 — 既有 dependency deprecation warning（不阻擋本 Task）

- 位置：task-2-final-tests.txt warnings summary；既有 .venv/Lib/site-packages/starlette/testclient.py:53，由 tests/test_api.py::test_api_lifespan_idempotency_and_private_state_projection 觸發。
- 原始結果為 `130 passed, 1 warning in 79.69s`，不是零 warning。anyio.abc.BlockingPortal alias deprecated；此 diff 未改 Starlette/anyio/lock，故分類既有維護事項，不要求盲升本 task 以外的依賴。

## 不能由本 diff 宣稱完成／後續交接

- 真 source owner binding 是 Task 3；現有格式／synthetic refs 驗證不證來源真實性。HTTP、writer admission、完整取消與 turn closure 屬 Task 4/5，未以缺少這些功能判本 Task 不合格。
- 具體 Task 5 seam：jd_service.py:72–75 在 engine quiescent=False 時回 unchanged/unconfirmed/reconcile，這目前保守地保持 operation 未閉合，沒有證據顯示本 diff 已提早解 gate；但 JdWriteOutcome 沒有 quiescence 欄位，且 JdEngine 不保留未 reap process 的外部 owner handle。focused 檢查確認 `QUIESCENCE_FIELD False`。後續 writer owner 不得把服務方法返回、或單查 receipt 無 row，當作 process 已停止；需要沿實際 process owner 保留／核對停止證據。這是明列的後續接線風險，並非要求本 Task 完成 writer lifecycle。
- 既有 Memory/Saver/Store ownership、正式 production adoption、自然模型品質與真人交付未由本 diff 重驗；無新證據要求擴查或重跑。

## 實際核對與限制

- task brief、implementation report、SDD reviewer rubric、current register/process、DB closure 與 ER02/ER03 條文均已核對。13 檔需求均有對應 diff；沒有发现新增第二 DB URL、Memory store、泛用 retry/diff 引擎或 root lock 修改。
- 首次合併讀取被 tool output 截斷；為取得原本未完整可見內容，按 diff 段落補讀。未另讀 changed source file、未跑 git、未 crawl codebase。
- 原始 final-tests 證據已核：130 passed、1 warning；完整 final JSONL 可解析為 24 records／24 heads／42 revisions／28 receipts，與 report 一致。沒有重新產生或覆寫 evidence。
- 僅針對上述 read exception 與 quiescence seam 執行一次無 DB、無 subprocess、無 paid model 的 fixed counterexample；未重跑 suite。
- 唯一寫入為本 scratch review 報告；未修改 code/index/branch，未 spawn agent／commit。

結論：交易與持久回執主要要求符合，Task 2 typed read 的 Node 例外邊界需修正 T2-R1 後再接受。T2-N1 不阻擋。

## Fix round 1 窄複核（2026-09-10）

Spec Compliance：PASS。Code Quality：APPROVED。T2-R1：CLOSED。

- 僅審 task-2-fix1.diff 相對原 review snapshot 的 jd_service.py 與 test_jd_store.py 修正，並核對 report round1／task-2-r1-focused.txt；未重審未改程式、未執行 suite 或新測試。
- jd_service.py:42–56 現在對可識別 JdEngineFailure 作有限分類：invalid selection/span→invalid_input；target_missing 保留；既存內容不支援→unsupported_content；engine failure/timeout→read_failed。這些 view 均能進既有 mapper，取消／未知 code 仍重新拋出，普通 RuntimeError 不被捕捉。修正沒有寫入 SQL、重試或更動已保存 receipt。
- test_jd_store.py:30–85 共 14 focused cases 透過真 JdService 與既有 SSOT/generated DTO mapper 驗完整輸出與單次 engine 呼叫，另核對取消／unknown／bug 原 exception identity。原始 GREEN 為 14 passed, 2 deselected in 0.42s；report 記錄 RED 11 failed/3 passed，與修正前漏出的 11 種分類相符。
- 此修正閉合 T2-R1，未發現新阻擋問題。T2-N1 仍為既有、不阻擋的 dependency warning；原 Task 3 source binding 與 Task 5 quiescence/process ownership 限制照原交接，不以本次 PASS 宣稱已完成。
- 唯一檔案變更為追加本 review 報告；未修改 code/index/branch、未跑 git、未 spawn 子 agent。
