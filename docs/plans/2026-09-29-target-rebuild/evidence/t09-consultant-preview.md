# T09 候選預覽與公開中間訊息

狀態：候選預覽、控制及已保存公開訊息回看已接通；後續切片與真模型旅程見下文及 T08。SSE 仍未實作，不代表整項 T09 完成。
責任依 [介面 §2–3](../../../implementation/interface-and-delivery.md)與 T09。

## 有界施工／驗證計畫

- [x] 從既有 checkpointer 的本 Turn response 原件投影完整 assistant commentary；排除 reasoning、final、工具與承接 input。原 response/item 身分去重，保存順序可回看。
- [x] 擴充 consultant-turn schema：nullable commentary（未配置 reader 不冒充空清單）、nullable candidate（僅 active/paused）；候選重用既有固定 profile/work schema 與 reader。正式生成 Python／TS。
- [x] 原 status 與 by-command GET 共用投影；checkpoint I/O 不佔用業務交易。未完成／取消候選不可成正式稿，跨檔案查詢拒絕。
- [x] Composer 顯示公開訊息，完成後可展開回看；JobFilePage 組裝只讀候選元件，與正式編輯及 PDF 區分。沿既有 1 秒 polling，不新增事件平台。
- [x] 代表性測試：原件含秘密時 HTTP 白名單、原生 saver 重開／模擬 current window 清除後訊息順序、候選修訂與取消隔離、UI reload／狀態推進／純文字轉義。

## 選擇與限制

沿官方 `BaseCheckpointSaver.alist`，不查框架 SQL，也不執行 Graph。鎖定 PostgreSQL saver 按 checkpoint ID 倒序返回；在已保留的本 Turn checkpoints 上投影，非逐 token 歷史。依據：[官方 checkpoint API](https://reference.langchain.com/python/langgraph.checkpoint/base/BaseCheckpointSaver)。若未來清除／裁剪 checkpoint，須先保存已承諾的公開訊息，不可直接丟失回看資料。

本切片按使用者指定在共享 target-rebuild 範圍自行實作，不建 worktree／子代理／提交；以本頁記錄驗收，不另建計畫權威。

## 接線

- 主線 bootstrap 將同一個 saver 傳給 `ConsultantStatusWorkflow(database.sessions, saver)`；本切片未改 bootstrap。沒有 reader 時 `commentary: null`，UI 明說不可讀，與 `[]` 區分。
- 原 status／by-command GET 均增加 `commentary`、`candidate`。中間訊息只有原 `response_id`、`message_id` 與公開文字，沒有正式 source ID／訪談序號。
- `candidate.profile` 與 `candidate.work` 來自單一固定候選修訂；work 重用 HTTP `work_view` mapper，剔除內容修訂／generation 等內部資料。
- `JobFilePage` 以 `InterviewComposer.renderCandidate` slot 組裝 `JdCandidatePreview`；interview 不 import jd-editor 私有元件，也不把候選寫入正式 Query cache。
- 框架單檔生成器不接受此處的整檔 root `$ref`。改沿既有 JSON Pointer 引用共享 property／definition，未複製欄位規則或修改生成器。

## 實際驗證（2026-09-30）

- API：`.venv-target/Scripts/python.exe -m pytest -p no:cacheprovider tests/unit/test_public_commentary.py tests/contracts/test_consultant_turn_contract.py tests/integration/test_consultant_progress.py tests/integration/test_consultant_status.py tests/integration/test_jd_work.py tests/integration/test_consultant_http_execution.py -q` → **14 passed**，其中 11 項使用指定本機 PG、每例 owned schema；synthetic HTTP 不發真模型。
- Web：`node node_modules/vitest/vitest.mjs run src/app/App.test.tsx src/features/interview/InterviewComposer.test.tsx src/features/jd-editor/JdCandidatePreview.test.tsx` → **23 passed**。公開文字／候選顯示各已看過 Red；另覆蓋同 command 恢復、取消退回正式區、完整集合只讀顯示。
- `tsc --noEmit`、scoped ESLint／Ruff、mypy 四個 API source files 均通過。
- 正式 `scripts/generate_contracts.py` 成功；後續 `--check` 只出現並行 `move-jd-item-arguments` 的「来源→來源」生成差異，consultant-turn 無差異。未覆寫其他代理的新更動。
- 自行審核 public field allowlist、scope 在 reader 前確認、固定修訂與 UI cache 隔離；依本次禁子代理指示，沒有獨立 reviewer。

限制：目前是按 execution ID 查回本 Turn 的預覽／公開訊息，未新增全部過往 Turn 的選擇列表。每次 polling 讀此 Turn 已保留的 checkpoint 歷史；未做長期歷史裁剪或效能 gate。沒有真 provider 外送或新增 IAB 旅程驗證。

## 控制 UI 後續切片（2026-09-30，受影響測試通過）

主線分派 Pascal 負責控制 HTTP／status／schema，UI worker 負責前端；bootstrap controller／runner wrapper／saver 由主線接線。本切片不改控制 workflow，不新增輸入／operation／事件平台。

- `ConsultantTurnControls` 只顯示 GET 的 `allowed_controls`，POST 原 execution 的 `pause`／`cancel`／`resume`，不傳 body／input identity。回覆經正式 schema 與 scope 驗證，但不寫入正式 JD cache，也不以回覆樂觀改寫 execution status。
- 每次控制成功／失敗皆 invalidate 原 execution query，重新 GET 確認；網路不明結果不自動重送。取消／失敗後沿既有「取回原文編輯」流程，由使用者主動 POST 新 command identity；resume 不建立 input。
- 控制 mutation 禁用自動 retry，並使用 `networkMode: always`，不讓離線狀態把控制排到未來自行執行。框架依據：[TanStack invalidation](https://tanstack.com/query/latest/docs/framework/react/guides/invalidations-from-mutations)、[network mode](https://tanstack.com/query/latest/docs/framework/react/guides/network-mode)。
- `pause_requested` 已由後端 owner 加入公開契約並正式生成；active＋true 才顯示「等待安全點」，paused 才宣告已暫停。`allowed_controls: [cancel]` 也可能表示 supervisor 停止，不能單靠它推導正在停妥。重開頁面查原 execution 仍可還原等待狀態，瀏覽器只保留既有 IDs，不存正文／控制效果。
- 三項代表測試通過：pause→等待時 reload→安全點→鍵盤同 Turn resume、cancel 回覆遺失後 GET 確認並以新 identity 重試原話、離線 pause 失敗不冒稱暫停／不排延後控制。既有 App 測例改為真按下取消控制，驗證候選移除但原正式 JD 保留。

### 本輪命令與接線

- Web：`node node_modules/vitest/vitest.mjs run src/app/App.test.tsx src/features/interview/InterviewComposer.test.tsx src/features/interview/ConsultantTurnControls.test.tsx src/features/jd-editor/JdCandidatePreview.test.tsx` → **26 passed**。
- API：指定測試 DSN、`.venv-target/Scripts/python.exe -m pytest -p no:cacheprovider tests/contracts/test_consultant_turn_contract.py tests/integration/test_consultant_http_controls.py tests/integration/test_consultant_status.py -q` → **15 passed**（14 真 PG owned schema＋1 contract；無 provider）。
- `node node_modules/typescript/bin/tsc --noEmit`、本輪六個 TS／TSX 檔的 ESLint、Prettier `--check` 均 exit 0。初次 Red 為尚未新增的公開控制／暫停意圖契約不被既有 validator 接受；未把此 Red 當資料庫行為反例。
- API client 對已核路徑 `POST /api/job-files/{file}/consultant-turns/{execution}/{pause|cancel|resume}` 發無 body 請求；生成型別與 Ajv 均沿同一 `consultant-turn.schema.json`。前端沒有手寫第二套 wire 格式。
- `InterviewComposer` 已直接組裝控制元件，`JobFilePage` 不需新 props 或額外接線。後端沿 `app.state.consultant_control_workflow` 與既有 router；主線已注入 controller／wrapper／saver，若 Demo process 尚是舊程式，須由主線依身分確認後重啟以載入新 required 欄位。

UI worker 本輪改 `InterviewComposer`、`interview-turn-api`、新增 `ConsultantTurnControls` 與其測試，補 Composer／App fixtures 及本 evidence；schema／status／HTTP／生成檔由 Pascal 修改。未改 bootstrap、模型工具、provider、`.env`，未提交。這是 mock UI＋真 PG HTTP 的有界驗證，尚未新增 IAB 控制旅程或真模型暫停測試，不取代整項 T09／T12 gate。

## 正式歷史回答的公開訊息回看（2026-09-30）

本節屬 **T09**，不是 T12 故障整合；不更改任務 gate。原 history 只有 source／序號／speaker／text，不能用當前 browser hint 或序號猜原 Turn。Kuhn 在原 interviews owner 增加 HTTP 專用 `messages[].execution_id`（required UUID 或 null，僅正式 consultant reply 有值），schema／生成及後端驗證見 [locator evidence](t09-history-turn-locator.md)。沒有新增 store／endpoint，Agent source DTO 不含此定位。

前端 `InterviewHistory` 僅為具有 locator 的顧問回答組裝 `HistoricalTurnMessages`。按鈕可用鍵盤展開，才以原 file＋execution GET 既有 consultant status；收合即卸載讀取，歷史不另輪詢或預載所有 Turn。改換 file／Turn 重設展開狀態，不依賴 localStorage hint。只顯示既有 allowlist commentary，與當輪元件共用 `PublicCommentaryContent` 純文字呈現／原順序／非正式不可引用標示，不顯示原輸入、候選、控制、reasoning 或 tools metadata。

讀取失敗保留錯誤及純 GET 重試；`commentary:null` 明示 reader 不可用，`[]` 明示沒有已保存公開中間訊息，不冒充同一狀態。正式歷史序號未給中間訊息使用。非正式 cancelled／failed Turn 不因本入口混入正式歷史。

### 實際驗證

- 基線全前端 64 passed；新增 6 項（歷史 reply 各自定位、按需／鍵盤讀取、順序／純文字、錯誤重試、null／空清單、foreign scope／私有欄位拒絕）後，`node node_modules/vitest/vitest.mjs run` → **13 files、70 passed**。展開讀取及正式歷史列入口均先觀察功能 Red，再轉 Green；新檔尚未存在時的 import error 不算行為反例。
- `node node_modules/typescript/bin/tsc --noEmit` → exit 0；`node node_modules/vite/bin/vite.js build` → exit 0，`dist` 成功產出。既有大 chunk 警告仍在：本輪 JS 約 774.11 kB（gzip 230.07 kB）；不藉此擴做 bundle 重構或假稱效能 gate 通過。
- 受影響六個 TS／TSX 檔 ESLint／Prettier check 通過；沒有新增瀏覽器付費輸入／provider 外送，也未啟停主線程序。

UI 改檔：`InterviewHistory.tsx`、`PublicTurnMessages.tsx`、`App.test.tsx` fixture；新增 `HistoricalTurnMessages.tsx`、`HistoricalTurnMessages.test.tsx`、`InterviewHistory.test.tsx`。未改 backend/schema/generated/bootstrap；主線不需新 UI props，只需 API process 載入 Kuhn 的新 history required 欄位。完整前端打包與 mock 測試不代替真實 IAB 歷史回看驗收。

## 整合與焦點競爭修正（2026-09-30）

建立／改名 Dialog 的 transition 完成時原本會搶回焦點，可能讓已在姓名欄輸入的後半段落到檔案名稱。以受控轉場重現兩個反例後，共用既有保護語意的 `shared/ui/dialog-focus`；已在對話框內操作時不再搶焦點，保留 MUI focus trap。JD 編輯器也使用同一 helper，沒有新增表單框架。

主線獨立執行全前端：**15 files、86 passed**；TypeScript 與 production build exit 0。bundle 約 777.47 kB（gzip 231.22 kB）的既有警告留 T15，不宣称已完成效能驗收。真模型三輪訪談、兩批 Memory 及第三輪暫停→重開→同輪續作的證據見 [T08 §5](t08-consultant-turn.md#5-真模型-demo-驗收2026-09-30)。以上沒有宣稱逐字 SSE 已接通。
