# 欄位來源標記／鎖定等級／UUID 身分 — 討論與決策記錄（living）

> 日期：2026-06-27　配套：`2026-06-27-field-provenance-lock-tiers-design.md`
> 用途：完整保留討論脈絡、每個決策的理由、被否決的方案與原因、參考資料、延後不做的項目與原因。供日後報告。

## 1. 緣起與問題

使用者問「我們不是有 uuid 嗎？就是 OPKST」，希望「欄位可以標記，改值就知道改的是官方的，也能區分自訂或官方，並能自行排序而不錯亂」。

釐清現況（事實）：
- 只有 **職責單元 `_uid`** 與 **任務 `_tid`** 有前端臨時 id（`ocsDoc.ts` `ensureIds`/`uid`），**O/P/K/S 完全沒有 id**。
- `_uid`/`_tid` 是**前端臨時 id**（dnd 用），**不進契約、重載重生**，非真 UUID。
- 「官方/已改/自訂」標記是**畫面即時比對官方清單推導**（`FieldCombobox.statusOf`、`DocHeader.catStatus`），不是存的。

→ 這正是「會錯亂」的根因：官方清單沒載入全判自訂；code+name 都改就對不回官方；不持久化、重載即失。

## 2. 決策清單（含理由）

- **F1 不是要 uuid，是要「存起來的來源標記」**：uuid 只解決身分/排序，無法分辨官方 vs 自訂。真正解法＝把 `_src`（官方/自訂）+ 來源直接存在項目上，不靠比對。
- **F2 持久化分層**：`_id`/`_src`/`_ref` **存進 draft**（重載不消失），**export 正式 JSON 一律剝除**（使用者：「我們有 JSON 特定格式」）。→ 採「只存 draft、出檔剝除」（非「存進 export」、非「純前端不持久化」）。
- **F3 不靠 code 比對判來源**：因為「有些項目沒有 code」「code 是位置序號、非唯一」（使用者明示：別職位的 K01 不一樣、K01/K02 換序沒差）。→ 身分用 UUID（代理鍵），code 僅顯示。
- **F4 三層 binding tier**（對齊 FHIR）：
  - 🔒 鎖定配對（基準代碼↔名稱、所屬類別三類）：官方唯讀，要不同走「＋加自訂」。
  - ✏️ 自由值（工作描述、基準級別）：自由改、**完全不標記**。
  - 📋 在地清單（O/P/K/S、態度、說明）：改即自訂、可自由排序、code 連號重編。
- **F5 移除「已改」與「重設回官方」**：使用者模型是「改了就直接變自訂，官方原封不動還在選單、可重選」。既然官方一直都在，要回去重選即可，「重設」多餘 → **砍掉已改中間態與 reset**。
- **F6 OPKS 兩套碼並存**：選單顯示「來源原始碼」（固定，取自來源職業文件）；文件顯示「位置序碼」（依順序連號重編）。同一筆在選單 `O1.1.1`、在文件 `O1.1.2` 是**預期行為**。
- **F7 排序採「連號重編 + UUID 身分」**：而非 LexoRank/fractional indexing（理由見 §3）。
- **F8 單值欄位（工作描述/基準級別）= 純自由值、不標記**（選項 A）。理由：單格無法 fork 成另一筆；標「已改」會把砍掉的中間態帶回、與 OPKS 不一致。
- **F9 來源顯示「首個 + +N + hover 全部」**，且 **+N = 隱藏數**（業界 avatar-group 慣例），非「共N 總數」。
- **F10 來源版面採 A（Material 3 supporting text，名稱下方次要行）**，否決 B（靠右）/ C（上方 overline），理由見 §3。
- **F11 來源僅在選單顯示**（不在文件項目上）；自訂項不進選單故無來源行。
- **F12 UI 不變原則**：只在下拉選單列加文字 + hover；文件/表格版型不動。🔒 類別官方列改唯讀屬「行為變更非版型」，且為使用者規範本身所要求。
- **F13 export 剝除＝本專案後端遞迴清 `_` 欄位**：發現本專案後端 `build()`（`ocs_doc.py`）原為「逐一 pop 指定 key、且只到 unit/task 層」，不會清葉項目的 `_id`/`_src`/`_ref`。經使用者同意（「可以隨便改，要規範、主流架構、解耦」），改為遞迴 helper `_strip_underscore`（刪任意深度任何 `_` 開頭 key），一勞永逸涵蓋既有 `_pool/_uid/_tid/_notes` 與新欄位。註：此為**本專案後端**，與延後的 O/P 原始碼（indexer/catalog 端）無關。
- **F14 多來源放 `OptionItem.srcs`、文件項 `_ref` 為單一 SourceRef**：spec §3 原將多來源寫成自我遞迴的 `SourceRef.sources?`；實作精化為——選單候選的多來源放 `OptionItem.srcs: SourceRef[]`，文件項 `_ref` 只記選中當下的首要來源。語意等價、較不自我遞迴。
- **F15 CellFiller 的 O/P/K/S 由 chips 改「可編輯直式列」（layout="list"）**：執行時發現主表格只把 OPKS 當計數格、編輯都在 CellFiller，而 CellFiller 原用 pills（chips）只能加/刪、無法就地改字 → 無法實現「改官方 O 內容→變自訂」。經使用者拍板改成與「態度」一致的可編輯直式列（代碼 + 名稱輸入框 + 自訂標記 + 刪除）。屬計畫缺口的修正，已停下確認後再做。

## 3. 被否決 / 不採用的方案（為什麼不做）

- **`_dirty` 布林 vs `_ref` 快照**：早期曾提「存 `_dirty` 翻 true」。**不採用**——無法顯示原值、無法判斷是否改回。最終因 F5 砍掉「已改」，`_ref` 改作「來源描述子」而非「已改比對基準」。
- **Figma 式「就地改→偷偷變自訂」用於 🔒**：**不採用於鎖定配對**。會讓人困惑「我改的明明是官方怎變自訂」。🔒 改採 Salesforce restricted picklist：官方唯讀、要不同就另加（最不意外，且字面對齊使用者規範）。注意：📋 在地清單**仍採**「改即自訂（fork）」——因為清單可以多一筆、且官方仍在選單可重選，不會困惑。
- **LexoRank / fractional indexing（Jira/Figma）做排序**：**不採用**。那是為「大量資料 + 多人協作」避免群體重編；本案每任務 K/S 僅寥寥數筆，重編成本趨近零，而 LexoRank 會產生**不連號的醜 code**，違背「本質上是遞增」。身分/排序分離的精神用 UUID 已達成，順序直接用陣列序、code 用位置算最簡單。
- **來源版面 B（靠右 metadata）**：**否決**。選單寬僅 ~288px（`w-72`），職業名 6~10 字 + ocs_code 同列幾乎必被截斷（Carbon 也提醒次要文字要短）。
- **來源版面 C（上方 overline）**：**否決**。把來源放名稱上方會切斷「勾選＋名稱」主動作的視覺連續、選單也少見此法、占垂直空間。
- **計數寫「共N（總數）」**：**否決**（使用者選 +N）。+N 為跨設計系統通用 overflow 慣例。
- **本期改後端讓 O/P 回原始來源碼**：**延後**（使用者：「之後再討論，先用已有的，不改後端」）。影響：O/P 來源行暫不含 `O1.1.1` 後綴。

## 4. 參考資料（權威/主流，不限年份）

- FHIR Terminologies — binding strength required/extensible/preferred/example：<https://www.hl7.org/fhir/terminologies.html>　→ 三層 tier 的依據。
- GNU gettext「Fuzzy Entries」+ `#|` previous-string：<https://www.gnu.org/software/gettext/manual/html_node/Fuzzy-Entries.html>　→ 「原值改了標記＋保留原文」的範式（最終因 F5 未採已改，但啟發 `_ref` 概念）。
- dbt：surrogate key 指南：<https://www.getdbt.com/blog/guide-to-surrogate-key>；Agile Data 自然鍵 vs 代理鍵：<https://agiledata.org/essays/keys.html>　→ UUID 當身分、code 當自然鍵。
- Salesforce restricted vs unrestricted picklist：<https://www.salesforceben.com/bad-value-for-restricted-picklist-field/>　→ 🔒 鎖定配對互動。
- VS Code settings modified indicator / reset-to-default：<https://code.visualstudio.com/docs/getstarted/settings>　→ 「只標非預設」呈現（與既有 D14「只標非官方」一致）。
- Figma 元件 override / detach / 本地副本：<https://help.figma.com/hc/en-us/articles/18490793776023-Update-1-Tokens-variables-and-styles>　→ 「改共用項即 fork」概念。
- 受控字彙 provenance（來源治理）：<https://jessicatalisman.substack.com/p/controlled-vocabularies-part-ii>；Wikipedia 受控字彙：<https://en.wikipedia.org/wiki/Controlled_vocabulary>。
- Material Design 3 List Item（overline/headline/supporting/trailing 槽位）：<https://m3.material.io/components/lists/guidelines>　→ 來源放 supporting text。
- Avatar group「+N」overflow + hover popover：GitLab Pajamas <https://design.gitlab.com/components/avatar-group/>、Atlassian <https://atlassian.design/components/avatar-group>、SAP Fiori、Innovaccer、Emplifi Soul、Procore（多家一致）。
- Carbon dropdown 次要文字要短：<https://carbondesignsystem.com/components/dropdown/usage/>。
- Atlassian Select 自訂 option 渲染：<https://atlassian.design/components/select>。

## 5. Bug / 風險記錄

- 本次設計階段未引入新 bug（未寫碼）。
- 既往相關 bug（背景）：CellFiller「一勾就關」已於前一輪修復（`fcb347e`，`onSave` 不再帶關閉 callback），本設計沿用「選了/不選不退出選單」前提以支援連續選取。
- 實作風險（計畫階段須驗證）：
  - **export/finalize 剝除**：須確認 finalize/export 對未知 `_` 欄位的處理；若後端 Pydantic 嚴格拒收未知欄位，PATCH draft 也須容忍（既有 `_tid`/`_uid`/`_notes` 已在 draft 流通，推測可行，仍須證實）。
  - **🔒 類別官方列改唯讀**：屬行為變更，須確認不影響既有「＋加自訂／刪列」路徑。
  - **位置序碼連號重編**：須確保重編後 `_ref`（來源原始碼）不被覆寫、判定仍正確。

## 6. 延後／未定（待之後討論）

- O/P 原始來源碼後綴（需後端 task-catalog 回原始碼 + per-item 來源）。
- export/finalize 是否將 `_src` 折成契約既有 `source_type`（`icap_official`/`company_defined`）——目前決定**不折、直接剝除**（使用者：JSON 特定格式不留），但日後若要在輸出保留 provenance 可重議。
- 跨來源去重的 K/S 在「改即自訂」後，是否影響文件層級去重邏輯（計畫階段釐清）。
