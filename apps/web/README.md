# Caliburn frontend（新目標施工中）

React／TypeScript／Vite 的新前端，目前可建立、列出、改名與選取隔離職務檔案，回看 App 正式開場，人工編輯 JD 四欄基本資料。尚無 AI 傳送或其餘 JD 集合／候選／來源編輯，不是完整產品已完成。現行根 `dev/start/build` 仍指向舊正式產品；後續依[任務計畫](../../docs/plans/2026-09-29-target-rebuild/tasks.md)逐步接線，最後才正式切換。

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

## 合成資料瀏覽器驗收

先依 backend README 以**專用空白測試 DB／namespace**初始化並啟動後端，再啟動此 Web。勿指向現行員工資料；測試會建立合成檔案，不刪既有資料。明確提供 loopback URL，不自動接任意現有站點：

```powershell
pnpm --filter @caliburn/frontend exec playwright install chromium
$env:CALIBURN_E2E_BASE_URL = 'http://127.0.0.1:5173'
pnpm --filter @caliburn/frontend test:e2e
```

Playwright 依 lock 的 Chromium 版本執行，另開隔離 context、不使用個人瀏覽器 profile。若安裝器受環境限制，`CALIBURN_E2E_CHROMIUM_PATH` 可明確提供已核對該 release 版本的 binary；未驗的跨版本不能視為等價證據。`test-results` 的故障 trace／截圖不入版控，僅供合成測試，避免對真實員工資料留無限紀錄。

目前 `tests/e2e` 驗建立／同名選取／reload／鍵盤／窄螢幕、列表改名不改訪談／姓名、POST 真提交後故意丟回應再確認、舊改名重送不覆蓋較新名稱、列表連線失敗；另驗 JD 四欄／局部清空、過期基底與 A 准入拒絕新人工修改、JD 提交回應遺失後沿原命令確認且呈現最新稿。後端是真 PostgreSQL；fault injection 用 Playwright network routing，不以 mock 成功回應代替 DB 提交。此 gate 不驗模型、A Turn／Memory 恢復、完整安全、PDF 或品質。
