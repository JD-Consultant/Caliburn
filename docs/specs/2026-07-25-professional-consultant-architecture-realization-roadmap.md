# AI 專業職務分析顧問：最終架構實現路線圖

> **【2026-08-01 現行裁決索引｜先讀這裡】**
> 本文提到的 **「K/S/A 支持度四級」（`behavior_grounded`／`employee_confirmed`／`reference_candidate`／`unsupported`）
> 已由 [ADR 0048](../adr/0048-opks-evidence-axes-and-document-level-competencies.md) 翻案**，
> 改為 `evidence_origin` × `task_linkage` 兩正交軸 ＋ `source_refs[]` 型別層非空。
> 原文保留供追溯，**不得據以施工**。
> OPKS 現行裁決 = **[0048](../adr/0048-opks-evidence-axes-and-document-level-competencies.md)（概念）
> ＋ [0049](../adr/0049-opks-derived-axes-evidence-whitelist-and-document-authority.md)（實作形狀）
> ＋ [0050](../adr/0050-opks-proposal-minimal-shape.md)（Proposal 形狀）**，三份一起讀。


> 日期：2026-07-25
> 狀態：Proposed，供 owner 審核
> 文件性質：從已核准顧問流程與最終程式架構，走到可測試核心、可恢復原型與 server-deployed Web 成品的實現路線
> 顧問流程權威：
> [`2026-07-25-professional-job-analysis-consultant-process-final-red-team.md`](2026-07-25-professional-job-analysis-consultant-process-final-red-team.md)
> 程式架構權威：
> [`2026-07-25-professional-job-analysis-consultant-llm-architecture-red-team.md`](2026-07-25-professional-job-analysis-consultant-llm-architecture-red-team.md)

---

> **【2026-07-26 修訂索引｜先讀這裡】**
>
> 本文件經外部紅隊複審後有七項修訂，分佈於六個章節。**原文一律保留並就地標記，不得據被否決的原文執行。**
> 完整依據見 [R1 紅隊複審與修訂裁決](2026-07-26-professional-consultant-r1-red-team-review-and-corrections.md)
> 與 [ADR 0040](../adr/0040-professional-consultant-engine-and-r1-validation-contract.md)。
>
> | 編號 | 位置 | 修訂 |
> |---|---|---|
> | C-01 | §6.3、§6.4 | 便宜模型優先**已否決**；先用最強模型建天花板 + 2×2 model × schema ablation |
> | C-02 | §8.7 | exit gate 的「或可診斷性」**已否決**；Task 邊界不得退步為硬條件，判準跑實驗前寫定 |
> | C-03 | §6.3 | 8 案例只作快速篩選；鎖架構前擴至 20–30；critical 跑 pass³；案例帶 `case_family_id`／`source_type` |
> | C-05 | §10.5 | Current State 唯一真相 + 同交易 append-only Journal（不要求可重建）；已定案，非待研究題 |
> | C-06 | §10.5 | 三層 eval capture + 單一不可變 Trial Manifest，置於 runtime 之外 |
> | C-08 | §11.5 | K/S/A 與 Indicator 加入四級支持度，Attitude 一併適用 |
> | C-09 | §14.4 | 匯出須明示為採 iCAP 版型的客製 JD，非官方職能基準，不自產基準代碼 |

---

> **【2026-08-03 owner 修訂】** [ADR 0056](../adr/0056-real-employee-pilot-release-gate.md) 將 R8 明確改為 Web
> 發布候選版，R9 改為第一版發布前必須通過的真實員工試用 gate。合成案例、高擬真 transcript、內部自測、LLM grader
> 或非操作者專家審閱都不能取代實際在職員工以本人工作完成端到端試用。
>
> [ADR 0057](../adr/0057-server-deployed-browser-product.md) 另取代「員工電腦 localhost」交付假設：R8 現為伺服器部署、
> 瀏覽器存取的 release candidate，可由企業自管或我們代管；development localhost 不是產品 boundary。R1–R7 gate 不變，
> 共享多租戶與 access model 仍須另案。

---

## 1. 這份路線圖解決什麼

前兩份權威文件已分別回答：

1. 專業職務分析顧問應該如何訪談、分析、修正並完成 JD；
2. 程式應如何用 Controller、Context、LLM Operations、Work Model、Proposal Boundary、Public Challenger、
   Guardrails 與 Harness 實現這套方法。

本文件回答第三個問題：

> 應該依什麼順序研究、設計、測試與實作，才能逐步得到成品，又不會先做完整 Web 或大量基礎設施，最後才發現
> Task 分析方向錯誤？

這不是 class-by-class、migration-by-migration 的施工計畫，也不會在還沒研究節點細節前先猜 schema。它固定：

- 哪一個垂直切片先做；
- 每個切片涵蓋哪些顧問責任與架構元件；
- 每個切片研究什麼；
- 最小要做出什麼可執行結果；
- 用哪些少量案例判斷可不可以往下走；
- 何時才接保存、公版、完整 JD 與 Web；
- 哪些功能明確延後。

每個切片開始前，仍要另寫該切片的研究規格；研究結論穩定後，才寫逐檔案實作計畫。這份路線圖不取代後續研究。

---

## 2. 最終成品定義

第一個正式成品是：

> 一個由企業或我們操作伺服器、員工以瀏覽器存取的 Web 應用。員工與 AI 專業顧問持續對話，逐步盤點與分析目前工作，AI 以提案方式協助
> 建立或修改 JD，員工可接受、修改、拒絕、延後或直接編輯；完整回合、顧問進度與多份 JD 可以保存、關閉並重新開啟。

這個「正式成品」定義只有在 R9 真實員工發布 gate 通過後成立；R8 只產出具備上述能力的 release candidate。

成品至少要讓員工完成以下旅程：

```text
建立或開啟一份 JD
  → AI 先理解角色目的與工作全貌
  → 廣度盤點工作週期與責任區域
  → 以代表性故事深挖工作
  → 跨故事形成並修正 Task
  → 整併 Duty，漸進分析 O/P/K/S/A
  → AI 提出可理解的文件修改
  → 員工接受／修改／拒絕／延後，或直接編輯
  → 公版在後段作 coverage challenge
  → 完成前反方檢查
  → 員工決定完成並匯出
```

第一版成品不包含：

- 共享多租戶 SaaS、tenant control plane、計費；
- 未經另案決定的 organization／member／ACL、角色或自建帳號密碼系統；
- 多人共編、主管或 HR 核准；
- 招募、課程、訓練、考核、稽核或 KPI 模組；
- Graph DB、通用 Graph runtime 或多 Agent 平台；
- token 生成中途恢復；
- 複雜 provenance UI、全面 hash／audit；
- 自動模型路由或跨員工語意結果 cache。

---

## 3. 文件鏈：從需求到最終程式文檔

後續文件不得彼此重寫或形成三套不同架構。文件權威順序如下：

| 文件 | 回答的問題 | 維護時機 |
|---|---|---|
| 顧問流程最終反方審查 | 專業顧問應做什麼、哪些做法會錯 | 顧問方法或產品目標改變時 |
| LLM 程式架構紅隊審查 | 程式如何忠實實現顧問流程 | 核心責任、權限或流程拓樸改變時 |
| 本實現路線圖 | 依什麼順序研究、驗證與交付 | 階段順序、gate 或成品範圍改變時 |
| 各切片研究規格 `docs/specs/` | 該節點應使用什麼方法與技術 | 每個切片動工前 |
| 各切片實作計畫 `docs/plans/` | 實作者要改哪些檔案、如何測試 | 研究與契約確認後 |
| 最終 living design `docs/design/professional-consultant-engine.md` | 已落地程式實際如何運作 | 第一條 production vertical 落地後，與程式同步維護 |

最後的 living design 不能現在憑空寫出不存在的 API、類別或資料表。它要在每個切片真正落地後逐步形成，最終至少包含：

- 使用者動作到程式 route 的完整路徑；
- Work Graph 與 Execution Graph 的實際型別與擁有者；
- 每個 LLM operation 的 input/output、prompt/context policy 與錯誤路徑；
- 提案、員工決策、Current JD 與直接編輯的資料流；
- 保存、恢復、公版檢索與匯出的真實邊界；
- Harness 如何重播相同案例比較 prompt、context 與模型；
- 已退役且禁止恢復的舊路徑。

---

## 4. 顧問流程與最終架構交叉檢查

### 4.1 檢查結果

顧問流程的 Step 0–11 均有程式架構責任與後續實現階段。沒有發現需要推翻整體顧問流程的缺口。

本次檢查發現的問題不是「顧問少做了一個步驟」，而是部分程式語意原本只隱含存在。這些語意已補入程式架構
Revision 3：

1. 恢復時保存上次停止原因、建議下一動作及完成／重新開啟狀態；
2. Role Hypothesis 明確包含 purpose、recipient、responsibility scope、environment／constraints 與混合職責；
3. 員工提供的 SOP、表單、舊 JD、工作清單與實際產出屬於獨立 Source Layer；
4. 短回答必須帶 `QuestionContext`，context 裁切必須顯示相關內容未載入；
5. 故事深挖使用 bounded `StoryFocus`，保存 chronology、input、action、judgment、outcome 等缺口；
6. 員工直接編輯立即更新 Document Layer，但不偽造訪談來源，並觸發受影響分析重整；
7. 對外只有六種 canonical `ConsultantAction`，內部 LLM operation 是 `ExecutionRoute`，兩者不再混為一套 enum。

### 4.2 Step 0–11 追蹤矩陣

| 顧問流程 | 主要程式責任 | 路線圖階段 | 驗證重點 |
|---|---|---:|---|
| Step 0 開啟／恢復 | Consultation State、Context Policy、Resume entry | R3–R5 | R3 恢復對話／工作模型；R5 再涵蓋提案與 JD |
| Step 1 Blind-first 角色定位 | Role Hypothesis、`turn.understand` | R2 | 保留多假說，不由職稱或公版先決 |
| Step 2 廣度工作地圖 | Coverage、`consultation.decide` | R2 | 日／週／月／年、例外、交接與低頻高影響不漏 |
| Step 3 持續顧問循環 | Controller、Context Policy、有限 ConsultantAction | R2 | 每輪全域理解，只選一個主要動作 |
| Step 4 故事深挖 | StoryFocus、Story、Work Unit | R1–R2 | 故事有深度，但故事不直接等於 Task |
| Step 5 Task 邊界 | `work.reconcile`、Task rubric | R1 | 工具、步驟、他人、過去、一次性不誤收 |
| Step 6 Duty 整併 | `job.analyze`、Task grouping | R4 | Task 穩定後才分組，不用公版盒子先套 |
| Step 7 O/P/K/S 漸進分析 | `job.analyze`、Task linkage、reopen | R4 | 不填空、不虛構，可反向修正 Task |
| Step 8 公版 challenge | Public Reference Challenger | R6 | reference 只追問／提案，不自動寫入 |
| Step 9 文件共編 | Proposal Boundary、Current JD、Direct Edit route | R5 | AI 只提案，員工決定，直接編輯可重整分析 |
| Step 10 最終反方檢查 | `quality.challenge`、blocker/warning | R7 | 主動找漏項、錯收、虛構與邊界錯誤 |
| Step 11 完成 | Completion policy、employee decision、export | R7–R8 | 非關鍵 unknown 可保留，完成後可重開 |

### 4.3 顧問流程文件是否需要再改

目前不需要。顧問流程文件已明確涵蓋：

- 支援員工提供工作文件，但不把文件當真相；
- 問題與短答共同理解；
- 固定責任、彈性路徑；
- 每輪全域理解；
- Story／Work Unit／Task 非一對一；
- Task 與 O/P/K/S 雙向修正；
- AI 提案、員工決策與直接編輯；
- 正常完整回合後可離開與恢復；
- 公版延後作 challenger；
- 完成前反方檢查。

三層真相、入口事件、action／route 分離等內容屬於程式實現語意，放在程式架構文件而不是反向污染顧問方法文件。

---

## 5. 實現策略選擇

### 5.1 否決：把每個元件各自做完再整合

```text
先做 Prompt Engine
  → 再做 Context Engine
  → 再做 Harness
  → 再做 Loop
  → 再做 Graph
  → 最後整合
```

問題是每個元件單獨看起來都可能正確，但整合後才發現：

- Context 丟掉更正；
- Task 分析過度切分；
- Loop 選到重複問題；
- Prompt 與 Work Model 對同一詞有不同定義；
- Harness 測的是 schema，不是職務分析品質。

這會重演「架構看起來完整，成品效果卻很差」。

### 5.2 否決：Web-first

先做聊天頁、JD canvas、保存與 API，會很快看見畫面，但也會讓錯誤的 Task 模型、提案粒度與 Context 介面提早固化。
若 Task 邊界後來需要重做，UI、API 與資料表會一起重構。

### 5.3 採用：薄垂直切片

每個切片都走完：

```text
一小段真實顧問問題
  → Context
  → LLM operation
  → Work Model 更新
  → 下一顧問動作或文件結果
  → 小型 Harness 評估
```

優點：

- 最早驗證最危險的 Task 分析；
- Prompt、Context、Loop 與資料語意一起接受結果檢驗；
- 每個切片都有可執行成果；
- 失敗時只重做小範圍；
- Web 與長期儲存等核心語意穩定後再接。

---

## 6. 每個切片的固定工作循環

每個階段都使用同一個簡化循環，不先建立通用平台。

### 6.1 研究

只研究該階段需要回答的問題：

- 專業顧問方法與資料定義；
- 目前官方 LLM prompt、structured output、context 或 eval 方法；
- 必要時比較兩種可行設計；
- 對最可能失敗的設計做 strongest-case red team。

研究結果寫入 `docs/specs/`，引用官方、規範、原作者或專業機構；不以來路不明文章作架構權威。

### 6.2 契約草案

每個節點只先固定：

- purpose；
- input；
- output；
- authority；
- allowed decisions；
- failure modes；
- stop condition；
- 哪些是 deterministic，哪些是 semantic。

不在研究階段先決定所有 class、table、event 或 framework。

### 6.3 小型能力案例

> **【2026-07-26 修訂 C-01／C-03｜模型策略與案例規模已修正】**
>
> 原文第 2 點「先跑一個固定便宜模型」會混淆「模型能力不足」與「架構設計錯誤」，並使 harness 永久
> over-fit 到弱模型；原文第 1、3 點的案例規模與 trial 數低於大廠建議一個量級。**現行規定為：**
>
> - **先以最強可用模型建立品質天花板，再往下換便宜模型**。快篩矩陣**同時**包含 A2–A5 的
>   model × schema 2×2（｛最強, 便宜｝×｛輕, 重 schema｝，架構固定兩階段），以及固定「最強 + 輕 schema」下
>   **A2 vs A6** 的兩階段／一次呼叫比較；另含 A1（同配置、minimal harness）作 harness 承重對照。
>   **勝出配置下的 matched comparison 延後到 shortlist 或 shipping model gate。**
>   六個 arm 的定義見 [ADR 0040](../adr/0040-professional-consultant-engine-and-r1-validation-contract.md) 決定 6。
> - 8 個案例保留作**快速篩選**（只用於淘汰明確錯誤設計，**不得用於宣稱架構勝出**）；
>   **鎖定架構前擴至 20–30 個**，critical case 跑 3 trials 看 pass³。
> - R1 **不做正式 power analysis**；同一 session 衍生案例共用 `case_family_id`，統計時整組算一個單位。
> - 案例 metadata 必含 `source_type`（`constructed_edge`／`human_manual_test`／`real_employee_interview`）。
>   **不設預設值，依實際來源分類**：人工構造＝`constructed_edge`；原樣使用人類操作逐字稿＝
>   `human_manual_test`；由舊 session 改寫或合成的新案例＝`constructed_edge`（可另留 `source_session_ref`）。
>   **一律不得升級為 `real_employee_interview`** —— owner 已裁定沒有真實員工訪談資料。
>
> 依據：[R1 紅隊複審與修訂裁決](2026-07-26-professional-consultant-r1-red-team-review-and-corrections.md) §3.1、§3.3、
> [ADR 0040](../adr/0040-professional-consultant-engine-and-r1-validation-contract.md) 決定 5–13。
> 以下原文保留供追溯，**不得據原文執行**。

- 第一個切片使用 6–8 個關鍵案例；
- ~~先跑一個固定便宜模型與一個簡單單 Agent baseline；~~ ←【C-01 已修正】
- ~~日常迭代每案例先跑一次；~~ ←【C-03 已修正】
- 只有 critical 或不穩定案例在 gate 前跑 2–3 trials；
- 發現真實新失敗才新增案例，不追求全面排列；
- 保存模型輸出、工作模型變化、下一問與人工判斷。

### 6.4 最小實作

- 先使用 fixture、CLI 或測試入口；
- 普通 application code 表示 Execution Graph；
- 固定單一模型與精確版本／slug；【C-01 補充：exact slug 與 endpoint 仍必須固定；但「固定哪一個」由 §6.3
  修訂框的 ablation 決定，不預設為便宜模型。另依 ADR 0040 決定 23–28：`require_parameters: true`、禁 fallback、
  live preflight 實送 portable schema、local verifier 永遠存在】
- Provider Adapter 保持薄；
- 不接 Web、不建 Graph runtime、不拆微服務；
- 不為還沒出現的 SaaS 或多人需求預留複雜欄位。

### 6.5 評估與裁決

每個切片結束只能有三種結論：

1. **通過**：達到 exit gate，可進下一階段；
2. **修正**：改 prompt、context、work model 或 operation 分工，再跑同一批案例；
3. **否決**：相對簡單 baseline 沒有改善，或增加 critical error，停止擴建並重審架構。

不能因為已寫很多程式就把失敗切片視為通過。

---

## 7. R0：文件與語意對齊

### 7.1 目的

確保顧問流程、程式架構與實現順序使用同一套語意，避免實作者自行發明另一套流程。

### 7.2 本階段結果

- 顧問流程 Step 0–11 已追蹤到架構元件；
- 程式架構已升至 Revision 3；
- Source／Work／Document 三層已明確；
- ConsultantAction 與 ExecutionRoute 已分開；
- 恢復、員工 supporting artifacts、QuestionContext、StoryFocus 與 direct edit reconciliation 已補齊；
- 本路線圖已建立。

### 7.3 Exit gate

- 兩份權威文件沒有互相矛盾的流程責任；
- 路線圖每一個階段都能指回顧問需求與架構元件；
- 沒有把 vNext、既有 API 或舊資料表相容當成前提；
- 沒有新增 SaaS、Graph framework 或多 Agent 需求。

---

## 8. R1：Task Discovery 垂直切片

### 8.1 為什麼最先做

上一版最嚴重的產品失敗是工作分析錯誤，例如把 Java、HTML、Python、Excel 或操作步驟各自變成 Task。
如果 Task 邊界不正確，後面的 Duty、Output、Indicator、K、S、A、公版與 UI 都只會把錯誤包裝得更完整。

### 8.2 最小流程

```text
員工一句話或短 transcript
  → turn.understand
  → Source Claims + Unmapped Signals
  → StoryFocus / Story / Work Units
  → work.reconcile
  → Task Candidates
  → consultation.decide
  → 一個自然的下一問
```

### 8.3 本階段要研究

#### `turn.understand`

- 如何高召回辨識同一句中的多個工作訊號；
- 問題與短回答如何共同構成有限主張；
- 更正、否定、過去、他人、共同、支援、一次性與不知道如何表示；
- 工具、方法、步驟、Output、Indicator、K/S 線索如何先保留而不升格；
- 如何保留無法映射的內容。

#### `work.reconcile`

- Story 如何拆成 0..N 個 Work Unit；
- 一個故事多工作、多故事一工作如何比較；
- Task 的 action、object、meaningful outcome、responsibility 與 assignability 判準；
- `ReconciliationDecision = add／edit／merge／split／no-op／clarify` 的邊界；
- 哪些判斷放 prompt、哪些放 deterministic verifier、哪些留給人工 rubric。

#### `consultation.decide`

- broaden、deepen_story、clarify_boundary 三種早期動作何時選；
- 如何以資訊價值、錯誤風險與員工負擔排序；
- 如何只問一個自然問題；
- 如何避免固定問卷與重複追問。

### 8.4 最小資料語意

只需要：

- Employee Message；
- `QuestionContext`；
- Source Claim；
- Unmapped Signal；
- StoryFocus／Story；
- Work Unit；
- Task Candidate；
- minimal Coverage Gap；
- `ConsultantAction`；
- operation result。

此時不需要：

- Current JD；
- Proposal；
- 完整 O/P/K/S/A；
- 公版 retrieval；
- 長期資料庫；
- Web；
- Graph framework。

### 8.5 第一批 8 個案例（**定位＝快速篩選**，見 §6.3 修訂框）

1. 工具名稱不是 Task；
2. 工具操作本身有獨立 outcome 與責任，因此可以是 Task；
3. 一個故事包含多個工作；
4. 多個故事共同支持一個 Task；
5. 過去工作不得成為現行 Task；
6. 他人工作／交接不得誤收；
7. 一次性支援不得升格成穩定 Task；
8. 員工更正先前說法。

共享 outcome 不過度拆分與不同 outcome 不過度合併，要嵌入第 3、4 類案例，不為增加測試數而額外建立大量排列。

> **【2026-07-27 補充｜八案全數為 development set，不切 holdout】**
>
> §10.6 已把「八個案例很容易被 Prompt 過度擬合」列為反方六。依
> [ADR 0041](../adr/0041-r1-p0-closure-first-version-context-and-holdout.md) 決定 13–17：
>
> - **八案不切 holdout**。§11 的 `TI-R1-01`–`08` 連 `輸入核心`、`預期` 與 `Critical failure` 都已公開，
>   而本文件是寫 prompt 的人必讀的 authority；答案已曝光的案例標成 holdout 不產生 unseen 證據。
> - 尤其**不得抽走第 2 案**（唯一的正向案例）：抽走會把 prompt 推向「看到工具就不建 Task」的單邊最佳化。
> - 八案期間的防線是**凍結期望**：`預期` 與 `Critical failure` 不得為配合模型輸出而改寫，要改須升 case
>   revision。第 2、7 案另標為 **locked regression cases**（防退步），不得宣稱證明 unseen generalization。
> - **未曝光評測集延到 20–30 案擴充階段**：在 prompt／context／schema **最終凍結之後**才建立
>   （以 freeze 的 commit SHA + canonical hash 為憑，**不以檔案時間為憑**），正反平衡，
>   其輸入與期望**不得寫進任何 authority 文件**。critical failure → 不得宣稱通過。
> - **命名誠實**：獨立人員製作且未曝光才叫 `holdout`；本 repo 一人團隊採時間隔離，
>   只能叫 `post-freeze fresh challenge set`；已看過或反覆執行的降級為 `regression set`。

### 8.6 輸出物

- 一份 R1 深入研究規格；
- 一份小型 operation 契約；
- 一個可從 fixture／CLI 執行的 Task Discovery prototype；
- 一份 baseline 與候選架構比較報告；
- 8 個案例的原始輸出、Task 判斷、下一問與人工 review。

### 8.7 Exit gate

> **【2026-07-26 修訂 C-02｜最後一條的「或」已修正】**
>
> 原文允許候選架構在 Task 邊界沒有改善時、僅憑「可診斷性較好」通過 R1，正好抵銷 §21
> 「Task Discovery 不優於簡單 baseline 就停」的效力。**現行規定為：**
>
> - **Task 邊界品質不得退步**為必要條件；可診斷性只作加分，不得單獨構成通過理由。
> - 所有判準必須在跑實驗**之前**寫定：哪些是 deterministic check、哪些是人工 rubric、
>   兩階段要贏多少才算贏。
> - 8 案例的結果只能用於淘汰明確錯誤設計，不能宣稱架構勝出（見 §6.3 修訂框）。
>
> 依據：[R1 紅隊複審與修訂裁決](2026-07-26-professional-consultant-r1-red-team-review-and-corrections.md) §3.2、
> [ADR 0040](../adr/0040-professional-consultant-engine-and-r1-validation-contract.md) 決定 9–11。

- critical negative cases 不把工具、過去、他人與一次性內容誤寫為穩定 Task；
- 一故事多工作與多故事一工作皆能形成合理候選；
- correction 能壓過舊說法；
- `no-op` 是正常結果，不強迫每輪產生 Task；
- 下一問自然、單一、不引導；
- ~~相對簡單單 Agent baseline，Task 邊界或可診斷性至少有一項實質改善，且無 critical regression。~~
  ←【C-02 已修正：Task 邊界不得退步為硬條件，可診斷性只加分】

若失敗，優先調整 claim、Work Unit、Task rubric、context packet 或 operation 分工；不要接資料庫與 Web。

---

## 9. R2：自適應多輪顧問循環

### 9.1 目的

把 R1 的單次分析變成能維持職務全貌、故事深度與彈性焦點的多輪顧問。

### 9.2 新增能力

- Blind-first Role Hypothesis：purpose、recipient、responsibility scope、environment／constraints、混合職責，以及
  2–3 個假說各自的支持、反例、未決與 active／weakened／rejected／accepted-for-now 狀態；
- 工作週期與責任區域 Coverage；
- bounded StoryFocus：chronology、input、action、judgment、outcome、recipient、ownership、typicality 的已知與缺口；
- 員工提供的工作材料以獨立、不可信 Source 載入；
- Conflict／Open Issue；
- 最近問題與避免重問；
- 六種 canonical ConsultantAction；
- Controller 的有限 route；
- 多輪 context packet；
- 簡單 in-memory／fixture state。

### 9.3 主要流程

```text
新回答
  → 全域理解所有訊號
  → 更新 Role / Coverage / Story / Work / Conflict
  → 必要時 reconcile Task
  → 根據資訊價值選一個 ConsultantAction
  → 問一個自然問題
```

階段焦點可以是角色、廣度、故事或 Task，但新回答裡的其他訊號仍要保留。

### 9.4 要研究

- blind-first 多角色假說如何形成與降權；
- coverage 如何導航而不變成填表分數；
- StoryFocus 何時開啟、關閉或切換；
- 如何選代表性故事，又不讓精彩故事掩蓋例行工作；
- SOP、舊 JD、工作清單或實際產出如何協助回憶，又不自動變成現行工作；
- 如何在長對話中只取 operation 需要的 context；
- context 省略如何讓模型知道「還有內容未載入」；
- 顧問問題如何兼顧資訊價值與員工負擔。

### 9.5 最小案例

在 R1 基礎上新增少量多輪案例：

- 模糊職稱但混合職責；
- 精彩事件掩蓋高頻例行工作；
- 員工在談 Output 時主動提出新工作；
- 短回答必須依 QuestionContext 才能正確理解；
- 員工回答「不知道／不適用／想不起來」；
- 舊 JD 看似正式，但員工明確說現況已不同；
- 相關舊來源刻意未載入時，context packet 明示 omission，而不是宣稱沒有其他工作；
- 已回答問題不得重問。

### 9.6 Exit gate

- 對話不是固定欄位問卷；
- 每輪都能接住跨焦點訊號；
- Role Hypothesis 可被反例削弱或推翻；
- 2–3 個 Role Hypothesis 的支持、反例、未決與狀態不會在 route 間遺失；
- Coverage 能發現未談責任，但不強迫補滿選填欄位；
- StoryFocus 可開啟、切換、關閉，保留八類故事位置的已知／缺口，並在適當時回到廣度盤點；
- Context packet 在相關來源未載入時帶 omission signal，模型不得把未載入判成不存在；
- 問題不重複、不一次問多項、不用公版引導答案。

---

## 10. R3：持久化保存、Pre-document Resume 與 Context State

### 10.1 目的

讓員工在一個完整 AI 回合結束後隨時離開，隔天回來仍是同一個顧問狀態。

### 10.2 必須保存

- 已完成 employee／AI turns；
- Source Layer，包含員工提供的工作材料及其最小來源資訊；
- Role Hypotheses；
- StoryFocus、Stories、Work Units；
- Task Candidates／Tasks；
- Coverage、Conflicts、Open Issues、Unmapped Signals；
- Current Focus；
- 上次停止原因與建議下一動作；
- completion／reopen 狀態。

Current JD 與 Proposal 會在 R5 加入；R3 先證明訪談與工作模型能正確恢復。因此本階段稱為
`pre-document resume`，不宣稱四種入口事件已全部完成。

### 10.3 Supporting Artifact 最小切片

R3 同時固定員工工作材料的最小 ingress 與保存語意：

- 接收已貼上或已抽出的可分析內容；通用檔案解析不是本階段目標；
- 保存 source ID、名稱、類型與內容；
- 將材料與 employee message、公版 reference 分區；
- 可在 Context Policy 選取時提供，也可完全不提供；
- 一份看似正式的舊 JD／SOP 不得覆蓋員工最新明確現況。

至少使用一個 fixture 證明：員工明確說現況已改變時，舊文件只能形成 challenge／open issue，不能改寫 Current Work Model。

### 10.4 入口事件

- Employee Message；
- Resume Session。

R5 再加入：

- Proposal Decision；
- Direct Document Edit。

### 10.5 要研究

> **【2026-07-26 修訂 C-05／C-06｜第 1 與第 6 點已改為定案，不再是待研究題】**
>
> 狀態與歷史的邊界已裁定如下，R3 研究不必再重新開放：
>
> ```text
> Current Work Model / Current JD  = 唯一現況真相；reload 直接讀取，不 replay
> Consultation Journal             = append-only（回合、員工決策、直接編輯），與現況修改同一 transaction；
>                                    不要求足以重建 Current State
> Eval Capture（runtime 之外）      = prompt／context／model 的比較重播，不參與 production reload
> ```
>
> Eval capture 保存三層（source/state snapshot／context packet + operation input／trial evidence），
> 由單一 **Trial Manifest**（一次 trial 一份、寫入後不可變）管理版本來源；
> `resolved_model`／`resolved_provider+endpoint` 必須取自**回應**，不得由請求推斷。
>
> 依據：[R1 紅隊複審與修訂裁決](2026-07-26-professional-consultant-r1-red-team-review-and-corrections.md) §3.5、
> [ADR 0040](../adr/0040-professional-consultant-engine-and-r1-validation-contract.md) 決定 18–22。
> 以下原文保留供追溯；其餘 4 點仍為 R3 待研究題。

- 哪一份 state 是 authority，哪些摘要只作索引；【C-05 已定案，見本節修訂框】
- 更正、否定與 supersession 如何在恢復後保持優先；
- operation-specific context 如何從同一 state 重建；
- 最小 server-side persistence 與完整回合提交邊界；
- provider／parse 失敗時如何保留上一完整回合；
- 如何避免過早建立 event sourcing、workflow checkpoint 或全面 hash。【C-05 已定案，見本節修訂框】

### 10.6 Exit gate

- 關閉並重新載入後，對話、工作模型、focus、矛盾與下一問一致；
- Role Hypothesis、StoryFocus、support／反例／未決與八類故事位置不因 reload 遺失；
- correction 不會因 reload 復活舊內容；
- omission signal 可由保存狀態重建，而不是 reload 後變成「沒有其他內容」；
- supporting artifact 可保存、重載與被 Context 選取，且不能覆蓋員工明確現況；
- 不重問已回答或已明確跳過的問題；
- provider 失敗不留下半套新 state；
- 不支援回答到一半或 token-level 恢復。

---

## 11. R4：Duty、O/P/K/S/A 漸進分析

### 11.1 目的

在 Task 邊界相對穩定後，產出專業 JD 所需內容，但不把它做成一次填滿六格的生成器。

### 11.2 流程

```text
stable-for-now Task
  → Output
  → Indicator
  → Knowledge / Skill
  → optional Attitude
  → 檢查是否反向揭露 Task 邊界錯誤
  → keep / clarify / reopen / merge / split
```

Duty 在有一批相對穩定 Task 後，依共同 purpose、outcome、responsibility 或 workflow stage 動態整併。

### 11.3 要研究

- 服務、監控、預防與決策工作的 Output 如何表示；
- Indicator 的 condition + observable behavior/result；
- 如何禁止沒有來源的數字門檻；
- Knowledge 與 Skill 的區分；
- 工具如何成為 Skill 的組成而不是 Skill 全文；
- 每項 K/S 如何連回一個或多個 Task；
- Attitude 何時有工作行為支持，何時必須 unknown；
- O/P/K/S 何時應 reopen Task。

### 11.4 最小案例

- 服務或監控 Task 沒有實體文件；
- 沒有數值來源，不得生成百分比或時間門檻；
- 一個 K/S 支援多個 Task；
- 職稱常見能力但本工作不需要；
- 公版尚未介入時仍可產生客製 K/S；
- O/P 揭露一個 Task 應拆成兩個；
- 不從聊天語氣推斷 Attitude。

### 11.5 Exit gate

> **【2026-07-26 修訂 C-08｜K/S/A 與 Indicator 加入支持度，原 gate 不足】**
>
> 原文只要求 task linkage 與禁止無來源數字。職務分析文獻（Morgeson et al. 2004, *JAP* 89(4), 674–686）顯示
> **在職者對 ability 陳述的評分膨脹顯著高於 task 陳述**，而本產品沒有主管或分析師對照樣本，
> 因此 K/S/A 是全份資料裡最脆弱的一格。**現行規定為：**
>
> | 支持度 | 定義 | 可否進正式 JD |
> |---|---|---|
> | `behavior_grounded` | 有具體 Task／故事／行為證據 | 可 |
> | `employee_confirmed` | 員工明確確認這是**工作要求**，不只是自己會 | 可，但保留標記 |
> | `reference_candidate` | 只來自公版 | 只能作候選 |
> | `unsupported` | 模型推測 | 不可 |
>
> - Attitude 與 Indicator 數值門檻**一併適用**。
> - 系統必須區分「員工會什麼」與「這份工作要求什麼」；「需要 Java」「主動積極」「每月 99%」
>   都要追問其 Task、行為、產出或實際判準。
> - **員工按接受不得被記錄成已有行為證據。**
>
> 依據：[R1 紅隊複審與修訂裁決](2026-07-26-professional-consultant-r1-red-team-review-and-corrections.md) §3.7、
> [ADR 0040](../adr/0040-professional-consultant-engine-and-r1-validation-contract.md) 決定 29–32。

- O/P/K/S/A 不要求每格都有值；
- 所有採用的 K/S 都有 Task linkage 與白話理由；【C-08 補充：另需帶支持度標記】
- 無來源數字不會成為已確認 Indicator；【C-08 補充：Indicator 門檻同樣帶支持度】
- Output 能涵蓋服務、狀態改變或判斷結果；
- O/P/K/S 能觸發 Task reopen，而不是把錯誤 Task 補完整。

---

## 12. R5：Proposal、Current JD 與員工共編

### 12.1 目的

把 Work Model 的分析安全地轉成員工可理解、可決定的正式文件。

### 12.2 新增語意

- Current JD；
- AI Proposal；
- before／after；
- add／edit／merge／split／delete；
- 白話理由與最小 source pointer；
- accept／edit／reject／defer；
- Direct Document Edit；
- 受影響分析的 reconciliation。

### 12.3 四種入口事件完整成立

```text
Employee Message
Proposal Decision
Direct Document Edit
Resume Session
```

R3 只完成 employee message／resume 的 pre-document fidelity；R5 要把 proposal、Current JD 與 direct edit 納入，
才完成四入口的 full resume fidelity。

### 12.4 要研究

- 一次 proposal 應多小，員工才看得懂；
- Task merge／split 如何顯示邊界差異；
- 員工修改後接受時，以什麼內容成為 Current JD；
- reject／defer 如何影響後續 context；
- direct edit 如何標記受影響 Task、Duty、O/P/K/S 與 pending proposal；
- 文件內容與工作來源矛盾時，何時澄清、何時尊重文件決定；
- 如何保存簡單來源 ID，而不做複雜 provenance UI。

### 12.5 最小可見原型

可以先用 CLI／開發頁顯示：

- 目前 JD；
- 一個小型 proposal；
- before／after；
- accept／edit／reject／defer；
- direct edit；
- reload 後結果。

此時仍不要求正式 Web 視覺成品。

### 12.6 Exit gate

- LLM 永遠不能直接 mutate Current JD；
- employee edit 後保存的是員工版本；
- reject 不會在後續被當成現況；
- direct edit 不會偽造 Source Claim；
- direct edit 能使相關分析進入待重整，而不是保持假一致；
- reload 後 proposal、decision、Current JD 與顧問焦點一致。
- 四種入口事件各自完成一輪後，reload 都能恢復相同的 Source／Work／Document 三層狀態。

R5 通過後，才算得到第一個「能實際共同建立 JD」的核心測試品。

---

## 13. R6：公版 Reference Challenger

### 13.1 目的

使用現有公版資料幫助補漏、比較與改善語言，但不讓公版取代員工現況。

### 13.2 啟動條件

- 已形成 Role Hypothesis；
- 已有一批員工內容支持的 Task；
- 需要 coverage challenge、K/S 候選或公版匯出比對。

### 13.3 流程

```text
Work Model
  → query projection
  → deterministic lexical + dense hybrid retrieval
  → 少量候選
  → public.challenge
  → match / partial / no-match / conflict，或保持未決並追問
  → validate_or_challenge 或 proposal
  → 員工決定
```

Retrieval node 只取得候選；`public.challenge` 只比較候選與 Work Model。它不擁有 Current JD 或員工決策，
不得直接採用候選；輸出只能導向 clarification／challenge 或 `document.propose`。

### 13.4 要研究

- 何時檢索、查詢由哪些已知內容形成；
- 現有 indexer／API 是否值得重用，或只重用資料與 ID；
- lexical 與 semantic 結果如何合併；
- 候選數量與 context 形式；
- public reference 與 employee supporting artifact 如何明確分區；
- 公版查無內容時，如何保留 document-local custom Task／K／S；
- 公版代碼、名稱、職類、職業、行業與基準級別如何作選填 Header proposal。

### 13.5 Exit gate

- blind-first 階段完全不以公版內容限制員工；
- retrieval score 不會直接成為適用判斷；
- `ReferenceMatch` 只使用 match／partial／no-match／conflict；資訊不足時保持未決並追問；
- no-match／conflict 不會自動覆蓋員工內容；
- 公版候選只能形成追問或 proposal；
- 公版沒有的實際工作仍可保留；
- 採用候選只需保存既有穩定 reference ID。

---

## 14. R7：完成判斷、反方檢查與匯出

### 14.1 目的

讓系統不是「有幾個 Task 就完成」，也不是「每格填滿才完成」。

### 14.2 `quality.challenge`

至少檢查：

- 是否漏掉高頻例行工作；
- 是否被精彩故事主導；
- 是否漏掉低頻高影響責任；
- 是否誤收過去、他人或一次性工作；
- 是否把工具或步驟升格；
- Task 是否過度拆分、合併或重複；
- Duty 是否合理；
- O/P/K/S/A 是否有 Task linkage；
- 是否有無來源數字或虛構內容；
- correction 是否生效；
- accepted proposal 是否與新來源衝突；
- 公版是否造成錨定；
- 是否仍有高影響 Unmapped Signal／Conflict／Open Issue。

### 14.3 完成裁決

- 角色 purpose 與主要責任可以解釋；
- 適用的工作週期、例外與低頻高影響責任已合理盤點；
- 關鍵 Task 邊界已穩定；
- 關鍵 Task 的適用 O/P/K/S 已達可供 JD 使用的程度；
- 無會顯著改變文件的重大矛盾；
- `quality.challenge` 沒有 blocker；
- Blocker 必須先處理；
- Warning 可由員工知情後保留；
- AI 只能建議完成；
- 員工決定完成；
- 已完成 JD 可以因新資訊或員工選擇重新開啟。

這不代表每一 Task 的 O/P/K/S 四格都必須填滿。自然不適用的 Output 可以省略，非關鍵內容可以 unknown；
只有使主要工作無法理解、查核或使用的缺口才是 blocker。

### 14.4 匯出

> **【2026-07-26 修訂 C-09｜匯出措辭必須明示非官方職能基準】**
>
> 依「職能發展及應用推動要點」第 2、7、9 點，**職能基準是「特定職業或職類」層級**、以行業／職業／職類為
> 發展範疇、由中央目的事業主管機關等發展（國際對應做法 DACUM 亦為 5–12 位專家 + 引導師的工作坊）。
> 本產品是一位員工 + AI 產出的**企業內個別職務說明書**，因此匯出必須標示：
>
> > 本文件為客製職務說明書，採 iCAP 職能基準欄位版型，不代表勞動部認證或官方職能基準。
>
> 且**不得自行產生看起來像官方認證的職能基準代碼**。
>
> 依據：[R1 紅隊複審與修訂裁決](2026-07-26-professional-consultant-r1-red-team-review-and-corrections.md) §3.8、
> [ADR 0040](../adr/0040-professional-consultant-engine-and-r1-validation-contract.md) 決定 33–34。

至少支援：

- 內部高品質 JD view；
- 政府公版格式 projection。【C-09：措辭見本節修訂框】

公版格式只是輸出映射，不反向限制內部資料模型。

### 14.5 Exit gate

- 有 blocker 時不建議完成；
- 關鍵 Task 的適用 O/P/K/S 未達可用程度時不建議完成；
- 非關鍵 unknown 不會被虛構填滿；
- final challenge 確實能把問題送回 clarification／reconciliation；
- 員工可完成、重新開啟與再次修改；
- 匯出不改變 Current JD 的內部 identity 與內容。

---

## 15. R8：伺服器部署 Web 發布候選版

### 15.1 何時才接

只有 R1–R5 的核心分析與共編路徑通過小型品質 gate 後，才投入完整 Web。R6、R7 可與 Web 後段整合交錯，
但不能讓 UI 反向固定錯誤的工作分析模型。

### 15.2 最小 UI

- 瀏覽器首頁：建立、開啟、重新命名、刪除多份 JD；
- 一次開啟一份 JD；
- 左側或主要區域：顧問對話；
- 同畫面：目前 JD canvas；
- proposal：before／after、白話理由、接受／修改／拒絕／延後；
- 員工可直接編輯 JD；
- 員工可選擇貼上或附加、查看、移除或替換支援的工作材料；不要求一定提供，也不建立通用文件管理平台；
- 顯示目前焦點、必要 warning 與尚待處理項；
- 保存狀態清楚；
- 關閉後重新開啟；
- 完成與匯出。

### 15.3 明確不加入

- 自建帳號密碼與密碼重設；
- 未經 access ADR 核准的 organization／member／role；
- 管理後台；
- 多人 presence／comment／approval；
- 共享多租戶 control plane；
- Electron／Tauri，除非 owner 之後明確要求。

### 15.4 建立 living 程式文檔

R8 的第一條真實 production vertical 通過後，建立：

`docs/design/professional-consultant-engine.md`

這裡的「第一條真實 production vertical」是指 server-deployed Web 的 employee message：

```text
UI
  → production request
  → Controller / Context / LLM operation
  → Source／Work state
  → proposal 或顧問問題
  → completed-turn persistence
  → reload
```

這份 living design 只能記錄已存在的 route、型別、operation、persistence 與錯誤路徑，不得複製研究中的預想 API。
R9 起，任何改變上述行為的程式變更都要同步更新此檔。

### 15.5 Exit gate

- production deployment 可在單一伺服器重複建立，另一台使用者裝置可透過 HTTPS 瀏覽器開啟；
- 員工不需要設定 host／port、啟停服務或接觸 deployment secret；
- 可以保存並重新開啟多份彼此隔離的 JD；
- migration、persistent data、health、backup／restore 與 upgrade／rollback 有可執行 runbook；
- 多名使用者或非受控網路 exposure 已有另案核准的 authentication／authorization policy；
- 對話、提案、Current JD 與顧問進度一致；
- supporting artifacts 可選提供、查看、移除／替換，且不會自動覆蓋員工現況；
- 完成主要使用旅程時不需要技術人員介入；
- `docs/design/professional-consultant-engine.md` 已由通過 gate 的真實程式路徑建立；
- 工程與模型 safety net 已綠，可交付受控的 R9 真實員工試用。

通過本 gate 只代表 release candidate 已成立，不代表「員工可用成品」已通過真人驗證。

---

## 16. R9：真實員工試用發布 gate 與品質打磨

R8 是可供受控試用的 release candidate，不是已可發布的員工成品。R9 必須由第一版的預期操作者，以本人目前實際從事的
工作完成小規模端到端試用；主管、HR 或 SME 可作第二層內容審閱，但不能取代 incumbent 操作。高擬真 transcript、模擬
persona、產品團隊自測、合成 eval 與 LLM grader 仍可用於除錯與 regression，但不能讓本 gate 成立。

Pilot 開始前須在獨立執行計畫固定 release scope、招募條件、情境 coverage、rubric、severity、樣本數與
pass／rework／invalid decision rule。試用至少要：

- 觀察員工從啟動、訪談、提案決策、保存／重開到匯出是否真正完成，並記錄 false-success、求助與放棄；
- 比較最終 JD 與本人工作證據，檢查 Duty／Task／O／P／KSA 的重要缺漏、捏造、邊界與 linkage；
- 記錄員工修改、拒絕、不理解的 proposal，以及漏問、重問、引導、訪談過長與不可恢復問題；
- 檢查敏感資料處理、員工可停止／拒絕／修正的 agency，以及 Evidence／reference／AI 推論的 provenance；
- 保留 consent／data plan、build 與設定、session evidence、內容驗證、issue register、release decision 與重測範圍；
- 比較模型、prompt 與 context policy，但一次只改一個主要變因；
- 評估 latency、token 與費用。

沒有合格真實員工、預先定義的門檻或可追溯證據時，pilot 無效而不是 pass。出現 release blocker 時回到受影響的 R1–R8
階段修正並重測；只有通過本 gate，M8 才能稱為第一個經真實員工驗證的可用成品。這仍不代表企業正式核准或組織級效度。

只有評測證明需要，才考慮：

- 對高風險 merge／split 或 final review 增加第二 Reviewer；
- 為特定 operation 引入**比 shipping 模型更強**的模型；←【C-01 補充：R1 已用最強可用模型建過天花板，
  所以這裡指的是「shipping 降本後，個別 operation 需要回補能力」，不是「第一次考慮強模型」】
- 導入 Graph runtime；
- fine-tuning；
- 新增更多正式資料來源。

---

## 17. 最終架構元件到階段的覆蓋

| 架構元件 | 首次出現 | 主要完成 | 後續擴充 |
|---|---:|---:|---|
| Consultation Controller | R1 | R2 | R3／R5／R7 加入口與 route |
| Context Policy | R1 | R3 | R4／R6 加 OPKS 與公版 context |
| `turn.understand` | R1 | R2 | 真實案例持續調校 |
| `work.reconcile` | R1 | R1 | R4 支援 Task reopen |
| `consultation.decide` | R1 | R2 | R6／R7 加 challenge／completion |
| `job.analyze` | R4 | R4 | 真實 JD 打磨 |
| `document.propose` | R5 | R5 | R6 公版候選與 R7 修正 |
| `public.challenge` | R6 | R6 | R9 調校候選比較與追問 |
| `quality.challenge` | R7 | R7 | R9 可選高風險 Reviewer |
| Open Work Model / Work Graph | R1 | R4 | R5–R7 增加文件與 reference 關係 |
| Proposal & Document Boundary | R5 | R5 | R8 UI |
| Public Reference Challenger | R6 | R6 | R9 調校 retrieval |
| Thin Model Gateway | R1 | R1 | 換模型時重跑 gate |
| Guardrails | R1 | R5 | R6／R7 加 reference／completion 規則 |
| Observability | R1 最小 | R8 | 只依診斷需求增加 |
| Quality Harness | R1 | 持續成長 | 每階段只新增必要案例 |
| Execution Graph | R1 普通 code | R7 | 有實證才評估 Graph runtime |
| Local Web | 無 | R8 release candidate | R9 真人發布 gate 與使用性打磨 |
| Living program design | 無 | R8 真實 production vertical 通過後 | R9 起跟隨行為變更 |

沒有任何階段要求「先完整做完 Prompt Engineering、再完整做 Context Engineering」。五種 Engineering 的角色是：

- Prompt：在每個 LLM operation 內；
- Context：在每個垂直切片依 operation 組裝；
- Harness：從 R1 起伴隨每個切片；
- Loop：從 R1 最小動作選擇，R2 形成多輪顧問；
- Graph：從 R1 明確 route 與 state，但第一版以普通 application code 實現。

---

## 18. 最小 Harness 策略

### 18.1 測什麼

優先測會直接毀掉 JD 品質的錯誤：

- false Task promotion；
- missed Task；
- over-split／over-merge；
- ownership、time scope、typicality；
- correction retention；
- unsupported O/P/K/S/A；
- unsupported numeric threshold；
- proposal authority；
- resume fidelity；
- public-reference anchoring；
- 重複、引導與過長問題。

### 18.2 不測什麼

第一版不追求：

- 每個 enum 的所有笛卡兒積；
- 每句 prompt 文字的 snapshot；
- 通用 agent benchmark；
- 全面 provider conformance；
- 為不存在的 SaaS、權限或多人流程建立測試；
- 以 100% code coverage 作為品質目標。

### 18.3 Grader 分工

- deterministic checks：明確禁令與不變量；
- rubric grader：Task 邊界、支持度、問題品質；
- 人工閱讀：模型是否像專業顧問，是否漏掉真實語意；
- 多 trial：只用於模型變異可能影響 gate 的 critical cases。

### 18.4 Harness 不是 production framework

Harness 可以直接呼叫相同 operation 與 state transition，但不應被 production route import 成產品依賴。它的目的只有：

- 重播；
- 比較；
- 評分；
- 保存證據；
- 阻止品質退化。

---

## 19. 研究與技術決策順序

### 19.1 現在先研究

下一份研究文件只處理 R1 Task Discovery：

1. `turn.understand` 的最小語意與 short-answer grounding；
2. Story／Work Unit／Task boundary 的專業判準；
3. `work.reconcile` 的決策集合；
4. `consultation.decide` 的早期三動作；
5. 8 個案例的**快速篩選**方法與 baseline 比較設計（8 案只淘汰明確錯誤，不宣稱勝出；鎖架構前擴至 20–30）；
6. **最強可用模型**的 operation 設計與結構化輸出能力，以及 model × schema ablation 的執行方式。
   ←【C-01／C-03 已修正；原文為「8 個案例與 baseline 比較方法」「固定便宜模型的 operation 設計與結構化輸出能力」】

### 19.2 現在不要研究到細節

- 最終 Web layout；
- 所有資料庫表；
- 公版 retrieval tuning；
- OPKS 完整 schema；
- Graph framework；
- 多 Agent；
- fine-tuning；
- SaaS；
- 大型 observability／audit。

這些不是永遠不做，而是現在的結果不能幫助判斷 Task 分析是否正確。

### 19.3 每次只打開一個主要不確定性

例如研究 R1 時，不同時比較：

- 三個模型；
- 四套 Prompt；
- 兩種 Work Model；
- 兩種 Graph framework。

~~先固定模型與測試案例，只比較 baseline 與一個候選架構。~~ ←【C-01 已修正】
**現行做法**：R1 刻意用受控的 factorial 設計同時打開**模型**與 **schema 重量**兩個變因（2×2），
因為兩者互為混淆因子（弱模型 + 重 schema 會同時退化，逐一變更無法歸因）。
其餘變因（prompt、Work Model、Graph framework）仍維持一次只動一個。
若失敗，再依錯誤歸因改一個主要變因。

---

## 20. 進度里程碑

| 里程碑 | 使用者能看到什麼 | 代表什麼 | 不代表什麼 |
|---|---|---|---|
| M1：Task 分析測試品（R1） | transcript → Task candidates → 下一問 | 最危險的工作邊界可被評估 | 還不是完整顧問或 JD |
| M2：多輪顧問測試品（R2） | 可連續對話、廣度／故事切換 | 顧問 Loop 與 Context 有基本效果 | 還不能可靠離開恢復 |
| M3：可恢復顧問原型（R3） | 關閉、重開後繼續同一狀態 | resident state 成立 | 還沒有完整 JD 共編 |
| M4：工作分析核心（R4） | Task、Duty、O/P/K/S/A 候選 | 專業 JD 內容可逐步形成 | AI 還不能安全寫入正式文件 |
| M5：共編核心測試品（R5） | proposal、決策、Current JD、direct edit | 已可實際共同建立小型 JD | 尚未做公版與完成檢查 |
| M6：完整 JD 核心（R6–R7） | 公版 challenge、反方檢查、完成與匯出 | 內容流程完整 | 尚未是員工友善成品 |
| M7：伺服器部署 Web 發布候選版（R8） | 瀏覽器可操作、保存多份 JD、重開、匯出 | 可進入受控真實員工試用 | 尚不是員工可用成品 |
| M8：真人驗證成品（R9） | 真實在職員工完成端到端旅程，已知 blocker 經處理與重測 | 第一個經真實員工驗證的可用產品 | 不自動取得企業核准或組織級正式效度 |

---

## 21. Stop／Rework 條件

以下任一情況出現，不得用更多 UI、資料表或 Agent 掩蓋：

- Task Discovery 不優於簡單 baseline；
- 工具、過去、他人、一次性工作仍常被誤收；
- Context packet 使 correction 復活或跨焦點訊號消失；
- Work Model 大量把重要內容丟進無法恢復的 unknown；
- Loop 變成固定問卷或重複追問；
- 多次 LLM 呼叫只增加錯誤、成本與延遲；
- O/P/K/S 為了完整率而虛構；
- Proposal 讓員工難以理解或大量直接重寫；
- 公版 candidate 開始主導員工內容；
- R8 前的核心測試品已顯示互動延遲不可接受。

重做順序：

1. 檢查 capability case 與 gold 是否代表真正顧問品質；
2. 檢查 Context 是否缺少／混入錯誤來源；
3. 檢查 Work Model 是否把語意硬塞錯類型；
4. 檢查 operation 是否分得過細或責任重疊；
5. 檢查 prompt／schema／verifier；
6. 最後才考慮 Reviewer 或 Graph runtime。←【C-01 已修正；原文為「最後才考慮更強模型、Reviewer 或
   Graph runtime」。**更強模型已在 R1 第一步用來建立品質天花板，不再是最後手段**；此處要問的是
   「便宜模型是否夠用」而不是「要不要升級模型」】

---

## 22. 最終裁決

### 22.1 採用

- 先完成本路線圖，再逐階段寫深入研究與實作計畫；
- 採薄垂直切片，不採孤立元件完工後再整合；
- 第一個切片是 Task Discovery；
- R1 只用 fixture／CLI、小型 Harness、**最強可用模型建立品質天花板**，並與**強模型 + 最小 harness**
  的簡單 baseline 對照；便宜模型於 ablation 中比較，不作為裁決架構的基準；
  ←【C-01 已修正；原文為「固定便宜模型與簡單 baseline」】
- Prompt、Context、Harness、Loop、Graph 在每個切片共同演進；
- Work Graph 保存系統知道什麼，Execution Graph 決定下一步；
- Execution Graph 第一版使用普通 application code；
- resident state、ephemeral LLM operations；
- 核心分析與共編通過後才做完整 Web；
- 每階段都可以被 eval 否決；
- 最終 living design 只描述已落地程式，不預寫虛構 API。

### 22.2 不採用

- 先做完整 Context Engine、Harness 平台或 Graph framework；
- 先完成 Web 再測 LLM 品質；
- 每個節點建立一個 Agent；
- 每輪 Planner + Worker + N Reviewers；
- 用更多測試數量、schema、hash 或 log 代替職務分析品質；
- 為未要求的 SaaS、多租戶、帳號或多人流程預留架構；
- 在 R1 尚未通過前設計完整 OPKS、公版匯出與所有資料表。

### 22.3 下一個工作

下一步是撰寫並審核：

> **R1 Task Discovery 垂直切片深入研究規格**

它只研究 `turn.understand`、`work.reconcile`、早期 `consultation.decide`、最小 Work Model 與 8 個 capability cases。
研究完成並經 owner 討論確認後，才寫 R1 的逐檔案實作計畫與 prototype。
