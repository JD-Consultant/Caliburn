# Caliburn frontend（新目標施工中）

React／TypeScript／Vite 的新前端，目前只顯示施工狀態，不是訪談或 JD 編輯產品已完成。現行根 `dev/start/build` 仍指向舊正式產品；後續依[任務計畫](../../docs/plans/2026-09-29-target-rebuild/tasks.md)逐步接線，最後才正式切換。

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

`src/shared/api/generated` 只由後端 schema 生成。不要為 TypeScript 另外手寫相同 wire 型別。此時尚無產品 E2E；不能把單元測試／build 通過稱為 UI 旅程完成。
