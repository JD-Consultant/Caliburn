# 未核准分支整體審查報告

- 審查日期：2026-08-08
- 審查基準：`origin/main` `9704a913f7746636088e0a6db4a825544d17270b`
- 審查對象：
  - `origin/feat/jd-header-and-readiness` `f26a512031aca2715b129117d063793926b7cbec`
  - `origin/docs/jd-export-adr-and-plans` `ea704c9dbe3a9d7cf9dd2539c2af5067051ee342`
- 性質：分支整體審查；不是合併決定、ADR 或實作計畫

## 1. 結論先講

兩個分支目前都**不通過整包合併**。理由不是測試是否通過，而是它們同時包含：

1. 尚未核准的產品部署方向；
2. 對目前 OPKS Accepted／Rejected 決策的替換；
3. 尚未審核的 prompt、wire schema 與 token 預設變更；
4. Header、Duty、排序、XLSX 匯出、R1 harness 等多條應分開審查的工作面。

這兩個分支仍保留作為候選來源，不刪除、不回退。後續只能從目前 `origin/main` 重新整理出小切片，再逐項審查與移植。

## 2. 基準與不可靜默替換的現況

目前 `origin/main` 已包含我們先前審核的 OPKS 分支，並保有：

- `docs/adr/0054-opks-progressive-elicitation-and-scheduled-child-operation.md`
  - Accepted；定義 OPKS 自動排定的 child operation、缺口持久化、receipt 與每回合限制。
- `docs/adr/0055-opks-gap-does-not-block-reanalysis.md`
  - Rejected；保留作為被否決的歷史裁決，不得當成現行規則，但也不能直接刪除並換成另一個 0055。
- `docs/plans/2026-08-05-opks-progressive-elicitation-plan.md`
  - 依 0054 實作 OPKS 漸進式蒐集流程。

兩個待審分支都從較早的 `82cc50f` 分出，沒有自然包含目前 `origin/main` 的所有後續提交。因此不能把它們視為目前主線的普通後續 commit。

## 3. 分項裁決

| 項目 | 裁決 | 說明 |
|---|---|---|
| Server／enterprise deployment scope | **不通過** | 分支修改 `AGENTS.md`、`docs/product-notes.md`、ADR 0057，把產品從 owner 已定的本機 Web 改成伺服器部署。這是產品決策，不是部署細節。 |
| 取代 OPKS ADR 與計畫 | **不通過** | 分支刪除目前 0054、0055、研究稿與計畫，改放另一套 0054／0055。未經 owner 新 ADR 審核，不得覆寫現行 OPKS 權威鏈。 |
| Task Analysis prompt 新增 header 背景規則 | **候選，另行審** | 「員工填寫的整體描述不是員工做過的事」與 0053 方向一致，但應從大分支抽出，並獨立檢查 prompt 影響。 |
| OPKS／Task prompt 改動 | **不通過目前版本** | 分支刪除 OPKS 缺口追問規則；這會讓主顧問失去目前 ADR 0054／0048 要求的追問與 settled issue 行為。 |
| OPKS wire schema／issue resolution | **不通過** | 分支移除 `issue_resolutions`，並把 `task_analysis_result_v3` 改回 `v2`。這不是瘦身，而是刪除已接通的缺口關閉資料流並造成 schema 身分衝突。 |
| `4096 → 16384` token 預設 | **暫不接受** | 修改 production `job_analysis_max_output_tokens`，會改變成本與截斷行為。需獨立研究、成本上限與模型／provider 證據，不能與 XLSX 混入。 |
| `professional_consultant`／R1 harness | **不併入現行工作面** | 可保留為離線研究資產，但目前主線工作面是 `app/job_analysis`；不能因測試或 harness 存在就恢復另一套顧問 runtime。 |
| Header／Readiness | **可繼續審** | `JdHeader` nullable、員工明確儲存、共用 authority seam、readiness 只提示等方向大致符合 0052／0053。需先從 Duty／OPKS／R1 變更中隔離。 |
| Duty／Task 職能級別 | **可繼續審** | 可能是匯出前必要切片，但要獨立檢查官方依據、資料模型、刪除／重排、readiness 與既有 Task carry-through。 |
| OPKS display order／XLSX 匯出 | **方向可接受，實作未核准** | deterministic assembly、渲染分層、XLSX 第一格式方向可審；但必須以目前主線重新整理，另驗官方版型、位置碼、缺漏呈現、API／Web 與 PostgreSQL。 |
| ADR 狀態 | **流程不通過** | 分支把 0057、0058、0059 標成 Accepted，但 owner 尚未審核這些內容。依 repo 紀律，應先 Proposed；Accepted 不能由提交者自行宣告。 |

## 4. Prompt 與 OPKS 變更的具體拒絕理由

這不是「prompt 風格不同」而已，而是改動了已接受的責任分工。

### 4.1 刪除主顧問的 OPKS 缺口追問規則

分支修改：

`apps/api/app/job_analysis/llm/prompt.py`

刪除了 `## OPKS 缺口的追問`，包含：

- 缺口要問行為與實例，不照唸摘要；
- K／S 缺口不得問成認領題或「你是否具備某能力」；
- settled issue 不得重問；
- `answered` 必須在同輪留下有效 Evidence。

拒絕理由：

1. 這些規則不是重複裝飾，而是主顧問在 gap 進入 agenda 後的唯一提問規則來源。
2. `opks_prompt.py` 是 specialist 產生 gap 摘要，不擁有對話；不能因 specialist 不輸出問句，就把主顧問的提問規則整段移除。
3. 移除後，模型仍可能產生形式合法但會誘導員工認領 K／S 的問題；local verifier 無法判斷這種語意品質。

因此此變更在目前 OPKS 架構下不接受。若要修改，必須提出新的研究紀錄，說明規則搬到哪裡、由哪一層負責，以及如何保留 0048／0054 的 K／S 防膨脹約束。

### 4.2 移除 `issue_resolutions` 與 v3 wire schema

分支修改：

- `apps/api/app/job_analysis/llm/result.py`
- `apps/api/app/job_analysis/llm/wire.py`
- `apps/api/app/job_analysis/llm/schemas/task_analysis_result_v3.json`
- 將 provider schema 名稱改回 `task_analysis_result_v2`

拒絕理由：

1. 目前 v3 的 `issue_resolutions[]` 是為了把「員工回答缺口」與一般 `work_signals[]` 分開，避免一個 signal 同時帶工作副作用與關閉 issue 的副作用。
2. 刪除它會讓已接受的 gap lifecycle 失去模型輸出承載，不能只稱為 schema 瘦身。
3. 同一個 provider schema name 對應兩種形狀會破壞 golden、journal payload、replay 與問題診斷的契約邊界。

這項不是可在 prompt review 中順手修正的問題；除非另開翻案 ADR，否則應完整保留目前 v3。

### 4.3 OPKS `uncertain` 改為空文字

分支修改 `apps/api/app/job_analysis/llm/opks_prompt.py`，把 `uncertain` 的非空缺口摘要改成空字串。

拒絕理由：

- 如果 gap 的摘要沒有內容，application 無法保存「缺什麼」；主顧問也無法在之後建立有意義的追問。
- 這會把已經解決的問題重新變成「只知道不足、不知道不足在哪裡」。
- 這不是單純減少輸出欄位，會改變 OPKS gap 的 domain 語意與 reload 後可恢復性。

若新形狀是刻意改成由 application 另行推導 gap，必須先說明推導資料來源；不能用空字串代替未設計的語意。

### 4.4 `4096 → 16384` 不是免費的安全修正

分支把 `apps/api/app/config.py` 的 production 預設提高到 16384。

這會同時改變：

- 最壞輸出成本；
- provider hard cap 行為；
- reasoning 與可見輸出的 token 分配；
- API timeout 與使用者等待時間。

即使某次真人試跑發生截斷，也不能直接把預設擴大四倍。需要另列：模型、provider route、實際 usage、成本上限、截斷率與成功輸出證據。未完成前保留目前 4096，或只在獨立 smoke command 以明確參數試驗，不改 production default。

## 5. 可保留的候選方向

### 5.1 Header／Readiness

分支中以下方向值得獨立審：

- `JdHeader` 欄位可為 `None`，員工按儲存才寫入；
- header 寫入走與 Task 相同的 `commit_authority_change()`；
- header 不進 OPKS packet；
- readiness 是 application／domain 純函式，只回固定 issue 清單；
- UI 不顯示百分比、不宣稱「完整」或「合格」。

目前不直接接受的原因是它與 Duty、server scope、R1 harness、OPKS schema 變更同時存在，無法從目前 diff 判斷真正最小切片。後續應從 `origin/main` 重做一個只含 Header／Readiness 的分支。

### 5.2 Duty／Task 職能級別

這條可以成為下一個獨立切片，但需另外確認：

- Duty 是否只由員工新增／編輯，是否禁止 AI 直接套用；
- `duty_id`、`competency_level` 是否在所有 AI／proposal 重建路徑完整 carry-through；
- 刪除 Duty 後 Task 是否保留並變成未分組；
- readiness 是否只提示、不阻擋；
- 匯出位置碼是否只在 render-time 產生。

分支自己的 Header 計畫先宣稱不做 Duty，後續同一分支又把 Duty 與 Task level 加入 readiness；這是計畫範圍不自洽，必須拆開再審。

### 5.3 XLSX 匯出

方向上可保留研究：

- `ExportDocument` 純組裝與 XLSX 渲染分層；
- 位置碼由 Duty／Task／OPKS display order 在匯出時產生；
- 第一版只做 XLSX，不先做 DOCX／PDF；
- 匯出不被 readiness 阻擋，缺漏另以工作表呈現。

但這只能表示「值得審」，不表示 branch 的 ADR 0058 已被接受。需以目前主線重新驗證官方欄位、P 位置碼、空欄、未分組 Task、多筆 K／S 與 Excel 實際版面。

## 6. 建議的重新審查順序

1. **先保留目前 `origin/main` 不動。** 不用這兩個分支直接做 merge resolution，因為那會把未審決策混進衝突解法。
2. **Header／Readiness**：從目前主線抽出最小實作，確認 API、PostgreSQL、Web 與 readiness。
3. **Duty／Task 職能級別**：獨立確認官方依據與 Current JD 寫入語意。
4. **OPKS display order 與 XLSX**：先審位置碼與版型，再審實作與瀏覽器下載。
5. **Prompt／token**：只有在對應研究、live evidence 與 owner 裁決完成後才另行處理；不跟匯出合併。
6. **R1 harness／server deployment／reference／subconversation**：各自另案，不放進上述功能切片。

## 7. 目前需要提交者修正或回答的事項

提交者若要繼續，第一版應先提供：

1. 一個從目前 `origin/main` 分出的最小候選分支；
2. 不刪除或覆寫 0054／0055 的 commit；
3. 不帶 server scope、R1 harness、16384 production default、OPKS v2 回退；
4. 將 Header、Duty、XLSX 分成可獨立審核的切片；
5. 對每個 Proposed ADR 標明未核准，不先自行改成 Accepted；
6. 對 prompt 變更提供「目前規則在哪裡、移除後由哪一層承擔」的說明與測試證據。

這份報告只判斷目前兩個分支能否作為整體合併來源；後續會依上述順序逐切片審核，遇到需要 owner 裁決的領域或產品決策會另行提出，不把提交者的 ADR 當成既定答案。
