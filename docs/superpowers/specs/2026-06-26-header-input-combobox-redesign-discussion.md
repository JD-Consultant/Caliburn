# 表頭/輸入 Combobox + 自動帶入 重設計 — 討論記錄（living doc）

**Date:** 2026-06-26
**Status:** 討論中（尚未定案、尚未實作）
**用途:** 完整記錄需求、研究參考、決策與「保留的舊作法」，供日後寫報告。本檔持續追加，不刪先前內容。
**Repo:** `s:\jobintel-ai`（前端 `frontend/`）

---

## 1. 需求（使用者原話彙整）

- 選完職類，要**自動填**：所屬類別、職能基準名稱、工作描述、基準級別、態度 A、應備資格/補充說明。
- 選完任務，要**自動填**每個任務的 O / P / K / S。
- **所有需要輸入的地方都要有選單**（使用者「都有資料」＝有官方 catalog 候選）。
- 選單之上要有**自動添加**：先一鍵自動填，再逐項調整。
- 要**研究權威/大廠/熱門專案**怎麼設計這種互動，作為依據。
- 要**盤點現有功能**：哪些改名／移位／刪除。
- 代碼 ↔ 名稱**一定綁定**；其餘欄位彈性。
- LLM 是**之後**的核心；目前的 CopilotKit 大概率會**重新設計**，故本設計的「LLM 相容原則」寫成**通用**、不綁現行 CopilotKit 實作。

---

## 2. 研究參考（權威來源 + 重點）

### 2.1 Combobox（可選清單 + 可自訂輸入）
- **W3C ARIA 1.2 — Combobox pattern**：可編輯輸入 + 彈出清單篩選/選取的無障礙標準。
- **Shopify Polaris — Combobox / Autocomplete**：大廠落地。「從預設或**可編輯**清單選一/多個值」；Autocomplete = combobox + listbox 組合；強調**即使不靠自動完成也要能搜尋/輸入**（無障礙）。
  - https://polaris.shopify.com/components/combobox
  - https://polaris-react.shopify.com/components/selection-and-input/autocomplete
- 對應需求：「有官方就從下拉選、沒有就打字（create custom）」。

### 2.2 Smart Defaults（預填 + 可調整）
- **Nielsen Norman Group — The Power of Defaults**：有既有資料就**預填**欄位，讓使用者**驗證/修改**；預設值兼具「即時範例說明」與「常見值提示」雙重 usability 貢獻；但預設若「presumptive 又難改」會反效果 → 必須**易於更改**。
  - https://www.nngroup.com/articles/the-power-of-defaults/
- **NN/g — Reduce Cognitive Load in Forms / EAS Framework**：用既有資料 prefill、讓使用者驗證更新，尊重自主又降低成本。
  - https://www.nngroup.com/articles/4-principles-reduce-cognitive-load/
- 對應需求：「自動添加，先填再調」＝ smart default；關鍵是「**填了但隨時可改**」。

### 2.3 實作技術選型（與現有 stack 一致）
- repo 既有 UI = **shadcn/ui**（`@/components/ui/*`：Button/Badge/Progress…）。
- Combobox 採 **shadcn 範式 = Popover + cmdk(Command)**，受控、無障礙（ARIA combobox）、支援自訂值與多選。**不引 Polaris 整套**（過重、風格不一致）。

---

## 3. 現有功能盤點（＝「舊作法」，保留記錄、不刪）

> 此節是日後報告的「before」基準。程式碼現況如實記錄；本次只討論不動碼。

### 3.1 兩條編輯路徑並存（核心痛點）
同一批表頭欄位目前**有兩種編輯方式**：
1. **表頭 inline 手打**（`DocHeader.tsx`）：代碼/名稱/類別/描述/級別全是 free-text `<input>`。
2. **側面板勾選**（`HeaderMetaPanel.tsx`，工具列〔表頭分類〕）：從 catalog 候選勾選類別/態度/資格/補充 + 主基準 radio（code/name/desc/level），預設全勾、按「套用」。

### 3.2 元件清單與輸入模式（before）
| 元件 | 角色 | 輸入模式（現況） |
|---|---|---|
| `DocHeader` | 表頭表格（代碼/名稱/類別/描述/級別）| uncontrolled `defaultValue` + `key={value}`（靠 remount 同步）, onBlur 提交 |
| `DocNotes` | 說明與補充（資格/補充清單）| uncontrolled `defaultValue` + `key`（NoteList 有 key）, onBlur 提交 |
| `JobDocTable` `EditableText` | 職責/任務改名 | uncontrolled `defaultValue`，**無 key（會 stale）**, onBlur 提交 |
| `HeaderMetaPanel` | 〔表頭分類〕側面板 | catalog 候選勾選 + 主基準 radio；按「套用」批次寫 |
| `CellFillerPanel` | 每任務 O/P/K/S 格 | local `useState`（panel 內受控）；K/S/A 從 ksa-pool 候選勾選、O/P 純手打；按「儲存」提交 |
| `AiTaskPanel` | ✨AI(5W2H) / 〔帶 catalog〕 | local state；生成或帶官方 O/P/K/S；按「套用」 |
| `OccupationPicker` | 〔選職類〕modal | 搜尋 + 複選 |
| `TaskCuratePanel` | 〔選任務〕modal | 候選勾選 + AI 預勾 + 自訂 |

### 3.3 autosave 模型（before）
- inline 欄位 onBlur → `persist(next)` → `patch.mutate` → 整-doc PATCH；panel 按鈕提交 → 一次 PATCH。
- 即「每次提交＝一個整份 OcsDocument PATCH」。

### 3.4 CopilotKit 現況（before；之後大概率重設計）
- `CopilotKitProvider` 全 app 包覆（`Providers.tsx`, runtimeUrl `/api/copilotkit`）。
- 但**工作台 `/v3/[id]` 與 intake 刻意不用 CopilotKit**（純 REST + react-query）。
- CopilotKit 目前只驅動 guided interview 的 interrupt UI（`InterruptHandlers.tsx`：select_profile/edit_tasks/curate_ks/curate_attitudes/ask_human/preview）。
- ⚠️ 使用者明示：**目前 LLM/CopilotKit 不必遷就，之後會重設計**。

---

## 4. 決策記錄（討論至今）

| # | 決策 | 選定 | 理由 |
|---|---|---|---|
| D1 | 互動範式 | **Combobox（官方下拉 + 可自訂）貫穿所有輸入** | ARIA/Polaris；使用者「都有資料」 |
| D2 | 自動填 | **smart default：一鍵自動帶入官方，再逐項調整** | NN/g Power of Defaults |
| D3 | HeaderMetaPanel | **刪除，折進表頭 inline combobox + 自動帶入** | 消除雙路徑混亂（§3.1）|
| D4 | 覆寫策略 | **預設只填空 + 顯式「重新帶入官方（覆寫）」鈕** | NN/g：預填但易改、不洗掉編輯 |
| D5 | 代碼/名稱綁定 | **代碼↔名稱一定綁定**（選 OCS → 名稱跟著；描述/級別以 smart default 帶但可改）；其餘欄位彈性 | 官方資料一致性 |
| D6 | 受控狀態 | combobox **受控、綁 OcsDocument state**（取代 uncontrolled+key remount）| 修焦點/同步；為 smart default & 未來 LLM 鋪路 |
| D7 | EditableText（職責/任務名）| **一併改受控** | 修「無 key 會 stale」、未來可程式改名 |
| D8 | 元件選型 | **shadcn(Popover+cmdk)**，不引 Polaris | 與現有 stack 一致 |
| D9 | persist 模型 | **討論中**（見 §6）| — |

---

## 5. 未來 LLM 相容三原則（通用、不綁現行 CopilotKit）

> 動機：之後 LLM 會是核心；但 LLM 操作的是「狀態與動作」，不是 widget。把握三原則，無論之後用哪套 agent 框架都相容。
1. **欄位受控、綁文件狀態** → 程式（自動帶入／未來 LLM）寫值能即時反映、不丟焦點。
2. **候選來源做成單一共享層**（包 `/header-meta` + competencies 的 hooks/型別）→ 人用的下拉候選＝未來 LLM 的 grounding 候選（同一份官方池）。
3. **單一寫入路徑** = `ocsDoc` setters + PATCH → combobox 選取、自動帶入鈕、未來 LLM 動作全走同一組 setter，行為一致、自動存。

（附：未來「工作台 + 行內 copilot」可能收斂取代現行獨立 interrupt walk，但屬另一獨立決定，本設計不強迫、也不打斷現行流程。）

---

## 6. persist 提交模型 — 詳細分析（D9，討論中）

目標：把編輯寫回後端（整份 OcsDocument PATCH）的時機/頻率，兼顧「不丟焦點、不 PATCH 風暴、不整表重繪、人/程式寫入不打架」。

前提：採「**local 編輯緩衝 + 選取/blur 才提交**」——自由文字打字期間只動 local state，**不**每鍵寫全域 doc，故 PATCH 頻率天然就低。

### 選項 A：事件即提交（無計時器）
- combobox **選一個選項** → 立即提交（1 PATCH）。
- **自由文字** → blur/Enter 才提交（1 PATCH）。
- 優點：可預測、簡單、等同現況粒度；對程式寫入好推理（每次寫＝1 PATCH）。
- 缺點：快速 tab 過多欄位＝多次 PATCH；**自動帶入若逐欄 setter 會 N 次 PATCH** → 對策：自動帶入**批次組成 next doc、單一 PATCH**。

### 選項 B：debounce 自動存（~500ms）
- 任何變更更新 local doc；最後一次變更後 500ms 才 PATCH。
- 優點：合併連續編輯/多欄自動填成較少 PATCH、更順。
- 缺點：較複雜（debounce + 導頁/unmount 要 flush + 「儲存中」狀態）；漏存風險（導頁前未 flush）；與程式寫入的順序較難推理。

### 選項 C：混合（推薦）
- **選取 / 結構操作（加列刪列）** → 立即提交。
- **自由文字（描述/自訂名/補充）** → blur 提交（或加 ~500ms debounce）。
- **批次操作（自動帶入官方、覆寫）** → 組成整份 next doc、**單一 PATCH**。
- flush 時機：blur / unmount / 導頁。

### 傾向
因「local 緩衝 + blur 提交」已讓自由文字不會每鍵 PATCH，**選項 A 已足夠**；debounce 屬選配優化。**最關鍵的硬規則：自動帶入務必批次成單一 PATCH**，不可逐欄觸發。
→ 待使用者拍板 A（簡單可預測）或 C（加 debounce 更順）。

---

## 7. 受控狀態重構範圍（討論中，已選為深入主題）

- **核心**：DocHeader（6 類欄位）→ 受控 combobox；DocNotes → 受控 combobox-add；確立 persist 模型（§6）。
- **選配（已決定一併做，D7）**：EditableText（職責/任務名）→ 受控，修 stale。
- **幾乎不動**：CellFiller / AiTaskPanel 已 local-controlled、按鈕提交；之後只加官方候選下拉。

---

## 8. 開放議題（待續）
- ~~D9 persist 模型 A vs C~~ → **定案 C**（見 §9）。
- 共享候選層的 hook/型別具體形狀（§5 原則 2）。
- 每任務 O/P/K/S 自動填：inline 於格子 vs 維持 panel；候選＝該任務官方（task_competencies）。
- 「自動帶入」按鈕的層級與位置（全表頭一鍵 / 每區一鍵 / 每欄一鍵）。
- 兩條編輯路徑（工作台 vs 未來 copilot）長遠收斂與否。
- 聚焦中遇外部寫入：是否顯示「官方值不同」提示（預設不覆蓋）。

---

## 9. 2026 研究補充 + D9 定案（autosave = C）

### 9.1 2026 / React 19 研究（前端為 Next 16 + React 19）
- **React 19 原生表單**（Actions / `useActionState` / `useFormStatus` / `useOptimistic` / `<form action>`）為**提交式表單 / server actions** 設計；其中只有 `useOptimistic` 與 autosave 相關，其餘**不適合**「邊改邊存、走 react-query PATCH」的文件編輯器。
- **RHF 2026**：仍適合「重驗證/動態陣列」表單；我們是 DnD 巢狀文件 + 多 panel + react-query 單一真相 → RHF 阻抗大、**不採用**。
- **autosave 2026**：react-admin `<AutoSave>`（debounce 預設 ~3s）、GitLab Pajamas（debounce + on-blur，點擊類立即）→ **hybrid 為權威**。react-query app 的樂觀更新慣用 **`onMutate`**（非 React 19 `useOptimistic`，那個綁 Actions）。
- 來源：Formisch《Choosing a React Form Library in 2026》、Croct《Best React form libraries of 2026》、react-admin AutoSave、react.dev useOptimistic、LogRocket RHF-vs-React19、GitLab Pajamas Saving&feedback。

### 9.2 定案
- **D9 = C**：選取/結構操作立即；自由文字 debounce ~500ms + blur；批次（自動帶入）單一 PATCH；顯示「儲存中…/已儲存」。
- **D10 狀態架構 = react-query 樂觀（onMutate）+ 欄位隔離（手刻）**；不引 RHF、不用 React 19 Actions。

---

## 10. 架構詳述：react-query 樂觀 + 欄位隔離（手刻）

> 現況：`usePatchDocument` 是 `onSuccess` 才 `setQueryData`（**非樂觀**，等 round-trip）。現在編輯「看似即時」是因 inline input 非受控（DOM 自存文字），但衍生狀態（完成度/連動/已填標記）有微延遲。改受控後需配樂觀更新。

### A. 寫入路徑：commit → 樂觀 → debounced PATCH
1. commit 當下立刻 `setQueryData(["document"], next)`（樂觀）→ UI 即時一致。
2. 網路 PATCH 走 debounce ~500ms：ref 存最新整份 doc、到期送一次、合併連續編輯；blur/關面板/導頁 flush。
3. `onError` → 回滾 snapshot + 顯示錯誤；`onSuccess(env)` → 以伺服器 canonical envelope 對帳版本。
4. 「儲存中…/已儲存」由 mutation pending/success 顯示。

### B. 欄位隔離（RHF 原則手刻）
- 可重用 `<FieldCombobox>`：props `value/options/allowCustom/multiple/onCommit`。
- 內部 `draft=useState(value)`；打字只動 draft（父層不重繪/不 PATCH）。
- 同步：`value` 變且**未聚焦** → `setDraft(value)`（反映自動帶入/連動/未來 LLM）；**聚焦中不覆蓋**。
- 提交：選官方選項立即 `onCommit`；自由文字 blur/debounce 才 `onCommit`。
- `React.memo` 隔離 sibling 重繪。

### C. code↔name 綁定
代碼選某 OCS → `onCommit` 一次寫 code＋name（＋desc/level smart default）＝一個 setter → 一次樂觀更新 → 名稱欄 `value` 變、未聚焦 → draft 同步顯示。

### D. 自動帶入（smart default）
「自動帶入官方」=一次組好填滿空欄的 `next`（來源 `/header-meta`）→ 單一樂觀更新 + 單一 PATCH。「重新帶入（覆寫）」同邏輯但覆蓋。

### E. 不用 React 19 useOptimistic
寫入走 react-query mutation；`onMutate` 即此 stack 的樂觀機制，混用 useOptimistic 會與 react-query 快取真相衝突。

### F. 風險/邊角
- 回應亂序 → debounce 合併 + 送整份 doc + 伺服器回 canonical 版本對帳。
- 聚焦中外部寫入 → 預設不覆蓋（保護打字）。
- 整份 doc payload 不大，OK。

---

## 11. 「自動帶入」呈現方式定案：選單內預勾 + 可移除 pills + 重拉鈕

使用者澄清（2026-06-26）：要的不是「盲目一鍵寫死」，而是「**選單一點開，官方就預先勾好，使用者取消/補勾；另有按鈕可把官方重新帶回；選單和按鈕都要有**」。理由：工作描述、說明**一定要看要改**。

### 11.1 研究佐證
- **smart defaults = 預載 + 驗證**：預填已知資料、讓使用者驗證/修改；多選用選單內 checkbox 預勾、關閉後**已選顯示為外部可移除 pills/tags**。（Zuko、Shopify、Carbon）
- **預勾 dark-pattern 分界**：GDPR/FTC 禁的是**同意類**預勾（需主動同意）；「不超出預期且**服務使用者利益**」的預選恰當。判準＝為使用者 or 為公司。本案＝官方事實、省工、可見可改 → **非 dark pattern**。（Termly、privacypolicies、UX Magazine）
- **LinkedIn skills**：建議挑 → 可移除 chips → 「當穩定事實的助手、保留敘事掌控、每次 review」。
- 來源：zuko.io smart-defaults、shopify cognitive-load、uxmag UX-of-defaults、termly GDPR-checkboxes、linkedin add-remove-skills。

### 11.2 每欄位型別模型（定案）
| 型別 | 互動 |
|---|---|
| 多值（類別/態度/資格/補充）| 選單開→官方**預勾**；已選＝外部**可移除 pills**；**「全選官方」**鈕重拉 |
| 綁定單值（代碼↔名稱）| 下拉選 OCS → code+name 綁定一起帶 |
| 自由單值（工作描述/級別）| **預填官方值、明顯可編輯**（描述為 textarea）；**「帶官方」**鈕重拉 |

- 「全選官方／帶官方」鈕 ＝ D4 顯式覆寫，做在每欄/每區。
- **收斂**：此「選單內預勾」即早先 deferred 的「自動添加」之更安全解法——**不在選職類時盲寫**，而是選單內預勾、攤給使用者看再 commit。
- HeaderMetaPanel 的「預設全勾」行為**保留**，搬成 inline 每欄（D3 不變）。

### 11.3 決策補充
- **D11 = 自動帶入以「選單內預勾 + 外部可移除 pills + 每欄/區重拉鈕」呈現**；不做盲目一鍵寫死；自由文字欄預填可改。
- **D12 = 所屬類別三類各自 name↔code 綁定**（職類別↔職類別代碼、職業別↔職業別代碼、行業別↔行業別代碼）。combobox 每個選項＝一個官方 `{code,name}` pair，選官方項即 code+名稱一起帶（綁定）；自訂項才允許手填、code 可空。延伸 D5。
  - 影響：取代現在 DocHeader「name/code 兩格各自手打」會對不起來的問題。
