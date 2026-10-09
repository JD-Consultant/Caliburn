# Caliburn frontend

正式前端以 React／TypeScript／Vite／MUI 建置，供操作者管理職務檔案、進行訪談及編修 JD。

- **職務檔案：**建立、列出、改名、選取與確認刪除資料隔離的檔案。整份刪除包含訪談、JD、Memory 與執行紀錄，不能復原；有未結束工作時不能刪除。
- **訪談：**送出輸入（Enter 送出、Shift＋Enter 換行；輸入法組字中的 Enter 不送出）、暫停／繼續／取消，查看即時與已保存的公開訊息、回看歷史及依條件撤回。
- **工作計畫：**展開同份唯讀 Markdown，查看焦點、工作方向與剩餘安排。顧問處理／暫停時可看候選，終局重新讀採用版；刷新失敗保留上一版並標示。空值不表示 JD 已完整，契約與驗證見 [Plan 保存與採用](../../docs/architecture/persistence.md#plan-從本輪候選到後輪可採用)。
- **JD：**人工編輯基本資料、職責與任務、成果／要求、知識／技能、協作與共通條件；顧問處理中可預覽候選 JD。
- **核對與交付：**回查正式 JD 來源與待核對標示（含 JD 項目旁的來源徽章），透過章節導覽及可收合職責閱讀內容，匯出正式 JD 為 PDF。

畫面為**左訪談／右 JD 並排**，窄螢幕以分頁切換。訪談輸入與處理控制固定在訪談欄底部；顧問處理或暫停時 JD 唯讀，候選預覽以獨立的「候選」樣式呈現，不取代正式稿。

依 [正式產品與選型](../../docs/architecture/design-decisions.md)，根 `dev/start/build` 已切換至 `apps/api`／`apps/web`，舊正式產品已退役。切換不代表所有品質情境都已驗證；限制見[架構驗證](../../docs/architecture/verification.md)。

字型為自架的 Inter 與 Noto Sans TC 可變字型（SIL OFL，授權隨套件），不對外連線。

## 開發與檢查

首次使用完整 App，從[快速開始](../../docs/operations/getting-started.md)安裝及啟動。下方說明前端開發；使用 `pnpm dev` 時，在啟動的終端按 Ctrl+C 停止，重新提供所需後端環境設定後可再次啟動。

介面行為與讀寫規則見[介面設計](../../docs/implementation/interface-and-delivery.md)，模組與程式寫法見[程式組織](../../docs/standards/code-organization.md)及[撰寫規範](../../docs/standards/coding-standard.md)。UI 與來源功能的執行原件只在本機保存；各次結果只支持當時受測範圍，不能由文件改版推定目前全部情境已通過。

正式 JD 來源按項目分組，各筆引用分別標示「JD 已修改」「來源已更新」或兩者；「查看差異」可按需展開 JD 內容與 Memory 來源的比較。JD 從該筆引用上次核對的修訂比較到目前正式稿，不限於上一輪；訪談原話不可改寫，因此只提供 JD 內容比較。查看不解除待核對。契約與驗證見[來源介面規範](../../docs/implementation/interface-and-delivery.md#31-正式-jd-來源的唯讀下鑽)。新增差異欄位需前後端一起更新，開發程序須載入同一版契約；不放寬前端驗證去接受舊格式。

顧問處理中可展開「推理摘要」，完成後從歷史回答的「處理紀錄」查看已保存摘要與處理過程；JD 查看／撤回按鈕另列，不顯示「JD 操作」標題。摘要與公開進度分開，不是完整內部思考，也不是可引用的正式訪談。前端只訂閱一條 `activity-stream`；重連／終態透過摘要 GET 補讀，不為回看而重跑模型。須搭配已提供這兩個入口的後端；錯誤不當成沒有摘要。接線與本輪驗證見 T09 推理摘要。

使用 `pnpm dev` 同時啟動前後端前，先依[原生開發](../../docs/operations/native-development.md)完成工具、資料庫與所需功能設定及首次初始化。以下從 repo root 使用 Node 24 及根 `packageManager` 指定的 pnpm：

```powershell
pnpm install --frozen-lockfile
pnpm dev      # 後端 :8100 與 Vite :5173 同時啟動（只開前端：pnpm --filter @caliburn/frontend dev）
```

開發站固定 `127.0.0.1:5173`；`/api` 代理到 `127.0.0.1:8100`。僅啟動前端時，後端另依[backend README](../api/README.md#後端入口pnpm-startpnpm-dev-所用)啟動。Ctrl+C 停止前景程序；不載入舊 Next.js 或 `.next` 生成物。

不使用 Vite 的本機建置模式：先 `build`，再由後端以 `CALIBURN_WEB_BUILD_DIRECTORY` 指向此 App 的 `dist` 絕對目錄，同一個 loopback 8100 提供畫面與 API；根 `pnpm build`／`pnpm start` 已接好此流程，見[同源啟動說明](../api/README.md#使用建置後的同源畫面)。現有 `/`、`/job-files/:jobFileId` 可直接開啟及重新整理；新增頂層 UI 路由須同步後端的明確 fallback 前綴。

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
uv sync --project apps/api --locked
pnpm --filter @caliburn/frontend codegen:check
```

`src/shared/api/generated` 只由後端 schema 生成，runtime guards 也使用相同 JSON Schema。不要為 TypeScript 另外手寫相同 wire 型別。路由在 `src/app`，檔案與訪談畫面分在 `src/features`；保存／快取／重送界線見[介面設計 §1.1](../../docs/implementation/interface-and-delivery.md#11-讀寫邊界)。

沒有本機 Turn 提示時，訪談區會先查後端 `/consultant-turns/current`，找回原進行中／暫停工作與控制，不重送訪談。未確認狀態前 JD 暫時唯讀、新輸入不能送出；失敗可按「重新查詢進行中處理」。既有未知命令仍查回原請求，不被空 current 取代。此版須搭配包含 current 入口的後端；只更新前端而未重啟舊後端可能得到 422／查詢錯誤，不應以忽略錯誤解鎖。證據與限制見發現入口。

開啟職務檔案後，JD 基本資料的職務名稱、所屬單位／工作範圍、匯報關係與職務目的可**點一下就地逐欄修改**（沒有「編輯基本資料」按鈕或表單）。每次只提交這一欄，刪空為清空；過期的編輯須重讀，不自動覆蓋。結果不明時在原處重新確認原命令，reload 也可用原命令確認，再讀目前稿。此為本分頁有限恢復，不承諾清除瀏覽器資料後保留暫存；具體責任見[介面 §1.2](../../docs/implementation/interface-and-delivery.md#12-基本資料編輯的讀取基底與恢復)。

「JD 職責與任務」支援新增、修改、排序、跨職責移動及刪除。刪職責會把任務保留在「未歸屬任務」，不刪內容；成果與要求分組維護、可獨立排序。

新增職責時，在職責清單末端就地輸入名稱，範圍之後在原處補。新增任務、知識／技能、協作對象與條件使用表單。編輯與搬移沒有整項編輯鈕（✎ 已拿掉）：任務與條件工具列的「移到…」選單搬職責／更正分類，清單標籤旁的「+」新增成果或要求，每項的 × 先確認再移除。

既有文字（含成果／要求、知識／技能、協作對象與條件的文字）可**點一下就地逐欄修改**：單行 Enter、多行 Ctrl／⌘＋Enter 儲存，Esc 取消。每次儲存是一筆單欄命令；基本資料與集合一次只開一個編輯。沒有 hover 的裝置會在標題下多看到一行說明。

表單與就地編輯器都固定讀取基底。結果不明時，在原處或區塊入口重新確認原命令；即使原目標後來已刪除，也不會被舊回傳復活。具體規則見[介面 §1.7](../../docs/implementation/interface-and-delivery.md#17-逐欄就地編輯)。

「JD 職責與任務」整段（所有職責、任務、「新增職責」列與未歸屬任務）可收合，「未歸屬任務」也能單獨收合。所需知識、所需技能、主要協作對象與工作條件與責任邊界四個區塊各自可收合，都預設展開；章節導覽跳到收合的區塊時會先打開它。詳見[介面 §1.3](../../docs/implementation/interface-and-delivery.md#13-職責與任務的人工編輯)。

「所需知識／技能」可增修刪共用定義、各自排序，並列出使用該定義的任務。每項任務可選用、解除與排序知識／技能；選取後即保存，解除不刪定義。共用說明改動反映所有用途，仍被使用時不能刪定義。資料全部來自同版組合讀取，命令沿同一待確認入口，不因舊回傳復活已刪或覆蓋較新內容。詳見[介面 §1.4](../../docs/implementation/interface-and-delivery.md#14-共用知識技能及任務關係的人工編輯)。

「主要協作對象」可先只記已知合作範圍，之後補名稱，並可排序或刪除。「工作條件與責任邊界」可增修刪共通條件、分類內排序及明確更正分類；保留原項目身分，不自動套用到任務。兩者沿同版集合讀取及原命令恢復。詳見[介面 §1.5](../../docs/implementation/interface-and-delivery.md#15-協作對象與共通條件的人工編輯)。

## 合成資料瀏覽器驗收

先依 backend README 以**專用空白測試 DB／namespace**初始化並啟動後端，再啟動此 Web。勿指向現行員工資料；測試會建立合成檔案，不刪既有資料。明確提供 loopback URL，不自動接任意現有站點：

```powershell
pnpm --filter @caliburn/frontend exec playwright install chromium
$env:CALIBURN_E2E_BASE_URL = 'http://127.0.0.1:5173'
pnpm --filter @caliburn/frontend test:e2e
```

第二組前端可指向另一個隔離後端。在**隔離後端的終端**先設定 `$env:CALIBURN_DEV_ORIGIN = 'http://127.0.0.1:5174'` 再啟動 8101；在**第二組前端的終端**設定 `$env:CALIBURN_API_PROXY = 'http://127.0.0.1:8101'` 後另開 `vite --host 127.0.0.1 --port 5174 --strictPort`，並將測試 URL 設為 5174。後端只增加這一個精確 loopback Origin，不允許任意本機埠；proxy 保留原 Origin，不偽裝成 5173，也不新增 CORS 許可。`test:proxy` 用實際 Vite config 與臨時 loopback HTTP server 驗證標頭保留，不接 Demo／資料庫／模型。

Playwright 依 lock 的 Chromium 版本執行，另開隔離 context、不使用個人瀏覽器 profile。若安裝器受環境限制，`CALIBURN_E2E_CHROMIUM_PATH` 可明確提供已核對該 release 版本的 binary；未驗的跨版本不能視為等價證據。`test-results` 的故障 trace／截圖不入版控，僅供合成測試，避免對真實員工資料留無限紀錄。

目前 `tests/e2e` 驗建立／同名選取／reload／鍵盤／窄螢幕、大寫 UUID 網址與小寫指向同一份檔案（`uuid-route.spec.ts`：唯一一次小寫 POST、唯一 hint key、原命令重開查回）、列表改名不改訪談／姓名、POST 真提交後故意丟回應再確認、舊改名重送不覆蓋較新名稱、列表連線失敗；另驗 JD 四欄／局部清空、職責／任務 CRUD／排序／移動、刪職責保留任務、共用知識／技能 CRUD 及多任務使用、反向用途、獨立排序、共用修訂刷新、協作與條件 CRUD／更正分類、過期基底與 A 准入拒絕新人工修改，以及 JD 提交回應遺失後沿原命令確認且呈現最新稿；`jd-structure.spec.ts` 另驗沒有 ✎、移到選單搬職責與更正分類、「+」新增與 × 移除各只送一筆命令，以及觸控裝置才看得到說明行；`jd-inline-edit.spec.ts` 另驗就地編輯（點文字改一欄、Enter／Ctrl＋Enter／Esc、其他控制項讓位、丟回應後在原處重新確認原命令、輸入法組字中的 Enter 不送出、窄螢幕）；`workspace.spec.ts` 另驗左右並排、整頁不捲動、章節導覽、職責、未歸屬任務、整段職責與任務與四個輔助區塊的收合，以及導覽跳到已收合的區塊時先展開它；`forced-colors.spec.ts` 另驗 Windows 高對比（強制色彩）下輸入器、送出鈕、說話者頭像、目前章節、聚焦與對話框仍有實線邊界或外框（該模式會移除陰影與底色）。後端是真 PostgreSQL；fault injection 用 Playwright network routing，不以 mock 成功回應代替 DB 提交。此 gate 不驗模型品質、Memory 恢復或完整安全。

顧問處理中的畫面行為（即時公開訊息、JD 唯讀、重開與另一分頁找回、暫停／續作、取消、被拒絕、PDF）用 `consultant-journey.spec.ts`，對象是**腳本化模型的隔離後端**（`apps/api/tests/fixtures/scripted_backend.py`，只替換 SDK 的 HTTP transport，其餘為真後端與 PostgreSQL），需另設 `CALIBURN_E2E_SCRIPT_URL`；沒設就 skip，skip 不代表通過。它是合成替身，不驗模型品質。
