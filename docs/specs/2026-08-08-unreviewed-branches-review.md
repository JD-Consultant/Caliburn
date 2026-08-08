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
| 衝突的 OPKS ADR 與計畫 | **不通過** | 分支從舊 base 分出，tip 因此缺少目前 0054、0055、研究稿與計畫，並另帶一套同號 ADR；沒有證據顯示提交者在 post-base commit 主動刪除現行文件，但整支合併仍會以 stale omission 覆蓋現行權威鏈。 |
| Task Analysis prompt 新增 header 背景規則 | **候選，另行審** | 「員工填寫的整體描述不是員工做過的事」與 0053 方向一致，但應從大分支抽出，並獨立檢查 prompt 影響。 |
| OPKS／Task prompt 差異 | **不通過目前版本** | 分支 tip 缺少主線後來新增的 OPKS 缺口追問規則；若直接 merge，主顧問會失去 ADR 0054／0048 要求的追問與 settled issue 行為。 |
| OPKS wire schema／issue resolution | **不通過** | 分支 tip 沒有主線後來新增的 `issue_resolutions` 與 `task_analysis_result_v3`。這不是提交者 post-base 主動瘦身，但整支合併的結果仍會刪除已接通的缺口關閉資料流並造成 schema 身分衝突。 |
| `4096 → 16384` token 預設 | **暫不接受** | 修改 production `job_analysis_max_output_tokens`，會改變成本與截斷行為。需獨立研究、成本上限與模型／provider 證據，不能與 XLSX 混入。 |
| `professional_consultant`／R1 harness | **不併入現行工作面** | 可保留為離線研究資產，但目前主線工作面是 `app/job_analysis`；不能因測試或 harness 存在就恢復另一套顧問 runtime。 |
| Header／Readiness | **可繼續審** | `JdHeader` nullable、員工明確儲存、共用 authority seam、readiness 只提示等方向大致符合 0052／0053。需先從 Duty／OPKS／R1 變更中隔離。 |
| Duty／Task 職能級別 | **可繼續審** | 可能是匯出前必要切片，但要獨立檢查官方依據、資料模型、刪除／重排、readiness 與既有 Task carry-through。 |
| OPKS display order／XLSX 匯出 | **方向可接受，實作未核准** | deterministic assembly、渲染分層、XLSX 第一格式方向可審；但必須以目前主線重新整理，另驗官方版型、位置碼、缺漏呈現、API／Web 與 PostgreSQL。 |
| ADR 狀態 | **流程不通過** | 分支帶入另一套自行標成 Accepted 的 0054–0057，並把 0058／0059 標成 Accepted；owner 尚未審核這些內容。依 repo 紀律，應先 Proposed；Accepted 不能由提交者自行宣告。 |

## 4. Prompt 與 OPKS tip 差異的具體拒絕理由

這不是「prompt 風格不同」而已。三點 ancestry 顯示以下 OPKS 差異主要是 stale branch **沒有包含**主線
後來的提交，不是提交者在 branch-owned commit 主動刪除；但若整支 merge，結果仍會覆蓋已接受的責任
分工，所以必須拒絕該合併結果。真正由 branch 主動新增的 header prompt 另在 §9 審查。

### 4.1 分支 tip 缺少主顧問的 OPKS 缺口追問規則

相對目前主線的 tip diff 顯示：

`apps/api/app/job_analysis/llm/prompt.py`

缺少 `## OPKS 缺口的追問`，包含：

- 缺口要問行為與實例，不照唸摘要；
- K／S 缺口不得問成認領題或「你是否具備某能力」；
- settled issue 不得重問；
- `answered` 必須在同輪留下有效 Evidence。

拒絕理由：

1. 這些規則不是重複裝飾，而是主顧問在 gap 進入 agenda 後的唯一提問規則來源。
2. `opks_prompt.py` 是 specialist 產生 gap 摘要，不擁有對話；不能因 specialist 不輸出問句，就把主顧問的提問規則整段移除。
3. 移除後，模型仍可能產生形式合法但會誘導員工認領 K／S 的問題；local verifier 無法判斷這種語意品質。

因此不能接受會造成此結果的整支合併。若未來要主動移除這些規則，必須提出新的研究紀錄，說明規則搬到哪裡、由哪一層負責，以及如何保留 0048／0054 的 K／S 防膨脹約束。

### 4.2 分支 tip 缺少 `issue_resolutions` 與 v3 wire schema

相對目前主線的 tip diff 顯示以下檔案回到 v3 之前的形狀；三點 diff 確認 branch 在 merge-base 後沒有
主動修改這四條路徑：

- `apps/api/app/job_analysis/llm/result.py`
- `apps/api/app/job_analysis/llm/wire.py`
- `apps/api/app/job_analysis/llm/schemas/task_analysis_result_v3.json`
- 將 provider schema 名稱改回 `task_analysis_result_v2`

拒絕理由：

1. 目前 v3 的 `issue_resolutions[]` 是為了把「員工回答缺口」與一般 `work_signals[]` 分開，避免一個 signal 同時帶工作副作用與關閉 issue 的副作用。
2. 合併後缺少它會讓已接受的 gap lifecycle 失去模型輸出承載，不能只稱為 schema 瘦身。
3. 同一個 provider schema name 對應兩種形狀會破壞 golden、journal payload、replay 與問題診斷的契約邊界。

這項不是可在 prompt review 中順手修正的問題；除非另開翻案 ADR，否則應完整保留目前 v3。

### 4.3 分支 tip 仍是舊的空文字 `uncertain`

分支從現行 gap 語意建立前分出，所以 tip 的 `apps/api/app/job_analysis/llm/opks_prompt.py` 仍要求
`uncertain` 空字串；這不是 branch-owned post-base 修改，但也不能帶回主線。

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

## 8. 提交者實際做了什麼（變更 inventory）

本節只描述分支中的實際內容，不代表接受其中的產品決策或實作。兩個分支大致是同一條長分支的不同終點；第二個分支在第一個分支之後再加上 OPKS 排序、匯出與額外 ADR。

### 8.1 `feat/jd-header-and-readiness`

這個分支實際做了六組事情：

1. **改產品範圍與舊 R1 研究資產**
   - 新增／修改 server／enterprise deployment 的說明。
   - 加入 `app/professional_consultant` 與 `apps/api/evals/professional_consultant/r1` 的離線 task-discovery、ablation capture、blind grader 與 scripted runner。
   - 這組不是目前 `app/job_analysis` 的 production vertical，而是另一套 R1 離線研究／評測工作面。

2. **新增 Current JD Header 與 readiness**
   - 新增 nullable 的 `JdHeader`，包含職能名稱、分類、工作描述、基準級別與補充說明等欄位。
   - 以 PostgreSQL authority row 的 JSON 欄位保存，新增 header migration、repository carry-through 與 `PUT /documents/{id}/jd-header`。
   - 寫入走員工明確儲存與既有 `commit_authority_change()`，不是 LLM 自動寫入。
   - readiness 是純函式，產生固定 issue 清單，只提示，不以百分比或「合格」阻擋文件。

3. **把 Header 放入 Task Analysis context**
   - Task Analysis packet 增加獨立的員工填寫整體描述區。
   - 沒有 ordinal／SourceRef，不作個別 Task 的證據，也不讓 OPKS packet 讀到這段。
   - prompt 增加「可作背景理解、不得單靠它產生 Task change」的說明。

4. **新增 Duty 與 Task 職能級別**
   - 新增 `Duty(duty_id, statement, display_order)`。
   - Task 新增 nullable `duty_id` 與 1–6 `competency_level`。
   - 新增 Duty 的保存、重排、刪除／解除分組，以及 Task 對 Duty 的檢查；刪 Duty 不刪 Task，而是留下未分組 Task。
   - readiness 擴充為可提示「Duty 缺漏、Task 未分組、Task 未填級別」等項目。
   - Web 已有 Duty 編輯器、Task 分組與級別選擇器；分支文件同時又提出 AI Duty suggestion，但該功能不是這組手動 CRUD 的同一件事。

5. **新增 OPKS display order**（第一個分支後段／第二個分支沿用）
   - O/P/K/S/A 各項增加員工控制的排序資料與 reorder API。
   - Web 用上移／下移按鈕修改同類項目的順序。

6. **分支 tip 缺少現行 OPKS 契約，並主動修改 Task Analysis 預設**
   - 因 stale base 沒有主線後來加入的 OPKS gap 追問規則。
   - 因 stale base 沒有後來加入的 `issue_resolutions[]` 與 v3 provider schema。
   - 因 stale base 保留 gap 建立前的空字串 `uncertain`；不是提交者 post-base 主動改回。
   - 將 production `job_analysis_max_output_tokens` 從 4096 改成 16384。
   - 前三項是 stale omission，最後一項才是 branch-owned 修改；整支合併仍會同時改變 OPKS 資料流、
     追問責任與成本上限。

### 8.2 `docs/jd-export-adr-and-plans`

這個分支包含上面全部內容，另外再做四組事情：

1. **增加匯出研究／設計與 ADR**
   - 新增 deterministic `ExportDocument` 組裝層與 XLSX renderer。
   - 匯出時依 Duty → Task → O/P 與文件層 K/S/A 產生位置碼，不把位置碼當持久 identity。
   - 匯出另提供缺漏資訊 sheet，且不因 readiness 缺漏阻擋下載。
   - 新增 `/documents/{id}/export` 與 Web 下載入口。
   - 分支也新增 export 與 AI Duty suggestion 相關 ADR／研究稿，但其中部分狀態未經 owner 審核，不可直接視為現行決策。

2. **新增 AI Duty suggestion 的研究／ADR**
   - 提出由獨立操作產生 Duty 候選，並要求員工審查；不是目前已完成的手動 Duty CRUD。
   - 這會引入另一條 AI 產生／Proposal 邊界，應與 Header、匯出分開審查。

3. **加入 XLSX 版型修正與實際下載流程**
   - 依官方範例調整兩張工作表的欄位與版面。
   - API 回傳檔案，Web 觸發下載；沒有把匯出 JSON 契約硬接到現有 `ocs-contract`。

4. **補充未來方向 ADR**
   - 加入 iCAP reference／indicator depth 與 per-task subconversation／Duty grouping suggestion 等 Proposed 方向。
   - 這些不是目前主線可以一起 merge 的實作內容。

### 8.3 用一條資料流看兩個分支

```text
員工編輯 Header ──> authority row / journal ──> Task Analysis context（背景，不是 evidence）

員工編輯 Duty ──> duty persistence ──> Task.duty_id / readiness ──> Web 分組與級別

員工調整 OPKS 順序 ──> display_order ──> ExportDocument ──> XLSX 下載

Task Analysis prompt/schema 變更 ──> OPKS gap／issue lifecycle 與 token 行為改變

R1 harness／server scope／future ADR ──> 旁支研究或產品方向，不是上述 Current JD 寫入必需品
```

因此目前不是「一個功能分支只加 Header」，而是把 Header、Readiness、Duty、Task level、OPKS 排序、XLSX、prompt/schema、token、R1 harness 與產品部署方向放在同一條分支上。下一輪討論應先決定哪些資料流值得保留，再逐一審核實作；不應先從 merge conflict 的檔案內容反推產品決策。

## 9. 第一輪切片審查：Header／Readiness

### 9.1 裁決

**方向有條件通過；目前實作不可原樣移植。**

Header／Readiness 本身符合 ADR 0052／0053，沒有理由因整體分支不通過而丟棄。但它必須從目前
`origin/main` 重新整理，保留現行 OPKS 0054 的 scheduler／gap／v3 schema，並先修下面的 blocker。

### 9.2 已驗證、可保留

1. `JdHeader` 與文件庫 `title` 分開，沒有擴充 `DocumentMetadataWrite`。
2. 九個欄位全部 nullable；沒有職能基準代碼／職類別代碼的輸入或生成路徑。
3. Header 是 Current JD authority：員工明確儲存、Journal、generation／CAS 與
   `commit_authority_change()` 共用；沒有 autosave、沒有 LLM 寫入。
4. PostgreSQL 只在既有 document authority row 增一組 JSONB＋schema id，沒有為單一 value object
   新建資料表或通用 metadata framework。
5. readiness 是 `app/job_analysis` 純函式；contract 只承載結果，Web 不重算、不做百分比、零 issue
   時不宣稱「完成」。
6. Header 只把職能基準名稱／工作描述放入 Task Analysis packet；該區沒有 ordinal／SourceRef，
   OPKS packet 的簽章也收不到 Header。
7. Web 允許員工填寫、清空與明確儲存，並沿用既有 dirty guard 與 Idempotency-Key 重送語意。
8. 2026 iCAP 研究原料支持目前欄位分界；工作產出、態度與說明補充沒有被誤判成必填。

獨立重跑分支快照 `31b3bd1` 的非 DB 測試：Header／readiness／context／prompt／OPKS context
`85 passed`，API／mapper／persistence contract／authority commit `52 passed`，另有 Header persistence
非 DB 路徑 `8 passed`。真 PostgreSQL 測試在本次隔離環境因 DB fixture 未啟用而 `10 skipped`；
因此分支文件記載的 real-PG 結果保留為提交者證據，本輪不冒充已獨立重現。

### 9.3 Blocker：`JobAnalysisState` 允許默認空 Header

分支刻意讓 `DocumentRecord.jd_header` 必填，避免新 persistence 建構點漏帶 Header；但
`JobAnalysisState` 卻寫成：

```python
jd_header: JdHeader = JdHeader()
```

實測：`JobAnalysisState.model_fields["jd_header"].is_required()` 為 `False`，直接建
`JobAnalysisState()` 會得到全空 Header。這讓任何漏帶欄位的新 state 建構點保持合法，下一次
`commit_authority_change()` 就可能把員工已填內容洗成空。

這在重新移植時風險更高：目前主線比該快照多了 OPKS scheduler／gap／child-operation 路徑，現行
`app/job_analysis` 共有九處 production `JobAnalysisState(...)` 建構點。分支只有一條「成功 AI turn
保留 Header」的整合測試，不能替其他 authoring／Proposal／OPKS 決策路徑提供結構保證。

最小修正：

- 把 `JobAnalysisState.jd_header` 改為必填，不給空值預設；
- 移植時讓所有 production 建構點顯式傳入當前 Header；
- 至少補 direct Task edit、Task Proposal decision、OPKS decision 三類 authority write 的
  Header-preservation regression。

不為此建立新的 state framework；讓既有型別拒絕漏帶即可。

### 9.4 Should fix：readiness `field` 是重複表示

`ReadinessIssue` 同時保存 `code` 與 `field`，但 Header 第一切片的 Web 只使用 `code`，而 `field`
可由固定 code 唯一推導。兩者可產生不一致，且 ADR 0052 只要求固定 issue codes，沒有要求暴露
domain path。後續匯出分支雖使用 `field`，那是尚未核准的 consumer，不能反過來擴大本切片契約。

最小 v1 建議只保留 code；若後續確有「點擊缺漏後聚焦欄位」需求，再由 code 在 Web 做固定 mapping。

### 9.5 需 owner 確認：基準級別只顯示數字是否足夠

目前下拉選項只有「第 1 級」到「第 6 級」。但 ADR 又禁止 LLM 推論、要求員工手選；若不顯示官方
六級定義或至少四個判斷維度，非職務分析專家的員工無法理解數字差異，選出的值容易變成猜測。

建議不加新欄位、不加 wizard，只在下拉旁提供可展開的官方級別摘要。這是靜態說明，不擴大
domain／API／DB。

### 9.6 文件措辭需收斂

分支把「所屬類別不提示」寫成 2026-08-05 owner 永久裁決，但本輪能獨立驗證的依據只有：官方文件
沒有明文要求三組皆必填，ADR 0052 決定 6 要求無法確定時不提示。因此實作選擇合理，但移植時應寫成
「v1 依保守規則不提示；有新官方依據再另案」，不要保留無法從 repo 證實的 owner 歷史或「永遠」。

### 9.7 移植界線

不可把 `31b3bd1` 當新基底，也不可直接接受整個 feature branch。Header commit 是基於較舊的
Task Analysis／OPKS 形狀；移植時必須：

- 保留目前 `task_analysis_result_v3` 與 `issue_resolutions[]`；
- 保留 0054 的 OPKS gap、digest、scheduler 與 child operation；
- 只帶入 Header domain／migration／authority seam／contract／API／Web，以及 Task Analysis packet
  的兩個背景欄位；
- 重新跑目前主線的 API、contract、Web 與 PostgreSQL 測試，不沿用舊分支的 pass 數字作結案依據。

## 10. 第二輪切片審查：Duty／每項 Task 職能級別

### 10.1 裁決

**資料形狀方向通過；目前實作不可原樣移植。**

`Duty → Task` 兩層、Task 使用 nullable `duty_id` 與 nullable 1–6 `competency_level`、位置碼只在
匯出時計算，均符合 ADR 0052 與 iCAP 研究原料。問題集中在 persistence 完整性、分組後的排序
行為，以及「員工手選級別」被分支自行當成最終產品流程。

### 10.2 已驗證、可保留

1. `Duty` 只保存穩定 ID、敘述與順序；沒有持久化 `T1`／`T1.1` 位置碼，也沒有用
   `ResponsibilityRole` 冒充 Duty。
2. 既有 Task 可合法維持未分組；沒有自動合成假的 Duty。OPKS 仍引用 `task_id`，沒有重做 identity。
3. `duty_id`／`competency_level` 走既有 Task direct-edit authority seam；AI Task change 不能填這兩欄，
   revise 時由 application 原樣 carry through，Proposal 的文字 edit 也不能夾帶結構改動。
4. Duty 的新增／改名／刪除／重排均為員工明確儲存，走 Journal、generation／CAS 與
   `commit_authority_change()`，沒有 autosave、沒有 LLM 寫入。
5. 刪除 Duty 會保留 Task、同交易解除 `duty_id`、保留 Task level 與 OPKS，並讓會寫回舊 Duty
   snapshot 的 pending Task Proposal 轉 stale；這條同步語意正確。
6. contract、route、Web 已能呈現 Duty 分組、未分組區與 nullable level；readiness 只提示、不阻擋。

獨立重跑 `f26a512` 快照：domain／readiness／mapper／authority commit `47 passed`；Duty persistence／
authoring 真 PostgreSQL `26 passed`；Duty HTTP route 真 PostgreSQL `7 passed`；migration 0016 cycle
`2 passed`；Web 分組純函式 `8 passed`。這些綠燈證明既有案例接通，不能覆蓋下面三個未測到的缺陷。

### 10.3 Blocker：`current_duties` 的空預設仍可洗掉員工資料

`JobAnalysisState` 寫成：

```python
current_duties: tuple[Duty, ...] = ()
```

目前分支雖逐一修了既有建構點，但型別仍允許未來新增 authority writer 時漏帶 Duty；該 writer
建出的 state 依然合法，下一次 `commit_authority_change()` 就會把整份 Duty 清空。這與 §9.3 的
Header blocker 是同一種缺陷。

最小修正：`jd_header` 與 `current_duties` 一起改為 `JobAnalysisState` 必填欄位；所有 production
建構點顯式 carry through，測試至少覆蓋 Task edit、Task Proposal decision、OPKS decision。

### 10.4 Blocker：migration 為配合 `replace()` 而取消外鍵

migration 0016 刻意不建立 `job_analysis_jd_tasks(document_id, duty_id)` 到
`job_analysis_jd_duties(document_id, duty_id)` 的外鍵。測試甚至證明直接 SQL 可寫入 dangling Duty，
直到下一次載入整份文件才 fail-closed。這讓 persistence 可以保存 domain 明定不可表示的 Current JD，
也代表任何漏走 application seam 的 bug 都可能讓整份文件無法開啟。

分支排除外鍵的理由只證明 `ON DELETE SET NULL` 不適合目前的 delete-all／reinsert `replace()`，
沒有證明「不能有外鍵」。PostgreSQL 18 官方文件明定：`NO ACTION` 可延後到 transaction 後段檢查，
讓同交易內後續命令修復暫時不一致；`RESTRICT` 才不能 defer：
https://www.postgresql.org/docs/18/ddl-constraints.html

最小修正是不蓋新 repository framework：建立 document-scoped composite FK，採
`DEFERRABLE INITIALLY DEFERRED`＋`ON DELETE NO ACTION`。一般 replace 可在同交易刪除後重插相同 Duty；
真正刪除 Duty 的 use case 已明確先把 Task `duty_id` 設為 `None`，commit 時仍可通過。若實測證明
這條在現行 SQLAlchemy flush 順序不可行，才退一步把 Duty repository 改成差異更新；不能直接取消
資料庫的核心參照完整性。

### 10.5 Blocker：分組畫面與全域 Task 重排的按鈕語意不一致

Web 把 Task 按 Duty 分組顯示，但每張卡的上移／下移仍用整份 `document.data.tasks` 的全域 index。
例如持久順序為：

```text
A(duty-1), B(duty-2), C(duty-1)
```

畫面顯示為 `duty-1: A, C` 與 `duty-2: B`。員工在 C 按一次「上移」，程式只會把 B／C 對調成
`A, C, B`；重新分組後畫面仍是 `A, C` 與 `B`，看起來完全沒移動，卻已改掉隱藏的匯出順序。
現有 Web 測試只驗分組，不驗按鈕重排，因此沒有抓到。

最小修正：保留資料庫的全域 `display_order`，但 UI helper 要找同一可見 group 的上一／下一個 Task，
再生成完整 `ordered_task_ids`；補一個「不同 Duty 的 Task 交錯」回歸測試。不需要改 schema 或新增
Duty-scoped order。

### 10.6 需 owner 裁決：每 Task 職能級別不能被默認成員工猜數字

分支自行把流程定成「員工從第 1–6 級手選」，而畫面只顯示數字。ADR 0052 決定 12 禁止 LLM
推論的是 **header 基準級別**；它沒有裁決每 Task level 永遠只能手選。iCAP 研究原料則明確寫：
每 Task level 應由「工作任務及其對應行為指標」判斷，並對照六級在情境變動、監督、自主性、
工作性質與判斷能力的定義。

因此可接受的最小界線是：

- 資料欄位與員工直接修改能力保留；員工永遠可覆寫、清空；
- 本切片至少在選單旁顯示官方六級摘要，不讓非專家只猜數字；
- 在 OPKS／行為指標尚未形成時，level 可保持空白，readiness 只提示不阻止；
- 是否由 AI 在 Task＋P 有足夠依據後提出 level 建議，另開小切片並由員工確認，不夾進本次移植。

若 owner 決定第一版永久只有手選，文件必須誠實寫成產品限制，不能宣稱 ADR 0052 或官方程序已經
替這個選擇背書。資料結構可先通過，但目前「手選且無定義」的成品流程不通過。

### 10.7 其他修正與移植界線

- §9.4 的 readiness `field` 重複表示問題也涵蓋本切片新增的三個 issue，移植時一併收斂。
- plan 檔有一個 EOF 空白行，`git diff --check 457ad5a^ f26a512` 會失敗；修掉即可。
- 分支沒有真人瀏覽器 smoke；修完排序與級別說明後，至少走一次新增 Duty、指派 Task、改級別、
  重排、刪 Duty／Task 留存的本機瀏覽器流程。
- 只移植 `457ad5a..f26a512` 的 Duty domain／persistence／authoring／contract／API／Web 必要內容；
  不連帶接受後續 AI Duty suggestion、匯出、OPKS schema 回退或 16384 token default。

## 11. 第三輪切片審查：OPKS 顯示順序

### 11.1 裁決

**domain／persistence／API 方向通過；Web 控制面目前不通過，不能原樣移植。**

`OpksItem.display_order`、每個 kind 的完整重排、提案接受時才配位置，以及 migration 依舊讀取順序回填，
都能支撐之後 deterministic 匯出。主要缺陷不是排序演算法，而是 K/S 是文件層實體，Web 卻只在 Task
投影裡提供移動按鈕，導致員工無法實際控制完整的文件層 K/S 順序。

這組功能位於 `48ae9a9..c3ee428`。它依賴尚未由 owner 核准的 ADR 0058；本節只審查排序切片，
不因分支把 0058 標成 Accepted 就接受整份匯出決策。

### 11.2 已驗證、可保留

1. `display_order` 是 OPKS item 的顯示位置，不取代 `entity_id`；O/P/K/S/A 的 identity、evidence 與
   Task／Indicator refs 均未改寫。
2. 新增項目取同 kind 的最大位置加一；接受 ADD Proposal 時才依當下 Current JD 配位置，REVISE 保留
   既有位置，避免 staged Proposal 預先占號或同批接受撞號。
3. reorder request 必須逐一覆蓋目前該 kind 的完整 ID 集合，拒絕遺漏、額外或重複 ID；整份 Current
   State 經既有 authority seam 重驗、寫 Journal 並 bump generation，沒有另開第二條 writer。
4. PostgreSQL 將 `display_order` 放在 relational column，含非負 CHECK 與
   `(document_id, entity_kind, display_order)` UNIQUE；migration 0017 依舊版
   `(created_at, entity_id)` 的每-kind 相對順序回填，沒有以文字相似度或建立時推測 identity。
5. replay 的內容指紋刻意不含位置，與既有 Task reorder 語意一致；同一把 key 換 payload 或目前集合已
   改變時 fail closed。
6. O/P 雖使用文件層 per-kind total order，但 Web 的 helper 會在完整清單中交換同一 Task 可見的相鄰項，
   其他 Task 的相對順序不變；匯出時再按 Task 篩選並重編位置碼，可以得到正確的 Task-local O/P 順序。
   這是簡化 persistence 的實作選擇，不是 iCAP 要求，文件不得把它寫成官方結構必然。

獨立重跑 `c3ee428` 快照：domain／persistence contract／verifier／context／operation `61 passed`；
OPKS reorder、0017 backfill／migration 與 API 真 PostgreSQL `13 passed`；共享 contract `16 passed`；
Web OPKS pure helper `10 passed`。這些測試證明既有案例接通，但沒有覆蓋 §11.3 的文件層 K/S 控制缺口。

### 11.3 Blocker：K/S 沒有完整、唯一的文件層排序入口

現行 domain 已定案：O/P 掛 Task；K/S 是文件層實體，可以連到多個 Task／Indicator，也可以暫時無連結。
後端 reorder API 也要求一次提交該 kind 的**全文件完整 ID 清單**。但 Web 的行為是：

- 每張 Task 卡只顯示投影到該 Task 的 K/S，移動相鄰項也只看該卡的可見子集合；
- 同一筆共享 K/S 會出現在多張 Task 卡，任一處移動都會改變同一份全域順序；
- 「尚未連結的知識與技能」區只有編輯／刪除，沒有上移／下移；
- 沒有任何一處列出每一筆 K 或 S 恰好一次的完整文件層順序。

因此最小反例已經足夠：K1 只連 Task 1、K2 只連 Task 2。兩張 Task 卡各只看見一筆，兩邊的上／下按鈕
都 disabled，員工不可能交換 K1／K2 的文件層順序；兩筆都未連結時甚至完全沒有移動按鈕。API 雖然
做得到，產品 UI 卻沒有可達路徑。共享 K/S 還會讓同一全域操作出現在多處，員工難以知道它會影響哪裡。

最小修正不是改 schema、也不是建立通用排序器：

- O/P 保留在各 Task 卡內排序；
- K、S、A 各提供一個完整的文件層排序投影，每個 entity 恰好出現一次，包含已連結、共享與未連結項；
- 若 Task 卡仍顯示 K/S 關聯，可保留閱讀／編輯入口，但不要在多張卡重複提供全域排序控制；
- 補三個 Web 回歸案例：K/S 分屬不同 Task、共享 K/S、兩筆未連結 K/S。

這不改變 K/S 的 Task refs，也不要求引入 drag-and-drop；沿用上／下按鈕即可。

### 11.4 Should fix：文件把全域唯一性說成位置碼必要條件

`CurrentJdOpks.display_orders_are_unique_within_each_kind()` 的 docstring 說同 kind 撞號就算不出唯一
`O1.1.1`，但 O/P 的輸出碼本來會在每個 Task 內重新編號。全文件 per-kind total order 可以作為簡單、
決定性的內部排序策略，卻不是產生唯一 Task-local O/P 碼的必要條件。

移植時保留目前資料形狀即可，但把理由改成「提供穩定的文件層 total order，匯出按 Task 投影後重編」；
不要用不存在的官方限制替實作選擇背書。

### 11.5 其他修正與移植界線

- `git diff --check cc1856e c3ee428` 目前會因三個檔案多一個 EOF 空白行失敗：
  `test_job_analysis_api_postgres.py`、`jobAnalysisOpks.test.ts`、display-order plan；移植前清掉。
- `OpksDirectEditPayload` 的 reorder 是 additive optional payload＋新 action；舊 payload 仍可讀，沒有證據要求
  為此另建相容層或通用版本框架。維持現有 Journal replay 測試即可。
- 目前只有 pure Web helper test，沒有真人瀏覽器 smoke。修完 K/S 入口後，至少走一次：跨 Task O/P、
  分屬不同 Task 的 K/S、共享 K/S、未連結 K/S、reload 與匯出前讀回。
- 只移植 `48ae9a9..c3ee428` 的 display-order domain／migration／persistence／authoring／contract／API／
  Web 必要內容；不連帶接受 0058 的 XLSX、AI Duty suggestion、OPKS schema 回退或 16384 token default。

## 12. 第四輪切片審查：deterministic 組裝／XLSX 匯出

### 12.1 裁決

**組裝層與下載 API 方向通過；XLSX renderer 與 Web 目前不通過，不能當成公版成品合併。**

`ExportDocument` 將位置碼留在匯出投影、不落庫，K/S 以文件層 identity 投影到相關 Task，route 只做
Current State → assemble → render → download，這些方向正確。問題集中在三件成品正確性：未儲存草稿、
公式注入，以及「與公版一模一樣」的宣稱與實際 workbook 不符。

本節審查 `cf66eed..4d223c4`。XLSX 作為第一版格式可接受；不接受的是分支未經 owner 核准就把 ADR 0058
標成 Accepted，並把「兩張工作表＋主表附加聲明」當成已定案。

### 12.2 已驗證、可保留

1. `assemble_export_document()` 是 application 的 frozen 純投影：零 IO、不 import transport contract，
   `T1`／`T1.1`／`O1.1.1`／`P1.1.1` 與 K/S/A 位置碼都不進 Current State。
2. Duty／Task 依 display order 排列，Task 在每個 Duty 內重編；O/P 在 Task 內重編且均為三段碼；
   K/S/A 使用文件層平坦碼。這與勞動部 2026-01-27 手冊附件 2-2 的欄位與範例碼一致：
   https://icap.wda.gov.tw/ap/get_file.php?c=%E8%81%B7%E8%83%BD%E5%9F%BA%E6%BA%96%E5%93%81%E8%B3%AA%E8%AA%8D%E8%AD%89%E4%BD%9C%E6%A5%AD%E6%89%8B%E5%86%8A.pdf&e=20260311201400.pdf&t=download
3. K/S 可由 `task_refs` 或 `indicator_refs` 投影到相關 Task；共享 K/S 保持同一 entity 與同一文件層碼，
   沒有為每個 Task 複製 identity。未分組 Task、空 Duty 與未連結 K/S 不會在 assembly 階段靜默消失。
4. `職能基準代碼`／`職類別代碼` 只顯示 iCAP 配發說明，不開輸入、不生成；職業別／行業別分類碼則取
   Current JD Header。沒有把 official identity 與 render-time position code 混在一起。
5. renderer 使用七個官方主欄位，O/P/K/S 同格換行，Duty 格跨 Task 列合併；態度與說明另列。
6. `GET /export` 無副作用、不要求 Idempotency-Key，回正確 XLSX media type 與 RFC 5987 中文檔名；404
   仍走既有 problem response。Web 使用 Blob 下載，沒有建立第二份 server state 或 Server Action writer。

獨立重跑 `4d223c4` 快照：export assembly／XLSX `34 passed`；export route 真 PostgreSQL `4 passed`；
Web 檔名 helper `3 passed`。另外直接讀回完整樣本：工作簿有 2 張表、主表 21×7，但
`bordered_cells = 0`；以 `work_description="=1+1"` 產出後，`B9` 的 `data_type` 為 `f`。後兩項正是
現有測試未涵蓋的 blocker。

### 12.3 Blocker：有未儲存編輯時仍匯出舊 Current State

`ConsultationWorkspace` 已把 Header／Duty／Task／OPKS 四種 dirty state 合成 `dirty`，用來阻擋離站；
匯出按鈕卻完全忽略它。分支註解以「匯出是純讀取、不動權威狀態」為理由說不需要 dirty guard，這把
**寫入安全**與**輸出內容正確性**混成一件事。

員工在畫面改完 Task 但尚未按儲存，直接按匯出，API 只會讀 PostgreSQL 既有 Current State；下載檔案
不含畫面上可見的修改，而且 UI 沒有警告。這是明確的資料落差，不是 UX 偏好。

最小修正：dirty 時停用匯出並顯示「請先儲存或取消目前編輯，再匯出」；不自動替員工儲存、也不把草稿
另送到 export API。補 Header 與 Task 各一個 component／browser case 即可，不建通用 draft framework。

### 12.4 Blocker：員工／模型文字可被寫成 XLSX 公式

renderer 的 `_put()` 直接把 domain string 指派給 openpyxl cell。openpyxl 官方文件明示，字串
`"=SUM(1, 1)"` 會被當作公式寫入；本輪也直接重現：`work_description="=1+1"` 讀回是 formula cell，
不是文字。官方說明：https://openpyxl.readthedocs.io/en/stable/simple_formulae.html

這些內容不全是程式常數：Header、Task、未分組內容與說明可能來自員工，OPKS 又可能來自 LLM。匯出後
檔案還會交給主管／HR 開啟，因此不能以「本機單人」排除公式注入或至少文字被錯誤求值的風險。
OWASP 對 spreadsheet formula injection 的風險與文字化原則亦有整理：
https://owasp.org/www-community/attacks/CSV_Injection

最小修正是一個 renderer-local text writer：所有 domain／員工／模型文字一律明確以字串 cell 寫入，
不要讓前導 `=` 被 openpyxl 推成 formula；系統自己沒有任何需要公式的欄位。補一個保存／讀回後
`data_type == "s"` 且顯示文字未變的回歸測試即可，不需要通用 security framework。

### 12.5 Blocker：目前 XLSX 還不是公版視覺格式

`docs/product-notes.md` 的現行產品規則是「未來匯出才要求與公版格式一模一樣」。官方附件 2-2 是一張
有明確框線、欄列與區塊邊界的表；分支 renderer 只設欄寬、粗體、換行與合併，完全沒有 Border／Fill／
列高／列印區設定。完整樣本讀回後 **0 個有邊框的儲存格**，所以目前只是把相同欄位文字放入 worksheet，
不能稱為公版版型成品。

最小修正：以官方附件 2-2 為視覺 reference，至少補主表與 Header／態度／說明區的框線、對齊、必要列高
與可列印寬度；產出一份含長中文、多筆 O/P/K/S、兩個 Task 的 fixture，實際用 Excel／LibreOffice 或
等價 renderer 做一次全頁視覺檢查。不要在沒有 reference 的情況自行美化，也不需要建立通用 spreadsheet
theme。

### 12.6 需 owner 裁決：何謂「公版一模一樣」

分支固定產生：

1. 第一張「職能基準表」；
2. 第二張「iCAP 版型缺漏」（即使 0 issue 也存在）；
3. 第一張表底部額外的「不代表勞動部認證」聲明；
4. 公版不存在的「尚未歸入主要職責／尚未連結工作任務」文字列。

後三類資訊都有合理產品目的，也試圖落實 ADR 0040 決定 33 與 ADR 0052 決定 5；但它們不是官方附件
2-2 的一部分，和 `product-notes` 的「一模一樣」無法同時逐字成立。ADR 0058 直接選擇「兩張表＋附加
聲明」只是未審核分支的裁決，不能倒推為 owner 已同意。

需要 owner 在移植前選定一句可測規則：

- **嚴格公版**：匯出檔只含官方表；缺漏由空白格呈現，聲明／無法映射的資料在下載前由 Web 清楚提示；或
- **公版主表＋伴隨資訊**：第一張表必須精確符合公版，允許額外的缺漏／說明工作表，並把
  `product-notes` 改寫成「公版主表一模一樣」，不再宣稱整個 workbook 一模一樣。

不建議第一版同時做兩種匯出模式；那會增加選項與測試矩陣，沒有目前使用證據。

### 12.7 Should fix：七份官方範例的證據不可複現

程式、測試、plan 與設計文檔多次宣稱「逐份核對七份官方範例」，但 repo 只寫「owner 提供」，沒有 URL、
檔名版本、hash 或可取得位置。2026 官方手冊足以直接支持七欄、位置碼與基本版型；它不能讓後續維護者
複現 `.odt`／`.docx` 範例的其他細節。

移植時要嘛把可公開的官方來源 URL／文件識別補入研究紀錄，要嘛把不可複現的「七份確認」降為背景，
由 2026 手冊附件 2-2 支撐可查證的規則。不要因這件事建立文件保存框架。

### 12.8 其他修正與移植界線

- `git diff --check c3ee428 4d223c4` 目前因 deterministic-export plan 多一個 EOF 空白行失敗；移植前清掉。
- Web 自行組下載檔名而不使用 response header；目前功能可用，但前端 sanitization 比後端少 control
  character 檢查。移植時讓前端 helper 一併移除不可列印控制字元即可，不必新增 filename library。
- 修完上述 blocker 後需要一個真人瀏覽器＋真 workbook smoke：未儲存時不可匯出；儲存後下載；長中文
  不截斷；公式樣文字保持文字；K/S 共用碼；缺欄仍可下載；Excel／LibreOffice 可開啟與列印。
- 只移植 `cf66eed..4d223c4` 的 assembly／renderer／route／Web 必要內容；不連帶接受後續 16384 token、
  prompt/schema 回退、server／enterprise scope 或 AI Duty suggestion。

### 12.9 Owner 裁決：本輪延後 XLSX

Owner 於 2026-08-09 決定先不處理 XLSX。§12.3–§12.8 保留作為之後移植匯出切片時的修正清單，
但不阻擋 Task Analysis／OPKS 核心流程繼續審查。匯出碼沒有改動 prompt、wire schema、Current State
寫入或 OPKS 排程，因此不需要為了延後 XLSX 回退核心功能；也不得把「延後」誤寫成 renderer 已通過。

## 13. 第五輪切片審查：Web 小修、診斷與 Task Analysis 輸出上限

### 13.1 裁決

`b6bb2e1` 不應整筆照收，但可以拆成四個獨立結果：

| 變更 | 裁決 |
|---|---|
| Consultation cache 修正 | **通過，應移植** |
| Proposal before／after `null` 文案修正 | **通過，應移植** |
| 不可提交結果的診斷 | **部分通過；保留安全 code，不記完整 provider／refusal 文字** |
| production `4096 → 16384` | **目前不通過；先補可複現 artifact，再選最小可行上限** |

此外，這個 commit **沒有修改 prompt 或 wire schema**。遠端分支出現 prompt/schema 回退，是因為它從舊
基準分出、缺少目前主線的 OPKS 漸進追問提交，不是 `b6bb2e1` 自己做的變更。因此可移植此 commit 的
小修，但絕對不能把 `origin/docs/jd-export-adr-and-plans` 整分支 merge 回來。

### 13.2 通過：Consultation cache 不得偽造完整 Document view

舊 `ConsultationPanel.applyView()` 用 `ConsultationView.document` 加 Task／OPKS 手工拼成 document query
cache，但前者只是 metadata projection；拼出的物件會缺 `jd_header`、`readiness` 與 `duties`。員工送出
回合或決定 Proposal 後，Header、Readiness、Duty 的消費者可能讀到形狀不完整的快取。

修正後只把完整 `ConsultationView` 寫入它自己的 query cache，document query 改成 invalidate 後由 API
重取。這符合 TanStack Query 的 server-state 邊界，沒有建立第二份 store，也沒有在 Web 重算 readiness。
這項是實際資料形狀 bug，應獨立移植。

### 13.3 通過：`jd_before` 與 `jd_after` 的 `null` 語意不同

Proposal 契約中：

- `jd_before = null` 表示該 Task 尚未在 Current JD（ADD 的正常前置）；
- `jd_after = null` 才表示建議從 Current JD 移除。

舊 UI 共用「從職務說明書移除」會把 ADD 提案的目前內容誤標成刪除。修正以 `side` 明確區分，before
的 null 不顯示、after 的 null 顯示移除，方向正確。這是呈現修正，不改 Proposal 契約。

### 13.4 部分通過：診斷需要安全邊界

`UncommittableOperationResult` 補上 outcome、provider detail 與 verifier code，對本機診斷有價值；Web
回應仍維持通用 503，沒有把內部原因直接交給使用者。但 route 新增 `logger.warning(..., error)` 會把完整
detail 寫入 log，而 `detail` 可能來自 provider error 或模型 refusal message，不保證只含安全枚舉。

最小移植方式：

- 例外內可保留 outcome 與 verifier code，測試／CLI 可讀；
- production log 只記例外類型、安全的 outcome／violation code，不記原始 refusal／provider message；
- 不新增通用 logging 或 redaction framework。

### 13.5 暫不通過：16,384 沒有可複現依據，也不是已校準的最小值

提交訊息與程式註解宣稱 2026-08-07 Task Analysis 真人試跑在 4,096 截斷，但該分支沒有對應的
experiment capture、usage、reasoning token、visible output token、request ID 或場景紀錄；repo 搜尋只找到
這兩處宣稱。既有 2026-08-02 OPKS 紀錄不能代替 Task Analysis，兩種 operation 的輸出量確實不同。

官方現行文件補出一個可信的成因：production adapter 固定 `reasoning.effort=high`；OpenRouter 對
Anthropic 模型會依 `max_tokens` 配 reasoning budget，high 約占 80%，且 reasoning token 也是計費 output。
Anthropic 同樣明定 `max_tokens` 包含當輪 thinking 並是硬上限。因此 4,096 可能只留下約 819 token 給
可見 JSON，發生截斷並不意外：

- https://openrouter.ai/docs/guides/best-practices/reasoning-tokens
- https://platform.claude.com/docs/en/about-claude/models/extended-thinking-models

但這只能證明 4,096 **可能太小**，不能證明 16,384 是最低且適當的 production default。16,384 同時把
單次輸出成本與最長延遲的硬上限放大四倍；官方建議依實際 workload 調校 reasoning／token budget，而
不是看到一次 length 就固定跳四倍。

通過條件維持最小：補回該次 Task Analysis capture，至少記錄 input／reasoning／visible output usage、
finish reason、場景與實際成本；用同一場景比較 8,192 與 16,384，取能穩定完成的最小值。這是一次小型
校準，不建 tokenizer、budget service 或 retry framework。校準前 production 保留 4,096。

### 13.6 Hard boundary：舊分支缺少現行 OPKS 漸進追問資料流

從遠端分支 tip `ea704c9` 到目前主線，`app/job_analysis` 路徑尚缺 18 個已審核提交，包括：

- OPKS eligibility／digest／scheduler 與每回合唯一 scheduled child；
- `uncertain` gap 的驗證、持久化、終端 failure／abandon；
- active／settled issue partition；
- `issue_resolutions[]` 與 `task_analysis_result_v3`；
- 主顧問的 OPKS gap 提問規則；
- 移除手動 OPKS 入口，以及 PostgreSQL progressive elicitation vertical。

數量可用 `git rev-list origin/docs/jd-export-adr-and-plans..origin/main -- apps/api/app/job_analysis`
重現；docs-only 提交不計入這個 18。

因此分支 diff 看到的「刪 prompt、v3 改回 v2」不是可以逐行挑選的普通衝突，而是 stale branch 用舊
snapshot 覆蓋新架構。合併策略只能是以目前主線為底，按 commit／檔案移植 §13.2–§13.4 的小修；任何
prompt、schema、scheduler、gap、durable turn 衝突一律保留目前主線，不採遠端分支版本。

### 13.7 驗證與尚缺測試

在隔離整合 worktree（已移植三項小修並單獨撤回 16K）執行：

- Web Vitest：`128 passed`；
- TypeScript：`npx tsc --noEmit` 通過；
- API targeted：`2 passed, 7 skipped`（7 項需 PostgreSQL，當輪未啟動資料庫）。

現有 Web suite 沒有直接掛載 `ConsultationPanel`／`ProposalCard` 的 component test；提交者在 commit message
宣稱跑過 browser，但 repo 沒有可重播 artifact。正式移植前各補一個小回歸測試：document cache 不會被
incomplete consultation projection 覆蓋；ADD Proposal 不顯示「移除」。不需要引入新的 Web test framework。

## 14. 第六輪切片審查：AI 輔助 Duty 建議

### 14.1 裁決

**目前方向不通過，不進實作細節審查。** `30450e9` 只有 Proposed ADR、研究與 plan，尚未動程式；應保留
作為被審查的設計紀錄，但不能照計畫施工。它解決的是「依職稱與摘要猜幾個 Duty 標題」，不是從員工
工作證據完成主要職責歸納，而且為未驗證的按鈕另外建立一個付費 operation。

可接受的未來方向是：已有一批員工證據支持、邊界穩定的 Task 後，AI 才提出
`Duty statement + member_task_ids` 的分組候選；員工確認後在同一個 authority commit 寫入 Duty 與 Task
membership。第一版先保留手動 Duty，不為早期猜測增加獨立 operation、wire schema 與 route。

### 14.2 Blocker：依賴的 ADR 權威鏈不存在於現行主線

ADR 0059 的主要依據是遠端分支自己的「0055 混合式職務發現」，並宣稱 owner 於 2026-08-06 指定要
「先做 Duty、AI 輔助」。現行主線的 0055 是另一份 Rejected OPKS 裁決，並沒有這條 Accepted authority；
未審分支也不能用自行標示的 owner 歷史取代當前審查。

研究中的混合式流程本身有合理來源，但它只能支持「參考框架可作假說、不能冒充員工證據」，不能直接
推出「現在就應新增只看 title／work_description 的按鈕與 operation」。在 owner 重新明確核准具體產品
效果前，0059 維持 Proposed，不能作 plan 的施工 authority。

### 14.3 Blocker：輸入不足，產物也沒有完成 Duty 的核心關係

計畫的輸入只有：

- document title；
- nullable `JdHeader.work_description`；
- 既有 Duty 的文字清單。

它刻意不讀 Task、employee Evidence 或 reference，也沒有 `uncertain`／clarification 輸出。因此
`work_description` 空白或很薄時，模型只能用職稱與先驗印象猜通用職責；這與現行顧問 prompt 的
「職稱式摘要是待驗證脈絡，不是做過的事」邊界相反。讓員工勾選只能防止靜默寫入，不能把猜測變成
專業分析。

更根本的是，wire 只有 `{ duties: [{ statement }] }`，不承載 Task membership。員工採用後得到的是空
Duty 標題，既有或後續 Task 仍要人工分配。iCAP 成品中的 Duty 是 Task 上一層分組；只想出章節名稱而
不回答哪些 Task 屬於它，沒有完成主要職責歸納。

### 14.4 Blocker：`Idempotency-Key` 沒有 receipt，實際不冪等

plan 要求 `POST /{document_id}/duty-suggestions` 帶 `Idempotency-Key`，理由是 provider call 會付費；同時
又要求不寫 Journal、不寫任何 receipt。這兩條不能同時成立：

1. 第一次 provider 已回應；
2. response 在到達 Web 前遺失，或員工重送；
3. server 沒有可查的 receipt；
4. 同一 key 會再次呼叫 provider、再次付費，且可能得到不同候選。

現有 OPKS generation 能用 key 防重，是因為它有 receipt-first durable operation，不是因為 HTTP header
本身具有魔法。若為候選補 Journal receipt，又推翻 ADR 所宣稱的「不落庫、零稽核」。為這個尚未證明
有用的按鈕新增完整 durable receipt 不划算；最小解是先不做這個 operation。

### 14.5 Blocker：多選後逐條新增會留下半套結果

Web 設計是多選候選後按一次「加入」，底層逐條呼叫既有 `addDuty()`。若第 1、2 筆成功、第 3 筆失敗，
Current JD 已經只加入一部分；畫面上的單次操作卻沒有原子性、也沒有明定如何顯示與重試剩餘項目。

不需要為此建立通用 batch framework。若日後做 Task-based Duty grouping，確認動作本來就會同時建立
Duty 與調整多筆 Task membership，應由單一 application use case 經既有 authority seam 原子提交；這比
讓 Web 編排 N 次 direct edit 更符合文件真相。

### 14.6 可保留的研究結論

下列內容可以沿用，不代表接受目前按鈕：

1. Duty 建議不得自動套用，員工必須保有確認／修改／拒絕權；
2. reference 候選不得冒充員工實際工作 Evidence；
3. 不把 Duty 塞進 Task Analysis 或 OPKS wire；若未來真的需要，使用 operation-specific schema；
4. 不生成 iCAP 配發的職能基準代碼／職類別代碼；
5. 第一版不急著接 legacy indexer，先讓員工 Task 證據形成再歸納，可同時避免過早 taxonomy anchoring。

### 14.7 建議的未來最小切片

若真實使用證明手動分組太慢，再開新的 Proposed ADR，範圍只含：

- pre-gate：至少有兩筆尚未分組、且沒有未決 Task identity／boundary 問題的 Current JD Task；
- input：Task statement／必要語意欄位與 employee Evidence 摘要，不只 title；
- output：少量 Duty 候選，每個帶明確 member Task ordinals；未涵蓋 Task 必須可見；
- employee review：可改 Duty 名稱與成員；不接受時兩層都不變；
- commit：一次原子寫入 Duty 與 Task membership；不由 Web 串 N 次 `addDuty()`；
- 不在第一版加入 reference、taxonomy、confidence、通用 Proposal framework 或自動重組既有 Duty。

這個切片才直接完成「主要職責歸納」，也和目前 Task → OPKS 的證據先行主線一致。

## 15. 第七輪切片審查：ADR 0060／0061 與企業版流程翻案

### 15.1 裁決

**兩份 ADR 都不通過，維持 Proposed，不得作為施工依據。** 0060 的 iCAP 全量統計、退役職類檢索 bug
與部分 readiness 發現值得保留；但它把描述統計誤升成官方語意，並用兩筆查詢宣稱 reference 品質已
解決。0061 則另建每 Task 子對話、Journal kind、per-task active question、摘要回流與新線索通道，和
現行「單一主對話＋OPKS gap 由主顧問追問」重複，屬明顯過度設計。

兩份文件都以未在現行主線確認的 owner 歷史作為主要翻案理由，且延續遠端分支自己那份衝突編號的
ADR 0055／0059。可查證研究資料可以移植；產品裁決、prompt 改寫與新 runtime 不能隨分支帶回。

### 15.2 Blocker：0060 對行為指標的官方語意判讀相反

0060 用「23,804 條 P 只有 0.05% 含數字」推出：行為指標只是具體行為描述、不是判斷是否做好，且
不含數值門檻。這個推論不成立：品質／能力程度可以用質性條件表達，不需要數字。

iCAP 官方現行頁面直接定義：行為指標是「**用以評估是否成功完成工作任務之標準**」，須描述任務情境
與應有行為或產出；2026 品質手冊也要求行為指標能具體反映能力展現程度。官方來源：

- https://icap.wda.gov.tw/ap/knowledge_introduction.php
- https://icap.wda.gov.tw/ap/get_file.php?c=%E8%81%B7%E8%83%BD%E5%9F%BA%E6%BA%96%E5%93%81%E8%B3%AA%E8%AA%8D%E8%AD%89%E4%BD%9C%E6%A5%AD%E6%89%8B%E5%86%8A.pdf&e=20260311201400.pdf&t=download

因此現行 prompt 的「能從工作行為或結果判斷是否做好」方向沒有被全量統計推翻。可改進的是讓 P
更具體地包含情境、行為、產出與真實條件，不是刪除判準語意。員工明講的 `5%`、`三天內` 或正式外部
規範仍應保留；禁止的是模型自行發明數字，ADR 0048 的既有界線較精確。

### 15.3 Blocker：語料長度不能把 Task identity 改成八字名詞短語

官方 Task 名稱中位數 8 字、P 中位數 25 字，是有價值的顯示與語料統計；它不能推出 Work Model／
Current JD 的 canonical Task statement 必須改成名詞短語。現行 Task identity 與 verifier 依賴明確的
action／object／purpose-result 語意，短標題無法取代。

若日後畫面真的太長，可在不改 identity 的前提下研究 deterministic display label 或 UI 摘要；目前沒有
真人證據要求多存一個欄位，更不能為追求八字中位數讓模型刪掉辨識 Task 邊界所需的資訊。

同理，官方 K/S 常用名詞化標籤可以作 prompt 風格參考，但不能把技能一律抽象成
`資料分析能力`、再把具體工具一律塞入 P。工具可能是 Task enabler、context 或 P 的一部分，應由工作
語意決定；一刀切會犧牲已建立的證據保真與可轉移技能判準。

### 15.4 Blocker：兩筆 query 不能證明 reference 流程可上線

研究的檢索實測只有兩個口語 query，兩者 top-1 命中同一類 ground truth；這能證明路徑可用，不能證明
不同職類、短答、近鄰職類與冷門職位的配對品質已校準。更重要的是同一研究已重現：退役職類
`CCM7114-005` 會以 score 1.0 排第一，系統目前無法可靠區分現行與歷史資料。

因此可以獨立接受並修復「歷史資料被標成 current」的 indexer bug；在修復、建立跨職類小型 holdout
與誤配處置前，不接受 reference 成為文件起點、官方 Duty 直接採用、持久待訪談清單與 K/S 池整套同時
上線。這不是反對 reference，而是避免用 n=2 的可行性 smoke 冒充產品品質 gate。

### 15.5 可保留：reference 與 readiness 的幾個小結論

1. 若未來採用 reference，文件必須記穩定來源與版本，UI 區分 employee／reference；不得把官方基準的
   代碼寫成本文件獲得的 iCAP 身分。
2. 退役職類被正規化為 current 是可重現缺陷，應在 `ocs-indexer` 獨立修復，不綁 JD 新流程。
3. `Task 沒有 P` 可作非阻擋 readiness 提示；官方明定 P 是任務對應內涵。
4. `Task 沒有 O` 不得自動列缺漏，既有 ADR 0052 與本次 21.8% 統計方向一致。
5. `Task 沒有 K/S linkage` 是否逐 Task 提示，要先對照文件層多對多模型；不能因公版列 K/S 就重新
   發明單一 Indicator ownership。
6. readiness 仍只提示、不宣稱完成、不阻擋保存或匯出。

### 15.6 Blocker：0061 的 per-Task 子對話重複現行 OPKS 漸進追問

現行 ADR 0054 與已實作流程是：OPKS specialist 分析單一 Task；遇到缺口就持久化 OpenIssue；主顧問在
**同一條對話**依 agenda 選中缺口、追問員工，再由新 Evidence 觸發重分析。這已經解決 O/P/K/S 缺資料
時「誰問、在哪裡問、如何 reload」的問題。

0061 另外建立：

- 每 Task 一條 conversation；
- 新 Journal kind；
- 每 Task 一份 active question；
- 子對話摘要回流主對話；
- 額外的新線索輸出與 packet 區段。

這會製造兩個 conversation owner、兩套 agenda 與上下文同步問題，卻沒有實測證明主對話不夠用。它也
違反產品已收斂的使用方式：員工只要在聊天室回答，AI 自行判斷是否需要 OPKS 分析與補問，不要求員工
切換 Task 子聊天室。

因此 0061 整體不採。若右欄 Task 卡未來要提供「聚焦此工作」導覽，它仍應只是主對話的 focus hint，
不建立第二份 conversation state。

### 15.7 Blocker：固定兩問與追問兩次不是專業完整性判斷

0061 把每 Task 固定成兩問（具體做哪些事→P；交出什麼、誰使用→O），並規定同一缺口最多追兩次。
兩問可以作 prompt 教材，不能成為流程契約：

- O 可合法不適用；
- P、K、S 的缺口數與內容依 Task 而異；
- 有些回答一次足夠，有些風險／例外工作需要更多澄清；
- 「兩次」文件自己承認沒有實證依據。

現行 gap lifecycle 已有 `answered`／`employee_unknown`／`not_applicable` 與 terminal receipt，能按資料實際
狀態停止，不必用固定問數猜測完整度。正確方向是保留兩個問句作例子，由 specialist 標出缺口、主顧問
依 agenda 一次問一個最有價值的問題。

### 15.8 後續最小順序

這批研究若要利用，拆成四個互不綁定的小工作：

1. 先修退役職類 current 判定與查詢過濾；
2. 以官方定義修訂 P prompt 的具體度教材，但保留「成功完成標準」與真實數值條件，另跑付費 eval；
3. 把 `Task 無 P` 加入 non-blocking readiness；
4. 等真實使用顯示 reference 或 Duty 分組確有需求，再各自開新的 Proposed ADR。

不做 per-task 子對話、持久待訪談清單、一次上線完整 reference 流程、Task 八字化、或 K/S 一律抽象化。

## 16. Owner 核准的選擇性移植白名單

### 16.1 裁決與基線

Owner 於 2026-08-09 核准從兩個未審分支**選擇性移植**，並在同日把 XLSX 納入本輪；本節因此覆蓋
§12.9 的「本輪延後 XLSX」。這不是核准任一遠端分支整包合併，也不是接受提交者自行標成 Accepted 的
ADR。實作一律以目前含 ADR 0054／0055 與 OPKS 漸進追問資料流的主線為底，舊分支只作 patch 來源。

`integrate/reviewed-origin-main` 是已把候選 commit 重放到新 OPKS 基線的隔離分支，可以用來降低機械衝突；
它本身仍不是可直接 merge 的交付物。正式移植使用乾淨 worktree、按下列小組逐項套用、逐組測試與 commit。

### 16.2 可移植白名單

| 小組 | 核准內容 | 候選來源 | 額外界線 |
|---|---|---|---|
| Header／Readiness | nullable `JdHeader`、PostgreSQL、員工 authoring seam、contract／API／Web、non-blocking readiness | `47e2840..fd56c94`、`5607553`、`26cbe90` | 不生成 header；不把 header 當 Evidence |
| Header 的 AI 背景區 | Task Analysis packet 新增無 ordinal／無 `SourceRef` 的 `employee_written_overview` | `0b04ba7`、`4755127` | 只准加入該 commit 的一行判準；prompt bytes guard 可由實測 5215 bytes 對應 `5200 -> 5300`，但不進 OPKS packet、不改 OPKS prompt／schema |
| Duty／Task 職能級別 | Duty domain／persistence／authoring／contract／API／Web，Task nullable duty 與 nullable competency level | `7e1f9de..ac3d3ea` | 只讓員工編輯；沒有 AI Duty 建議按鈕或付費 operation |
| OPKS 顯示順序 | 同 kind 的 `display_order`、重排 use case／API／Web move controls | `c59d15c..b2ba8c6` | 不改分析、digest、scheduler、gap lifecycle、wire schema 或自動觸發 |
| Deterministic XLSX | 純 `ExportDocument` 組裝、XLSX renderer、下載 API／Web | `14feb32..80ed7cb`，研究／Proposed ADR 來源 `08aaed7..6292157` | 必須先完成 §16.3 的公版與安全修正，不原樣照收 renderer |
| Web 小修 | Consultation cache 失效重取；Proposal before／after null 文案 | `42b7118` 的兩個 Web 檔 | 從混合 commit 手動拆出，不帶 16K 或原始 provider detail |
| 安全診斷 | outcome 與 verifier violation code 可供本機測試／診斷 | `42b7118` 的 application／route 片段 | production log 不寫原始 provider／refusal detail；不建 logging framework |

計畫與實驗紀錄可按實際追溯需要帶入，但不得把已完成的舊 plan 當成目前施工清單，也不得用舊實驗覆蓋
新 OPKS 實證。新的施工順序與驗收命令另寫本輪 bite-size plan。

### 16.3 XLSX 的核准形狀與必修項目

Owner 先前已裁決：Web 畫面可以比公版更細，**匯出才必須與公版職務說明書一致**。因此本輪選擇
§12.6 的「嚴格公版」，而不是提交者的兩張工作表設計：

1. workbook 只含官方 `職能基準表`；不加「iCAP 版型缺漏」工作表、非官方聲明或自創說明列；
2. Current State 中沒有公版欄位可承載的資訊不塞進檔案；缺漏、未分組與未連結提醒在下載前由 Web 顯示；
3. 未分組但仍屬 Current JD 的 Task 不得靜默消失，應在官方 Task 列中保留，Duty 儲存格留白；
4. dirty 時停用匯出並提示先儲存或取消，不自動替員工保存；
5. 所有員工／模型文字由 renderer-local writer 強制寫成文字，前導 `=` 不得成為公式；
6. 依 2026 手冊附件 2-2 補齊框線、對齊、必要列高、列印寬度與合併區域，不自行建立通用 theme；
7. 位置碼只在匯出投影計算，K/S many-to-many identity 不複製、不落庫；
8. 官方證據以可公開重現的 2026 手冊為準；無 URL／識別／hash 的「七份範例」不得當作可重現依據；
9. 驗收包含真 workbook 與瀏覽器 smoke：未儲存不可匯出、長中文、公式樣文字、共享 K/S、空欄、
   Excel／LibreOffice 開啟與列印。

ADR 0056 在移植時維持 `Proposed` 並依本節修正；owner 審閱修正版後，才另 commit 轉 `Accepted`。
`docs/contract-strategy.md` 只有在 0056 接受時才能同步把 export seam 指向新 exporter，不沿用舊分支對
ADR 0058 的交叉引用。這不接受遠端分支自行核准的 ADR 0058／0059，也不讓匯出反向改動 Current State
或 AI operation。

### 16.4 明確拒絕／不得夾帶

下列項目不在白名單，即使 cherry-pick 發生衝突也不得以「解衝突」之名帶入：

- production `job_analysis_max_output_tokens: 4096 -> 16384`；
- 任何 Task Analysis／OPKS prompt 改寫，唯一例外是 §16.2 明列的 header 背景一行；
- `task_analysis_result_v3 -> v2`、移除 `issue_resolutions[]`、`uncertain.text` 清空；
- OPKS eligibility／digest／scheduled child／gap／agenda／receipt／failure recovery 的舊分支版本；
- AI Duty 建議按鈕、title／work description 猜 Duty、額外付費 operation、Web 串 N 次非原子 add；
- ADR 0060／0061 的 Task 八字化、P 語意翻案、完整 reference 流程、per-Task 子對話與固定兩問；
- 舊分支自行標成 Accepted 的另一套 ADR 0054（cutover）、0055（hybrid discovery）、0056（pilot gate）
  與 0057（server deployment）；可查證研究若要重用，須依現行編號另案審查；
- server／enterprise／tenant／登入／多人協作產品範圍；
- `professional_consultant`／R1 harness 作為 production runtime；
- 舊系統資料搬遷、雙寫、`app.interview`／`interview_vnext`／`job_authoring` 依賴。

### 16.5 實作與委派紀律

- 架構、prompt、OPKS 邊界、ADR 與最終合併由主審模型決定；不得委派產品裁決。
- Luna Max 可處理 commit inventory、機械 cherry-pick、測試清單、fixture 與簡單獨立 patch；其輸出仍須由
  主審逐 diff 驗收。
- 混合 commit（特別是 `42b7118`）不得整筆套用；按檔案／hunk 拆分。
- 每組先補或保留會失敗的回歸測試，再移植最小程式，綠了才 commit；不在同一 commit 混下一組。
- 全程不得 merge `origin/feat/jd-header-and-readiness`、`origin/docs/jd-export-adr-and-plans` 或
  `integrate/reviewed-origin-main` 整支。
