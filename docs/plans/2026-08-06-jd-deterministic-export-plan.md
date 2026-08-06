# JD deterministic export（切片 B）實作計畫

- 日期：2026-08-06
- 狀態：T1–T5 COMPLETE（切片 A 已完成）
- 決策：[ADR 0058](../adr/0058-jd-deterministic-export-shape-and-format.md)（本切片的權威依據）；
  延續 [ADR 0052](../adr/0052-jd-readiness-assessment-and-official-code-boundaries.md) 決定 4／5／8／10／13／14
- 研究：[`2026-08-06-jd-deterministic-export-research.md`](../specs/2026-08-06-jd-deterministic-export-research.md)
- 版型權威：[iCAP 2026 手冊逐字核對](../specs/2026-08-02-icap-2026-quality-manual-form-authority.md)、
  [2022 指引欄位標準](../specs/2026-07-13-ai-redesign-raw-icap-field-standards.md)
- **前置切片**：[O/P/K/S/A 員工可控排序](2026-08-06-job-analysis-opks-display-order-plan.md)（切片 A）
  ——位置碼由 `display_order` 推出，A 未完成前不得開工 B
- 現行設計：[`task-analysis-engine.md`](../design/task-analysis-engine.md)

## 1. 目標與現況

切片 A 完成後，Current State 具備公版六個 header 欄位、Duty→Task 兩層結構、每 Task 職能級別、
文件層平坦編號且**員工可排序**的 K/S/A，以及每 Task 可排序的 O/P——匯出所需的一切都齊了。
剩下的是把它排成一份符合 iCAP 2026 手冊版型的 XLSX，這是 ADR 0052 決定 14 特地留白的部分。

## 2. 範圍

做：
- 純函式組裝：`JobAnalysisState` → `ExportDocument`（位置碼、排序、未歸類 Task 集合全部算好）
- XLSX renderer（`openpyxl`）：**兩個工作表**——公版表格 ＋ 缺漏清單
- 一條 route：`GET /documents/{document_id}/export`
- Web 匯出按鈕
- 修正 `docs/contract-strategy.md` 那句過時預答（ADR 0058 決定 7 要求）

不做（ADR 0058「不在本 ADR 範圍」已列）：DOCX／PDF renderer、O→P 參照連結、
`JdTask` 內部欄位的附錄、職業別／行業別代碼格式檢查。

## 3. 位置碼（ADR 0058 決定 3–4 的施工版）

```
T{i}         = current_duties 依 display_order 排序後的第 i 個（1-based）
T{i}.{j}     = 該 Duty 底下的 Task 依 display_order 重新從 1 排序後的第 j 個
未歸類 Task   = duty_id 為 None（指向不存在 Duty 者理論上不可達——JobAnalysisState 已拒絕
               dangling duty_id——仍併入同一集合，不特判）
O{i}.{j}.{k} = 該 Task 的 OUTPUT 依 display_order 排序後的第 k 個
P{i}.{j}.{k} = 該 Task 的 INDICATOR 依 display_order 排序後的第 k 個   ← 三段，與 O 同層
K{n}/S{n}/A{n} = 全文件該 kind 依 display_order 排序後的第 n 個
```

## 4. Task 切片（一個 task 一個 commit，綠了才 commit）

### T1 — `ExportDocument` 純組裝與位置碼

1. `app/job_analysis/application/export.py`：
   - `ExportOpksEntry`（`position_code`、`text`）
   - `ExportTaskEntry`（`position_code: str | None`——未歸類為 `None`、`statement`、
     `competency_level`、`outputs`／`indicators`）
   - `ExportDutySection`（`position_code`、`statement`、`tasks`）
   - `ExportDocument`（`title`、`header: JdHeader`、`duties`、`unassigned_tasks`、
     `knowledge`／`skills`／`attitudes`）——frozen `DomainModel`
   - `assemble_export_document(state, *, title) -> ExportDocument`：零 IO，
     **不 import transport contract**（比照 `assess_readiness()`）
2. 測試 `tests/test_job_analysis_export_assembly.py`：
   - 位置碼正確（多 Duty、多 Task、Duty 內重新從 1 編號、O/P 三段且同層）
   - 未歸類 Task 進 `unassigned_tasks`、`position_code` 為 `None`、**不遺漏**
   - K/S/A 是文件層平坦編號，不隨 Task 重複
   - 空文件回傳全空但不拋錯
   - 決定性：同輸入兩次呼叫結果相等

完成條件：純函式零 IO；AST guard 仍綠。

### T2 — XLSX renderer（兩個工作表）

1. `app/job_analysis/application/export_xlsx.py`：`render_xlsx(document, readiness) -> bytes`。
2. **工作表 1「職能基準表」**：版面依 **2026-08-06 逐份核對的七份官方職能基準範例**
   （`.odt` 2023 版與 `.docx` 2025 版結構一致），不是照手冊散文推的——
   主表**七欄**（主要職責｜工作任務｜工作產出｜行為指標｜職能級別｜職能內涵K｜職能內涵S）、
   同格內多筆**換行**並列、位置碼與文字**不留空格**、主要職責格**垂直合併**、
   態度與說明與補充事項**各自獨立區塊**。
   - 未填欄位**維持空白儲存格**，不印「（尚未填寫）」——欄位必須在，只是空的（ADR 0058 決定 12）
   - **未歸入主要職責的 Task 必須有自己的區塊**，不得因為排不進表格而消失（決定 3 的硬性要求）
   - `職能基準代碼`／`職類別代碼` 標「（iCAP 計畫執行單位提供）」，不留輸入痕跡
   - ADR 0040 決定 33 的公版措辭固定寫在表上
3. **工作表 2「iCAP 版型缺漏」**：由 `assess_readiness()` 產出（**落實 ADR 0052 決定 4**），
   標題沿用「iCAP 版型欄位尚有 X 項未填」，逐條列出 issue；**零 issue 時該表保持空的清單但仍存在**
   （比照 `ReadinessNotice` 零 issue 不渲染的精神，這裡改為「表在、內容為空」，
   因為工作表結構固定比動態增減表更容易被下游工具處理）。
4. 測試 `tests/test_job_analysis_export_xlsx.py`：用 `openpyxl` 讀回位元組後斷言——
   - 表頭六欄與位置碼、敘述文字落在正確儲存格
   - 未歸類 Task 區塊確實存在且列出對應 Task
   - 缺漏工作表存在、內容等於 `assess_readiness()` 的結果、措辭不含「不完整／不合格／未通過」
   - 空文件仍產出合法 XLSX
   - 公版措辭與兩個免填代碼欄位的固定文案存在

完成條件：讀回渲染結果驗證內容，不只驗證「沒拋錯」。

### T3 — HTTP route

1. `GET /{document_id}/export`，`Response` 直接回位元組，
   `media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"`，
   `Content-Disposition: attachment`（檔名用文件 `title`，**非 ASCII 需正確編碼**）。
   唯一錯誤路徑 `DocumentNotFound → 404`；**不需要 `Idempotency-Key`**（GET、無副作用）。
2. 不進 `job-analysis-contract`（ADR 0058 決定 8）。
3. 測試：200 帶正確 `Content-Type`／`Content-Disposition`、未知文件 404、
   **readiness 有缺漏時仍然 200**（匯出永遠放行的迴歸測試）。

### T4 — Web 匯出按鈕

1. `jobAnalysisApi.ts`：取回 `Blob` 並觸發下載。**不能複用 `download.ts` 的 `downloadJson()`**
   ——那支是 JSON-only，需要二進位版本。
2. `ConsultationWorkspace.tsx` header 區加「匯出」按鈕；**不需要 dirty guard**（純讀取）。
3. 可抽出的純邏輯（檔名組裝等）放 `src/lib/` 才有 vitest 覆蓋。
4. web 三件套＋`npm run build`。

完成條件：**本切片明確沒有真人瀏覽器驗證**（比照 Duty T6 的坦白）——若要驗證需重啟本機
dev server，動手前先問。

### T5 — 文檔同步（併在各 commit 或收尾補齊）

1. `docs/contract-strategy.md` §5 契約 #4：把「`ocs-contract` remains the public/export shape」
   改成準確反映 ADR 0058 決定 7 的覆蓋——**不刪歷史，註明已被取代**，避免下一個讀者照舊文字犯錯。
2. `docs/design/task-analysis-engine.md`：§2 補匯出組件；補「位置碼不落庫」與「匯出永遠放行」
   兩條不變量，指回 ADR 0058。
3. `ARCHITECTURE.md`：視既有寫法決定要不要補匯出能力，不強行擴充不相關段落。

## 5. 開放問題（不擋 T1–T5）

- `JdTask` 內部欄位要不要以附錄工作表匯出
- 職業別／行業別代碼格式檢查
- O→P 參照連結（ADR 0058「不在本 ADR 範圍」已說明：匯出不需要，屬品質工作面）

## 6. T1 執行證據（2026-08-06）

- baseline：完整 API `2158 passed`。
- **`ExportOpksEntry.position_code` 做成 nullable，這是初稿沒想到的。** 未指派主要職責的 Task
  沒有 `T{i}.{j}`，也就推不出 `O{i}.{j}.{k}`。第一版寫成「未指派 Task 的 O/P 直接不帶出來」，
  **那是靜默刪掉員工內容**——排不進表格不是把它從成品上刪掉的理由（ADR 0052 決定 5）。
  改成位置碼為 `None` 但內容照帶，並以 mutation check 證明這條測試是承重的
  （還原成回 `()` → `test_an_unassigned_task_keeps_its_content_but_gets_no_code` 變紅）。
- **`_in_kind()` 明確依 `display_order` 排序，不依賴 tuple 既有順序。** 這正是切片 A 決定
  不要求 `CurrentJdOpks` canonical 排序時所承諾的「位置碼正確性由匯出端負責」；
  有專測把 tuple 故意亂序，斷言位置碼仍正確。
- 另有測試守：Duty 內 Task 重新從 1 編號、O 與 P 三段同層、K/S/A 文件層平坦且**同一條 K
  支援兩個 Task 時不複製**（ADR 0048 決定 7）、空職責照樣出現、**任何 Task 都不會遺失或重複**、
  空文件不拋錯、header 原樣帶過、同輸入同輸出。
- 完整 API：**`2169 passed / 0 failed / 0 skipped`**（+11）。
- 下一個是 T2（XLSX renderer，兩個工作表）。

## 7. T2 執行證據（2026-08-06）

- baseline：完整 API `2169 passed`。
- 版面：一條 Task 佔 `max(1, |O|, |P|)` 列，職責／任務／級別只寫在第一列，
  O 與 P 各自往下填。第二條工作產出因此落在 `O1.1.2` 那一列，不擠在同一格。
- **兩個 iCAP 配發代碼固定印「（iCAP 計畫執行單位提供）」**，有測試斷言剛好出現兩次
  ——不開輸入欄、不生成（ADR 0052 決定 8）。
- **缺漏維持空白儲存格**：有測試斷言公版表上不出現「尚未填寫」「不完整」等字樣。
  要交給主管／HR 的是這張表，不該被提示文字弄髒。
- **缺漏工作表呼叫 `assess_readiness()`**（落實 ADR 0052 決定 4），措辭
  「iCAP 版型欄位尚有 X 項未填」；另有測試斷言不出現「不完整／不合格／未通過」
  （ADR 0052 決定 7）。零 issue 時該表仍存在並顯示 0 項。
- `READINESS_LABELS` 有一條**機械守衛**：`set(READINESS_LABELS) == set(ReadinessIssueCode)`。
  新增 issue code 卻忘了文案會直接變紅，不會默默把機器代碼印給主管看。
  （Web 另有一份文案；兩個呈現面各自持有，但都不自行判斷缺漏——ADR 0052 決定 3。）
- 未歸入主要職責的 Task 有自己的區塊且**保留 O/P 內容**（無位置碼）；
  以 mutation check 證明是承重的（拿掉該區塊 → 測試變紅）。
- 空職責照樣印出（`duty_without_task` 要讓人看見）；空文件仍產出合法 XLSX。
- 位元組不保證穩定（XLSX 內含 zip timestamp），所以決定性測試比對的是**讀回的內容**。
- 另跑了一次人工檢視：把兩張工作表印成文字方格核對版面，確認表頭空格、
  `O1.1.2` 換列、空職責、未歸類區塊與缺漏表都如預期。
- 完整 API：**`2184 passed / 0 failed / 0 skipped`**（+15）。
- 下一個是 T3（HTTP route）。

## 8. 官方範例核對後的版面修正（2026-08-06）

owner 提供七份官方職能基準文件（會計助理／會計人員／會計主管／採購專員／採購經理／
行政總務主管 的 `.odt` 與 `.docx`）。逐份核對後，T1／T2 的版面有多處要改——
手冊散文沒說清楚的，真實範例說清楚了。

| | 官方範例 | 修正前 |
|---|---|---|
| 主表欄位 | **七欄**，最後兩欄是職能內涵 K 與 S | 五欄，K/S 放表格外清單 |
| K/S 擺放 | **每個 Task 列列出該 Task 的 K/S**（`K01` 在多列重複） | 文件底部平坦清單 |
| 位置碼 | **不留空格**（`O1.1.1提款單/匯款單`） | 有空格 |
| 多筆 O/P/K/S | **同格換行** | 各佔一列 |
| 主要職責格 | 跨其 Task 列**垂直合併** | 只寫第一列 |
| 表頭 | 名稱**擇一填寫**（職類／職業兩列）；所屬類別三列，名稱與代碼**同列** | 每項一列 |
| 態度／說明 | **各自獨立表格** | 與 K/S 並列的清單 |

**這不需要新 ADR。** 第一眼以為「K/S 每列重複」推翻了 ADR 0048 決定 7 的「匯出時不必複製
K/S」，但那是誤讀：「不必複製」講的是 identity（不鑄 `K01-a`／`K01-b`），而同一條決定
**明文允許**「UI 可把 K/S 投影在 Task 或 Indicator 底下」。官方表格正是如此——`K01` 到哪一列
都是同一個知識，只是被引用多次。ADR 0058 本身也沒有規定欄位數，那是本 plan 先前自己猜的。

### 連帶的兩個實作決定

- **`ExportTaskEntry` 增 `knowledge`／`skills`**，依 `task_refs` **或**透過 `indicator_refs`
  連到該 Task 的指標來過濾（ADR 0048 決定 6：K/S 與 Task／Indicator 多對多，
  只看 `task_refs` 會漏掉「只掛在指標上」的）。編號仍是文件層。
- **`unlinked_knowledge`／`unlinked_skills`**：沒連上任何 Task 的 K/S 主表放不下，
  但**不得從成品上消失**——與未指派 Task 同一條理由。有測試斷言
  「每一條 K 不是出現在某個 Task 底下，就是出現在未連結區」。

### 一處我自行決定的對應

官方「職能基準名稱（擇一填寫）」有職類／職業兩列。我們的 `JdHeader.competency_name`
是單一欄位，無法分辨。**填在「職業」列**，因為我們產出的是**特定職位**的職務說明書；
「職類」列留空。若 owner 認為該反過來，改一行即可。

### 說明與補充事項維持自由文字

官方有「建議擔任此職類／職業之學歷／經驗／或能力條件：」與「其他補充說明：」兩個子標題。
owner 於 2026-08-06 裁定**維持單一自由文字**（`JdHeader.notes`），不拆欄位——
第一版是員工確認的 JD 草稿，不是送審的職能基準，硬套子標題會讓員工以為必須填學歷條件。

- 完整 API：**`2192 passed / 0 failed / 0 skipped`**（+8：assembly +3、xlsx +5）。

## 9. T3–T5 執行證據（2026-08-06）

- **T3 route**：`GET /{document_id}/export`，回 XLSX 位元組，無 `Idempotency-Key`（GET 無副作用）。
  `Content-Disposition` 用 **RFC 6266／5987** 的雙寫法：ASCII fallback ＋ 百分比編碼的
  `filename*`——中文標題直接塞 `filename=` 會被瀏覽器存成亂碼。檔名先清掉路徑字元，
  清完是空的用固定 fallback，免得存出一個沒有名字的檔。
  測試：200 帶正確 media type 與 `filename*`、**讀回位元組確認是可開啟的 XLSX**（不是空殼）、
  未知文件 404、**readiness 有缺漏時仍 200**（匯出永遠放行的迴歸測試）、連續兩次 GET 都成功。
- **T4 Web**：`ConsultationWorkspace` header 加匯出按鈕。**不需要 dirty guard**（純讀取，
  不動任何權威狀態）。`downloadJson()` 是 JSON-only，另加 `downloadBlob()`；
  `exportDocument()` 不能走 `request()`（那支預期 JSON），但失敗時後端仍回 problem+json，
  所以錯誤路徑照樣解析成 `JobAnalysisApiError`。檔名組裝抽成 `lib/jobAnalysisExport.ts`
  才有 vitest 覆蓋（Duty T6 的教訓），有測試守路徑字元與空標題 fallback。
- **T5 文檔**：`contract-strategy.md` §5 契約 #4 那句「`ocs-contract` remains the
  public/export shape」**以引用區塊標明已被 ADR 0058 決定 7 取代**——不刪歷史，
  讓下一個讀者不會照舊文字重新犯錯。`docs/design/task-analysis-engine.md` §2 補上
  匯出組裝與匯出渲染兩列，並把匯出狀態從「仍未做」改為完成。
- **本切片沒有真人瀏覽器驗證**（比照 Duty T6 與切片 A 的坦白）——要驗證需重啟本機
  dev server，動手前先問。route 層有真 PostgreSQL HTTP 測試覆蓋。
- 完整 API：**`2196 passed / 0 failed / 0 skipped`**（+4）。
  web **`125 passed`**（+3）＋tsc＋lint＋`npm run build` 全綠。

