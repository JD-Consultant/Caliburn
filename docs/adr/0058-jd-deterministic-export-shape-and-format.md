# 0058. JD 匯出：組裝與渲染分層、位置碼演算法、不重用 `ocs-contract`、XLSX 為第一版格式

- 狀態：Proposed
- 日期：2026-08-06
- 依據：[`docs/specs/2026-08-06-jd-deterministic-export-research.md`](../specs/2026-08-06-jd-deterministic-export-research.md)
- 延續：[0052](0052-jd-readiness-assessment-and-official-code-boundaries.md) 決定 4／5／8／10／14
  （exporter 呼叫同一套 assessment、缺漏只提示不阻擋、兩種代碼權責、位置碼定義、匯出留給本 ADR 實作）；
  [0040](0040-professional-consultant-engine-and-r1-validation-contract.md) 決定 33–34（公版匯出措辭、禁止生成官方認證碼）；
  [0048](0048-opks-evidence-axes-and-document-level-competencies.md) 決定 5（O/P 掛 Task、K/S/A 掛文件的官方編號依據）
- 覆蓋：[`docs/contract-strategy.md`](../contract-strategy.md) §5 契約 #4 一句 2026-07-30 的預答
  「`ocs-contract` remains the public/export shape」——見決定 5 與其理由
- 更正：[0055](0055-hybrid-job-discovery-and-ttop-formation.md) **脈絡段**把行為指標寫成 `P1.1.1.1`（四段）
  ——見決定 4。0055 的**決定內容不受影響**。

## 脈絡

ADR 0052 決定 14 明文「正式匯出為 deterministic，不讓 LLM 參與。**本 ADR 不實作匯出。**」
Duty 切片（T1–T6）已把六個公版 header 欄位、Duty→Task 兩層結構與每 Task 職能級別全部接通並可由員工
在瀏覽器編輯；資料齊了，缺的只是「把 Current State 排成一份符合 iCAP 2026 手冊版型的檔案」。

研究紀錄核對出四件需要在動手前釘死的事：

1. **位置碼要怎麼算、順序算誰的。** 官方手冊沒有規定 O/P/K/S 在同一 Task 或同一文件內誰排第幾；
   現有 `OpksItem` 也沒有 `display_order`，讀出順序落在 `created_at`。
2. **`packages/ocs-contract` 能不能直接當匯出目標。** `contract-strategy.md` 早先預答「可以」，但那句話
   寫於 ADR 0048/0049（K/S/A 改文件層平坦多對多）與 Duty 切片**之前**。
3. **交付檔案格式。** `python-docx`／`openpyxl`／`reportlab` 已裝在 `apps/api` 但零 import——是預先鋪好的路，
   不是已選定的路。
4. **行為指標的位置碼是三段還是四段。** 文件之間不一致（見決定 4）。

## 決定

### A. 分層：組裝與渲染分開

1. **`ExportDocument` 是一個 frozen 值物件**，由純函式 `assemble_export_document(state, *, title) -> ExportDocument`
   從 `JobAnalysisState` 算出，住 `app/job_analysis/application`，**零 IO、不 import transport contract**
   ——同一條界線比照 `assess_readiness()`（ADR 0052 決定 1）。所有位置碼在這裡算出，
   **只存在於這個回傳值裡，不落庫**（重申 ADR 0052 決定 10）。
2. **渲染是獨立的一步**：吃 `ExportDocument`、吐檔案位元組。組裝層只有一個，渲染層可以有多個
   （第一版只做 XLSX，未來 DOCX／PDF），各自獨立測試。

### B. 位置碼演算法

3. 演算法：

   ```
   T{i}         = current_duties 依 display_order 排序後的第 i 個（1-based）
   T{i}.{j}     = 該 Duty 底下的 Task 依 display_order 重新從 1 排序後的第 j 個
   O{i}.{j}.{k} = 該 Task 的 OUTPUT 依 display_order 排序後的第 k 個
   P{i}.{j}.{k} = 該 Task 的 INDICATOR 依 display_order 排序後的第 k 個
   K{n} / S{n} / A{n} = 全文件該 kind 依 display_order 排序後的第 n 個（文件層平坦編號）
   ```

   **未指派 Duty 的 Task 沒有 `T{i}.{j}`**，在 `ExportDocument` 裡歸進獨立的「未歸入主要職責」集合，
   不得為了湊出位置碼而虛構 Duty（ADR 0052 決定 13 的匯出端體現），且渲染層**必須把這群 Task 呈現出來**。

4. **行為指標是三段 `P{i}.{j}.{k}`，與工作產出同層。** 官方表單 F3-3（2022 指引 p73）與 2026 手冊體例格式
   逐字核對皆為三段，ADR 0052 決定 10 亦寫三段；**ADR 0055 脈絡段的 `P1.1.1.1`（四段）是筆誤**，
   其決定內容未受影響。語意上也只有三段成立：官方允許操作性任務不列 O、成果併入 P 的描述
   （2022 指引 p37），若 P 巢狀在 O 底下，省略 O 就會讓 P 無處可掛。

5. **O/P/K/S/A 的順序由員工控制**，`OpksItem` 取得 `display_order`，在 `(document_id, entity_kind)`
   範圍內唯一；位置碼在各自 scope 內重新從 1 編號。這**沿用 Duty／Task 的既有先例**——
   `JdTask.display_order` 是文件層唯一，而 `T{i}.{j}` 在 Duty 內重編。
   **此為本 ADR 對研究紀錄 §4 空缺的裁決，不是延續現狀**：現行 `created_at` 順序雖然決定性，
   但員工無法調整工作產出在公版表上的先後，而 Duty／Task 都有上下移按鈕，這個不對稱沒有理由。
   施工上它是匯出的**前置切片**——位置碼由排序推出，先出匯出再改排序會讓已交付文件的編號改變。

### C. 不重用 `ocs-contract`

6. **`ExportDocument` 是 `app/job_analysis` 自己的形狀，不是 `ocs-contract` 的 `OcsDocument`。**
   `ocs-contract` 保留給 `pdf-to-json`／`ocs-indexer` 那個 bounded context（解析既有官方 PDF、
   餵 Qdrant reference 檢索），兩者不搬、不重寫、不繼承，比照 ADR 0043／0054 的既有原則。
7. `docs/contract-strategy.md` §5 契約 #4「`ocs-contract` remains the public/export shape」
   一句在此**明確覆蓋、不再適用於 `app/job_analysis` 的匯出**。理由見研究紀錄 §5：
   K/S/A 文件層平坦編號與 `ocs-contract` 巢狀的 `competency_blocks` 結構衝突（ADR 0048 決定 6
   已裁定 K/S 與 Task／Indicator 多對多，單一所有權會強迫複製）；`OcsProfile.ocs_code` 必填
   與 ADR 0052 決定 8「不得生成職能基準代碼」衝突。**這不是否定 `ocs-contract` 本身**，
   是否定「兩個不同 bounded context 的匯出目標必須共用同一個形狀」這個假設。
8. `ExportDocument` **不進 `packages/job-analysis-contract`，也不開新的 JSON Schema 契約**。
   依 `contract-strategy.md` 判準：它沒有非 Python 消費者——Web 只觸發下載並依 `Content-Disposition`
   命名，不解析匯出內容——不構成新的跨語言 seam。

### D. 格式、路由與缺漏呈現

9. **第一版只做 XLSX**（`openpyxl`）。官方 F3-3 本質是一張大表，欄列對應最直覺；
   政府單位與 HR 也慣於收 Excel。DOCX／PDF 留給未來切片。
10. 路由 `GET /documents/{document_id}/export`，回應
    `Content-Type: application/vnd.openxmlformats-officedocument.spreadsheetml.sheet`、
    `Content-Disposition: attachment`；回應主體是位元組串流，不經過 `job-analysis-contract` 的 JSON 型別。
11. **匯出永遠放行**，不受 `DocumentReadiness` 任何 issue 阻擋（重申 ADR 0052 決定 5）。
12. **缺漏呈現採「公版表留白 ＋ 獨立缺漏工作表」**：
    - 第一個工作表是公版表格，未填欄位**維持空白儲存格**——不自動補、不由 LLM 生成、
      **不靜默省略那一格**（欄位必須在，只是空的）；正式表格上不加「（尚未填寫）」這類雜訊文字。
    - 第二個工作表由 exporter **呼叫 `assess_readiness()`** 產出缺漏清單，措辭沿用既有的
      「iCAP 版型欄位尚有 X 項未填」（ADR 0052 決定 7，**不得**用「不完整／不合格／未通過」）。
    - 這是**落實 ADR 0052 決定 4「未來 exporter 呼叫同一套 assessment——UI 與匯出共用同一份真相」**。
      若匯出完全不呼叫 assessment，該決定會變成死條文；若把缺漏標記塞進正式表格，
      又會弄髒要交給主管／HR 的公版版面。兩個工作表同時滿足決定 4 與決定 5。
13. 匯出檔案固定附上 ADR 0040 決定 33 的公版措辭：「採 iCAP 職能基準欄位版型的客製職務說明書，
    不代表勞動部認證或官方職能基準」；`職能基準代碼`／`職類別代碼` 兩欄維持空白或標示
    「（iCAP 計畫執行單位提供）」，**不開輸入痕跡、不生成**。

## 不在本 ADR 範圍

- **O→P 的參照連結。** 官方語意確實耦合（O 是「對應該工作任務**及行為指標**之關鍵產出項目」，
  且操作性任務的成果「列於行為指標之描述中」），但**公版表格沒有表達該對應的欄位**，匯出不需要它；
  加上去會製造新的非法狀態（O 指向另一個 Task 底下的指標）。ADR 0048 決定 18–19 已用 **rubric**
  接住這件事（無實體交付物時 O 寫成維持的狀態／避免的後果／遵循的規章；連這都寫不出來則標記
  Task 邊界可疑、退回 `work.reconcile`、不硬補 O）。是否要在模型層表示這個耦合，留給品質工作面。
- `JdTask` 的內部欄位（`purpose_result`／`context`／`frequency_text`／`responsibility_role`／`enablers`）
  是否以附錄形式匯出。公版表沒有這些欄位，第一版不印。
- 職業別／行業別代碼的格式檢查。

## 後果

### 正面

- 組裝與渲染分層，讓「位置碼怎麼算」可以像 `assess_readiness()` 一樣被獨立單元測試，
  改渲染排版不必重驗位置碼。
- 決定 5 讓員工對公版表上每一格的先後都有控制權，Duty／Task／O/P/K/S 排序行為一致，
  不會出現「有些能調、有些不能」的意外。
- 不重用 `ocs-contract` 避免兩個 bounded context 的匯出需求互相拖累。
- 兩個工作表的設計讓 ADR 0052 決定 4 與決定 5 同時被落實，而不是二選一。

### 負面／代價

- **決定 5 讓本工作面變成兩個切片**：`OpksItem.display_order` 需要 migration、repository、
  reorder use case、route 與 Web 上下移按鈕，規模等同 Duty 切片，且**必須先於匯出完成**。
  代價是匯出交付時間往後推一個切片。
- `contract-strategy.md` 需要在同一個 commit 更新那句過時的預答，否則下一個讀者會照舊文字重新犯錯。
- XLSX-only 意味著習慣拿 Word 收審閱意見的情境本版還不支援；`python-docx`／`reportlab` 雖已安裝，
  要等下一個切片才會被使用。
- 缺漏工作表是匯出檔案的一部分，會跟著交給主管／HR。這是刻意的——ADR 0052 決定 5 要求缺漏在成品上
  看得見——但代表交出去的檔案會明白列出哪些欄位還沒填。
