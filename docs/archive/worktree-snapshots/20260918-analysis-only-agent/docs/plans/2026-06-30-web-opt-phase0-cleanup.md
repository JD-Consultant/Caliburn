# Web 優化 階段0:清理(刪死代碼) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 移除 `apps/web` 兩個無人 import 的死代碼元件,建立後續優化的綠色打底。

**Architecture:** 純刪除,零行為變更(move-only 的極致:只移除未使用碼)。驗證靠「全 repo grep 無引用 + TypeScript 編譯 + ESLint + Next build」皆綠。

**Tech Stack:** Next.js 16 / React 19 / TypeScript 5 / ESLint 9。web 無單元測試框架,故驗證 = `npx tsc --noEmit` + `npm run lint` + `npm run build`。

## Global Constraints

- 維護者用**繁體中文**;commit message 用英文 conventional commits 即可。
- web 驗證指令固定為:`npx tsc --noEmit`、`npm run lint`、`npm run build`(於 `apps/web` 下)。
- 一個 task 一個 commit;綠了才 commit。**不要 push**。
- 範圍僅限本階段:**只刪這兩個元件檔**。`src/lib/api.ts` 的 `clarify` 等匯出(對映後端 `/ai/*` 端點的契約面)**不動**——即使暫時無前端消費者,屬刻意保留的 API 介面。
- QueryClient 全域預設集中**不在本階段**(移至階段1快取,與 staleTime 政策一起決定)。

---

### Task 1: 刪除死代碼元件 `AiTaskPanel` 與 `FieldBoundSelect`

**Files:**
- Delete: `apps/web/src/components/interview/AiTaskPanel.tsx`
- Delete: `apps/web/src/components/interview/fields/FieldBoundSelect.tsx`

**Interfaces:**
- Consumes: 無。
- Produces: 無(僅移除;不新增任何被他處依賴的符號)。

**背景**:全 repo(排除 node_modules)搜尋,這兩個元件名只出現在各自定義檔,無任何 import 端;確認為死代碼。

- [ ] **Step 1: 動手前先證明真的沒人引用**

Run（於 `s:\caliburn`,Bash 工具)：
```bash
rg -n "AiTaskPanel|FieldBoundSelect" --glob '!**/node_modules/**' apps/web
```
Expected: 只列出 `apps/web/src/components/interview/AiTaskPanel.tsx` 與
`apps/web/src/components/interview/fields/FieldBoundSelect.tsx` 自身(即各自的 `export function …`)。
若出現任何**其他**檔案 → 停手,代表並非死代碼,回報後重新評估。

- [ ] **Step 2: 刪除兩個檔案**

Run（於 `s:\caliburn`,Bash 工具）：
```bash
git rm apps/web/src/components/interview/AiTaskPanel.tsx \
       apps/web/src/components/interview/fields/FieldBoundSelect.tsx
```
Expected: git 顯示兩檔 `rm`。

- [ ] **Step 3: TypeScript 編譯需綠(證明無斷引用)**

Run（於 `s:\caliburn\apps\web`）：
```bash
npx tsc --noEmit
```
Expected: 無輸出、exit 0。若報 `Cannot find module …AiTaskPanel/FieldBoundSelect` →
代表仍有引用,Step 1 漏看,回報。

- [ ] **Step 4: ESLint 需綠**

Run（於 `s:\caliburn\apps\web`）：
```bash
npm run lint
```
Expected: 無 error(既有 warning 維持原狀即可,不在本階段處理)。

- [ ] **Step 5: Next build 需綠(終局驗證)**

Run（於 `s:\caliburn\apps\web`）：
```bash
npm run build
```
Expected: build 成功(exit 0)。確認刪除未波及 route/元件樹。

- [ ] **Step 6: Commit**

Run（於 `s:\caliburn`）：
```bash
git commit -m "chore(web): remove dead components (AiTaskPanel, FieldBoundSelect)"
```
Expected: 兩檔刪除入 commit。**不要 push。**

---

## Self-Review

- **Spec coverage:** 對應研究紀錄 §4 D-3a(刪死代碼)。D-3b(集中 QueryClient 預設)**刻意延後**到階段1,已於 Global Constraints 載明,非遺漏。
- **Placeholder scan:** 無 TBD/TODO;每步皆有具體指令與預期輸出。
- **Type consistency:** 本階段不新增/改型別,僅刪除;Step 3 的 `tsc` 即型別一致性的守門。
- **風險:** 極低(刪未引用碼);三道綠(tsc/lint/build)足以攔截任何遺漏的引用。
