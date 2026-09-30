# T09 最小 commentary 串流 UI

狀態：2026-09-30 有界前端切片已實作並通過 mock UI／型別／打包驗證；未做真 API、SSE 網路或瀏覽器驗收，不代表整項 T09 完成或正式產品已切換。

責任依 [Goal／任務入口](../README.md)、[介面 §2–3](../../../implementation/interface-and-delivery.md)及 [契約策略](../../../contract-strategy.md)。既有已保存訊息與歷史回看見 [T09 前切片](t09-consultant-preview.md)。

## 接線與邊界

- `InterviewComposer` 只在同 file／execution 經 GET 確認 `active` 時掛載 `StreamingPublicTurnMessages`，以兩個 ID 作 React key。`paused`／終態、換檔或卸載會關閉原訂閱，disposed callback 也拒收排隊中的遲來事件。沒有 hint-only 訂閱。
- interview 專用 `useConsultantCommentaryStream` 使用原生 `EventSource`，URL 是 `GET /api/job-files/{file}/consultant-turns/{execution}/commentary-stream`；只監聽 `commentary`、`open`、`error`，不處理 SDK 原始事件或自行切 SSE framing。
- runtime guard 直接編譯 Kuhn 提供的 [commentary-update 正式 schema](../../../../apps/api/contracts/http/commentary-update.schema.json)，型別直接 import 同源生成的 `CommentaryUpdate`。恰為 `job_file_id`、`execution_id`、`response_id`、`message_id`、`text`；extra 欄位或 foreign scope 事件整筆拒絕。本 worker 未手寫或修改 schema／生成檔。
- `text` 是同訊息的累積全文，按 `(response_id, message_id)` 取代而非拼接。純文字 React 呈現，不執行 HTML；標示「即時公開訊息（尚未保存、非正式訪談、不可引用）」。沒有正式訪談序號或 source identity。
- status 已保存的同身分訊息優先，串流不得覆蓋；已保存 `text: ''` 合法，不能用未保存舊字串補回。`commentary: []` 與 reader 不可用的 `null` 沿既有語意處理。
- 暫態只在 mounted 元件 state，沒有新 store／localStorage／全域 cache；也不把串流 payload 寫入 React Query。歷史回看仍只讀已保存 status，不掛串流。
- `open`／`error` 只 invalidate 原 execution status GET。原生 EventSource 自行處理可重連情形；`CLOSED` 只提示即時顯示中斷，並不 cancel／submit／resume，也不自行重建 EventSource 迴圈。重連時丟棄舊暫態基線，重新依已保存 GET 與之後累積全文顯示，不承諾事件 replay。
- 終態、正式歷史／JD invalidation、候選預覽與控制都保留既有 status 權威。未知 `done` 事件、斷線及連線關閉均不能宣告完成或改 command identity。

主線不需新增 UI props 或 JobFilePage 接線；僅需後端同源路由與 public allowlist 上線。慢讀 drop／超大訊息不投遞時，既有 status polling 仍為已保存內容的恢復來源；本輪未對真後端慢讀行為作驗證。

## TDD 與實際命令

工作目錄 `S:/caliburn/apps/web`，2026-09-30 約 11:47–11:52（Asia/Taipei）：

- Red：`node node_modules/vitest/vitest.mjs run src/features/interview/InterviewComposer.stream.test.tsx` → **8 failed**，斷言均觀察到原 UI 沒有建立訂閱，而非 missing import／編譯錯誤。
- 接線後首輪 3 passed／5 failed；五例是 query invalidation 完成後尚未送達 React 畫面的測試同步問題。改為等待實際已保存文字／close 可觀察結果，沒有 sleep、移除斷言或放寬結果。相同命令 → **8 passed**。
- 補初始狀態未確認／已完成不得訂閱的第九例；`node node_modules/vitest/vitest.mjs run` → **16 files、95 passed，exit 0**。
- `node node_modules/typescript/bin/tsc --noEmit` → **exit 0**。
- `node node_modules/eslint/bin/eslint.js src/features/interview/use-consultant-commentary-stream.ts src/features/interview/PublicTurnMessages.tsx src/features/interview/InterviewComposer.tsx src/features/interview/InterviewComposer.stream.test.tsx src/shared/api/validation.ts` → **exit 0**。
- `node node_modules/prettier/bin/prettier.cjs --check src/features/interview/use-consultant-commentary-stream.ts src/features/interview/PublicTurnMessages.tsx src/features/interview/InterviewComposer.tsx src/features/interview/InterviewComposer.stream.test.tsx src/shared/api/validation.ts` → **exit 0**。
- `node node_modules/vite/bin/vite.js build` → **exit 0**。JS 779.79 kB、gzip 231.79 kB；既有 >500 kB chunk 警告仍在，不宣稱效能 gate 完成。

新九例涵蓋精確 URL、active 准入、累積全文去重、私有／錯 scope／SDK 原始事件拒絕、HTML 轉義、不存正文、已保存優先與合法空字串、斷線／原生重連／CLOSED 不送指令不改 identity、四種離開 active 的狀態、StrictMode／換檔／直接呼叫舊 callback 的隔離。既有完整前端回歸也包含取消、暫停、未知受理、歷史回看與 Undo。

## 改檔與限制

本 worker 只修改 `InterviewComposer.tsx`、`PublicTurnMessages.tsx`、`shared/api/validation.ts`，新增 interview hook、`InterviewComposer.stream.test.tsx` 與本 evidence。沒有修改其他 UI／API／bootstrap／generated，沒有提交、子代理、provider 外送、瀏覽器操作、`.env` 讀取或服務重啟。

依 executing-plans／TDD 做有界接線與反例，verification-before-completion 要求 fresh evidence；使用者 scope 優先，未另外建立工作樹、計畫平台或 ledger。自行複核所有改動及生命週期，沒有獨立 reviewer。`EventSource` 原生網路、proxy buffering、真 provider commentary 白名單／慢讀背壓與重連的整合結果由後端／主線切片驗收；本頁不以 mock 通過代替它們。
