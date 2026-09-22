# Spec Compliance

- ❌ **Issues found／Task5 尚不可接受**：T5-R01–R06 為既定 admission、結果可見性、有限恢復與完整 drain 契約缺口；六項均 OPEN，非新產品／框架／authority 選擇。
- 核對範圍：BASE `8eec072d51e97735b22c5f0df598b67101fe570b`；root 凍結的 31 source、`task-5-review.diff`／manifest／逐檔 snapshot，以及單獨 `.gitattributes` support diff。README 按提供的 prior11 baseline 審 Task5 新增段，未對既有研究下 finding。報告以原 `scratch/task-5-report.md` 解析來源；未以作者聲稱代替 diff／caller／raw。
- 核對 authority：Topic `JD-R002/C03`，隔離 G7；唯一 gate 為 Task5 實作 review／必要修正。Task1–4 accepted、Task6 未做；production ADR0060、Proposed0073／0074、0付費及自然模型／真人 IME 未通過邊界不變。
- 路徑縮寫：以下 `A/`＝`experiments/analysis-agent/`、`W/`＝`experiments/jd-editor/web/`、`E/`＝`docs/specs/evidence/jd-editor-task5/implementation/`，均相對 `S:/caliburn/.worktrees/analysis-only-agent`；行號以凍結 snapshot 的實際 source 計。

# Strengths

- `A/src/analysis_agent/jd_engine.py:34–94,130–197` 在 Popen 前登記，保留實際 handle、spawn 中狀態與 I/O threads；cleanup 不成功時保留 entry。`test_jd_native_lifecycle.py:14–104` 分別檢驗 BaseException、process 已退但 I/O 活著、原 handle 及 spawn 未返回，沒有把 Future.done 當整組停止。
- `A/src/analysis_agent/windows_lifecycle.py:46–122` 的入口順序、私有 ACL、mutex、exact 舊 Job、active-zero／absence、新 Job 不重用及 membership 檢查有明確 fail-closed 路徑。`A/src/analysis_agent/api.py:100,214` 與 `A/tests/jd_browser_server.py:39,102` 連到真 bootstrap；raw 的 managed child／重開事件與未測 nested-incompatible 分開表述。
- `A/src/analysis_agent/jd_store.py:172–190` 先鎖 head、下一 statement 查 scoped receipt；具名風險核對同檔 `publish:233–291`，同步 SQL 先 lock、後 mutation，沒有把 lock 與 receipt 塞進同 statement。`jd_reconcile.py:35–47` 僅能以原身分閉合 failure，不重建 candidate。
- `A/src/analysis_agent/conversation.py:186–199,228–325` 與 `jd_tools.py:384–436` 補 root-only manual identity、原 factory 驗證、所有 pending bindings、paired-unconfirmed 與 child-terminal 路徑；原 ToolMessage 不重複或改寫，已確認 manifest 隨 child→root 傳遞。`test_jd_close_reconcile.py:14–76` 及原 raw 有直接斷言。
- `A/src/analysis_agent/jd_routes.py:28–57,207–234`、`scripts/export_web_contract.py:4–12` 與 `W/src/generated/analysis-api.ts:188–241` 由 actual DTO 生成三個共同必填 gate 分支；GET 不呼叫 native／reconcile。`.gitattributes:25–26` 僅保護 Task5 evidence raw bytes，無額外 runtime 範圍。

# Issues

## Critical

- 無。

## Important

### T5-R01／P2／OPEN：送出對話在第二次 admission 未重核封存

- 位置：`A/src/analysis_agent/service.py:500–541,553–570`，尤其 `557–563`；實際 caller `update_document:230–236`，下游 `catalog.py:138–144`。
- 違反：Task5 成品旅程 admission 增補、preflight A03：archive／rename 與新 run 必須由同文件 admission 裁決。
- 問題：`submit` 離開第一段 lock 後，不論是否選取都會再進第二段 lock；第二段只查 accepting／running／JD busy，未再查 archived。另一請求可在空檔成功封存，接著本請求仍 create_run、保存 HumanMessage、launch。selection 的 active_entries 也在第二段 lock 前先減回零，metadata 變更不更新 generation，不能封住這條競速。
- 反例：`scratch/task-5-review-admission.py` 執行凍結的 actual `submit`／`update_document` AST 方法，在第一次 unlock 插入 archive；輸出 `archived=true, created_runs=1, saved_inputs=1, launch_calls=[new-input]`。下游 actual `Catalog.create_run` 沒有 archived 防線。這是純 stub 邊界反例，沒有真模型／DB。
- 要求：在最終同文件 admission 一次重新核當時有效的 archive／原 request／pending 條件，保留 selection reservation 到裁決完成；加 barrier 反例，讓封存與新 run 只有合法的一方獲准。

### T5-R02／P2／OPEN：cachelost 恢復的終局結果被 fresh discovery 清掉

- 位置：`W/src/jd/useJdSession.ts:183–206,214–229`；消費畫面 `W/src/jd/JdWorkspace.tsx:305–315`。
- 違反：manual transport §4／MT11：成功、no_change 與 terminal failure 必須展示原結果，無 cache 也能確認原保存效果。
- 問題：無 candidate 時 `applyRecovery` 立即返回；POST 的 available 僅暫存於 `this.recovery`。緊接著 `refresh()` 只做無 key discovery；server 已清 descriptor，回 no_pending/null，`refreshRecovery:205` 就把原 available 覆蓋。按鈕操作完成後既沒有原 key 區塊，也沒有成功／失敗訊息；下一次 refresh 亦無 key 可查原結果。
- 反例：`scratch/task-5-review-probes.cjs` 用 TypeScript 轉譯凍結 actual `JdSession`，對 cachelost 的 `save_failed`、`committed` 各做一次 POST。兩者完成時均為 `recovery={status:no_pending,request_key:null}, error='', notice='', terminalStillVisible=false`；gate 是 false，並非靠鎖保留結果。
- 要求：保存此次明示恢復的原 key／terminal 可見結果，讓 fresh discovery 只更新目前 owner/gate；不得拿 no_pending 覆掉已確認結果，也不能碰新 candidate／dirty。補成功、no_change、failure 的 cachelost 完成後畫面／session 斷言。

### T5-R03／P2／OPEN：無 run／descriptor 的 retained read 沒有可理解的恢復出口

- 位置：`A/src/analysis_agent/service.py:261–276,296–313,347–358`；`W/src/jd/useJdSession.ts:103–116,194–206`；`W/src/jd/JdWorkspace.tsx:116–145,235–243,305–315`。
- 違反：preflight §12、A06／NL04／NL07 及已採用停止／重開旅程：不能讓員工一直等待不存在的 run；可以沿既定受控 API 重開，不要求新增通用 cancel route。
- 問題：HTTP selection 或 submit-before-create_run 的 native owner 清理失敗後，可形成 `no_pending + request_key=null + write_blocked=true + can_recover=false`。session 鎖住 editor／送出，但 recovery 區塊要求 request_key、停止按鈕要求 run，header 可仍顯示「已保存」。成功 refresh 又清掉 error，畫面沒有殘留工作診斷或 API 重開說明。報告所稱受控整 API 重開只在工程文字，實際員工畫面無對應出口。
- 核對：只因這個具名 UI 風險補讀 diff 截在 component 中段之前的凍結 `JdWorkspace`；未發現其他承接。`jd_read_entry`／typed read failure 保留 owner 本身是正確的，缺的是阻塞原因與可操作恢復接點。
- 要求：用既有 server owner 診斷呈現此無 run 情境及明確有限的受控重開步驟／入口，保留閱讀與 dirty；不得假造 run／candidate 或直接解 gate。新增一個此 DTO 狀態的 session／畫面反例即可，不需擴造通用 recovery 系統。

### T5-R04／P2／OPEN：有界 PG 對帳等待仍占住全域 admission lock

- 位置：`A/src/analysis_agent/service.py:334–338,422–426,734–738`；`A/src/analysis_agent/jd_store.py:183–190`。
- 違反：manual transport §3 的「全域 admission lock 不包住等待」、Task5 P04／另一文件可繼續的邊界。
- 問題：`recover_manual` 只把 native cleanup 移到 lock 外，重新拿全域 `self.lock` 後整段執行 `_reconcile_manual`，其中 head FOR UPDATE 可以等舊交易／timeout。failure closure 又有另一 SQL attempt；`stop` 的 `_close_turn` 也在同全域 lock 下沿此 PG port。A 的 recovery 等鎖期間，B 的 submit／manual／metadata 都進不了 admission，即使 B 完全無關。
- 反例：同一 `scratch/task-5-review-admission.py` 執行 actual `recover_manual`，在其 `_reconcile_manual` SQL 接點設 Event barrier；另一執行緒的全域 lock 非阻塞取得回 false。此為原控制流程的純同步 fixture；既有真 PG 測試另已證 head lock 確實會等待，沒有重跑 DB。
- 要求：以同文件 reservation／generation 維持排他，讓 native 與 PG 等待皆在全域 lock 外；重入核身分／generation 後再發布 closure。補 A 對帳等 head lock 時 B 能獨立 admission 的有限反例，勿更動 SQL authority。

### T5-R05／P2／OPEN：原完整 manual-save 重試先清 descriptor，遮蔽既有 terminal

- 位置：`A/src/analysis_agent/service.py:371–380,426–433`；HTTP caller `A/src/analysis_agent/jd_routes.py:262–273`。
- 違反：Task5 M04／M06、原 Task4 receipt-first 與 manual transport §3／§4：已保存結果的可讀性與 owner 清理完成分開；晚到原 POST 先回原 terminal。
- 問題：同 key pending 且 manual_active=false 時，`save_manual` 在查 receipt 前直接 `return _reconcile_manual`。即使 operation 已 committed，descriptor clear 再失敗，或另個唯讀 owner 令 proof 暫不可用，原 full-payload retry 仍拋 PublicationUncertain，而不是原 terminal；route 只攔 ServiceConflict／ValueError，會變未分類 server error。新 key-only route 已修此語意，原 full route 尚未承接。
- 反例：純 AST fixture 給 exact key/digest、可讀 committed receipt、descriptor clear unconfirmed，actual `save_manual` 輸出 `outcome=PublicationUncertain, terminal_receipt_reads=0`。
- 要求：先核原 receipt/digest，再按匹配 owner 決定是否可清；清不成仍回原結果並保留 gate／descriptor。不得因回 terminal 就忽略真正 outstanding owner；加 exact full POST 的 clearfail／active sibling 反例。

### T5-R06／P2／OPEN：明示 recovery 不在 shutdown 的 admission／drain 計數內

- 位置：`A/src/analysis_agent/service.py:306–343,752–789`。
- 違反：preflight §10 全入口 drain、NL07：先停新 admission，再等原 Python entry／native／binding closure，最後釋資源；read/recovery 也須受同一停止邊界約束。
- 問題：`can_recover`／`recover_manual` 沒有 accepting 檢查；恢復只設 `context.closing`，不加入 `active_entries` 或其他被 `close` 等待的計數。`close` 的 predicate 只等 create_active／active_entries，之後也不等待既有 recovery 的 closing。因而已在 lock 外 cleanup 的 recovery 可與 shutdown 自行 `_reconcile_manual` 競跑，甚至在 close 返回、resource manager 已開始釋放 Saver／DB 後才做末尾 `manual_recovery`；accepting=false 時亦仍可新取 recovery 權。這不是 ordinary read 是否可用的問題，而是整 App 已進 drain 的界線。
- 核對限制：上述缺口由 actual owner／close caller 可直接看出；本 review 未跑真 shutdown 故障。已有 `test_close_signals_and_drains_every_native_app_entry` 的四個參數只有 manual／read／selection／create，不包含 recovery 中途進 global close，不能代證此入口。
- 要求：把已 admission 的 recovery 纳入同一 App entry drain，停止後拒新的明示 recovery（既有只讀原結果可按可用資源處理），等其 Python／native／對帳完整 unwind 再釋資源；補一個 recovery barrier＋close 的有限反例。沿既有 owner，不新增協調服務。

## Minor

### T5-R07／P3／OPEN：最後測試輸出仍有已知依賴警告

- 位置：`E/raw/task5-final-jd.log:2–8`、`E/raw/task5-last-affected.log:2–8`。
- 問題：Starlette TestClient 引用 `anyio.abc.BlockingPortal` 產生 DeprecationWarning；36 PASS／最後8 PASS 並非無警告輸出。不是 production 缺陷，也不撤銷通過數。
- 要求：在結果明記此 upstream 相容警告並有限處理；不要為了消音擴大換框架或全面隱藏警告。原 log 不改。

# Checks／證據效力

- ✅ 已讀原 raw：`task5-final-jd.log`＝36 PASS＋1 warning；`task5-final-web.log`＝23 PASS；`task5-final-codegen.log`＝生成一致；types／lint 檔無錯誤輸出。`task5-final-memory-captured.log`＝62 PASS／1 FAIL，保留首敗；`task5-memory-fix-green.log`＝受影響43 PASS；`task5-last-affected.log`＝8 PASS＋1 warning。重疊案例未相加。這些綠燈不覆盖 T5-R01–R06。
- ✅ 已讀 `task5-process-first.log`、`task5-nl10-nl13.log`、`task5-nl11-nl12.log`、`task5-nl12-prelock.log`、runtime／browser-server raw；核 actual fixture 與結果對應，包括 native outstanding、新 managed process 的0native／0provider、COMMIT／create 原 key、PgSleep 前置 statement 與 later_mutations_sent=0。harness 善後未當產品停止 proof。
- ⚠️ NL08 的 child 是 CREATE_SUSPENDED，未直接觀測 JS transform 執行中；NL10 是 manual A＋selection B，未直接觀測 AI edit A＋selection B 同次 crash；NL11 是本機 nested success 與 restricted-handle 真 Assign denied，未證 nested-incompatible。這些限制是真實且明確的；kernel containment 與 AI binding 的分開證據可支持各自責任，不能標為 exact 原情境已跑。本 review 不因缺少 exact 組合自動要求擴跑；仍須保留 NOT RUN 效力。
- ⚠️ MT 有 actual TestClient／PG／root、生成契約及 session／component 證據；無 cachelost 真 browser 按鈕全流程。HTTP worker12632 未載最後兩小修，最後 source 的該兩修只有 TestClient；不據舊 HTTP 成功聲稱最後 browser 已驗。T5-R02／R03 正是目前 session／畫面證據沒有攔住的實際缺口。
- ✅ 具名 caller 補讀仅限：R01 `Catalog.create_run/update_document` 的防線；R03 diff 截斷的 `JdWorkspace` 前半；PG proof 的 `JdStore.publish/_connection`；對照 adopted lifecycle／manual transport。未爬全 repo、未重讀 key/env、未改 source／計畫／raw、未操作 git／provider／DB／Windows Job／既有 API 程序，無 subagent。
- ✅ 新增窄驗證仅 `scratch/task-5-review-probes.cjs`（actual JdSession 轉譯，cache／API 純 mock，無網路）與 `scratch/task-5-review-admission.py`（actual frozen methods AST，catalog／graph／SQL stage 純 stub，Event／lock 排程）。兩命令均 exit0，輸出是預期缺陷的觀測，不是產品 PASS；没有重跑完整套或重造原 raw。
- ✅ 窄 fixture SHA256：`task-5-review-probes.cjs`＝`acf8e40fc96c91752fd84c9cacecf405aa62b7cf6250085fc8759100c2dd6b71`；`task-5-review-admission.py`＝`2ccea8e48b6795bbb6a50ce6f3e38cca7013f073ead4429ac983802b731ba3c2`。
- ✅ 窄命令 cwd=`S:/caliburn/.worktrees/analysis-only-agent`：`.superpowers/sdd/2026-09-10-jd-editor-core-implementation/task4-runtime/node-v22.23.2-win-x64/node.exe scratch/task-5-review-probes.cjs`；`experiments/analysis-agent/.venv/Scripts/python.exe scratch/task-5-review-admission.py`。僅啟動解譯器執行純 fixture，沒有 native bridge／server／DB 子程序。

# Assessment

- **Task quality：Needs fixes。** 原身分、程序停止與 PG 對帳的主要責任接得清楚，也有真 kernel／PG 原始證據；但最终 admission race、終局結果消失、無 run 阻塞出口以及恢復的全域鎖／shutdown owner 尚影響實際可用性與安全閉合，不能接受 Task5 或進 Task6 包裝成功。
- **Next gate：** 原作者集中修 T5-R01–R06，對應窄反例及受影響檢查後凍結 fix diff，由同 reviewer 只核 closure；R07 明確記錄／有限處理。0付費、原 raw／未測限制、production authority 均保留，不重新開產品或框架設計。
