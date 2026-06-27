# 欄位來源標記、鎖定等級與 UUID 身分 — 設計

> 日期：2026-06-27　狀態：設計定案（待寫實作計畫）
> 範圍：v3 前端職務說明書編輯（DocHeader / FieldCombobox / CellFiller / JobDocTable / DocNotes + ocsDoc setters + types）。後端**本期不動**。

## 1. 目的

讓文件裡的每個葉項目（O/P/K/S、態度 A、所屬類別三類、說明補充、基準代碼↔名稱）能：

1. **區分官方 vs 自訂**，且**改了官方內容就成為自訂**（不留「已改」中間態）。
2. **靠穩定身分（UUID）識別**，使排序、就地編輯都不錯亂——不靠 code 比對（有些項目沒有 code，且 code 是位置序號、非唯一）。
3. **在選單顯示每個官方候選的來源**（來自哪個官方職業基準），多來源可展開看全部。

非目標（明確排除）：
- 「已改」狀態與「重設回官方」——**移除**，改用「改了即自訂、官方仍可重選」。
- O/P 候選的「原始來源碼」（如 `O1.1.1`）後綴顯示——**後端本期不改**，延後另議；本期 O/P 來源行只顯示「職業名 + ocs_code」。
- 文件/表格版型變動——**不動**；只在下拉選單列加文字 + hover。

## 2. 背景：為什麼是「存標記 + UUID」而非「比對推導」

現況的「官方/已改/自訂」是**畫面即時比對官方清單**推導（`FieldCombobox.statusOf`、`DocHeader.catStatus`）。問題：官方候選沒載入時全判自訂；code+name 都改就對不回官方；不持久化，重載即失。

權威做法佐證本設計：

- **FHIR binding strength**（required / extensible / preferred / example）：不同欄位該有不同「必須遵守官方清單」的嚴格度 → 本設計的三層 tier。
- **代理鍵 vs 自然鍵**（Kimball/dbt）：業務碼（K01）會重複、隨位置變、跨來源不唯一 → 身分須用 surrogate key（UUID），code 只是顯示用自然鍵。
- **Salesforce restricted picklist**：受限清單不讓在 UI 改值，要不同值就另加 → 🔒 鎖定配對採此法。
- **Figma 元件 detach / 受控字彙 provenance**：改共用項即 fork 成獨立物件、並記錄來源 → 「改官方即自訂」+ 存來源。
- **Material 3 List Item supporting text + avatar group「+N」overflow**：選單次要行放來源 + 多來源用「+N」hover 展開。

## 3. 資料模型（前端，`_` 前綴＝前端專用、export 剝除）

```ts
// types/index.ts
interface ItemMeta {
  _id?: string;                 // 穩定 UUID：dnd/編輯 React key + 排序錨點
  _src?: "official" | "custom"; // 來源；加入當下即定，永不靠比對
  _ref?: SourceRef;             // 官方來源描述子；改內容→清空（轉自訂）
}
interface SourceRef {
  ocs_code: string;             // 來源官方基準碼，如 INM3513-009v1
  occupation_name: string;      // 來源職業名，如 AIoT應用工程師
  code: string;                 // 該項在「來源文件」中的原始碼（如 O1.1.1 / K01 / INM）
  sources?: SourceRef[];        // 多來源時的完整清單（首個外的其餘；供「+N」hover）
}

interface CodeName { code: string; name: string }      // 既有；+ ItemMeta 欄位（選擇性）
interface Indicator { code: string; text: string }     // 既有（P）；+ ItemMeta 欄位
```

實作上將 `_id` / `_src` / `_ref` 加到 `CodeName`、`Indicator`，以及表頭三類 `category` 的項目。

- `_src==="official"`：項目鏡射某官方候選，內容等同來源；`_ref` 記來源。
- `_src==="custom"`：自訂；無 `_ref`。
- 一旦使用者**改動官方項內容** → `_src="custom"`、`_ref=undefined`、`_id` 保留。

## 4. 三層鎖定等級（binding tier）

| Tier | 欄位 | code | name/內容 | 改內容的行為 | 排序 |
|------|------|------|-----------|--------------|------|
| 🔒 **鎖定配對**（required/restricted） | 基準代碼↔名稱、所屬類別三類（職類/職業/行業 各 name↔code） | 官方項唯讀 | 官方項唯讀 | **不可就地改**；要不同 → 走「＋加自訂」開一筆 custom（官方項不動） | 官方序固定 |
| ✏️ **自由值**（example） | 工作描述、基準級別 | — | 隨意改 | 自由改，**完全不標記** | — |
| 📋 **在地清單**（preferred + 代理鍵） | O、P、K、S、態度 A、說明補充 | 系統遞增、鎖定（位置序碼） | 隨意改 | **改即自訂**（fork）；官方項仍在選單、可重選 | UUID 身分；自由排序，code 依陣列位置**連號重編** |

判定隨 tier：
- 🔒：官方項從不就地改，故無「就地已改」；只有「官方（選中）」或「自訂（另加）」。
- ✏️：純值，無標記。
- 📋：兩態——官方（選中、未改，不標）/ 自訂（另加或改過官方，標「自訂」）。

## 5. 狀態與標記

| 狀態 | 條件 | 標記 |
|------|------|------|
| 官方 | `_src==="official"`（選中、未改） | 無 |
| 自訂 | `_src==="custom"`（＋加的，或改過官方的） | 琥珀「自訂」 |

**無「已改」、無「重設回官方」**。要回官方 → 在選單重新選取即可。

## 6. OPKS 選取/編輯流程（以 O 為例，定案）

1. 選單列出**官方候選**，顯示其**來源原始碼**（如 `O1.1.1`，取自來源職業文件，固定不變）。
2. 選中官方 → 文件加入該筆，文件顯示**位置序碼**（依本文件順序 `O1.1.1`），`_src=official`、`_ref` 設定。
3. **改動其內容** → 立刻 `_src=custom`、`_ref` 清空；選單裡該官方項**變回未勾選**；該自訂筆仍顯示位置序碼；官方候選**完全不變**。
4. **再選一次官方** → 接在後面，文件顯示下一個位置序碼（`O1.1.2`）。

**兩套碼並存且為預期行為**：
- **選單碼** = 來源原始碼（固定）。
- **文件碼** = 位置序碼（依順序連號重編，由 UUID 維持身分，故重編不影響來源/自訂判定）。

P/K/S/態度/說明同此模型（態度碼 `A01…`、K/S 碼系統遞增、說明無碼）。

## 7. 選單來源顯示（版面 A：Material 3 supporting text）

- 每個官方候選**名稱下方加一行淡灰小字**：`{occupation_name} · {ocs_code}`。
- **多來源**（同概念出現在多個官方職業）：顯示 `{首個職業} {ocs_code}  +N`，其中 **+N = 隱藏數**（首個以外的來源數，業界 avatar-group 慣例）。
- **hover「+N」** → popover 列出全部來源：`• {occupation_name} {ocs_code}`（逐行）。
- **僅選單顯示**；文件項目不顯示來源。
- **自訂項不進選單** → 無來源行。

資料來源（本期僅用既有，不改後端）：
- **類別/態度（header-meta）**：`HeaderMetaCandidate.sources: string[]`（ocs_codes）已有；`occupation_name` 由 `meta.primary_options`（`ocs_code → occupation_name`）解析。
- **O/P/K/S（task-catalog）**：一個任務僅來自一個官方職業 → 來源 = 任務的來源職業（`task.provenance.ocs_code` + 解析職業名）。**K/S 有原始碼**；**O/P 原始碼後端本期未提供** → O/P 來源行暫不含原始碼後綴（延後）。

## 8. 持久化

- `_id` / `_src` / `_ref` **存進 draft**（PATCH 寫入，重載不消失；如同既有 `_tid`/`_uid`/`_notes`）。
- **finalize/export 一律剝除**（正式 JSON 為既有特定契約格式，不帶前端欄位）。剝除點沿用既有「export 剝 `_` 欄位」機制；需確認 finalize/export 對未知 `_` 欄位的處理（計畫階段驗證）。

## 9. 約束與影響面

- **UI 不變**：僅在下拉選單列**加文字 + hover**；文件/表格版型不動。
- **必要行為變更（非版型）**：
  - 🔒 所屬類別：官方列的 name/code 由「可就地改」改為**唯讀**；要自訂仍走既有「＋加自訂」。（對齊使用者規範「一一對應不可改，想改走自訂」。）
  - 📋 OPKS/態度/說明：官方項就地改 → 自動轉自訂（`_src`→custom、清 `_ref`）。
  - 移除 `statusOf` / `catStatus` 的**比對推導**，改讀存好的 `_src`/`_ref`。
- **後端不動**：O/P 原始來源碼延後另議。

## 10. 可能觸及的檔案（供計畫參考，非最終）

- `frontend/src/types/index.ts` — `CodeName`/`Indicator` 加 `_id`/`_src`/`_ref`；`SourceRef`。
- `frontend/src/lib/ocsDoc.ts` — `ensureIds` 擴及葉項目補 `_id`；setter（`setKS`/`setOp`/`setAttitudes`/`setNotes`/類別 setters）寫 `_src`/`_ref`；就地改→轉 custom 的邏輯；位置序碼重編；export/finalize 剝除確認。
- `frontend/src/lib/headerMeta.ts` — option 帶 `SourceRef`（由 `sources` + `primary_options` 組）。
- `frontend/src/hooks/useTaskCatalog.ts` — O/P/K/S option 帶來源（任務來源職業）。
- `frontend/src/components/interview/v3/fields/FieldCombobox.tsx` — 選單列加來源行 + 「+N」hover popover；以 `_src`/`_ref` 取代 `statusOf` 推導；自訂標記。
- `frontend/src/components/interview/v3/DocHeader.tsx` — 🔒 類別官方列唯讀；類別 option 來源行；以 `_src` 標自訂。
- `frontend/src/components/interview/v3/{CellFillerPanel,DocNotes,JobDocTable}.tsx` — 沿用 FieldCombobox 新行為。

## 11. 測試考量（前端 gate：`tsc --noEmit` + `npm run lint`）

- 型別：新欄位為選擇性，不破壞既有契約序列化。
- 行為（手動/邏輯函式可單測者集中在 `ocsDoc.ts`）：
  - 選官方 → `_src=official`、`_ref` 正確；改內容 → 轉 `_src=custom`、清 `_ref`、`_id` 不變。
  - 排序後位置序碼連號重編，且來源/自訂判定不變。
  - export/finalize 後 `_id`/`_src`/`_ref` 不出現在輸出。
  - 多來源 option 的 `+N` 與 hover 清單數量正確。
