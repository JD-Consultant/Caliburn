# 0056. 嚴格公版職務說明書 XLSX 匯出

- 狀態：Accepted
- 日期：2026-08-09
- 依據：[`docs/specs/2026-08-08-unreviewed-branches-review.md`](../specs/2026-08-08-unreviewed-branches-review.md) §12、§16，
  [`docs/specs/2026-08-02-icap-2026-quality-manual-form-authority.md`](../specs/2026-08-02-icap-2026-quality-manual-form-authority.md)
- 延續：[0052](0052-jd-readiness-assessment-and-official-code-boundaries.md) 的 readiness、代碼權責與 deterministic export 邊界
- 核准：2026-08-09 owner 明確核准選擇性移植 XLSX，並要求匯出與公版一致

## 脈絡

Current JD 的 Header、Duty、Task、OPKS 與排序會形成比公版更細的本機編輯模型；這是員工工作介面的需要，
不代表匯出可以改變官方版型。未審分支已證明純組裝、XLSX renderer 與下載 route 可行，
但其第二張缺漏工作表、非官方聲明、dirty 狀態下仍可下載，以及文字可能被 Excel 解讀為公式，
都不符合本產品的匯出邊界。

匯出必須同時保住兩件事：只輸出員工已保存的 Current State，不讓草稿或 LLM 在下載時改資料；
產物只呈現公版容許的欄位與版面，不把本產品的診斷資訊偽裝成官方內容。

## 決定

1. `app/job_analysis/application` 提供純、無 IO 的 `ExportDocument` 投影，從一份已驗證的
   `JobAnalysisState` 決定性組裝匯出內容。renderer 只消費此投影，不讀資料庫、不呼叫 LLM，
   也不自行重算產品語意。
2. 第一版只提供 XLSX。XLSX renderer 與 application 投影分開；PDF／DOCX 待真實需求出現再做，
   不先建立通用匯出 framework。
3. `T1`／`T1.1`／`O1.1.1`／`P1.1.1` 與 `K01`／`S01`／`A01` 都是依當下排序產生的版面位置碼，
   不落庫、不取代 `duty_id`／`task_id`／`entity_id`。文件層 K／S 的多對多 refs 保留，
   不為輸出複製 domain identity。
4. workbook **只含官方 `職能基準表`**。不得加入「缺漏」工作表、產品聲明、自創說明列或其他非公版內容。
   Current State 沒有公版位置可承載的資訊不塞入檔案。
5. 未分組但仍屬 Current JD 的 Task 必須保留在官方 Task 列，Duty 欄留白；不得因缺少 Duty 而靜默省略。
   官方允許空白或本產品尚無可信資料的欄位保持空白，不由 application 或模型補值。
6. readiness 不阻擋匯出。Web 在下載前呈現既有 readiness、未分組與未連結提示；有未保存編輯時停用匯出，
   要求員工先保存或取消，不自動保存，也不把畫面草稿混入 XLSX。
7. renderer 的單一文字寫入 seam 必須把員工與模型文字寫成字串；前導 `=`、`+`、`-`、`@` 等內容
   不得成為公式。系統沒有任何需要公式的匯出欄位。
8. 儲存格合併、框線、對齊、換行、列高、欄寬與列印設定依 2026-01-27 官方手冊中的
   `職能基準表` 體例實作並以真實 workbook 驗證，不以自製版型宣稱「公版」。
9. 下載使用 `GET /documents/{document_id}/export` 的唯讀 binary response，回 XLSX media type 與可用的中文檔名；
   不要求 `Idempotency-Key`。route 只做 transport mapping，組裝與渲染錯誤回既有 typed problem response。
10. 匯出屬 `job_analysis` bounded context，不復用 OCS contract，也不為內部 application 投影新增 JSON Schema seam。

## 後果

### 正面

- Web 編輯模型可持續比公版更細，匯出仍能穩定對齊官方表格。
- 缺漏提示與正式文件分離，不會把產品診斷內容誤認成官方欄位。
- 匯出可重現、可離線測試，且不產生新的 LLM 成本或文件權威來源。
- 位置碼與 identity 分離，重排只改匯出位置，不改 domain reference。

### 代價

- readiness 仍只提示不阻擋，因此員工可以下載含空白欄位的公版文件；下載前的可見提示承擔這項風險。
- 不屬於公版的本機細節不會出現在 XLSX；需要保存完整內部資訊時仍以 Current State 與 Web 為準。
- 第一版需維護一份經實際 Excel／LibreOffice 開啟與列印驗證的官方版型 fixture；版型日後變更時須重新核對官方來源。

## 不在本 ADR 內

- AI 自動建立 Duty、修改 Task／OPKS prompt、OPKS lifecycle 或 scheduler；
- `4096 → 16384` token 預設、server／enterprise scope、舊 R1 runtime；
- PDF／DOCX、通用模板引擎、舊資料搬遷或舊系統整合；
- 本機一鍵啟動器與部署包裝；它們是後續獨立切片。
