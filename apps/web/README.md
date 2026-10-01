# Caliburn frontend

React／TypeScript／Vite／MUI 的新前端。可建立、列出、改名與選取隔離職務檔案；與 AI 顧問訪談（送出輸入、暫停／繼續／取消、即時與已保存的公開訊息、歷史回看與條件撤回）；JD 人工編輯（基本資料、職責與任務、成果／要求、知識／技能、協作、共通條件）；顧問處理中的候選 JD 預覽；正式 JD 來源回查與待核對標示（含 JD 項目旁的來源徽章）；章節導覽與可收合職責；匯出正式 JD 為 PDF。畫面為**左訪談／右 JD 並排**（窄螢幕以分頁切換）：訪談輸入與處理控制固定在訪談欄底部；顧問處理或暫停時 JD 唯讀、候選預覽以獨立的「候選」樣式呈現，不取代正式稿。這不是完整產品驗收：真模型長訪談、故障競爭與品質 gate 仍屬 T12／T14–T17。現行根 `dev/start/build` 仍指向舊正式產品；後續依[任務計畫](../../docs/plans/2026-09-29-target-rebuild/tasks.md)逐步接線，最後才正式切換。視覺規則與已驗／未驗範圍見 [UI 改版證據](../../docs/plans/2026-09-29-target-rebuild/evidence/t09-ui-redesign.md)。

## 開發與檢查

從 repo root 使用 Node 24 及根 `packageManager` 指定的 pnpm：

```powershell
pnpm install --frozen-lockfile
pnpm dev      # 後端 :8100 與 Vite :5173 同時啟動（只開前端：pnpm --filter @caliburn/frontend dev）
```

開發站固定 `127.0.0.1:5173`；`/api` 代理到 `127.0.0.1:8100`。後端啟動依[backend README](../api/README.md)。Ctrl+C 停止前景程序；不載入舊 Next.js 或 `.next` 生成物。

不使用 Vite 的本機建置模式：先 `build`，再由後端以 `CALIBURN_WEB_BUILD_DIRECTORY` 指向此 App 的 `dist` 絕對目錄，同一個 loopback 8100 提供畫面與 API；見[同源啟動說明](../api/README.md#使用建置後的同源畫面)。現有 `/`、`/job-files/:jobFileId` 可直接開啟及重新整理；新增頂層 UI 路由須同步後端的明確 fallback 前綴。此功能不是 T18 正式切換，不改根 scripts。

```powershell
pnpm --filter @caliburn/frontend test
pnpm --filter @caliburn/frontend test:proxy
pnpm --filter @caliburn/frontend typecheck
pnpm --filter @caliburn/frontend lint
pnpm --filter @caliburn/frontend format:check
pnpm --filter @caliburn/frontend build
```

生成契約還需要 uv 及隔離的 Python 環境：

```powershell
$env:UV_PROJECT_ENVIRONMENT = Join-Path $PWD 'apps/api/.venv-target'
pnpm --filter @caliburn/frontend codegen:check
```

`src/shared/api/generated` 只由後端 schema 生成，runtime guards 也使用相同 JSON Schema。不要為 TypeScript 另外手寫相同 wire 型別。路由在 `src/app`，檔案與訪談畫面分在 `src/features`；保存／快取／重送界線見[介面設計 §1.1](../../docs/implementation/interface-and-delivery.md#11-t02-已落地的讀寫邊界)。

沒有本機 Turn 提示時，訪談區會先查後端 `/consultant-turns/current`，找回原進行中／暫停工作與控制，不重送訪談。未確認狀態前 JD 暫時唯讀、新輸入不能送出；失敗可按「重新查詢進行中處理」。既有未知命令仍查回原請求，不被空 current 取代。此版須搭配包含 current 入口的後端；只更新前端而未重啟舊後端可能得到 422／查詢錯誤，不應以忽略錯誤解鎖。證據與限制見[發現入口](../../docs/plans/2026-09-29-target-rebuild/evidence/t09-current-turn-discovery.md)。

開啟職務檔案後，「編輯基本資料」可改職務名稱、所屬單位／工作範圍、匯報關係與職務目的。只提交改動欄位，全部刪空為清空；舊表單衝突須重讀，不自動覆蓋。結果不明時重開或 reload 可用原命令確認，再讀目前稿。此為本分頁有限恢復，不承諾清除瀏覽器資料後保留暫存；具體責任見[介面 §1.2](../../docs/implementation/interface-and-delivery.md#12-t03-基本資料編輯的讀取基底與恢復)。

「JD 職責與任務」支援新增、修改、排序、跨職責移動及刪除；刪職責會把任務保留在「未歸屬任務」，不刪內容。成果與要求分組維護、可獨立排序。編輯表單固定讀取基底；未知結果的原命令可由區塊入口重新確認，即使原目標後來已刪除也不會被舊回傳復活。詳見[介面 §1.3](../../docs/implementation/interface-and-delivery.md#13-t03-職責與任務的人工編輯)。

「所需知識／技能」可增修刪共用定義、各自排序，並列出使用該定義的任務。每項任務可選用、解除與排序知識／技能；選取後即保存，解除不刪定義。共用說明改動反映所有用途，仍被使用時不能刪定義。資料全部來自同版組合讀取，命令沿同一待確認入口，不因舊回傳復活已刪或覆蓋較新內容。詳見[介面 §1.4](../../docs/implementation/interface-and-delivery.md#14-t03-共用知識技能及任務關係的人工編輯)。

「主要協作對象」可先只記已知合作範圍，之後補名稱，並可排序或刪除。「工作條件與責任邊界」可增修刪共通條件、分類內排序及明確更正分類；保留原項目身分，不自動套用到任務。兩者沿同版集合讀取及原命令恢復。詳見[介面 §1.5](../../docs/implementation/interface-and-delivery.md#15-t03-協作對象與共通條件的人工編輯)。

## 合成資料瀏覽器驗收

先依 backend README 以**專用空白測試 DB／namespace**初始化並啟動後端，再啟動此 Web。勿指向現行員工資料；測試會建立合成檔案，不刪既有資料。明確提供 loopback URL，不自動接任意現有站點：

```powershell
pnpm --filter @caliburn/frontend exec playwright install chromium
$env:CALIBURN_E2E_BASE_URL = 'http://127.0.0.1:5173'
pnpm --filter @caliburn/frontend test:e2e
```

第二組前端可指向另一個隔離後端。在**隔離後端的終端**先設定 `$env:CALIBURN_DEV_ORIGIN = 'http://127.0.0.1:5174'` 再啟動 8101；在**第二組前端的終端**設定 `$env:CALIBURN_API_PROXY = 'http://127.0.0.1:8101'` 後另開 `vite --host 127.0.0.1 --port 5174 --strictPort`，並將測試 URL 設為 5174。後端只增加這一個精確 loopback Origin，不允許任意本機埠；proxy 保留原 Origin，不偽裝成 5173，也不新增 CORS 許可。`test:proxy` 用實際 Vite config 與臨時 loopback HTTP server 驗證標頭保留，不接 Demo／資料庫／模型。

Playwright 依 lock 的 Chromium 版本執行，另開隔離 context、不使用個人瀏覽器 profile。若安裝器受環境限制，`CALIBURN_E2E_CHROMIUM_PATH` 可明確提供已核對該 release 版本的 binary；未驗的跨版本不能視為等價證據。`test-results` 的故障 trace／截圖不入版控，僅供合成測試，避免對真實員工資料留無限紀錄。

目前 `tests/e2e` 驗建立／同名選取／reload／鍵盤／窄螢幕、列表改名不改訪談／姓名、POST 真提交後故意丟回應再確認、舊改名重送不覆蓋較新名稱、列表連線失敗；另驗 JD 四欄／局部清空、職責／任務 CRUD／排序／移動、刪職責保留任務、共用知識／技能 CRUD 及多任務使用、反向用途、獨立排序、共用修訂刷新、協作與條件 CRUD／更正分類、過期基底與 A 准入拒絕新人工修改，以及 JD 提交回應遺失後沿原命令確認且呈現最新稿。後端是真 PostgreSQL；fault injection 用 Playwright network routing，不以 mock 成功回應代替 DB 提交。此 gate 不驗模型品質、Memory 恢復或完整安全。

顧問處理中的畫面行為（即時公開訊息、JD 唯讀、重開與另一分頁找回、暫停／續作、取消、被拒絕、PDF）用 `consultant-journey.spec.ts`，對象是**腳本化模型的隔離後端**（`apps/api/tests/fixtures/scripted_backend.py`，只替換 SDK 的 HTTP transport，其餘為真後端與 PostgreSQL），需另設 `CALIBURN_E2E_SCRIPT_URL`；沒設就 skip，skip 不代表通過。它是合成替身，不驗模型品質。步驟與結果見 [T09 旅程證據](../../docs/plans/2026-09-29-target-rebuild/evidence/t09-consultant-journeys.md)。
