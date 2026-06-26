# 表頭/說明輸入 Combobox + 自動帶入 重設計 — Design Spec

**Date:** 2026-06-26
**Status:** 設計定案，待寫實作計畫（writing-plans）
**Repo:** `s:\jobintel-ai`（前端 `frontend/`，Next 16 + React 19）
**討論記錄/報告素材（含研究來源與推理）:** [2026-06-26-header-input-combobox-redesign-discussion.md](./2026-06-26-header-input-combobox-redesign-discussion.md)

## Goal

把工作台（`/v3/[id]`）的**表頭與說明欄位**從「free-text 手打 + 另開勾選側面板」改成**統一的 combobox（官方下拉＋可自訂）**，每個有官方資料的欄位都能「**選單一開即預勾官方、可取消/補勾、可一鍵重拉官方**」，並建立支撐此互動的**受控狀態 + 樂觀 autosave** 管線。消除「inline 手打 vs 側面板勾選」雙路徑。

## Scope

**In — Phase 1（表頭/說明）**
- 表頭 `DocHeader`：代碼/名稱、所屬類別（職類別/職業別/行業別）、工作描述、基準級別。
- 說明 `DocNotes`：應備資格、補充說明。
- 態度 A（目前由 CellFiller(a) + HeaderMetaPanel 編輯）→ 納入同 combobox 範式。
- 刪除 `HeaderMetaPanel` 側面板（行為折進 inline）。
- 狀態/儲存管線：`usePatchDocument` 升級樂觀 + debounced；新 `<FieldCombobox>` / `<FieldText>` 元件；共享候選 hooks。

**In — Phase 2（任務 O/P/K/S，D13）**
- `CellFillerPanel` 每格抽屜升級成 combobox 範式（官方候選＝`task_competencies` 依 task_code；預勾+pills+自訂+該格帶官方）。
- 任務列保留「帶官方」一鍵整任務（沿用現〔帶 catalog〕）+ 保留 ✨AI(5W2H)；**AI/LLM 內部不改，只保留按鈕**。

**Out（非本 spec）**
- 未來 LLM/CopilotKit 整合（目前 CopilotKit 大概率重設計；本 spec 只守「LLM 相容三原則」鋪路，不實作；AI 面板內部邏輯不動）。
- 兩條編輯路徑（工作台 vs guided interrupt）長遠收斂。

## 決策摘要（D1–D12，詳見討論記錄）

- **D1** 互動範式＝Combobox（官方下拉＋可自訂）貫穿所有輸入。
- **D2** 自動填＝smart default（NN/g）。
- **D3** 刪 `HeaderMetaPanel`，折進 inline。
- **D4** 覆寫＝預設只填空 + 顯式「重拉官方」鈕。
- **D5** 代碼↔名稱綁定。
- **D6** 欄位受控（狀態隔離，取代 uncontrolled+key remount）。
- **D7** 職責/任務名 `EditableText` 一併改受控（修 stale）。
- **D8** 元件＝shadcn(Popover+cmdk)，不引 Polaris。
- **D9** autosave＝**C**（選取立即、文字 debounce ~500ms + blur、批次單一 PATCH、顯示儲存中/已儲存）。
- **D10** 狀態架構＝react-query 樂觀(`onMutate`) + 欄位隔離（手刻）；不引 RHF、不用 React 19 Actions。
- **D11** 自動帶入呈現＝**選單內預勾 + 外部可移除 pills + 每欄/區重拉鈕**；不盲目一鍵寫死；自由文字欄預填可改。
- **D12** 所屬類別三類各自 **name↔code 綁定**（選官方 {code,name} pair 一起帶；自訂可手填、code 可空）。
- **D13** 任務 O/P/K/S＝**每格側邊抽屜（一次一格）升級 combobox** + 任務列「帶官方」一鍵整任務 + 保留 ✨AI；候選＝`task_competencies` 依 task_code；**AI/LLM 內部不改**。

## 架構

### A. 狀態 / 儲存（D10/D9）
- 維持 `OcsDocument` 為單一真相 + react-query。
- 升級 `usePatchDocument`：
  - `onMutate(next)`：`cancelQueries(["document",id])` → snapshot → `setQueryData` 樂觀寫入 `next`（UI 即時一致）→ 回傳 `{prev}`。
  - `onError`：回滾 `prev` + 顯示錯誤。
  - `onSuccess(env)`：以伺服器 canonical envelope 對帳（版本/id）。
- **頁面層 persist 升級為「即時樂觀 + debounced PATCH」**：commit 當下立即樂觀更新快取；網路 PATCH 經 ~500ms debounce（ref 存最新整份 doc，合併連續編輯；blur/關面板/導頁 flush）。批次操作（自動帶入）組成單一 `next` → 單一 PATCH。
- 「儲存中…/已儲存」由 mutation `isPending`/`isSuccess` 驅動（沿用現有 `savedAt`）。

### B. 欄位隔離（D6）
新增可重用元件（`frontend/src/components/interview/v3/fields/`）：
- **`<FieldCombobox>`**（多選 / 單選綁定）
  - Props：`value`（已提交，來自 doc）、`options: {code,name}[]`（官方候選）、`multiple`、`allowCustom`、`onCommit(next)`、`preselectOfficial`（D11 預勾）。
  - 內部 `draft = useState(value)`；打字/勾選只動 draft（父層不重繪/不 PATCH）。
  - 同步：`value` 變且**未聚焦/未展開** → `setDraft(value)`；聚焦中不覆蓋。
  - 提交：選官方項/勾選 → 立即 `onCommit`；自由文字 → blur/debounce → `onCommit`。
  - UI：cmdk 選單（內部 checkbox 預勾官方）＋**已選顯示為外部可移除 pills**；附**「全選官方」**鈕。
  - `React.memo` 隔離 sibling 重繪。
- **`<FieldText>`**（自由單值：工作描述/級別）
  - 預填官方值、明顯可編輯（描述為 textarea）；附**「帶官方」**鈕重拉；commit on blur/debounce。
- **`<FieldBoundSelect>`**（綁定單值：代碼↔名稱）
  - 下拉選某 OCS → `onCommit` 一次寫 code+name（+desc/level smart default）。

### C. 共享候選層（LLM 相容原則 2）
- `useHeaderMeta(profileId)` 已存在（`/header-meta` 聚合官方候選）。
- 新增純 selector（同檔或 `lib/headerMeta.ts`）把 `HeaderMeta` 切成各欄位 `options`：
  - `job_categories/occupations/industries` → 各 `{code,name}[]`（D12 綁定來源）。
  - `attitudes` → `{code,name}[]`。
  - `prerequisites/supplements` → `string[]`。
  - `primary_options` → 綁定單值（代碼/名稱/描述/級別）來源。
- 同一份候選供 combobox 與**未來 LLM grounding** 共用（不重複）。

### D. 每欄位型別模型（D11/D12）
| 欄位 | 元件 | 行為 |
|---|---|---|
| 職能基準代碼 / 名稱 | `<FieldBoundSelect>` | 選 OCS → code+name 綁定；desc/level smart default 帶入可改 |
| 所屬職類別（+代碼）| `<FieldCombobox multiple>` | 選單預勾官方 `{code,name}` pairs；pills 可移除；「全選官方」；D12 綁定 |
| 所屬職業別（+代碼）| `<FieldCombobox multiple>` | 同上 |
| 所屬行業別（+代碼）| `<FieldCombobox multiple>` | 同上 |
| 職能內涵 態度 A | `<FieldCombobox multiple>` | 同上（候選＝attitudes）|
| 工作描述 | `<FieldText textarea>` | 預填官方、可編輯、「帶官方」重拉 |
| 基準級別 | `<FieldText number>` | 預填官方、可改、「帶官方」重拉 |
| 應備資格 / 補充說明 | `<FieldCombobox multiple allowCustom>` | 選單預勾官方文字候選；pills 可移除；可自訂；「全選官方」|
| 職責/任務名 | 受控輸入（`<FieldText>`）| 修 stale（D7）；無官方候選、純自訂 |

## 元件變更（盤點 → 具體動作）

| 檔案 | 動作 |
|---|---|
| `components/interview/v3/fields/FieldCombobox.tsx` | **新增**（cmdk + pills + 預勾 + 全選官方）|
| `components/interview/v3/fields/FieldText.tsx`、`FieldBoundSelect.tsx` | **新增** |
| `lib/headerMeta.ts`（或 hook 內）selector | **新增**（HeaderMeta → 各欄 options）|
| `hooks/useDocument.ts` `usePatchDocument` | **升級**樂觀 onMutate + 對帳 |
| `app/v3/[id]/page.tsx` persist | **升級**即時樂觀 + debounced flush；移除〔表頭分類〕入口與 `showHeaderMeta` |
| `components/interview/v3/DocHeader.tsx` | **重寫**：各格改用 Field* 元件（D11/D12）|
| `components/interview/v3/DocNotes.tsx` | **重寫**：改 `<FieldCombobox allowCustom>` |
| `components/interview/v3/HeaderMetaPanel.tsx` | **刪除**（行為折進 inline；確認無其他引用）|
| `components/interview/v3/JobDocTable.tsx` `EditableText` | **改受控**（D7）；A 區改用 FieldCombobox；任務格顯示摘要 pills、保留列上「帶官方」+✨按鈕（Phase 2）|
| `components/interview/v3/CellFillerPanel.tsx` | **Phase 2 升級**：每格抽屜改用 `<FieldCombobox>`（O/P/K/S 四格皆官方候選=task_competencies；預勾+pills+自訂+該格帶官方）|
| `components/interview/v3/AiTaskPanel.tsx` | **保留**（✨5W2H + 帶 catalog）；**內部 LLM 邏輯不改**，只跟著欄位/型別 rename 微調 |
| `lib/ocsDoc.ts` setters | 沿用既有 `setPrimaryBasis/setOcsName/setProfileField/setOcsLevel/setCategory/upsertCategory/addCategory/deleteCategory/setAttitudes/setNotes`；視綁定需求補小 setter |
| `types/index.ts` | 視需要加 `KsaPoolItem`/候選型別；表頭文件契約 CodeName 不變 |
| shadcn `command`/`popover` | 若未安裝則 **新增**（`@/components/ui`）|

## 資料流範例
- **選 OCS（代碼欄）**：`onCommit` → `setPrimaryBasis(doc, {ocs_code, occupation_name})` + smart-default desc/level（只填空）→ 一次樂觀更新 → 名稱/描述/級別欄 `value` 變、未聚焦 → 顯示。
- **開類別選單**：預勾官方 `{code,name}` pairs（D11）→ 取消/補勾 → 關閉/勾選 commit → pills 顯示 → debounced PATCH。
- **「全選官方」鈕**：把該欄 official 全帶回（覆寫該欄）→ 樂觀 + PATCH。

## LLM 相容三原則（鋪路，不實作）
1. 欄位受控、綁文件狀態（程式寫入即時反映、不丟焦點）。
2. 候選來源單一共享層（人用＝未來 LLM grounding）。
3. 單一寫入路徑（ocsDoc setters + 樂觀 PATCH）。

## 測試
- 前端無單元測試框架 → gate＝`cd frontend && npx tsc --noEmit && npm run lint`。
- 手動驗證：選 OCS 綁定帶入、類別預勾/pills/全選官方、描述預填可改、autosave「儲存中/已儲存」、刪 HeaderMetaPanel 後無斷點。
- 後端不需改（`/header-meta`、`/document` PATCH 既有）。

## 任務 O/P/K/S（Phase 2，D13）

研究：多列×多欄複雜輸入 → **側邊抽屜**優於 inline（表頭=一筆→inline；任務=多列→抽屜）。

- **每格側邊抽屜（一次一格）**：點任務的某格（O/P/K/S）→ 抽屜開該格 `<FieldCombobox>`。
  - 候選＝該任務官方 `task_competencies(competencies(ocs_code), task_code)`：K/S/O＝`{code,name}`、P＝`{code,text}`。
  - 行為同 D11：官方預勾 + pills 可移除 + 可自訂 + 該格「帶官方」重拉。
  - 沿用現有「local state、按鈕提交」（對程式寫入安全）。
- **任務列**：保留一顆「帶官方」一鍵整任務（沿用現〔帶 catalog〕＝`AiTaskPanel autoCatalog`）；保留 ✨AI(5W2H)。
- **AI/LLM 內部不改**：`AiTaskPanel` 的 `draftOP/recommendKS/clarify` 邏輯不動，只跟欄位/型別 rename 微調。
- 候選來源：per-task 需要 `competencies(ocs_code)` 的 per-task 切片；沿用 `useKsaPool`/新增 per-task selector（依 task 的 `provenance.ocs_code` + `task_code`）。

## Out of Scope / 後續
- 未來 LLM/CopilotKit 整合；兩路徑收斂（AI 面板內部邏輯不動）。
- 「聚焦中遇外部寫入是否提示官方值不同」（預設不覆蓋，提示待議）。
