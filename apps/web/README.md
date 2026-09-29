# Caliburn frontend（新目標施工中）

React／TypeScript／Vite 的新前端，目前可建立、列出、改名與選取隔離職務檔案，回看 App 正式開場，人工編輯 JD 基本資料、職責與任務、獨立成果／要求、共用知識／技能及任務關係。尚無 AI 傳送、協作者／共通條件、候選或來源編輯，不是完整產品已完成。現行根 `dev/start/build` 仍指向舊正式產品；後續依[任務計畫](../../docs/plans/2026-09-29-target-rebuild/tasks.md)逐步接線，最後才正式切換。

## 開發與檢查

從 repo root 使用 Node 24 及根 `packageManager` 指定的 pnpm：

```powershell
pnpm install --filter @caliburn/frontend --frozen-lockfile --strict-peer-dependencies
pnpm --filter @caliburn/frontend dev
```

開發站固定 `127.0.0.1:5173`；`/api` 代理到 `127.0.0.1:8100`。後端啟動依[backend README](../api/README.md)。Ctrl+C 停止前景程序；不載入舊 Next.js 或 `.next` 生成物。

```powershell
pnpm --filter @caliburn/frontend test
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

開啟職務檔案後，「編輯基本資料」可改職務名稱、所屬單位／工作範圍、匯報關係與職務目的。只提交改動欄位，全部刪空為清空；舊表單衝突須重讀，不自動覆蓋。結果不明時重開或 reload 可用原命令確認，再讀目前稿。此為本分頁有限恢復，不承諾清除瀏覽器資料後保留暫存；具體責任見[介面 §1.2](../../docs/implementation/interface-and-delivery.md#12-t03-基本資料編輯的讀取基底與恢復)。

「JD 職責與任務」支援新增、修改、排序、跨職責移動及刪除；刪職責會把任務保留在「未歸屬任務」，不刪內容。成果與要求分組維護、可獨立排序。編輯表單固定讀取基底；未知結果的原命令可由區塊入口重新確認，即使原目標後來已刪除也不會被舊回傳復活。詳見[介面 §1.3](../../docs/implementation/interface-and-delivery.md#13-t03-職責與任務的人工編輯)。

「所需知識／技能」可增修刪共用定義、各自排序，並列出使用該定義的任務。每項任務可選用、解除與排序知識／技能；選取後即保存，解除不刪定義。共用說明改動反映所有用途，仍被使用時不能刪定義。資料全部來自同版組合讀取，命令沿同一待確認入口，不因舊回傳復活已刪或覆蓋較新內容。詳見[介面 §1.4](../../docs/implementation/interface-and-delivery.md#14-t03-共用知識技能及任務關係的人工編輯)。

## 合成資料瀏覽器驗收

先依 backend README 以**專用空白測試 DB／namespace**初始化並啟動後端，再啟動此 Web。勿指向現行員工資料；測試會建立合成檔案，不刪既有資料。明確提供 loopback URL，不自動接任意現有站點：

```powershell
pnpm --filter @caliburn/frontend exec playwright install chromium
$env:CALIBURN_E2E_BASE_URL = 'http://127.0.0.1:5173'
pnpm --filter @caliburn/frontend test:e2e
```

Playwright 依 lock 的 Chromium 版本執行，另開隔離 context、不使用個人瀏覽器 profile。若安裝器受環境限制，`CALIBURN_E2E_CHROMIUM_PATH` 可明確提供已核對該 release 版本的 binary；未驗的跨版本不能視為等價證據。`test-results` 的故障 trace／截圖不入版控，僅供合成測試，避免對真實員工資料留無限紀錄。

目前 `tests/e2e` 驗建立／同名選取／reload／鍵盤／窄螢幕、列表改名不改訪談／姓名、POST 真提交後故意丟回應再確認、舊改名重送不覆蓋較新名稱、列表連線失敗；另驗 JD 四欄／局部清空、職責／任務 CRUD／排序／移動、刪職責保留任務、共用知識／技能 CRUD 及多任務使用、反向用途、獨立排序、共用修訂刷新、過期基底與 A 准入拒絕新人工修改，以及 JD 提交回應遺失後沿原命令確認且呈現最新稿。後端是真 PostgreSQL；fault injection 用 Playwright network routing，不以 mock 成功回應代替 DB 提交。此 gate 不驗模型、A Turn／Memory 恢復、完整安全、PDF 或品質。
