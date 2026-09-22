# Web 優化 階段1b:跨重載持久化（穩定版 persistQueryClient,選擇性)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 用 TanStack 官方**穩定版** `PersistQueryClientProvider` + localStorage,**選擇性**把批次 `task-catalogs` 與 `header-meta` 快取持久化到瀏覽器,讓重新整理頁面後不必重打 indexer;`document`（of-record）絕不持久化。

**Architecture:** `Providers` 改用 `PersistQueryClientProvider`，掛 `createSyncStoragePersister`（localStorage）。用 `dehydrateOptions.shouldDehydrateQuery` + query `meta:{persist:true}` 只存標記過的 query。重載時 `task-catalogs` 批次自 localStorage 還原 → 既有 seeding effect 重新灌各任務快取 → 開填格/級別 0 等待。`buster` 綁 schema 版本、`maxAge` 24h、被持久化 query `gcTime ≥ maxAge`。

**Tech Stack:** TanStack Query v5（穩定 `persistQueryClient` 家族）。新增 2 個官方第一方套件。前端驗證三道綠 + 手動重載驗證（web 無單元測試框架）。

## Global Constraints

- **依賴 pin 對齊** `@tanstack/react-query@5.100.10`（見 `apps/web/package.json`）：新套件同版號 `5.100.x`。
- **只持久化** `task-catalogs`（批次）與 `header-meta`；**絕不**持久化 `document`/`profiles`/`task-candidates`。
- monorepo 用**單一 root lockfile**（npm workspaces）；安裝走 `-w @caliburn/web`，commit 連 root `package-lock.json`。
- 前端驗證:`cd apps/web && npx tsc --noEmit`、`npm run lint`、`npm run build`。
- 一 task 一 commit,綠了才 commit;**不要 push**。
- **不在本階段**:QueryClient 其他全域預設（D-3b，可選、另議);O/P code 消費（階段 2b）。

## File Structure

- `apps/web/package.json` + root `package-lock.json` — 新增 2 依賴。
- `apps/web/src/components/layout/Providers.tsx` — `QueryClientProvider` → `PersistQueryClientProvider` + persister + 選擇性 dehydrate。
- `apps/web/src/hooks/useTaskCatalog.ts` — 批次 query 加 `meta:{persist:true}` + `gcTime`。
- `apps/web/src/hooks/useDocument.ts` — `useHeaderMeta` 加 `meta:{persist:true}` + `gcTime`。

---

### Task 1: 加依賴 + 改用 `PersistQueryClientProvider`（選擇性持久化骨架）

**Files:**
- Modify: `apps/web/package.json`（+ root `package-lock.json`，由 npm 自動）
- Modify: `apps/web/src/components/layout/Providers.tsx`

**Interfaces:**
- Consumes:`@tanstack/react-query`（`QueryClient`、`defaultShouldDehydrateQuery`）、`@tanstack/react-query-persist-client`（`PersistQueryClientProvider`）、`@tanstack/query-sync-storage-persister`（`createSyncStoragePersister`）。
- Produces:選擇性持久化的 Provider；此 task 後**尚無 query 標記 meta → 實際不持久化任何東西**（安全 no-op，骨架就緒）。

- [ ] **Step 1: 安裝 2 個官方套件（pin 對齊 react-query）**

Run（於 `s:\caliburn`）：
```bash
npm install -w @caliburn/web \
  @tanstack/react-query-persist-client@5.100.10 \
  @tanstack/query-sync-storage-persister@5.100.10
```
> 若該 patch 版不存在,改用同 minor 最新:`@5.100`。安裝後 `apps/web/package.json` 應出現這兩個 dependency。

- [ ] **Step 2: 改寫 `Providers.tsx`**

整檔換成：
```tsx
"use client";

import { QueryClient, defaultShouldDehydrateQuery } from "@tanstack/react-query";
import { PersistQueryClientProvider } from "@tanstack/react-query-persist-client";
import { createSyncStoragePersister } from "@tanstack/query-sync-storage-persister";
import { CopilotKitProvider } from "@copilotkit/react-core/v2";
import { useState } from "react";

// 持久化版本印記:schema/契約破壞性變更時 bump → 自動失效舊快取（spec D-1d）。
const PERSIST_BUSTER = "ocs-v4-1";
const MAX_AGE = 1000 * 60 * 60 * 24; // 24h；被持久化 query 的 gcTime 需 ≥ 此值。

export function Providers({ children }: { children: React.ReactNode }) {
  const [qc] = useState(() => new QueryClient());
  // storage 在 SSR（無 window）給 undefined → createSyncStoragePersister 自動 noop。
  const [persister] = useState(() =>
    createSyncStoragePersister({
      storage: typeof window !== "undefined" ? window.localStorage : undefined,
      key: "caliburn-rq-cache",
    }),
  );
  return (
    <PersistQueryClientProvider
      client={qc}
      persistOptions={{
        persister,
        maxAge: MAX_AGE,
        buster: PERSIST_BUSTER,
        // 只持久化標了 meta.persist 的 query（task-catalogs/header-meta）；document 不存。
        dehydrateOptions: {
          shouldDehydrateQuery: (q) =>
            defaultShouldDehydrateQuery(q) && q.meta?.persist === true,
        },
      }}
    >
      <CopilotKitProvider runtimeUrl="/api/copilotkit">{children}</CopilotKitProvider>
    </PersistQueryClientProvider>
  );
}
```

- [ ] **Step 3: 三道綠**

Run（於 `s:\caliburn\apps\web`）：
```bash
npx tsc --noEmit && npm run lint && npm run build
```
Expected: tsc 無輸出;lint exit 0;build 成功。

- [ ] **Step 4: 手動 smoke（不應壞既有行為）**

`npm run up` + `turbo dev`,開 dashboard 與一份文件,確認頁面正常（持久化此時尚未實際生效,僅驗 Provider 換掉沒壞）。

- [ ] **Step 5: Commit**

```bash
git add apps/web/package.json package-lock.json apps/web/src/components/layout/Providers.tsx
git commit -m "feat(web): PersistQueryClientProvider with selective (meta-based) persistence [spec D-1d]"
```

---

### Task 2: 標記 `task-catalogs` 與 `header-meta` 為可持久化

**Files:**
- Modify: `apps/web/src/hooks/useTaskCatalog.ts`（`useTaskCatalogs` 的 useQuery）
- Modify: `apps/web/src/hooks/useDocument.ts`（`useHeaderMeta` 的 useQuery）

**Interfaces:**
- Consumes:Task 1 的 `shouldDehydrateQuery`（讀 `q.meta.persist`）。
- Produces:`task-catalogs`、`header-meta` 兩 query 帶 `meta:{persist:true}` + `gcTime: 24h` → 實際被寫入 localStorage、重載還原。

- [ ] **Step 1: `useTaskCatalogs` 批次 query 加 meta + gcTime**

在 `apps/web/src/hooks/useTaskCatalog.ts` 的 `useTaskCatalogs` 內,`useQuery` 物件加兩個欄位:
```typescript
  const q = useQuery({
    queryKey: ["task-catalogs", profileId],
    queryFn: () => getTaskCatalogs(profileId),
    enabled,
    staleTime: STALE,
    gcTime: 1000 * 60 * 60 * 24, // ≥ persist maxAge(24h)，否則被 GC 早於還原期限
    refetchOnWindowFocus: false,
    meta: { persist: true }, // 准予持久化（spec D-1d）
  });
```

- [ ] **Step 2: `useHeaderMeta` 加 meta + gcTime**

在 `apps/web/src/hooks/useDocument.ts` 的 `useHeaderMeta`:
```typescript
export function useHeaderMeta(profileId: string, enabled: boolean) {
  return useQuery({
    queryKey: ["header-meta", profileId],
    queryFn: () => getHeaderMeta(profileId),
    enabled,
    staleTime: 5 * 60 * 1000,
    gcTime: 1000 * 60 * 60 * 24, // ≥ persist maxAge
    refetchOnWindowFocus: false,
    meta: { persist: true },
  });
}
```

- [ ] **Step 3: 三道綠**

Run（於 `s:\caliburn\apps\web`）：
```bash
npx tsc --noEmit && npm run lint && npm run build
```
Expected: 全綠。

- [ ] **Step 4: 手動驗證（持久化生效）**

`npm run up` + `turbo dev`,開一份有任務的文件:
1. DevTools → Application → Local Storage → 應見 key `caliburn-rq-cache`,內含 `task-catalogs`/`header-meta`（**不含** `document`）。
2. **重新整理頁面** → Network:**不應**再發 `GET …/task-catalogs`（自 localStorage 還原);開填格/級別仍 0 等待。
3. DevTools 確認 localStorage **沒有** document 內容（of-record 不持久化）。
Expected: 上述成立。

- [ ] **Step 5: Commit**

```bash
git add apps/web/src/hooks/useTaskCatalog.ts apps/web/src/hooks/useDocument.ts
git commit -m "feat(web): persist task-catalogs + header-meta across reloads (meta.persist)"
```

---

## Self-Review

- **Spec coverage:** 對應研究紀錄 §1 D-1d（修正後的穩定版）。選擇性持久化（排除 document）= Task 1 的 `shouldDehydrateQuery` + Task 2 的 meta 標記。
- **Placeholder scan:** 無 TBD/TODO;每步含實際碼與指令。
- **Type consistency:** `shouldDehydrateQuery` 讀 `q.meta?.persist`（Task 1）⇄ Task 2 設 `meta:{persist:true}`,鍵名一致;`gcTime`(24h) ≥ `MAX_AGE`(24h)。
- **安全:** Task 1 後無 query 標 meta → 不持久化任何東西（骨架安全);SSR storage=undefined → persister noop。`document` 永不帶 meta → 不入 localStorage。
- **風險:** 低。最壞情況持久化失效則退回每次重抓（現狀),不影響正確性。`buster` 改變即整批失效。
