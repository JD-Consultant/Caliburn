# 表頭/說明/任務 Combobox + 自動帶入 重設計 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把工作台 `/v3/[id]` 的表頭/說明/任務 O-P-K-S 輸入統一成「shadcn(cmdk) Combobox（官方下拉＋可自訂、官方預勾、可移除 pills、一鍵帶官方）」，並建立支撐的「受控欄位 + react-query 樂觀 + debounced autosave」管線；刪除 `HeaderMetaPanel` 雙路徑。

**Architecture:** `OcsDocument` 仍為單一真相 + react-query。`usePatchDocument` 升級樂觀（onMutate 寫快取、onError 回滾、onSuccess 對帳）；頁面用 debounced commit 合併 PATCH。每欄位為隔離的受控元件（local draft，commit on select/blur），透過既有 `lib/ocsDoc.ts` setters 寫回。候選來自既有 `/header-meta`（表頭）與 `/ai/recommend-ks`+`/ai/draft-op` 空 note catalog 模式（任務）。

**Tech Stack:** Next 16 + React 19 + TypeScript（Turbopack）、@tanstack/react-query、shadcn/ui、cmdk、@radix-ui/react-popover、@dnd-kit、lucide-react、tailwind。

## Global Constraints

- 前端**無單元測試 runner**；每個任務 gate ＝ `cd frontend && npx tsc --noEmit` **且** `cd frontend && npm run lint`，皆須零錯誤；外加該任務的**手動驗證**步驟。
- `frontend/AGENTS.md`：這不是你熟的 Next.js — 寫元件碼前先看 `frontend/node_modules/next/dist/docs/` 相關段落。
- 不引 react-hook-form、不用 React 19 `<form action>`/`useActionState`（D10）。Combobox 用 shadcn(Popover+cmdk)（D8），不引 Polaris。
- **AI/LLM 內部不改**：`AiTaskPanel` 的 `draftOP/recommendKS/clarify` 邏輯不動（D13）；只跟欄位/型別 rename 微調與「帶官方」按鈕保留。
- 文件 of-record 的 `CodeName` 維持 `{code,name}`；provenance 顯示用 `sources` 等只放顯示型別，不污染契約欄。
- 覆寫策略：自動帶入**只填空**；另有顯式「帶官方/全選官方」鈕做覆寫（D4）。
- 代碼↔名稱綁定（D5）；所屬類別三類各自 name↔code 綁定（D12）。
- commit 後 PATCH 走 ~500ms debounce + 選取/結構操作立即 + 批次單一 PATCH（D9）。
- Spec：`docs/superpowers/specs/2026-06-26-header-input-combobox-redesign-design.md`；討論記錄：同目錄 `-discussion.md`。
- 分支：`feat/v3`。commit 無 `Co-Authored-By`。

## File Structure

**新增**
- `frontend/src/components/ui/popover.tsx`、`frontend/src/components/ui/command.tsx`（shadcn 基礎）
- `frontend/src/components/interview/v3/fields/FieldCombobox.tsx`（多/單選 combobox：官方預勾+pills+自訂+帶官方）
- `frontend/src/components/interview/v3/fields/FieldText.tsx`（自由單值：預填可改+帶官方）
- `frontend/src/components/interview/v3/fields/FieldBoundSelect.tsx`（代碼↔名稱綁定單選）
- `frontend/src/lib/headerMeta.ts`（`HeaderMeta`→各欄 options 純函式）
- `frontend/src/hooks/useTaskCatalog.ts`（任務官方 O/P/K/S 候選）

**修改**
- `frontend/src/hooks/useDocument.ts`（`usePatchDocument` 樂觀；新 `useAutosaveDocument`）
- `frontend/src/components/interview/v3/DocHeader.tsx`、`DocNotes.tsx`（改用 Field*）
- `frontend/src/components/interview/v3/JobDocTable.tsx`（A 區 FieldCombobox；EditableText 受控；任務格摘要 pills；「帶官方」按鈕）
- `frontend/src/components/interview/v3/CellFillerPanel.tsx`（每格改 FieldCombobox）
- `frontend/src/components/interview/v3/AiTaskPanel.tsx`（保留；按鈕文案微調）
- `frontend/src/app/v3/[id]/page.tsx`（移除 HeaderMetaPanel 入口/state；persist 改用 useAutosaveDocument）
- `frontend/src/types/index.ts`（顯示型別 `OptionItem`/`HeaderMeta` 對齊；無契約欄變更）

**刪除**
- `frontend/src/components/interview/v3/HeaderMetaPanel.tsx`

---

## Phase 1 — 基礎管線 + 表頭/說明

### Task 1：安裝 combobox 相依 + shadcn primitives

**Files:**
- Modify: `frontend/package.json`（透過 npm i）
- Create: `frontend/src/components/ui/popover.tsx`、`frontend/src/components/ui/command.tsx`

**Interfaces:**
- Produces：`Popover/PopoverTrigger/PopoverContent`（from `@/components/ui/popover`）；`Command/CommandInput/CommandList/CommandEmpty/CommandGroup/CommandItem`（from `@/components/ui/command`）。

- [ ] **Step 1: 看 Next 指南 + 裝相依**

先讀 `frontend/node_modules/next/dist/docs/` 是否有對第三方 client 元件的限制（AGENTS.md 要求）。然後：
```bash
cd frontend && npm i cmdk @radix-ui/react-popover @radix-ui/react-checkbox use-debounce
```

- [ ] **Step 2: 確認安裝成功**

Run: `cd frontend && node -e "console.log(require('cmdk/package.json').version, require('@radix-ui/react-popover/package.json').version, require('use-debounce/package.json').version)"`
Expected: 印出三個版本號（非報錯）。若 React 19 peer 衝突，改 `npm i --legacy-peer-deps <pkgs>` 並在 commit message 註明。

- [ ] **Step 3: 建 `popover.tsx`**

`frontend/src/components/ui/popover.tsx`（shadcn 標準封裝；`cn` 來自既有 `@/lib/utils`，若無此檔則改用 `clsx`）：
```tsx
"use client";
import * as React from "react";
import * as PopoverPrimitive from "@radix-ui/react-popover";
import { cn } from "@/lib/utils";

export const Popover = PopoverPrimitive.Root;
export const PopoverTrigger = PopoverPrimitive.Trigger;
export const PopoverAnchor = PopoverPrimitive.Anchor;

export const PopoverContent = React.forwardRef<
  React.ElementRef<typeof PopoverPrimitive.Content>,
  React.ComponentPropsWithoutRef<typeof PopoverPrimitive.Content>
>(({ className, align = "start", sideOffset = 4, ...props }, ref) => (
  <PopoverPrimitive.Portal>
    <PopoverPrimitive.Content
      ref={ref}
      align={align}
      sideOffset={sideOffset}
      className={cn(
        "z-50 w-72 rounded-md border bg-popover p-0 text-popover-foreground shadow-md outline-none",
        className,
      )}
      {...props}
    />
  </PopoverPrimitive.Portal>
));
PopoverContent.displayName = "PopoverContent";
```
若 `@/lib/utils` 不存在 `cn`，先建：
```tsx
// frontend/src/lib/utils.ts
import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";
export function cn(...inputs: ClassValue[]) { return twMerge(clsx(inputs)); }
```
（先 `ls frontend/src/lib/utils.ts` 確認；存在就沿用。）

- [ ] **Step 4: 建 `command.tsx`**

`frontend/src/components/ui/command.tsx`：
```tsx
"use client";
import * as React from "react";
import { Command as CommandPrimitive } from "cmdk";
import { cn } from "@/lib/utils";

export const Command = React.forwardRef<
  React.ElementRef<typeof CommandPrimitive>,
  React.ComponentPropsWithoutRef<typeof CommandPrimitive>
>(({ className, ...props }, ref) => (
  <CommandPrimitive ref={ref} className={cn("flex h-full w-full flex-col overflow-hidden rounded-md bg-popover text-popover-foreground", className)} {...props} />
));
Command.displayName = "Command";

export const CommandInput = React.forwardRef<
  React.ElementRef<typeof CommandPrimitive.Input>,
  React.ComponentPropsWithoutRef<typeof CommandPrimitive.Input>
>(({ className, ...props }, ref) => (
  <div className="flex items-center border-b px-3">
    <CommandPrimitive.Input ref={ref} className={cn("flex h-9 w-full bg-transparent py-2 text-sm outline-none placeholder:text-muted-foreground", className)} {...props} />
  </div>
));
CommandInput.displayName = "CommandInput";

export const CommandList = React.forwardRef<
  React.ElementRef<typeof CommandPrimitive.List>,
  React.ComponentPropsWithoutRef<typeof CommandPrimitive.List>
>(({ className, ...props }, ref) => (
  <CommandPrimitive.List ref={ref} className={cn("max-h-64 overflow-y-auto overflow-x-hidden p-1", className)} {...props} />
));
CommandList.displayName = "CommandList";

export const CommandEmpty = React.forwardRef<
  React.ElementRef<typeof CommandPrimitive.Empty>,
  React.ComponentPropsWithoutRef<typeof CommandPrimitive.Empty>
>((props, ref) => <CommandPrimitive.Empty ref={ref} className="py-4 text-center text-sm text-muted-foreground" {...props} />);
CommandEmpty.displayName = "CommandEmpty";

export const CommandGroup = React.forwardRef<
  React.ElementRef<typeof CommandPrimitive.Group>,
  React.ComponentPropsWithoutRef<typeof CommandPrimitive.Group>
>(({ className, ...props }, ref) => (
  <CommandPrimitive.Group ref={ref} className={cn("overflow-hidden p-1 text-foreground", className)} {...props} />
));
CommandGroup.displayName = "CommandGroup";

export const CommandItem = React.forwardRef<
  React.ElementRef<typeof CommandPrimitive.Item>,
  React.ComponentPropsWithoutRef<typeof CommandPrimitive.Item>
>(({ className, ...props }, ref) => (
  <CommandPrimitive.Item ref={ref} className={cn("relative flex cursor-pointer select-none items-center gap-2 rounded-sm px-2 py-1.5 text-sm outline-none data-[selected=true]:bg-accent data-[selected=true]:text-accent-foreground", className)} {...props} />
));
CommandItem.displayName = "CommandItem";
```

- [ ] **Step 5: gate**

Run: `cd frontend && npx tsc --noEmit && npm run lint`
Expected: 零錯誤。

- [ ] **Step 6: Commit**
```bash
cd frontend && git add package.json package-lock.json src/components/ui/popover.tsx src/components/ui/command.tsx src/lib/utils.ts
git commit -m "feat(fe): add cmdk/popover deps + shadcn command/popover primitives"
```

---

### Task 2：樂觀 + debounced autosave 管線

**Files:**
- Modify: `frontend/src/hooks/useDocument.ts`

**Interfaces:**
- Consumes：`patchDocument(profileId, content)`（既有 `@/lib/api`）、`DocumentEnvelope`/`OcsDocument`（`@/types`）。
- Produces：
  - `usePatchDocument(profileId)`：升級為樂觀（`onMutate` 寫快取 + snapshot；`onError` 回滾；`onSuccess` 以 env 對帳）。
  - `useAutosaveDocument(profileId) -> { doc: OcsDocument | undefined, status, commit(next: OcsDocument): void, flush(): void }`：`commit` 立即樂觀更新 + ~500ms debounced PATCH；`status` ∈ `"idle"|"saving"|"saved"|"error"`。

- [ ] **Step 1: 升級 `usePatchDocument` 為樂觀**

替換 `useDocument.ts` 內 `usePatchDocument`：
```tsx
export function usePatchDocument(profileId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (content: OcsDocument) => patchDocument(profileId, content),
    onMutate: async (content: OcsDocument) => {
      await qc.cancelQueries({ queryKey: ["document", profileId] });
      const prev = qc.getQueryData<DocumentEnvelope>(["document", profileId]);
      qc.setQueryData<DocumentEnvelope>(["document", profileId], (old) =>
        old ? { ...old, content } : old);
      return { prev };
    },
    onError: (_e, _content, ctx) => {
      if (ctx?.prev) qc.setQueryData(["document", profileId], ctx.prev);
    },
    onSuccess: (env: DocumentEnvelope) => qc.setQueryData(["document", profileId], env),
  });
}
```

- [ ] **Step 2: 加 `useAutosaveDocument`**

在 `useDocument.ts` 末尾新增（用 `use-debounce` 的 `useDebouncedCallback`）：
```tsx
import { useDebouncedCallback } from "use-debounce";
import { useQueryClient } from "@tanstack/react-query";

export function useAutosaveDocument(profileId: string) {
  const qc = useQueryClient();
  const patch = usePatchDocument(profileId);
  // 最新整份 doc 暫存於 ref，debounce 到期送一次（合併連續編輯）。
  const latest = { current: undefined as OcsDocument | undefined };
  const flushPatch = useDebouncedCallback(() => {
    if (latest.current) patch.mutate(latest.current);
  }, 500);
  const commit = (next: OcsDocument) => {
    latest.current = next;
    // 立即樂觀寫入快取（UI 即時一致）
    qc.setQueryData<DocumentEnvelope>(["document", profileId], (old) =>
      old ? { ...old, content: next } : old);
    flushPatch();
  };
  const flush = () => { flushPatch.flush(); };
  const env = qc.getQueryData<DocumentEnvelope>(["document", profileId]);
  const status: "idle" | "saving" | "saved" | "error" =
    patch.isPending ? "saving" : patch.isError ? "error" : patch.isSuccess ? "saved" : "idle";
  return { doc: env?.content, status, commit, flush };
}
```
> 註：`latest` 用 module-local 物件不可跨渲染保存 → 改用 `useRef`。實作時把 `const latest = useRef<OcsDocument>()` 置於 hook 內（此處示意；用 `import { useRef } from "react"`）。

修正版（採用）：
```tsx
import { useRef } from "react";
export function useAutosaveDocument(profileId: string) {
  const qc = useQueryClient();
  const patch = usePatchDocument(profileId);
  const latest = useRef<OcsDocument | undefined>(undefined);
  const flushPatch = useDebouncedCallback(() => {
    if (latest.current) patch.mutate(latest.current);
  }, 500);
  const commit = (next: OcsDocument) => {
    latest.current = next;
    qc.setQueryData<DocumentEnvelope>(["document", profileId], (old) =>
      old ? { ...old, content: next } : old);
    flushPatch();
  };
  const env = qc.getQueryData<DocumentEnvelope>(["document", profileId]);
  const status = patch.isPending ? "saving" : patch.isError ? "error" : patch.isSuccess ? "saved" : "idle";
  return { doc: env?.content, status: status as "idle"|"saving"|"saved"|"error", commit, flush: () => flushPatch.flush() };
}
```

- [ ] **Step 3: gate**

Run: `cd frontend && npx tsc --noEmit && npm run lint`
Expected: 零錯誤。

- [ ] **Step 4: 手動驗證（暫時掛測試按鈕，驗完移除）**

確認 server 在跑（`http://localhost:3000`）。在任一現有編輯處改值 → 應**即時**反映、頁面 console 無錯。（完整 UX 於後續任務驗。）

- [ ] **Step 5: Commit**
```bash
cd frontend && git add src/hooks/useDocument.ts
git commit -m "feat(fe): optimistic usePatchDocument + useAutosaveDocument (debounced)"
```

---

### Task 3：候選 selectors `lib/headerMeta.ts`

**Files:**
- Create: `frontend/src/lib/headerMeta.ts`
- Modify: `frontend/src/types/index.ts`（加顯示型別 `OptionItem`）

**Interfaces:**
- Consumes：`HeaderMeta`（`@/types`，既有）。
- Produces：型別 `OptionItem = { code: string; name: string; sources?: string[] }`；函式
  - `categoryOptions(meta, kind: "job_categories"|"occupations"|"industries") -> OptionItem[]`
  - `attitudeOptions(meta) -> OptionItem[]`
  - `noteOptions(meta, field: "prerequisites"|"supplements") -> string[]`
  - `primaryOptions(meta) -> HeaderMetaPrimaryOption[]`（直接回 `meta.primary_options`）

- [ ] **Step 1: 加型別**

`types/index.ts` 末尾新增：
```ts
export interface OptionItem {
  code: string;
  name: string;
  sources?: string[];
}
```

- [ ] **Step 2: 建 selectors**

`frontend/src/lib/headerMeta.ts`：
```ts
import type { HeaderMeta, HeaderMetaPrimaryOption, OptionItem } from "@/types";

export function categoryOptions(
  meta: HeaderMeta,
  kind: "job_categories" | "occupations" | "industries",
): OptionItem[] {
  return (meta[kind] ?? []).map((c) => ({ code: c.code, name: c.name, sources: c.sources }));
}

export function attitudeOptions(meta: HeaderMeta): OptionItem[] {
  return (meta.attitudes ?? []).map((a) => ({ code: a.code, name: a.name, sources: a.sources }));
}

export function noteOptions(meta: HeaderMeta, field: "prerequisites" | "supplements"): string[] {
  return (meta[field] ?? []).map((t) => t.text);
}

export function primaryOptions(meta: HeaderMeta): HeaderMetaPrimaryOption[] {
  return meta.primary_options ?? [];
}
```

- [ ] **Step 3: gate**

Run: `cd frontend && npx tsc --noEmit && npm run lint`
Expected: 零錯誤。

- [ ] **Step 4: Commit**
```bash
cd frontend && git add src/lib/headerMeta.ts src/types/index.ts
git commit -m "feat(fe): headerMeta selectors + OptionItem type"
```

---

### Task 4：`<FieldCombobox>`（多選核心）

**Files:**
- Create: `frontend/src/components/interview/v3/fields/FieldCombobox.tsx`

**Interfaces:**
- Consumes：`Popover*`、`Command*`、`OptionItem`、`Badge`、`Button`。
- Produces：
```ts
function FieldCombobox(props: {
  label: string;
  value: { code: string; name: string }[];      // 已提交（來自 doc）
  options: OptionItem[];                          // 官方候選
  allowCustom?: boolean;                          // 可自訂打字新增
  onCommit: (next: { code: string; name: string }[]) => void;
  pillSources?: boolean;                          // pill 上顯示來源「共 N」
}): JSX.Element
```
- 行為：開啟時官方候選**預勾**（已在 value 的也勾）；勾/取消即更新 local draft，**關閉 popover 時 commit**（或每次 toggle 即 commit——採每次 toggle commit，配 D9 debounce）；已選顯示為**外部可移除 pills**；「全選官方」鈕把所有 options 併入（只填空，不移除自訂）。

- [ ] **Step 1: 寫元件**

`frontend/src/components/interview/v3/fields/FieldCombobox.tsx`：
```tsx
"use client";
import { useState } from "react";
import { Check, ChevronsUpDown, Plus, X } from "lucide-react";
import type { OptionItem } from "@/types";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { Command, CommandEmpty, CommandGroup, CommandInput, CommandItem, CommandList } from "@/components/ui/command";
import { Button } from "@/components/ui/button";

type Item = { code: string; name: string };
const keyOf = (i: { code: string; name: string }) => i.code || "name:" + i.name;

export function FieldCombobox({
  label, value, options, allowCustom = false, onCommit, pillSources = false,
}: {
  label: string;
  value: Item[];
  options: OptionItem[];
  allowCustom?: boolean;
  onCommit: (next: Item[]) => void;
  pillSources?: boolean;
}) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const sel = new Set(value.map(keyOf));
  const sourcesOf = (k: string) => options.find((o) => keyOf(o) === k)?.sources ?? [];

  const toggle = (opt: { code: string; name: string }) => {
    const k = keyOf(opt);
    if (sel.has(k)) onCommit(value.filter((v) => keyOf(v) !== k));
    else onCommit([...value, { code: opt.code, name: opt.name }]);
  };
  const remove = (k: string) => onCommit(value.filter((v) => keyOf(v) !== k));
  const addCustom = () => {
    const n = query.trim();
    if (!n || value.some((v) => v.name === n)) { setQuery(""); return; }
    onCommit([...value, { code: "", name: n }]);
    setQuery("");
  };
  const selectAllOfficial = () => {
    const next = [...value];
    for (const o of options) if (!next.some((v) => keyOf(v) === keyOf(o))) next.push({ code: o.code, name: o.name });
    onCommit(next);
  };

  return (
    <div className="space-y-1.5">
      <div className="flex flex-wrap gap-1">
        {value.map((v) => {
          const k = keyOf(v);
          const n = pillSources ? sourcesOf(k).length : 0;
          return (
            <span key={k} className="inline-flex items-center gap-1 rounded-full border bg-muted/50 px-2 py-0.5 text-xs">
              {v.code ? <span className="font-mono text-muted-foreground">{v.code}</span> : null}
              <span>{v.name}</span>
              {n > 1 ? <span className="rounded bg-sky-100 px-1 text-[10px] text-sky-700" title={"來自：" + sourcesOf(k).join("、")}>共 {n}</span> : null}
              <button type="button" className="text-muted-foreground hover:text-destructive" onClick={() => remove(k)}><X className="h-3 w-3" /></button>
            </span>
          );
        })}
      </div>
      <div className="flex items-center gap-1.5">
        <Popover open={open} onOpenChange={setOpen}>
          <PopoverTrigger asChild>
            <Button type="button" variant="outline" size="sm" className="justify-between gap-1 text-xs">
              {label} <ChevronsUpDown className="h-3.5 w-3.5 opacity-50" />
            </Button>
          </PopoverTrigger>
          <PopoverContent className="w-72">
            <Command>
              <CommandInput placeholder={allowCustom ? "搜尋或輸入自訂…" : "搜尋官方候選…"} value={query} onValueChange={setQuery} />
              <CommandList>
                <CommandEmpty>
                  {allowCustom && query.trim() ? (
                    <button type="button" className="inline-flex items-center gap-1 text-xs text-sky-700 hover:underline" onClick={addCustom}>
                      <Plus className="h-3 w-3" /> 新增「{query.trim()}」
                    </button>
                  ) : "無候選"}
                </CommandEmpty>
                <CommandGroup>
                  {options.map((o) => {
                    const k = keyOf(o);
                    return (
                      <CommandItem key={k} value={`${o.code} ${o.name}`} onSelect={() => toggle(o)}>
                        <Check className={"h-3.5 w-3.5 " + (sel.has(k) ? "opacity-100" : "opacity-0")} />
                        {o.code ? <span className="font-mono text-xs text-muted-foreground">{o.code}</span> : null}
                        <span className="flex-1">{o.name}</span>
                        {pillSources && (o.sources?.length ?? 0) > 1 ? <span className="text-[10px] text-sky-700">共 {o.sources!.length}</span> : null}
                      </CommandItem>
                    );
                  })}
                </CommandGroup>
              </CommandList>
            </Command>
          </PopoverContent>
        </Popover>
        <Button type="button" variant="ghost" size="sm" className="text-xs text-muted-foreground" onClick={selectAllOfficial}>帶官方</Button>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: gate**

Run: `cd frontend && npx tsc --noEmit && npm run lint`
Expected: 零錯誤。

- [ ] **Step 3: Commit**
```bash
cd frontend && git add src/components/interview/v3/fields/FieldCombobox.tsx
git commit -m "feat(fe): FieldCombobox (official pre-pick + pills + custom + 帶官方)"
```

---

### Task 5：`<FieldText>` + `<FieldBoundSelect>`

**Files:**
- Create: `frontend/src/components/interview/v3/fields/FieldText.tsx`、`FieldBoundSelect.tsx`

**Interfaces:**
- `FieldText(props: { value: string; placeholder?: string; multiline?: boolean; official?: string; onCommit: (v: string) => void }): JSX.Element` — 受控 local draft，blur 提交；`official` 有值時顯示「帶官方」鈕填入。
- `FieldBoundSelect(props: { value: { ocs_code: string; name: string }; options: { ocs_code: string; name: string }[]; onCommit: (o: { ocs_code: string; name: string }) => void }): JSX.Element` — 下拉選一個 OCS，commit 綁定 code+name。

- [ ] **Step 1: `FieldText.tsx`**
```tsx
"use client";
import { useEffect, useRef, useState } from "react";
import { Layers } from "lucide-react";

export function FieldText({
  value, placeholder, multiline = false, official, onCommit,
}: { value: string; placeholder?: string; multiline?: boolean; official?: string; onCommit: (v: string) => void }) {
  const [draft, setDraft] = useState(value);
  const focused = useRef(false);
  // value 變且未聚焦 → 同步（反映自動帶入/綁定/外部寫入）
  useEffect(() => { if (!focused.current) setDraft(value); }, [value]);
  const commit = () => { if (draft !== value) onCommit(draft); };
  const cls = "w-full rounded-md border px-2.5 py-1.5 text-sm focus:outline-none";
  return (
    <div className="space-y-1">
      {multiline ? (
        <textarea className={cls} rows={3} placeholder={placeholder} value={draft}
          onFocus={() => (focused.current = true)} onBlur={() => { focused.current = false; commit(); }}
          onChange={(e) => setDraft(e.target.value)} />
      ) : (
        <input className={cls} placeholder={placeholder} value={draft}
          onFocus={() => (focused.current = true)}
          onBlur={() => { focused.current = false; commit(); }}
          onKeyDown={(e) => { if (e.key === "Enter" && !multiline) e.currentTarget.blur(); }}
          onChange={(e) => setDraft(e.target.value)} />
      )}
      {official != null && official !== "" && official !== draft ? (
        <button type="button" className="inline-flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground"
          onClick={() => { setDraft(official); onCommit(official); }}>
          <Layers className="h-3 w-3" /> 帶官方
        </button>
      ) : null}
    </div>
  );
}
```

- [ ] **Step 2: `FieldBoundSelect.tsx`**
```tsx
"use client";
import { useState } from "react";
import { Check, ChevronsUpDown } from "lucide-react";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { Command, CommandEmpty, CommandGroup, CommandInput, CommandItem, CommandList } from "@/components/ui/command";
import { Button } from "@/components/ui/button";

type Opt = { ocs_code: string; name: string };
export function FieldBoundSelect({ value, options, onCommit }: { value: Opt; options: Opt[]; onCommit: (o: Opt) => void }) {
  const [open, setOpen] = useState(false);
  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <Button type="button" variant="outline" size="sm" className="w-full justify-between gap-1 text-xs">
          <span className="truncate">{value.ocs_code ? `${value.ocs_code}　${value.name}` : "選擇職能基準…"}</span>
          <ChevronsUpDown className="h-3.5 w-3.5 opacity-50" />
        </Button>
      </PopoverTrigger>
      <PopoverContent className="w-80">
        <Command>
          <CommandInput placeholder="搜尋職能基準…" />
          <CommandList>
            <CommandEmpty>無候選</CommandEmpty>
            <CommandGroup>
              {options.map((o) => (
                <CommandItem key={o.ocs_code} value={`${o.ocs_code} ${o.name}`} onSelect={() => { onCommit(o); setOpen(false); }}>
                  <Check className={"h-3.5 w-3.5 " + (value.ocs_code === o.ocs_code ? "opacity-100" : "opacity-0")} />
                  <span className="font-mono text-xs text-muted-foreground">{o.ocs_code}</span>
                  <span className="flex-1">{o.name}</span>
                </CommandItem>
              ))}
            </CommandGroup>
          </CommandList>
        </Command>
      </PopoverContent>
    </Popover>
  );
}
```

- [ ] **Step 3: gate**

Run: `cd frontend && npx tsc --noEmit && npm run lint`
Expected: 零錯誤。

- [ ] **Step 4: Commit**
```bash
cd frontend && git add src/components/interview/v3/fields/FieldText.tsx src/components/interview/v3/fields/FieldBoundSelect.tsx
git commit -m "feat(fe): FieldText + FieldBoundSelect (controlled, 帶官方, code↔name bound)"
```

---

### Task 6：DocHeader 改用 Field*（含 D5/D12 綁定）

**Files:**
- Modify: `frontend/src/components/interview/v3/DocHeader.tsx`

**Interfaces:**
- Consumes：`FieldCombobox`、`FieldText`、`FieldBoundSelect`、`headerMeta` selectors、`ocsDoc` setters（`setPrimaryBasis/setCategory/setProfileField/setOcsLevel`）、`useHeaderMeta`。
- Produces：`DocHeader({ document, onChange })` 簽名不變（`onChange` 仍回整份 doc 交上層 commit）。

- [ ] **Step 1: 重寫 DocHeader**

重寫 `DocHeader.tsx`，要點（保留 5 欄表格外觀，但每格換 Field*）：
- 載 `useHeaderMeta(profileId, hasOccupations)` → 但 DocHeader 目前不收 profileId。**改簽名**：`DocHeader({ document, profileId, onChange })`，並在 `JobDocTable` 傳入 `profileId`（見 Task 8）。
- 代碼/名稱列：用 `<FieldBoundSelect value={{ocs_code: p.ocs_code, name: p.ocs_name.occupation_name}} options={primaryOptions(meta).map(o => ({ocs_code:o.ocs_code, name:o.occupation_name}))} onCommit={(o)=>onChange(setPrimaryBasis(doc, {ocs_code:o.ocs_code, occupation_name:o.name, job_category_name: primaryOptions(meta).find(x=>x.ocs_code===o.ocs_code)?.job_category_name||""}))} />`。職類名（job_category_name）顯示用既有 `<FieldText>`（可改），official＝該 primary 的 job_category_name。
- 所屬類別三類：各一個 `<FieldCombobox label={類別名} value={p.category[kind]} options={categoryOptions(meta, kind)} onCommit={(items)=>onChange(setCategory(doc, kind, items))} />`（D12 綁定由 options 是 {code,name} pair 達成）。
- 工作描述：`<FieldText multiline value={p.job_description} official={primaryOptions(meta).find(x=>x.ocs_code===p.ocs_code)?.job_description} onCommit={(v)=>onChange(setProfileField(doc,"job_description",v))} />`。
- 基準級別：`<FieldText value={p.ocs_level!=null?String(p.ocs_level):""} official={String(primaryOptions(meta).find(x=>x.ocs_code===p.ocs_code)?.ocs_level ?? "")} onCommit={(v)=>onChange(setOcsLevel(doc,v))} />`。

完整骨架：
```tsx
"use client";
import type { OcsDocument } from "@/types";
import { useHeaderMeta } from "@/hooks/useDocument";
import { categoryOptions, primaryOptions } from "@/lib/headerMeta";
import { setCategory, setOcsLevel, setOcsName, setPrimaryBasis, setProfileField } from "@/lib/ocsDoc";
import { FieldCombobox } from "./fields/FieldCombobox";
import { FieldText } from "./fields/FieldText";
import { FieldBoundSelect } from "./fields/FieldBoundSelect";

const TH = "border bg-muted/50 px-3 py-2 text-left align-top font-medium whitespace-nowrap";
const TD = "border p-2 align-top";

export function DocHeader({ document: doc, profileId, onChange }: {
  document: OcsDocument; profileId: string; onChange: (d: OcsDocument) => void;
}) {
  const p = doc.ocs_profile;
  const { data: meta } = useHeaderMeta(profileId, !!p.ocs_code);
  const opts = meta ? primaryOptions(meta) : [];
  const cur = opts.find((o) => o.ocs_code === p.ocs_code);
  const cats = (kind: "job_categories" | "occupations" | "industries") => meta ? categoryOptions(meta, kind) : [];

  return (
    <table className="w-full table-fixed border-collapse overflow-hidden rounded-lg border text-sm">
      <colgroup><col className="w-32" /><col /></colgroup>
      <tbody>
        <tr><th className={TH}>職能基準（代碼/名稱）</th><td className={TD}>
          <FieldBoundSelect
            value={{ ocs_code: p.ocs_code, name: p.ocs_name.occupation_name }}
            options={opts.map((o) => ({ ocs_code: o.ocs_code, name: o.occupation_name }))}
            onCommit={(o) => onChange(setPrimaryBasis(doc, { ocs_code: o.ocs_code, occupation_name: o.name, job_category_name: opts.find((x) => x.ocs_code === o.ocs_code)?.job_category_name || "" }))}
          />
        </td></tr>
        <tr><th className={TH}>職類名稱</th><td className={TD}>
          <FieldText value={p.ocs_name.job_category_name ?? ""} official={cur?.job_category_name ?? ""}
            onCommit={(v) => onChange(setOcsName(doc, "job_category_name", v))} />
        </td></tr>
        <tr><th className={TH}>所屬職類別</th><td className={TD}>
          <FieldCombobox label="選職類別" value={p.category.job_categories} options={cats("job_categories")}
            onCommit={(items) => onChange(setCategory(doc, "job_categories", items))} />
        </td></tr>
        <tr><th className={TH}>所屬職業別</th><td className={TD}>
          <FieldCombobox label="選職業別" value={p.category.occupations} options={cats("occupations")}
            onCommit={(items) => onChange(setCategory(doc, "occupations", items))} />
        </td></tr>
        <tr><th className={TH}>所屬行業別</th><td className={TD}>
          <FieldCombobox label="選行業別" value={p.category.industries} options={cats("industries")}
            onCommit={(items) => onChange(setCategory(doc, "industries", items))} />
        </td></tr>
        <tr><th className={TH}>工作描述</th><td className={TD}>
          <FieldText multiline value={p.job_description ?? ""} official={cur?.job_description ?? ""}
            onCommit={(v) => onChange(setProfileField(doc, "job_description", v))} />
        </td></tr>
        <tr><th className={TH}>基準級別</th><td className={TD}>
          <FieldText value={p.ocs_level != null ? String(p.ocs_level) : ""} official={cur?.ocs_level != null ? String(cur.ocs_level) : ""}
            onCommit={(v) => onChange(setOcsLevel(doc, v))} />
        </td></tr>
      </tbody>
    </table>
  );
}
```

- [ ] **Step 2: gate**

Run: `cd frontend && npx tsc --noEmit && npm run lint`
Expected: 零錯誤（若 `JobDocTable` 尚未傳 profileId，會在 Task 8 修；此步驟若 tsc 報 DocHeader 呼叫端缺 profileId，先在 JobDocTable 補傳——見 Task 8 Step 1，可提前做）。

- [ ] **Step 3: 手動驗證**

`http://localhost:3000` 開一個已選職類的 profile → 表頭應顯示綁定下拉、類別 combobox（官方候選可勾、pills 可移除）、工作描述/級別預填可改+「帶官方」。改值 → 即時 + 自動儲存。

- [ ] **Step 4: Commit**
```bash
cd frontend && git add src/components/interview/v3/DocHeader.tsx
git commit -m "feat(fe): DocHeader → Field* combobox (bound code/name, category pre-pick, 帶官方)"
```

---

### Task 7：DocNotes 改 FieldCombobox（可自訂）

**Files:**
- Modify: `frontend/src/components/interview/v3/DocNotes.tsx`

**Interfaces:**
- Consumes：`FieldCombobox`、`useHeaderMeta`、`noteOptions`、`setNotes`。
- Produces：`DocNotes({ document, profileId, onChange })`（**加 profileId**）。
- 註：notes 是 `string[]`；用 FieldCombobox 需把字串轉成 `{code:"", name:text}` 進出。

- [ ] **Step 1: 重寫 DocNotes**
```tsx
"use client";
import type { OcsDocument } from "@/types";
import { useHeaderMeta } from "@/hooks/useDocument";
import { noteOptions } from "@/lib/headerMeta";
import { setNotes, type NoteField } from "@/lib/ocsDoc";
import { FieldCombobox } from "./fields/FieldCombobox";

function NoteCombo({ doc, profileId, field, title, onChange }: {
  doc: OcsDocument; profileId: string; field: NoteField; title: string; onChange: (d: OcsDocument) => void;
}) {
  const { data: meta } = useHeaderMeta(profileId, !!doc.ocs_profile.ocs_code);
  const options = (meta ? noteOptions(meta, field) : []).map((t) => ({ code: "", name: t }));
  const value = (doc.notes?.[field] ?? []).map((t) => ({ code: "", name: t }));
  return (
    <div>
      <p className="mb-1.5 text-sm font-medium">{title}</p>
      <FieldCombobox label="選/輸入" value={value} options={options} allowCustom
        onCommit={(items) => onChange(setNotes(doc, field, items.map((i) => i.name).filter(Boolean)))} />
    </div>
  );
}

export function DocNotes({ document: doc, profileId, onChange }: {
  document: OcsDocument; profileId: string; onChange: (d: OcsDocument) => void;
}) {
  return (
    <div className="space-y-4 rounded-lg border bg-background p-4">
      <p className="text-sm font-semibold">說明與補充事項</p>
      <NoteCombo doc={doc} profileId={profileId} field="prerequisites" title="建議擔任此職類／職業之學歷／經歷／或能力條件" onChange={onChange} />
      <NoteCombo doc={doc} profileId={profileId} field="supplements" title="其他補充說明" onChange={onChange} />
    </div>
  );
}
```

- [ ] **Step 2: gate**

Run: `cd frontend && npx tsc --noEmit && npm run lint`
Expected: 零錯誤。

- [ ] **Step 3: 手動驗證**：說明區可從官方候選勾選、可自訂輸入、pills 可移除、自動存。

- [ ] **Step 4: Commit**
```bash
cd frontend && git add src/components/interview/v3/DocNotes.tsx
git commit -m "feat(fe): DocNotes → FieldCombobox (official + custom)"
```

---

### Task 8：A 區 FieldCombobox + EditableText 受控 + 刪 HeaderMetaPanel + 接 profileId/autosave

**Files:**
- Modify: `frontend/src/components/interview/v3/JobDocTable.tsx`、`frontend/src/app/v3/[id]/page.tsx`
- Delete: `frontend/src/components/interview/v3/HeaderMetaPanel.tsx`

**Interfaces:**
- Consumes：`FieldCombobox`、`attitudeOptions`、`useHeaderMeta`、`setAttitudes`、`useAutosaveDocument`。
- Produces：`JobDocTable` 多收 `profileId`；`DocHeader`/`DocNotes` 傳入 `profileId`；A 區用 FieldCombobox；`EditableText` 改受控。

- [ ] **Step 1: JobDocTable 接 profileId + 傳給 DocHeader/DocNotes**

- `JobDocTable` props 加 `profileId: string`；`<DocHeader document={document} profileId={profileId} onChange={onChange} />`、`<DocNotes document={document} profileId={profileId} onChange={onChange} />`。

- [ ] **Step 2: A 區改 FieldCombobox**

把 JobDocTable 內「職能內涵（A）」區塊（原本 onClick `onCell({kind:"a"})` 開 CellFiller）改成 inline FieldCombobox：
```tsx
import { useHeaderMeta } from "@/hooks/useDocument";
import { attitudeOptions } from "@/lib/headerMeta";
import { setAttitudes } from "@/lib/ocsDoc";
import { FieldCombobox } from "./fields/FieldCombobox";
// …在 JobDocTable 內：
function AttitudeBlock({ document: doc, profileId, onChange }: { document: OcsDocument; profileId: string; onChange: (d: OcsDocument) => void }) {
  const { data: meta } = useHeaderMeta(profileId, !!doc.ocs_profile.ocs_code);
  return (
    <div className="rounded-lg border bg-background p-4">
      <p className="mb-2 text-sm font-medium">職能內涵（A=態度，全職類共用）</p>
      <FieldCombobox label="選態度" value={doc.ocs_attitude?.attitudes ?? []} options={meta ? attitudeOptions(meta) : []}
        allowCustom onCommit={(items) => onChange(setAttitudes(doc, items))} />
    </div>
  );
}
```
在 `JobDocTable` render 用 `<AttitudeBlock document={document} profileId={profileId} onChange={onChange} />` 取代原 A 區塊；`CellTarget` 的 `"a"` 分支與 `onCell({kind:"a"})` 移除（A 不再走 CellFiller）。

- [ ] **Step 3: EditableText 改受控**

`JobDocTable.tsx` 的 `EditableText` 改成受控（local draft + value 同步未聚焦 + blur commit）：
```tsx
import { useEffect, useRef, useState } from "react";
function EditableText({ value, placeholder, onCommit, className = "" }: {
  value: string; placeholder?: string; onCommit: (v: string) => void; className?: string;
}) {
  const [draft, setDraft] = useState(value);
  const focused = useRef(false);
  useEffect(() => { if (!focused.current) setDraft(value); }, [value]);
  return (
    <input value={draft} placeholder={placeholder}
      onFocus={() => (focused.current = true)}
      onBlur={() => { focused.current = false; if (draft !== value) onCommit(draft); }}
      onKeyDown={(e) => { if (e.key === "Enter") e.currentTarget.blur(); }}
      onChange={(e) => setDraft(e.target.value)}
      className={"rounded border border-transparent bg-transparent px-1 py-0.5 hover:border-input focus:border-input focus:bg-background focus:outline-none " + className} />
  );
}
```

- [ ] **Step 4: page.tsx 移除 HeaderMetaPanel + 改用 useAutosaveDocument**

`frontend/src/app/v3/[id]/page.tsx`：
- 移除 `import { HeaderMetaPanel }`、`showHeaderMeta` state、`<Button …setShowHeaderMeta>`〔表頭分類〕、底部 `{showHeaderMeta && …}` 區塊。
- `persist` 改用 `useAutosaveDocument`：
```tsx
const { doc: liveDoc, status: saveStatus, commit, flush } = useAutosaveDocument(id);
// 用 commit 取代原 patch.mutate；header 顯示 saveStatus（saving/saved）。
// onChange 一律 commit(next)。離開頁面 flush()。
```
- `JobDocTable` 傳 `profileId={id}`。
- 其他用到 `patch.isPending` 的地方改 `saveStatus === "saving"`。

- [ ] **Step 5: 刪 HeaderMetaPanel + 確認無殘留引用**
```bash
cd frontend && git rm src/components/interview/v3/HeaderMetaPanel.tsx
git grep -n "HeaderMetaPanel\|showHeaderMeta\|setShowHeaderMeta" -- src
```
Expected grep：無輸出（全部已移除）。

- [ ] **Step 6: gate + 手動**

Run: `cd frontend && npx tsc --noEmit && npm run lint`
Expected: 零錯誤。
手動：表頭/說明/態度全用 combobox；〔表頭分類〕按鈕消失；改名即時不 stale；autosave 顯示「儲存中/已儲存」。

- [ ] **Step 7: Commit**
```bash
cd frontend && git add -A src/components/interview/v3/JobDocTable.tsx src/app/v3/[id]/page.tsx
git commit -m "feat(fe): inline attitude combobox + controlled EditableText + remove HeaderMetaPanel; autosave wired"
```

---

## Phase 2 — 任務 O/P/K/S（每格抽屜升級 combobox）

### Task 9：`useTaskCatalog` hook（任務官方候選）

**Files:**
- Create: `frontend/src/hooks/useTaskCatalog.ts`

**Interfaces:**
- Consumes：`recommendKS`、`draftOP`（`@/lib/api`，既有；空 note → 回 catalog，不呼 LLM）。
- Produces：`useTaskCatalog(profileId, taskKey, enabled) -> { knowledge: OptionItem[]; skills: OptionItem[]; outputs: OptionItem[]; indicators: { code: string; text: string }[]; isLoading }`，依 `taskKey` 快取。

- [ ] **Step 1: 寫 hook**
```tsx
import { useQuery } from "@tanstack/react-query";
import { draftOP, recommendKS } from "@/lib/api";
import type { OptionItem } from "@/types";

export function useTaskCatalog(profileId: string, taskKey: string, enabled: boolean) {
  const q = useQuery({
    queryKey: ["task-catalog", profileId, taskKey],
    enabled: enabled && !!taskKey,
    staleTime: 5 * 60 * 1000,
    queryFn: async () => {
      const [ks, op] = await Promise.all([
        recommendKS({ profile_id: profileId, task_key: taskKey }),
        draftOP({ profile_id: profileId, task_key: taskKey }),
      ]);
      return {
        knowledge: ks.knowledge.map((k) => ({ code: k.code, name: k.name })) as OptionItem[],
        skills: ks.skills.map((s) => ({ code: s.code, name: s.name })) as OptionItem[],
        outputs: op.outputs.map((o) => ({ code: "", name: o.name })) as OptionItem[],
        indicators: op.indicators.map((i) => ({ code: "", text: i.text })),
      };
    },
  });
  return {
    knowledge: q.data?.knowledge ?? [], skills: q.data?.skills ?? [],
    outputs: q.data?.outputs ?? [], indicators: q.data?.indicators ?? [],
    isLoading: q.isLoading,
  };
}
```

- [ ] **Step 2: gate**

Run: `cd frontend && npx tsc --noEmit && npm run lint`
Expected: 零錯誤。

- [ ] **Step 3: Commit**
```bash
cd frontend && git add src/hooks/useTaskCatalog.ts
git commit -m "feat(fe): useTaskCatalog (per-task official O/P/K/S via catalog mode)"
```

---

### Task 10：CellFillerPanel 每格改 FieldCombobox

**Files:**
- Modify: `frontend/src/components/interview/v3/CellFillerPanel.tsx`

**Interfaces:**
- Consumes：`FieldCombobox`、`useTaskCatalog`、`getBlock/setKS/setOp/setAttitudes`。
- 行為：K/S/O 用 `FieldCombobox`（options＝該任務官方；value＝block 對應陣列；commit 走 `setKS/setOp`）；P（indicators）用 FieldCombobox（以 `{code:"", name:text}` 轉接，commit 時轉回 `{code,text}`）。每格附「帶官方」（FieldCombobox 內建）。

- [ ] **Step 1: 重寫 CellFillerPanel body**

把原 `Picker`（K/S/A）與 `OutputEditor/IndicatorEditor`（O/P）統一成 combobox。核心：依 `target.kind` 取對應 options 與 value，render 一個 `FieldCombobox`，`onCommit` 寫回 doc 後 `onSave(doc)`。範例（知識 K）：
```tsx
import { useTaskCatalog } from "@/hooks/useTaskCatalog";
import { FieldCombobox } from "./fields/FieldCombobox";
import { getBlock, setKS, setOp } from "@/lib/ocsDoc";
// taskKey 由 target 任務的 task_codes[0].code 取得（CellFillerPanel 已有 doc/unitIdx/taskIdx）
```
對 K：
```tsx
const cat = useTaskCatalog(profileId, taskKey, true);
const block = getBlock(document, unitIdx, taskIdx);
// K：
<FieldCombobox label="選知識 K" value={block?.knowledge ?? []} options={cat.knowledge} allowCustom
  onCommit={(items) => onSave(setKS(document, unitIdx, taskIdx, "knowledge", items))} />
// S：options=cat.skills、setKS(...,"skills",...)
// O：value=block?.outputs ?? []、options=cat.outputs、setOp(document,unitIdx,taskIdx,items,block?.indicators??[])
// P：value=(block?.indicators??[]).map(i=>({code:i.code,name:i.text}))、options=cat.indicators.map(i=>({code:i.code,name:i.text}))、
//    onCommit=(items)=>onSave(setOp(document,unitIdx,taskIdx,block?.outputs??[],items.map(i=>({code:i.code,text:i.name}))))
```
`CellFillerPanel` 需接收 `profileId`（從 page 傳入）。A 分支已於 Task 8 移除，可一併刪 CellFiller 內 `kind==="a"` 處理。

- [ ] **Step 2: page.tsx 傳 profileId 給 CellFillerPanel**

`<CellFillerPanel … profileId={id} />`（型別加 `profileId: string`）。

- [ ] **Step 3: gate + 手動**

Run: `cd frontend && npx tsc --noEmit && npm run lint`
Expected: 零錯誤。
手動：點任務某格 → 抽屜開 combobox，官方候選可勾（O/P/K/S 都有候選）、pills 可移除、可自訂、「帶官方」可補；存後表格摘要更新。

- [ ] **Step 4: Commit**
```bash
cd frontend && git add src/components/interview/v3/CellFillerPanel.tsx src/app/v3/[id]/page.tsx
git commit -m "feat(fe): CellFiller per-cell FieldCombobox (official O/P/K/S pre-pick + custom)"
```

---

### Task 11：任務列摘要 pills + 「帶官方」按鈕文案

**Files:**
- Modify: `frontend/src/components/interview/v3/JobDocTable.tsx`、`frontend/src/components/interview/v3/AiTaskPanel.tsx`

**Interfaces:**
- Produces：任務列每格按鈕顯示已填 pills/數量（沿用既有 `Cell` 的 filled/n）；列上「帶 catalog」按鈕文案改「帶官方」（功能不變＝`AiTaskPanel autoCatalog`）；`AiTaskPanel` 內部 LLM 邏輯不動。

- [ ] **Step 1: 按鈕文案**

`JobDocTable.tsx` 任務列「帶 catalog」按鈕文字改「帶官方」、tooltip 改「一鍵帶入此任務的職能基準官方 O/P/K/S」。`AiTaskPanel.tsx` autoCatalog 模式標題「一鍵帶入 catalog」→「帶官方」。其餘不動。

- [ ] **Step 2: gate + 手動**

Run: `cd frontend && npx tsc --noEmit && npm run lint`
Expected: 零錯誤。手動：列上「帶官方」一鍵帶整任務官方仍運作；✨AI(5W2H) 仍運作。

- [ ] **Step 3: Commit**
```bash
cd frontend && git add src/components/interview/v3/JobDocTable.tsx src/components/interview/v3/AiTaskPanel.tsx
git commit -m "feat(fe): task row 帶官方 button label; keep ✨AI panel internals"
```

---

### Task 12：全站 gate + build + 手動 e2e

**Files:** 無（驗證任務）

- [ ] **Step 1: 全量 gate**

Run: `cd frontend && npx tsc --noEmit && npm run lint`
Expected: 零錯誤。

- [ ] **Step 2: build**

Run: `cd frontend && npm run build`
Expected: build 成功（Turbopack）。若失敗，依錯誤修正對應任務檔。

- [ ] **Step 3: 手動 e2e checklist**（`http://localhost:3000`，需 backend 8001 + indexer 8000 在跑、Qdrant=ocs_v4）
  - 選職類 → 表頭代碼/名稱綁定下拉；類別三類官方預勾、pills 可移除、自訂、帶官方。
  - 工作描述/級別預填可改、「帶官方」可重拉。
  - 說明與補充：官方候選 + 自訂。
  - 態度 A inline combobox。
  - 任務每格抽屜 combobox（O/P/K/S 官方候選 + 自訂 + 帶官方）；列上「帶官方」一鍵整任務；✨AI 仍可用。
  - autosave：改值即時、顯示「儲存中/已儲存」；重整後保留。
  - 〔表頭分類〕入口已消失、無 console 錯誤。

- [ ] **Step 4: Commit（若有微修）**
```bash
cd frontend && git add -A && git commit -m "chore(fe): combobox redesign final gate (tsc/lint/build green)"
```

---

## Self-Review

**Spec coverage：**
- D1 combobox 範式 → T4/T5/T6/T7/T8/T10。✓
- D2/D11 自動帶入（預勾+pills+帶官方）→ FieldCombobox（T4）。✓
- D3 刪 HeaderMetaPanel → T8。✓
- D4 只填空 + 帶官方覆寫 → FieldCombobox `selectAllOfficial` / FieldText `帶官方`。✓
- D5/D12 綁定 → FieldBoundSelect（T5/T6）+ category options 為 {code,name}（T6）。✓
- D6 受控 → Field* + EditableText（T5/T8）。✓
- D7 EditableText 受控 → T8。✓
- D8 shadcn(cmdk) → T1/T4。✓
- D9 autosave C → useAutosaveDocument debounce（T2）。✓
- D10 樂觀 → usePatchDocument onMutate（T2）。✓
- D13 任務 O/P/K/S 抽屜 + 帶官方 + 保留 ✨/不改 LLM → T9/T10/T11。✓

**Placeholder scan：** 每個程式步驟均附實碼；rewrites 提供完整骨架或逐欄 wiring。`useAutosaveDocument` 已標明用 `useRef`（非 module-local）。無 TBD。

**Type 一致性：** `FieldCombobox` value/onCommit＝`{code,name}[]`，與 `setCategory/setKS/setAttitudes/setNotes` 對齊；P 以 `{code,name}` 轉接、commit 轉回 `{code,text}`（setOp 簽名）。`OptionItem` 跨 selectors/hooks/元件一致。`useTaskCatalog.indicators` 為 `{code,text}` 與轉接相符。

## Out of Scope（不做）
- 未來 LLM/CopilotKit 整合；AI 面板內部邏輯不動。
- 兩條編輯路徑收斂；聚焦中外部寫入提示。
- 後端不需改（沿用 `/header-meta`、`/document` PATCH、`/ai/recommend-ks`、`/ai/draft-op`）。
