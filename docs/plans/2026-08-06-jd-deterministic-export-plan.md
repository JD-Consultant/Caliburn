# JD deterministic export（切片 B）實作計畫

- 日期：2026-08-06
- 狀態：T1–T5 尚未開工；**依賴切片 A 完成**
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
2. **工作表 1「職能基準表」**：表頭六欄 ＋ Duty→Task→O/P 表格 ＋ 職能級別 ＋ K/S/A 清單 ＋
   說明與補充事項。
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
