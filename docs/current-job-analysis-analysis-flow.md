---
title: 現行 Job Analysis 詳細分析流程
audience: 人與 coding agent
updated: 2026-08-09
---

# 現行 Job Analysis 詳細分析流程

> **歷史文件，禁止據此施工（2026-08-28）**：本文件記錄 ADR 0060 hard cut 前的 `app/job_analysis` 流程，所述 `Work Model`、`Proposal`、舊 API 與來源／核准生命週期均不是下一版目標。現行 production 請讀 [`design/consultant-runtime.md`](design/consultant-runtime.md)；下一版目標以 [`adr/0071-revisable-work-understanding-context-and-review-provenance.md`](adr/0071-revisable-work-understanding-context-and-review-provenance.md) 與 [`superpowers/plans/2026-08-28-consultant-work-understanding-and-workspace-implementation.md`](superpowers/plans/2026-08-28-consultant-work-understanding-and-workspace-implementation.md) 為準。本文只供追溯，不授權恢復舊模組、舊名稱或 compatibility layer。

> 本文件只描述現行 `app/job_analysis` 與 `/workspace` 主線。
> 舊的 `interview`、OCS editor、`job_authoring`、`/dashboard`、`/documents/*` 與
> `docs/archive/jobintel-v3/` 不屬於本流程。

現行分析流程的核心是：**模型負責理解與提出候選，application 負責驗證與決定能否寫入，員工負責批准 Current JD 的變更。**

## 1. 建立或開啟職務說明書

使用者進入 `/workspace`：

```text
文件庫
  ↓
建立或開啟 document
  ↓
載入 Current JD、Work Model、Proposal、OPKS、conversation
```

主要 API：

```text
GET /api/v1/job-analysis/documents
PUT /api/v1/job-analysis/documents/{document_id}
GET /api/v1/job-analysis/documents/{document_id}
GET /api/v1/job-analysis/documents/{document_id}/consultation
```

建立新文件時，系統會：

1. 建立一份空的 Current JD。
2. 建立固定的顧問開場。
3. 設定第一個 `active_question`。
4. 把開場寫入 Journal。
5. 不呼叫 LLM。

因此，「開場」不是模型即時生成的，也不是另外建立 chat table。

## 2. 員工直接編輯 Current JD

員工可以先不訪談，直接新增或修改 Task：

```text
新增／修改／刪除／排序 Task
  ↓
application 驗證
  ↓
鎖定 document
  ↓
寫入 Current JD
  ↓
寫入 Journal
  ↓
authority_generation + 1
  ↓
PostgreSQL commit
  ↓
Web reload
```

這條路徑：

- 不呼叫 LLM。
- 不經過 AI Proposal。
- 必須使用 `Idempotency-Key`。
- 同一筆操作重送不會重複寫入。
- Task 刪除或變更時，相關 Proposal 會被標為 stale。
- 對應的 OPKS 連結也會在同一個 transaction 內清理。

這裡的 Current JD 是員工文件真相；不能為了湊 Work Model 而自動補造內容。

## 3. 員工提交一輪訪談回答

員工在對話框輸入一句話，例如：

> 我每週檢查客戶訂單，遇到異常時會和倉庫及業務協調處理。

前端送出：

```text
POST /api/v1/job-analysis/documents/{document_id}/turns
```

這一輪會先產生一個 `operation_id`，並檢查 Journal：

- 如果相同 `operation_id`、相同回答已完成：直接回傳原結果，不再付費呼叫模型。
- 如果相同 `operation_id` 但回答不同：回傳 idempotency conflict。
- 如果尚未執行：才開始新的分析。

## 4. 建立 Context Packet

application 會把目前所有必要狀態組成 `TaskAnalysisPacket`：

```text
完整對話紀錄
目前回合 ID
Current Work Model
Current JD
目前 active question
既有 Proposal
目前的 open issues
```

函式是：

```python
build_context_packet(...)
```

Context Packet 不是把整個資料庫原樣丟給模型，而是經過投影：

- Task 會重新編成 ordinal，例如 `Task 1`、`Task 2`。
- SupportLink 也使用 task-local ordinal。
- 不把內部 UUID、資料庫 ID、proposal ID 送給模型。
- 模型只能根據員工可讀文字與 ordinal 指涉內容。
- 同一份輸入必須產生同一份 packet。

這一步的目的是讓模型理解目前工作狀態，但不讓模型直接操作系統內部 identity。

## 5. 呼叫 LLM

接著執行一次 Task Analysis operation：

```text
TaskAnalysisPacket
  ↓
render_context_packet()
  ↓
純文字 user message
  +
TASK_ANALYSIS_INSTRUCTIONS
  +
task_analysis_result_v3 schema
  ↓
一次 OpenRouter HTTP request
```

現行規則：

- 一次 operation 只允許一次 HTTP。
- 沒有隱藏 retry。
- 沒有 fallback provider。
- 不使用 planner、agent loop 或 Graph runtime。
- 固定使用設定好的 exact model。
- 使用 `reasoning: high`，但不把 reasoning 回傳給 application。
- response 裡的 model 必須與設定的 exact model 相符。

模型收到的是：

```text
System message:
  工作分析規則與輸出規則

User message:
  脫敏後的 Context Packet 文字

Response schema:
  task_analysis_result_v3
```

## 6. 模型輸出分析結果

模型主要會提出幾種類型的內容。

### 工作訊號 `work_signals`

描述員工這一輪回答中，哪些內容可能是工作證據，例如：

- 實際負責的事情。
- 工作的對象與目的。
- 頻率。
- 責任邊界。
- 使用的工具或條件。
- 例外與判斷情境。

### Task change

模型可以提出：

- `add`
- `revise`
- `withdraw`
- `merge`
- `split`
- `no_match`

這些都是候選變更，不代表已經修改 Current JD。

### Open issue

如果資訊不足、責任邊界不清楚或可能有重複工作，模型可以提出 open issue，要求後續追問。

### 下一題

模型選擇下一個最高資訊價值的問題。

第一版不是固定問卷。每一輪可以：

- 找到 0 到 N 個工作訊號。
- 深挖目前故事。
- 回到例行、週期或例外責任。
- 優先追問會改變 Task 邊界的問題。

系統不允許模型宣稱「整份 JD 已完成」。

## 7. Mapper 還原模型輸出

模型輸出先通過 wire contract：

```python
TaskAnalysisWire.model_validate_json(text)
```

再由 mapper 還原成內部 domain 結構：

```python
wire_to_task_analysis_result(...)
```

這一層只做：

- wire 欄位轉換。
- ordinal 還原。
- 空值轉換。
- domain object 建立。

它不負責自行判斷：

- 哪個工作真的應該合併。
- 哪個工作真的應該拆開。
- 這個目的是否合理。
- 這個 Task 是否具有專業品質。

那些是語意品質與員工審核問題，不由 mapper 偷做。

## 8. Deterministic Verifier 驗證

接著進入 verifier：

```python
verify_task_analysis_result(...)
```

Verifier 是純函式，不呼叫 LLM，負責擋住可以機械判斷的錯誤，例如：

- quote 必須是員工原話的逐字片段。
- ordinal 必須存在且在合法範圍內。
- retired Task 不得被重新指涉。
- `no_match` 不得同時帶 target。
- `merge` 至少要有兩個成員。
- `split` 只能繼承明確指定的來源。
- 同一個 Task 不可被兩筆互相衝突的 change 同時修改。
- 逐欄完全相同的重複訊號必須拒絕。
- withdraw 必須有原因。
- Proposal 的欄位組合必須符合 action。

結果可能是：

| 結果 | 處理 |
|---|---|
| `verified` | 進入 transition |
| `rejected` | 不套用，保存違規原因 |
| `invalid_output` | 輸出不是合法契約，不重試同一份 |
| `refused` | 模型拒答，不當成系統錯誤 |
| `failed` | timeout、連線錯誤、截斷或 model mismatch |

重要的是：**通過 verifier 不代表模型分析品質一定正確**。Verifier 只保證可機械驗證的契約與資料安全。

## 9. Transition 判斷能否直接改 Work Model

驗證通過後，進入：

```python
apply_task_analysis_result(...)
```

這一步根據目前 Current JD 判斷 identity gate。

### 情況 A：新增 Task

```text
模型提出 add
  ↓
建立 Work Model Task 候選
  ↓
建立 pending add Proposal
  ↓
等待員工決定
```

新增候選可以立即進入 Work Model，但不會直接進 Current JD。

### 情況 B：修改不在 Current JD 的 Work Model Task

如果只是分析內容修正，且沒有影響 Current JD：

```text
直接更新 Current Work Model
```

### 情況 C：修改已存在於 Current JD 的 Task

如果修改會影響員工文件：

```text
更新 Work Model 候選
  +
建立 Proposal
  ↓
等待員工接受或修改
```

### 情況 D：withdraw

如果目標 Task 不在 Current JD：

```text
可以直接 retire Work Model Task
```

如果目標 Task 已經在 Current JD：

```text
不能直接刪除
  ↓
建立 withdraw Proposal
  ↓
等待員工決定
```

### 情況 E：merge 或 split

如果 merge／split 會影響 Current JD：

```text
暫不套用 topology
  ↓
建立帶 staged delta 的 Proposal
```

如果不影響 Current JD，才可以直接更新 Work Model。

最重要的不變量是：

```text
apply_task_analysis_result()
永遠不直接修改 Current JD
```

Current JD 只能透過員工的 Proposal decision 或人工編輯改變。

## 10. Proposal 由員工決定

Web 會顯示 Proposal card，讓員工選擇：

- Accept
- Edit then accept
- Reject
- Defer
- Request revision

決策 API 不會再呼叫 LLM。

### Accept

```text
套用模型提出的 jd_after 或 topology delta
  ↓
重新計算 display_order
  ↓
更新 Current JD
  ↓
更新 Work Model／Proposal 狀態
  ↓
寫 Journal
  ↓
authority_generation + 1
  ↓
commit
```

### Edit then accept

```text
員工修改文字
  ↓
套用員工修改後的內容
  ↓
建立 direct-edit Evidence
  ↓
寫 Proposal decision Journal
  ↓
更新 Current JD
```

### Reject 或 Defer

```text
Proposal 結束
Current JD 不變
```

### Stale

如果員工審核前，Current JD 已被其他操作改過：

```text
重新鎖定 document
  ↓
比對 jd_before、generation、read-set
  ↓
不一致
  ↓
Proposal 標記 stale
  ↓
禁止把舊內容硬套回去
```

因此模型不可能在員工已修改文件後，拿舊結果覆蓋新內容。

## 11. 主回合提交與 OPKS 排程

Task Analysis 主回合完成後，application 會根據最新狀態判斷是否自動排定 OPKS child operation。

候選 Task 必須符合：

- 在 Current JD 中。
- 對應的 Work Model Task 是 `ACTIVE`。
- 至少有一筆有效員工 Evidence。
- 沒有 active open issue。
- 沒有 pending／deferred OPKS Proposal。
- 本輪的下一題沒有正在詢問它。

系統依 Current JD 的 `display_order` 選出最多一個 Task，並產生：

```text
task_id
analysis_input_digest
opks:auto:{task_id}:{digest}
```

這個排程結果會和主回合一起寫入 completed-turn payload，避免重播時重新挑選另一個 Task。

## 12. OPKS child analysis

一次 `/turns` 最多包含：

```text
一個主顧問分析
+
一個 OPKS specialist 分析
```

OPKS 不由員工按按鈕觸發，也沒有 background worker。

### 建立 OPKS Context

只投影被選中的 Task：

```text
選定 Task 的語意
有效 employee_turn Evidence
有效 direct_edit Evidence
該 Task 現有 O/P
文件層 K/S ordinal
與該 Task 相關的 OPKS Proposal
```

沒有有效員工 Evidence 時：

```text
OpksGroundingUnavailable
→ 不呼叫 provider
```

### OPKS 模型輸出

模型可以提出：

- `add_new`
- `reuse_existing`
- `revise_existing`
- `remove_existing`
- `uncertain`

### OPKS verifier

Verifier 只負責：

- ordinal 是否有效。
- O/P 是否綁定正確 Task。
- K/S refs 是否存在。
- reuse／remove 的引用是否合法。
- 是否有機械契約錯誤。

它不判斷：

- 這個 O/P 是否真的重要。
- 指標是否足夠可觀察。
- 數值是否合理。
- K/S 是否真的適合該 Task。

這些最後由 Proposal 與員工決定。

### OPKS Proposal

```text
verified OPKS changes
  ↓
建立 pending OpksProposal
  ↓
寫 generation receipt
  ↓
authority transaction commit
```

AI 不直接修改 Current JD OPKS。

OPKS Proposal 的決策：

- `accepted`：套用模型候選。
- `edited`：套用員工修改文字，建立 direct-edit Evidence。
- `rejected`：不改 Current JD。
- `deferred`：保留待處理。
- `stale`：相關 Task 或內容已變更，不能套用。

## 13. OPKS 缺口如何回到訪談

如果 OPKS specialist 回傳：

```text
uncertain
```

系統會建立帶有以下資訊的缺口：

```text
subject_task_id
opks_axis
terminal_resolution
```

下一輪主顧問不能直接把這個缺口刪掉，而必須透過：

```text
issue_resolutions[]
```

處理。

可能結果：

- `answered`：員工這一輪提供了新的有效證據。
- `employee_unknown`：員工明確表示不知道。
- `not_applicable`：員工表示不適用。

其中 `answered` 必須同一輪真的留下對應的員工 Evidence，否則只是模型假裝把問題關掉，系統會拒絕。

## 14. Reload、重試與故障處理

每次模型分析都會有 authority snapshot：

```text
authority_generation
packet read-set
conversation authority
```

模型呼叫期間不持有 PostgreSQL lock。模型回來後才重新鎖定文件並檢查：

```text
目前資料是否仍等於模型分析時看到的資料？
```

如果不一致：

```text
StaleAuthoritySnapshot
→ 舊結果不套用
```

同一個 idempotency key 重送：

```text
相同回答
  → 回傳既有結果，不再呼叫模型

不同回答
  → IdempotencyConflict
```

OPKS child 失敗時：

```text
主顧問回合仍然保留
OPKS 自己留下 failed receipt
Current JD 不被錯誤結果修改
```

而且：

- reload 不會偷偷補跑 OPKS。
- GET 不會啟動 background worker。
- 沒有隱藏 retry。
- 不宣稱 exactly-once。
- 所有結果都能從 PostgreSQL 與 Journal reload 回來。

## 15. 整體責任分工

```text
員工
  └─ 提供工作事實、修改內容、批准文件

LLM
  └─ 理解上下文、提出工作訊號、Task change、下一題與 OPKS 候選

mapper
  └─ 把模型輸出轉回 domain 形狀

verifier
  └─ 擋機械契約錯誤與不合法引用

transition
  └─ 根據 identity gate 決定更新 Work Model 或建立 Proposal

application
  └─ 控制流程、交易、idempotency、snapshot、generation、Journal

Current JD
  └─ 只有員工人工編輯或 Proposal decision 才能改變
```

## 16. 一句話總結

```text
員工證據
→ Context Packet
→ 一次模型分析
→ deterministic verifier
→ Work Model 候選
→ Proposal gate
→ 員工決策
→ authority commit
→ Current JD
→ 下一輪重新分析
```

## 參考文件

- [Task Analysis 引擎端到端設計](design/task-analysis-engine.md)
- [產品／UX 決策與範圍](product-notes.md)
- [現行架構鳥瞰](../ARCHITECTURE.md)
- [ADR 索引](adr/README.md)

## 研究文件索引：工作／Task 怎麼判斷

### 建議先讀

- [Task 邊界、merge/split 與同一性判準研究](specs/2026-07-28-task-boundary-merge-split-and-identity-research.md)
  - 目前 Task Analysis v1 最直接的判準研究。
  - 說明什麼算一個 Task、工具與步驟為何通常不是 Task、何時要 split、何時要 merge，以及新敘述如何對齊既有 Task。
  - 邊界不清時不使用文字相似度猜測，而是保留 issue 並追問員工。
  - 文件自身標示為 Proposed；正式施工時仍以 [ADR 0040](adr/0040-professional-consultant-engine-and-r1-validation-contract.md)、[ADR 0042](adr/0042-r1-screening-stop-and-a6-first-version-default.md) 與本文件現行設計為準。

- [AI 專業職務分析顧問流程：最終反方審查與品質設計](specs/2026-07-25-professional-job-analysis-consultant-process-final-red-team.md)
  - 說明為什麼不能用「一段故事直接變一個 Task」、不能把工具名稱升格成工作，也不能把公版內容當成員工實際工作。
  - 保留全域理解、跨故事比較、反證追問、Task 邊界檢查與員工權威。

- [專業顧問架構 R1 紅隊複審與修訂裁決](specs/2026-07-26-professional-consultant-r1-red-team-review-and-corrections.md)
  - 說明品質評測、模型策略、證據支持與 Current State／Journal 邊界。
  - 重要提醒：Task 品質尚不能因 scripted smoke 綠燈而宣稱已通過。

### Task 判斷的實際摘要

一個 Task 候選通常要能說清楚：

1. 做了什麼 action。
2. 對什麼 object／工作對象做。
3. 產生什麼 meaningful outcome、purpose 或責任結果。
4. 這是職務責任，而不是單純工具、程式語言、步驟或偶然事件。

判斷方向：

- 多個 action 若共享同一個 purpose／result，可以是同一個 Task。
- 多個 action 有不同目的、不同責任或不同產出時，檢查 split。
- 兩個敘述語意重疊、無法各自獨立成立時，檢查 merge。
- 只是使用工具、系統或方法時，通常放入 enabler，不建立新的 Task。
- 工具本身若伴隨獨立結果、責任與查核標準，才可能形成合法 Task。
- 判斷平手時不自動 merge，也不自動 split，改為 clarify／追問。
- 不確定新敘述是否就是既有 Task 時，不用文字相似度靜默合併或刪除。

另外，[不完整 JD Task 的明確對齊與員工確認](specs/2026-07-29-job-analysis-partial-jd-task-reconciliation-research.md)
說明只有名稱／描述的員工 Task 如何保存、如何由後續訪談追問，以及為什麼不能自動猜測 duplicate identity。

## 研究文件索引：OPKS 怎麼分析

### OPKS 總裁決

- [OPKS 設計裁決](specs/2026-08-01-opks-design-decisions-research.md)
  - OPKS 研究的入口文件，整理 O／P／K／S／A 的證據、文件層 identity、Proposal gate 與生成邊界。

- [ADR 0048：OPKS 證據兩軸與文件層 K/S/A](adr/0048-opks-evidence-axes-and-document-level-competencies.md)
  - 定義 `evidence_origin`、`task_linkage`、`source_refs[]` 與 O/P/K/S/A 的歸屬。

- [ADR 0049：OPKS 投影、Evidence 白名單與文件權威](adr/0049-opks-derived-axes-evidence-whitelist-and-document-authority.md)
  - 定義哪些資料能作 Evidence、哪些軸由 refs 推導，以及 OPKS 為何是獨立 operation 與獨立 wire schema。

- [ADR 0050：OPKS Proposal 最小形狀](adr/0050-opks-proposal-minimal-shape.md)
  - 定義每項 OPKS 建議一筆 Proposal，不抽通用 Proposal framework。

- [ADR 0051：OPKS Proposal 狀態機與穩定 entity ID](adr/0051-opks-proposal-status-machine-and-stable-entity-id.md)
  - 定義 `pending`、`deferred`、`accepted`、`edited`、`rejected`、`stale` 六種狀態與 entity identity。

### OPKS 五份原料研究

- [OPKS 原始生成與 grounding](specs/2026-08-01-opks-raw-llm-generation-grounding.md)
  - 模型如何在有員工依據時提出候選，避免從職稱、公版或想像補齊內容。

- [工作產出研究](specs/2026-08-01-opks-raw-work-outputs.md)
  - O（Output）如何從實際工作結果判斷，而不是把漂亮的職責句改寫成產出。

- [行為指標研究](specs/2026-08-01-opks-raw-performance-indicators.md)
  - P（Performance Indicator）如何連回實際可觀察的行為、結果或查核條件。

- [技能與技能分類研究](specs/2026-08-01-opks-raw-skills-taxonomies.md)
  - K／S 的來源與分類限制；第一版不讓外部 taxonomy 取代員工實際工作證據。

- [效度與 AI 法規研究](specs/2026-08-01-opks-raw-validity-and-ai-regulation.md)
  - 說明 OPKS 內容的效度邊界，以及不能把客製職務分析自動升格成招募或甄選標準。

### OPKS 漸進式分析與缺口追問

- [OPKS 漸進式蒐集研究](specs/2026-08-04-opks-progressive-elicitation-research.md)
  - 研究為什麼移除「產生／重新分析」按鈕，改由主回合提交後的 application pre-gate 自動排定最多一個 OPKS child operation。
  - 說明 `uncertain`、持久化 gap、item-level 部分發布、`issue_resolutions[]`、digest、receipt 與 replay 邊界。

- [ADR 0054：OPKS 自動排定 child operation](adr/0054-opks-progressive-elicitation-and-scheduled-child-operation.md)
  - 上述研究的現行 Accepted 決策；實作與流程以這份 ADR 和 `task-analysis-engine.md` 為準。

- [OPKS 缺口與再分析封鎖關係研究](specs/2026-08-06-opks-gap-reanalysis-blocking-research.md)
  - 這是針對 live smoke 的診斷研究，專門討論 active gap 是否阻擋後續再分析。
  - 只能作為風險與未來重啟條件的研究紀錄，不可直接拿來改流程。

- [ADR 0055：未解 OPKS 缺口不再阻擋再分析](adr/0055-opks-gap-does-not-block-reanalysis.md)
  - **Rejected，暫不採用。** 現行仍以 ADR 0054 的 active-gap pre-gate 為準。

## OPKS 研究結論的短版

```text
已確認的 Task
  ↓
檢查是否有有效員工 Evidence
  ↓ 沒有
不呼叫 OPKS provider
  ↓ 有
application 選出一個 Task
  ↓
建立單一 Task OPKS Context
  ↓
一次 OPKS operation
  ↓
模型提出 add／reuse／revise／remove／uncertain
  ↓
OPKS verifier 只驗 ordinal、refs 與機械規則
  ↓
建立 OPKS Proposal 或持久化 gap
  ↓
員工接受／修改／拒絕／稍後處理
  ↓
才更新 Current JD OPKS
```

OPKS 的核心不是「把五個欄位填滿」，而是：

- O/P 必須能連回實際 Task。
- K/S 可以是文件層 entity，再由 refs 投影到多個 Task。
- Evidence 主要來自 `employee_turn` 與 `direct_edit`。
- Proposal decision 本身不能偽造成員工 Evidence。
- 模型不應從公版、職稱或一般常識補造 O/P/K/S。
- verifier 不判斷專業品質；專業合理性由 rubric 與員工 Proposal 審核共同把關。
