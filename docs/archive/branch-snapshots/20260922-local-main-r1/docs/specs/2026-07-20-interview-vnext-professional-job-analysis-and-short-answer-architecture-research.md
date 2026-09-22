---
title: Interview vNext 員工訪談、專業職務分析與即時 JD 共編架構研究
status: accepted-research; R5 authority is ADR 0037 + amendment; post-R5 product authority is ADR 0038
date: 2026-07-20
revision: 9
audience: owner, architect, implementer, evaluator
scope: R5 前置設計；員工訪談、短回答、即時共編、當下單一職務、document-local K/S 與交付 projection
---

# Interview vNext 員工訪談、專業職務分析與即時 JD 共編架構研究

> 本文保存 R5 前置研究、產品邊界與後續職務分析／共編方向；**不是 exact implementation authority**。owner 已於
> 2026-07-20 核准 R5 必要裁決，active 決策為
> [`ADR 0037`](../adr/0037-interview-vnext-question-frame-contextual-evidence-and-employee-authority.md)，exact build authority 為
> [`R5 grounded short-answer amendment`](../plans/2026-07-20-interview-vnext-v3-5a-r5-grounded-short-answer-amendment-plan.md)。
> owner 於 2026-07-22 另行確認 R5 後的 Context Engine、LLM operations、Agenda／Sufficiency、Authoring Core、AI proposal、
> 公版metadata／retrieval與產品交付順序；active authority為
> [`ADR 0038`](../adr/0038-interview-vnext-context-engine-and-professional-consultant-workflow.md)。
> 不得因本文存在就自行新增 migration、production route、Web wiring 或 paid live。
>
> **Revision 3（owner scope correction）**：現有 editor、深文件契約、API、indexer 與欄位都只是可盤點的既有資產，
> 不是必須整合的限制。目標架構先以產品品質、可追溯性與一人團隊可維護性設計，再用明確 gate 決定保留、
> 包裝、遷移或替換哪些既有元件。
>
> 本階段產品只處理「一個人當下的工作 → 這一份專屬職務說明書」。客戶可能是公司、個人或其他單位，但不建立
> 公司層 capability catalog、跨職務 K/S 共用、人才盤點或個人能力評分。這些都不是目前需求。
>
> **Revision 4（employee product correction）**：第一版不是 SaaS，也沒有另一位職務分析顧問負責審稿。
> 使用者與最終決策者就是員工；AI 扮演專業顧問。員工可在訪談期間直接修改文件，AI 的新增、修改與刪除只能先形成
> 可理解的 proposal，由員工接受、修改後採用或拒絕。共編不是訪談結束後才接上的附屬 editor，而是從第一輪就與
> 對話同步的產品核心；但 editor UI 不得反向污染 R5 的 turn-grounding contract。
>
> **Revision 5（code-audit refinement）**：literal 與 contextual provenance 仍必須分型，但不再建立與 Evidence 平行的
> `ContextualAssertion` aggregate。現有 Episode／Gap／Inference／Candidate 全以 `evidence_id` 閉合，因此 active 決策是
> `Evidence.v3.support = literal_employee_span | contextual_answer` discriminated union。此修正保留兩種證明強度，並避免
> R5 為一個短答功能重寫整個 Job Model support graph。
>
> **Revision 6（post-R5 product authority）**：固定一個conversation owner與application-owned workflow；`turn.interpret`、
> `question.select`、`episode.code`、`job.consolidate`、`requirements.draft`、`job.compose`分成versioned operations，使用
> operation-specific typed context。`JobStateDigest`由canonical draft確定性投影，provider memory不是domain truth；AI文件
> 變更一律proposal，員工direct edit立即成為draft truth。不得重新合併成大型`consultant.advance`prompt。
>
> **Revision 7（local-web product scope lock）**：第一個成品是員工電腦本機運行的 Web 應用程式，不是雲端網站或
> 單人版 SaaS。啟動流程可開啟 localhost UI，但員工不拿遠端網址、不註冊、不登入、沒有帳號密碼，也不設定 host／port。
> 這不強制完全離線：本機 Web app 可使用 owner 配置的 OpenRouter key。除非 owner 明確改變範圍，不做 organization、tenant
> product behavior、ACL、計費、雲端部署或多人協作；研究與工程優先投入訪談品質、LLM 工作分析與 JD 成品品質。

> **Revision 9（2026-08-03 server deployment correction）**：Revision 7 的員工電腦／localhost topology 已由
> [ADR 0057](../adr/0057-server-deployed-browser-product.md) 取代。現行是單企業 server deployment，可由企業自管或我們代管，
> 員工以瀏覽器存取；共享多租戶、多人角色與 identity 仍另案。Revision 7 的其他職務分析優先序不變。
>
> **Revision 8（no-history MVP correction）**：owner 於 2026-07-24 決定第一個成品不做 JD 版本歷史。active JD
> persistence 只保存每份文件的目前內容；員工直接編輯或接受 AI proposal 時更新 current relational rows，不建立完整
> immutable revision、不複製全文件 rows，也不加入 `entity_version`／`link_version`。本文後續所有 revision、restore、
> revision diff、head hash／CAS 描述一律降為後續可選優化，不是 MVP 實作要求。AI 仍只能提出 proposal，不能繞過員工
> accept／edit／reject。詳細 current-table authority 見
> [Job Authoring v2 本機單一現況儲存設計](2026-07-24-job-authoring-v2-relational-storage-research.md)。

## 1. 結論先行

可以從訪談中建立以下正式交付欄位：

1. 主要職責；
2. 工作任務；
3. 工作產出；
4. 行為指標；
5. 職能內涵 K（knowledge）；
6. 職能內涵 S（skills）；
7. 必要時再加職能級別、態度、任職條件與整體工作描述。

但這些欄位**不能全部由 R5 單輪模型直接產生**。員工看到的是「跟 AI 顧問對話，同時看著自己的 JD 逐步成形」；
內部才拆成可驗證的 operations：

```text
訪談原話／短回答
  -> Conversation Grounding（知道這句在回答哪一題、哪個 slot）
  -> Employee Evidence（員工事實，保留可驗證 provenance）
  -> Episode / Task Model（同一工作片段的輸入、行動、產出、標準、例外）
  -> Candidate Job Model（主要職責、任務、產出、指標）
  -> Optional Reference Coverage（查公版，判定 usable/partial/no-match）
  -> Document-local K/S Drafting（公版不足時依已確認 task 產候選）
  -> Employee Review（員工用白話確認符合工作、修改或拒絕）
  -> Canonical Job Model Revision
  -> Live Authoring Workspace（員工也可隨時直接編輯）
  -> Deterministic Export（OCS JSON、JD、PDF、XLSX、API）
```

R5 的原始「只接受 current employee quote」設計適合作為 literal evidence gate，但不足以支援自然訪談。
短回答不應靠放寬 quote verifier 解決，而應新增**機器可讀 Question Frame + Answer Binding + composite
provenance**。如此「是」、「每週」、「主管」、「都會」可以被正確理解，又不會把 AI 問題中的假設偷偷洗成
員工事實。

推薦維持單一 adaptive conversation owner、typed operations、deterministic reducers/verifiers、provider-neutral
port；不因本需求新增多 Agent framework、session vector database 或把完整 transcript 每輪全部送入模型。

現有 OCS document、editor `_pending`、knowledge pack 與 Qdrant pipeline **不可直接被宣告為 canonical product core**。
它們需分別接受 authoring fidelity、provenance、document-local K/S、retrieval quality、維運成本與 migration cost gate。

原 R5 計畫不可直接開工，因它明文延後短答繼承問題 scope，且把「每天／每週／每月」同時當成 current marker。
Revision 5 已由 ADR 0037／R5 amendment 凍結 QuestionFrame、AnswerBinding、Evidence.v3 support union、interpretation
receipt 與 frequency/time 規則，故 **R5 現在可按新 authority 開工**。文件 proposal UI、政府公版匯出與舊／新 editor
選型仍不阻塞 R5。

## 2. 本次實際閱讀與盤點範圍

### 2.1 附件公版

已逐頁讀取 `S:\jd-pdf-to-json\data\AIoT應用工程師-職能基準.pdf`。檔案內實際有 10 個 PDF page
object，但頁首標示「共 11 頁」；因此不能宣稱已讀到不存在於檔案中的第 11 個 page object。

附件內容包括：

- 職能基準代碼、名稱、分類、職業與行業；
- 整體工作描述與基準級別；
- T1–T6 主要職責；
- 各主要職責下的工作任務；
- O-code 工作產出；
- P-code 行為指標；
- 每個 block 的職能級別；
- K01…K45 知識；
- S01…S41 技能；
- A01…A11 態度；
- 學歷、經驗與能力條件。

附件證明目標不是一般徵才網站的一頁式 JD，而是較完整的 **Occupational Competency Standard /
Competency-based Job Model**。

### 2.2 現有 Caliburn

已核對：

- 現行 OCS deep-document authority：[`apps/api/docs/document-of-record.md`](../../apps/api/docs/document-of-record.md)；
- OCS/JD JSON 欄位：[`docs/ocs-schema.md`](../ocs-schema.md) 與
  [`packages/ocs-contract`](../../packages/ocs-contract/)；
- editor 與 knowledge pack：[`docs/design/editor-knowledge-pack.md`](../design/editor-knowledge-pack.md)；
- knowledge pack 組裝：[`apps/api/docs/knowledge-pack-assembly.md`](../../apps/api/docs/knowledge-pack-assembly.md)；
- Qdrant/indexer pipeline：[`apps/ocs-indexer/docs/pipeline.md`](../../apps/ocs-indexer/docs/pipeline.md)；
- BGE-M3 embedder：[`apps/embedder/README.md`](../../apps/embedder/README.md)；
- vNext Evidence、Inference、CandidateJobItem、Gap、ContextBuilder；
- 現行 R5 C1 v2 提案與 R6 eval 邊界。

現有系統已有可用元件，但不代表它們是 greenfield 最佳解。真正缺口是：

```text
對話語意與短回答
  -> 可追溯 Employee Evidence
  -> 任務／產出／指標／K/S 候選
  -> versioned authoring/review model
 -> one or more delivery surfaces
```

現有 [`ADR 0030`](../adr/0030-ai-coedit-tracked-changes-one-brain.md) 的「AI 不可靜默改動、員工可接受／拒絕」方向可保留，
但有兩個實作裁決與 Revision 4 衝突：它把 proposal 主要存為文件內 `_pending`，且人改內容只記 trace、不讓後續模型
知道。新產品需要 canonical proposal/decision 與 `JobStateDigest`，否則 AI 會重問或重提員工已經親手改過的內容。本文
核准後必須另寫 superseding ADR 指明替換哪些段落，不能讓實作者同時遵循兩套 authority。

既有 contract 的 `CompetencyBlock.knowledge/skills` 只保存 `CodeName`，沒有 typed basis、evidence/reference closure 與
review status。knowledge pack 又以原始字串精確比對去重。這些設計可作 OCS exchange/editor projection，但在決定
「為何這份 JD 需要這項 K/S」時仍不足；不過本階段只補 document-local requirement，不建立跨文件 concept graph。

### 2.3 外部 authority

本研究只採供應商官方工程文件、政府職務分析標準、官方 occupational taxonomy 或官方原始研究。完整連結見
§19。

## 3. 「一份 JD」其實有兩種產品

### 3.1 徵才用 Job Description

企業常見的徵才 JD 通常包括：職稱、工作摘要、主要職責、工作內容、資格條件、技能、經驗、匯報關係與工作
條件。它適合招募溝通，但通常不會逐任務列出 O/P/K/S linkage。

### 3.2 職能基準／職能型職務說明書

使用者附件與現有 editor 屬於更完整的第二種：

```text
職務基本資料
  └─ 工作描述／基準級別
主要職責（OCU / Duty）
  └─ 工作任務（Task）
       └─ 工作產出（Output）
       └─ 行為指標（Performance / Behavior Indicator）
       └─ 職能級別
       └─ K：完成任務需理解的原則、事實、概念
       └─ S：完成任務需能執行的認知或技術操作
全職務
  └─ A：態度
  └─ 任職條件／補充事項
```

勞動部 iCAP 將職能基準定義為主要工作任務、行為指標、工作產出、知識、技能、態度等能力組合；2026 品質
認證手冊仍使用相同欄位。故 Caliburn 應保留完整 canonical job model，再投影成：

- canonical authoring workspace（可由既有 editor adapter 或新 UI 實作）；
- PDF、XLSX、JSON；
- 簡化的招募 JD；
- 訓練需求或能力盤點。

檔案格式不是 domain model。不能讓 PDF 表格版面反過來限制訪談內部狀態。

## 4. Authority 對職務分析流程的共同結論

### 4.1 iCAP：訪談是底稿，不是最終真理

iCAP《職能基準發展指引》建議混合使用：

- 訪談法：蒐集基本資料與內涵底稿；
- 功能分析法：以結果／產出為導向，按「動詞、受詞、條件」分解主要功能、子功能與功能單元；
- 專家會議：確認職能單元、K/S/A 與職能級別；
- 驗證：確認內容完整、適切且能反映產業需求。

這直接否定「把 transcript 丟給一個 prompt，一次生成整張表」作為專業流程。

### 4.2 OPM：任務與職能必須建立 linkage

OPM 的 job analysis 流程是：收集職務資料、列任務、辨識 critical tasks、辨識 critical competencies、讓
SME 評定每個 competency 對每個 task 的重要程度，再保留有 linkage 的項目。K/S 不是從職稱或單句自述自動
長出來的標籤。

### 4.3 O*NET／ESCO：Job 與 Worker Requirements 分層

O*NET Content Model 明確區分：

- Job：tasks、work activities、work context；
- Worker requirements/characteristics：knowledge、skills、abilities、work styles。

ESCO 也把 occupation 與 knowledge/skill concepts 分開，以有版本、穩定 URI 與關係資料連結。ESCO v1.2
採用 AI 抽取與 linking，但仍結合 human expertise 與 quality improvement，而不是讓生成文字直接成為 taxonomy
truth。

### 4.4 OpenAI／Anthropic：typed extraction + workflow + eval

- OpenAI Structured Outputs 保證 schema adherence，不保證內容真實；使用者輸入不足時，schema 反而可能迫使
  模型填入幻覺值，因此 schema 仍需 nullable/empty path 與 semantic verification。
- OpenAI 的 meeting-intelligence 官方範例要求 decision/action item 帶 transcript evidence reference，並以
  deterministic check 驗證 segment ID 與 quote；LLM judge 只作補充。
- Anthropic 建議已知、可分解任務先使用簡單 composable workflow；只有 eval 證明不足才增加 agentic
  complexity。
- Anthropic context engineering 將 context 視為有限 attention budget，應每輪選最小且高訊號的狀態，而不是
  把完整歷史、全部 OCS 與所有中間產物塞入 prompt。

這與 Caliburn 現有 Evidence-first、ContextBuilder、typed LLM Port、deterministic reducer、Capture/eval 主線
一致。

## 5. Recommended target architecture

```text
┌──────────────────────── Employee Workspace ─────────────────────────┐
│ AI 顧問對話                         Live JD canvas                  │
│ 問問題／說明進度                    員工直接編輯（立即生效）       │
│                                      AI 修改（先顯示 proposal）      │
│                                      符合我的工作／修改／不符合     │
└──────────────────┬──────────────────────────┬───────────────────────┘
                   │ employee turn            │ document command/decision
                   ▼                          ▼
┌──────────────────────────┐      ┌───────────────────────────────────┐
│ Conversation Core        │      │ Canonical Job Authoring Core      │
│ QuestionFrame            │      │ entities + draft revisions        │
│ R5 Turn Interpreter      │      │ employee commands                 │
│ literal/contextual gates │      │ AI proposals + employee decisions │
│ Evidence/Gap reducers    │      │ provenance + optimistic conflict  │
└────────────┬─────────────┘      └────────────────┬──────────────────┘
             │ grounded support                    │ accepted job state
             └──────────────────┬──────────────────┘
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│ Context Engine / Workflow Policy                                    │
│ minimal operation packet + current JobStateDigest + next best gap   │
└───────────────┬───────────────────────────────┬─────────────────────┘
                │                               │
                ▼                               ▼
┌────────────────────────────┐     ┌──────────────────────────────────┐
│ Episode / Job Operations   │     │ Optional Official Reference Port │
│ task/output/indicator/duty │     │ public task/O/P/K/S snapshots     │
└──────────────┬─────────────┘     └────────────────┬─────────────────┘
               └──────────────────────┬─────────────┘
                                      ▼
                         ┌──────────────────────────┐
                         │ AI Document Proposals    │
                         │ including document-local │
                         │ K/S + task linkage       │
                         └────────────┬─────────────┘
                                      ▼ employee decision
                         Canonical revision -> deterministic export
                         internal JD / government OCS / PDF / XLSX
```

這是 deterministic workflow with semantic decision points，不是一組角色互相聊天的 multi-agent system。
任何 editor、API 或 retrieval engine 都是上述 domain ports 的 adapter，不得反過來決定 canonical model。

這張圖有兩條同等重要的輸入路徑：

1. 員工在聊天中回答，由 R5 形成 literal 或 contextual-support Evidence；
2. 員工在文件中直接編輯，由 Authoring Core 形成 employee-authored document assertion。

第二條不送進 R5，也不假裝成 transcript quote。它直接成為目前 draft 的有效內容，並透過 `JobStateDigest` 讓
Question Policy 知道哪些內容已填、哪些 gap 仍存在。AI 若要據此推導其他欄位，仍須建立有 support linkage 的
proposal，不能把一次直接編輯無限外推。

## 6. 五種來源必須分開

| Source channel | 能證明什麼 | 不能證明什麼 |
|---|---|---|
| Employee literal evidence | 員工這一輪明說的事實與限定條件 | 未說出的 currentness、ownership、K/S、KPI |
| Employee contextual answer | 員工對一個已持久化、可驗證 question frame 的確認／否認／slot value | 任意舊問題、複合 leading question 中未被清楚確認的所有假設 |
| Employee document edit | 員工主動寫入或修改後採用的文件內容 | 不代表 transcript 曾說過，也不能自動支持其他衍生欄位 |
| Reference knowledge | 官方名稱、定義、相似任務、O/P/K/S 候選及來源 | 員工實際有做、員工一定具備某技能 |
| AI inference / optional policy | 專業措辭、task linkage、候選標準或另行提供的規則 | 未經員工接受前不是這份 JD 的 accepted truth |

任何 projected job claim 都要保存來源類型。reference relevance、employee actuality、employee approval 是三個不同
判斷，不得合併成一個模糊 confidence score。

## 7. 短回答不能靠完整 transcript 猜

### 7.1 問題本質

自然訪談常出現：

- 「是／對／沒錯」；
- 「不是」；
- 「每週」；
- 「主管」；
- 「兩個都有」；
- 「看情況」；
- 「差不多」；
- 「是，但月底會多做一份報告」。

只看 current employee quote，無法知道「每週」是哪個任務的頻率、「主管」是 recipient 還是 owner；但直接把上一題
文字複製成 evidence 又會讓 leading question 污染事實。

Google Dialogflow CX 的現行 form filling 仍把 active parameter 與 session state 分開保存；OpenAI Responses 與
AWS Bedrock 也把 conversation/session state 當一級資料。Caliburn 不應只保存自然語言問題，還要保存其意圖。

### 7.2 `QuestionFrame.v1`

每次顧問提問時，Question Policy 必須同時產生自然語言與機器可讀 frame；application 驗證後持久化。

```text
QuestionFrame.v1
  question_frame_id: application UUID
  session_id
  consultant_turn_id
  episode_id | null
  selected_gap_id | null
  document_id | null
  target_entity_ids[]
  mode:
    open_narrative
    slot_request
    atomic_confirmation
    choice
    correction_check
    episode_review
  target_evidence_ids: tuple[UUID, ...]
  target_candidate_ids: tuple[UUID, ...]
  requested_slots: tuple[GapDimension, ...]
  propositions: tuple[QuestionProposition, ...]
  choices: tuple[QuestionChoice, ...]
  provenance_policy:
    literal_only
    bind_slot
    confirm_atomic
    review_candidates
  question_text_hash
  frame_hash
  status: active | consumed | stale | superseded
  valid_for_next_employee_conversation_turn: true
```

`QuestionProposition` 不是 employee evidence。它至少保存：

```text
ordinal
subject
kind
claim
source_kind: prior_employee_support | employee_document_edit | public_reference | ai_inference
support_refs[]
reference_urns
introduced_dimensions
```

ID 由 application 派生；模型不得產 DB identity 或任意 cross-reference key。

Lifecycle：同一 session 最多一個 active frame；下一個 employee **conversation turn** 消耗它。文件 direct edit 本身不
消耗 frame；但若修改到 frame 的 target entity/version，frame 轉 `stale`，下一個短答不能再綁定。新的 AI 問題會把
舊 frame 標成 `superseded`。open narrative 可沒有 proposition；atomic confirmation 必須剛好一個。

### 7.3 confirmation 防 leading 規則

`atomic_confirmation` 只有在以下條件全部成立時可用：

1. frame 只有一個清楚 proposition；
2. proposition 只確認一個工作事實，或所有其他欄位已有 employee evidence；
3. 一題不得同時首次引入 action、ownership、frequency、output、recipient 等多個未知事實；
4. reference-derived proposition 要標示來源，不得偽裝成員工先前說過；
5. frame 只對緊接的下一個 employee conversation turn 有效，且 target 未因 direct edit 變 stale；
6. response text hash 必須與 persisted frame 對得上；
7. 若問題文字與 frame 不一致，整個 contextual binding fail closed。

錯誤問題：

> 所以你每週主責製作缺貨報告並交給採購主管，對嗎？

它同時引入頻率、ownership、output、recipient；回答「對」語意不夠精確。

較好的問題：

> 這項彙整工作通常多久做一次？

回答「每週」只填 frequency slot。

### 7.4 `TurnInterpretOutput.v2` 應擴充的 proposal

為控制 latency，第一版仍使用一次 provider call，同時輸出：

```text
dialogue_act:
  standalone_answer | affirm | deny | slot_value | choose |
  correction | dont_know | decline | stop | off_topic | mixed

literal_observations[]
answer_bindings[]
user_signal
episode_signal
emergent_topics[]
turn_insufficiency_codes[]
```

`AnswerBindingProposal`：

```text
binding_kind: proposition | slot | choice | review
proposition_ordinal | null
slot | null
choice_ordinals[]
answer_quote
answer_quote_occurrence
resolution: affirmed | denied | value | ambiguous | unknown
value_text | null
insufficiency_codes[]
```

request 每次只帶一個 active frame，模型不得回傳 frame/domain ID。模型只提 binding ordinal；application 從 operation
input 取得真正 frame identity，並驗證 frame scope、ordinal、quote、slot type、single-target 與 expiry。

### 7.5 contextual evidence 需要 composite provenance

目前 `Evidence.v2` 只有一個 employee quote/span，無法誠實表示：「語意來自問題 frame，權威來自員工短答」。
Revision 4 曾推薦保留 `Evidence.v2` 並另建 `ContextualAssertion.v1`。Revision 5 盤點現有 Episode、Gap、Inference、
Candidate 與 ContextBuilder 後，改採 **`Evidence.v3` + discriminated support union**。不要把完整 proposition 偽裝成
由「是」字面支持，也不要讓 literal consumers 誤把 composite claim 當逐字 quote；但不需因此建立第二套 assertion graph。

```text
Evidence.v3
  evidence_id
  session_id
  subject / kind / claim / qualifiers
  support:
    literal_employee_span
      employee_turn_id / quote / span / quote_match
    | contextual_answer
      employee_turn_id / answer_quote / answer_span
      question_frame_id / definition_hash
      target_ordinal / target_hash
      binding_kind / resolution / value-or-choice
  status / supersession
  extractor_operation_id
```

不變量：

- 每筆 contextual support 必須閉合到驗證時 eligible 的 QuestionFrame 與 employee answer span；同一 reducer commit後該
  frame轉 consumed，Evidence仍引用其 immutable definition/target hash；
- reference snippet 永遠不可成為 employee authority；reference-derived proposition 仍須標示來源；
- full claim 不需是「是」的 substring，但必須等於已驗證 frame proposition／slot resolution；
- correction、withdraw、supersede 語意仍由 deterministic reducer 處理。

後續 Job Model仍引用 `evidence_id`；要顯示或評分證明強度時先依 `support_kind` 分流，不把兩者壓成模糊 confidence。

平行 `ContextualAssertion` 只在未來有證據顯示 assertion 具有完全不同 lifecycle/ownership 時再考慮；R5 不先支付整個
support graph 的 polymorphic migration 成本。

### 7.6 短回答 acceptance matrix

| Frame | Employee answer | 結果 |
|---|---|---|
| atomic confirmation | 「是／對」 | contextual confirmation；保留 question + answer provenance |
| atomic confirmation | 「不是」 | denied/correction proposal，不接受原 proposition |
| frequency slot | 「每週」 | 綁到指定 task/evidence 的 frequency；不可建立新 task |
| recipient slot | 「主管」 | recipient value；subject/ownership 不變 |
| choice, single-select | 「A」 | 選 A；choice ordinal 必須存在 |
| choice, multi-select | 「兩個都有」 | 只有 frame 明示 multi-select 才接受全部 |
| numeric slot | 「差不多」 | ambiguous；不產 exact threshold |
| expired/missing frame | 「是」 | 不綁定舊問題；回 no-work-fact/clarification |
| any valid frame | 「是，但月底還會做報告」 | 同時產 binding + literal observation |
| composite leading frame | 「對」 | fail closed，問一個較小的澄清問題 |

## 8. 怎麼縮短訪談，而不是降低資料品質

### 8.1 不逐格問表格

不應依 OCS 欄位順序逐一詢問每個任務的 frequency、ownership、output、indicator、K、S。推薦策略：

1. 先用 open narrative 收工作廣度；
2. 自動拆出高價值 task/episode；
3. 每個 episode 預設只追問 1–2 個最高價值 gap；
4. K/S 主要靠已確認 task + optional reference + AI drafting，員工只需用白話判斷「這份工作是否真的需要」；
5. 數字 KPI、能力級別、態度只在產品需要且證據不足時追問；
6. unknown 是合法狀態，不用為填滿每一格無限追問；
7. 在 authoring workspace 依同一 task／episode 成組審候選，避免聊天逐筆確認；
8. 不能因追求完整表格而追問低價值欄位；unknown、not_applicable 與「稍後由 AI 起草」都是合法狀態。

### 8.2 資訊價值與負擔共同排序

Gap priority 應由 application policy 根據：

```text
JD value
contradiction risk
whether this answer unlocks T/O/P/K/S mapping
existing evidence redundancy
employee burden
sensitivity
remaining interview budget
```

R5 只回報 observation/binding/insufficiency，不自行判斷「這個 qualifier 對 JD 重不重要」。重要性由 agenda/gap
policy 決定。

### 8.3 自然的 episode close

AI 可以用一句短 recap 收尾：

> 我先整理成「彙整各門市缺貨明細，供採購主管安排補貨」，目前知道是每週進行；我接著想了解另一項工作。

員工可立即更正，但不要求每輪回答「確認」。更完整的 task/output/indicator/K/S 候選直接顯示在同步文件區，以
「符合我的工作／修改後採用／不符合」一次處理。proposal 應在 episode close 或有實質新資訊時產生，不要每一句話
都讓文件閃動。

### 8.4 interview budget

Anthropic Interviewer 的公開測試採 10–15 分鐘 adaptive interview，並以 plan、interview、analysis 三階段加上
human collaboration。Caliburn 不必硬鎖相同時間，但第一版應把下列指標列為 release metric：

- 中位訪談時間；
- 每個 accepted task 所需回合數；
- clarification rate；
- 使用者提前停止率；
- 「被正確理解」評分；
- AI proposal accept/edit/reject rate；
- 員工直接編輯率與 AI proposal 被 direct edit 取代率；
- 最終 JD usefulness。

只看 extraction precision 而不看訪談負擔，會再次得到工程測試漂亮、產品體驗失敗的系統。

## 9. 從 Evidence 到最終欄位的操作定義

### 9.1 主要職責（Duty / OCU）

主要職責是多個相關 task 的上位目的或功能群，不是把員工的一句話直接改寫成 T1。

推薦生成流程：

1. 只聚合 current、affirmed、employee-owned/shared/assists 的 active tasks；
2. 依共同 purpose、workflow stage、stakeholder、system/domain 聚類；
3. 產生「動詞／功能 + 受詞／領域」名稱；
4. 保存 child task candidate IDs 與 evidence closure；
5. AI 可提出重分組、改名、合併、拆分 proposal，員工決定採用、修改或拒絕；
6. projector 最後才編 T1、T2…位置碼。

`CandidateKind` 目前缺 `duty`；核准本文後應新增，而不是把 duty 塞入 task 或只靠 Episode target 代替。

### 9.2 工作任務（Task）

Task statement 最小形狀：

```text
observable action + object
+ optional condition/input/purpose/output
```

接受條件：

- action 明確；
- subject/ownership 不是他人；
- time/polarity 可投影為現行工作；
- 至少閉合到 literal 或 contextual employee evidence；
- reference task 相似只能協助命名，不能證明員工有做。

Job Model 裡的 task 以受訪者當下實際工作為 truth，**不需要公版先存在**。外部 OCS/NICE/O*NET task 只能作 optional
reference/alignment，不能取代這份 JD 的 task identity。此階段不把 task 提升成公司模板，也不處理跨 JD 重用。

### 9.3 工作產出（Output）

iCAP 定義為任務最主要的過程或最終關鍵產出，並建議優先列書、文件、圖表等有形交付；純操作任務可沒有 O。

Output 可是：

- 文件／報告／清單／規格；
- 系統、程式、設定、資料集；
- 決策或核准結果；
- 可識別的服務結果或完成狀態。

禁止把每個 action 名詞化後硬當 output。「維護系統」不等於必然產出「維護報告」。若只有 action，保留 output gap
或合法空陣列。

### 9.4 行為指標（Performance / Behavior Indicator）

iCAP 將行為指標定義為評估是否成功完成任務的標準，需說明情境與應有行為／產出。推薦 canonical shape：

```text
condition/context
  + observable behavior
  + object/output
  + quality/result/standard
  + optional threshold
```

來源規則：

- condition、behavior、result 各自保存 evidence 或 approved reference/policy；
- 數值 threshold 只能來自 employee support、另行提供且獲接受的 policy，或員工直接輸入；
- reference indicator 可以作候選措辭，不可自動成為 employee fact；
- 不產生「積極負責、溝通良好」等不可觀察口號；
- 不把 ability/attitude 標籤直接當 indicator。

現有 `QuantitativeThreshold.source_type` 的 employee/policy/human 分流概念應保留，但下一個 active contract 應把
`human` 中性值明確 rename 為 `employee_direct_input`；舊值只留歷史 schema，不能暗示另有專業顧問替員工把關。

### 9.5 K（Knowledge）

iCAP 2026 手冊定義為執行任務所需理解、可應用於該領域的原則與事實。K linkage 需要：

- 明確 task candidate；
- OCS/ESCO/NICE/其他公版候選，或根據本職務 task 形成的 document-local K；
- task–knowledge relevance reason；
- 這份 JD 內的 requirement ID；有公版來源才帶 reference URI/version；
- employee decision；員工審的是「這份工作是否需要這項知識」，不是術語或 taxonomy 是否學術正確。

員工提到工具或動作不代表已證明具備所有底層理論知識。

K statement 應描述單一可理解與取回的概念，例如「告警分級與升級規則」，不是「熟悉、了解、精通」等熟練度
措辭，也不是把整個 task 改寫成名詞。流程、資料模型、設備原理、產品規則與法遵規範完全可以是這份 JD 的 K；
它們不需要先存在於公版，也不需要因此建立公司層 catalog。

### 9.6 S（Skills）

iCAP 定義為完成任務所需的認知能力或技術操作能力。推薦 S statement 描述可學習、可觀察的做法，例如：

- 撰寫需求規格；
- 設計資料交換格式；
- 執行系統故障排除；
- 分析測試結果並提出優化方案。

「使用 Excel/SAP/Python」先是 tool evidence。只有 evidence 顯示如何配置、分析、排錯、整合或達成品質標準，才形成
skill candidate；reference 可提出候選，仍需 task linkage 與 employee review。系統必須把 linkage 用白話呈現，例如
「因為你需要依告警紀錄定位同步異常，所以建議加入這項技能」。

S statement 應描述一個可觀察 action，例如「依告警紀錄定位跨系統資料同步異常」。工具、知識、態度、職稱與
抽象能力不得直接冒充 S。公版沒有這項技能時，建立這份 JD 的 custom skill candidate，而不是選一個語意較遠的
官方 skill 硬貼標籤。

### 9.7 公版沒有任務或 K/S 時的正式流程

公版不是 allow-list。NIST workforce playbook 明確承認組織同時有 common tasks 與 context-unique tasks；T/K/S
building blocks 可依情境組成工作角色。OPM 也允許依 job analysis 補充或修改 competencies。因此 no-match 不是
retrieval failure，也不要求建立企業 taxonomy；只代表這份 JD 要使用 custom requirement。

```text
confirmed job-local task
  -> optionally retrieve bounded public references
  -> coverage decision: usable | partial | no_match | ambiguous
  -> usable: adapt reference wording only where it truly fits
  -> partial: keep supported part + draft the missing job-local K/S
  -> no_match: draft document-local K/S from task/output/indicator/context
  -> K/S authoring-rule + evidence/support + duplicate-within-document gates
  -> employee plain-language review
  -> save in this CurrentJobDocument and link to its task
```

禁止的捷徑：

- nearest vector 一定要選一筆；
- 把自訂 wording 覆蓋到官方 URI；
- AI 自創 `icap_ref`、ESCO URI 或官方 code；
- 把「這個職務需要某技能」誤寫成「受訪員工已具備某技能」。

這份 JD 內的最小 Knowledge／Skill 與 linkage：

```text
JobKnowledgeRequirement
  knowledge_id                 # application UUID；只在本 JobModel 中穩定
  statement
  support_refs[]
  public_alignment | null       # source URI/version + usable/partial；沒有也合法
  status: proposed | accepted | edited | rejected

JobSkillRequirement
  skill_id                     # application UUID；只在本 JobModel 中穩定
  statement
  support_refs[]
  public_alignment | null
  status: proposed | accepted | edited | rejected

TaskKnowledgeLink
  task_id                      # 真正的 application UUID，不是 T1/T2
  knowledge_id
  relevance_reason
  support_refs[]

TaskSkillLink
  task_id                      # 真正的 application UUID，不是 T1/T2
  skill_id
  relevance_reason
  support_refs[]
```

這是 domain contract，不是資料庫 DDL。資料庫不得把 `linked_task_ids` 存成 `T1/T2` 字串或 UUID array；K 與 S
各自成為不同 entity/table，task linkage 以帶外鍵的兩張 association table 保存。`T1/K01/S01` 只由 projector
在顯示或匯出時依排序產生。只做同一份 JD 內的重複檢查與 task linkage，不做跨 JD alias、全公司 concept
identity、發布或 deprecation lifecycle。詳細關聯式設計見
[Job Authoring v2 關聯式儲存研究](2026-07-24-job-authoring-v2-relational-storage-research.md)。

後兩者是不同 domain：

```text
JobRequirement: 這個 task 要求哪些 K/S
PersonCapabilityAssessment: 某個人目前具備到什麼程度
```

本產品目前先做 JobRequirement。除非另有 assessment evidence、rubric 與授權，不從工作訪談順便建立個人能力評分。

### 9.8 Ability、Attitude、Level

- Ability 應由跨 episode pattern 或員工明確確認產生，不由單輪工具使用推斷；
- Attitude 高度容易受語氣偏誤影響，第一版不主動由訪談語氣推斷；若要交付，應由跨情境可觀察行為形成 proposal 並由員工確認；
- competency level 不由模型憑措辭直接猜，可取 approved reference level、rubric rating 或 employee decision；
- 全部都是後續 consolidation/review，不是 R5 literal extraction 的責任。

## 10. Context Engine 應如何供應每一步

### 10.1 R5 turn packet

只給：

- persisted QuestionFrame；
- preceding consultant turn；
- current employee turn；
- active episode identity；
- selected gap；
- correction candidates；
- 少量 recent active evidence／contradiction。

R5 不讀 OCS reference，也不讀完整 JD，避免 reference laundering 與 editor shape 污染。若上一題是在確認一個文件
proposal，所需 target、base revision 與 proposition 必須已封裝在 QuestionFrame；R5 只做 answer grounding。

### 10.2 Question Policy packet

Question Policy 可讀：

- active episode／gap priority；
- active QuestionFrame 與最近必要的 employee support；
- `JobStateDigest`：目前 document、已接受的 duty/task/output/indicator/K/S 摘要、Task 的
  purpose/frequency/ownership/importance/typicality、未解 critical gaps、pending/stale proposal 計數與明確
  correction target；
- interview budget、fatigue／decline state。

`JobStateDigest` 是 canonical authoring state 的 bounded projection，不是完整 editor JSON。員工直接新增一個 task 後，
digest 會讓 Question Policy 停止再問「你還有哪些工作」，改問該 task 最有價值的缺口；這是共編與訪談真正同步的
地方。

最小 contract：

```text
JobStateDigest.v1
  session_id / document_id
  selected_items[]:
    entity_id
    kind: duty | task | output | indicator | knowledge | skill
    parent_entity_id | null
    statement
    task_analysis | null:
      purpose_text | null
      frequency_value / frequency_unit / frequency_text | null
      ownership / importance / typicality | null
      time_share_percent | null
  unresolved_gaps[]:
    gap_id / target_entity_id / dimension / severity
  pending_proposal_targets[]       # ID/kind/target only，不把 proposed value 當 truth
  stale_proposal_targets[]
  omitted_counts_by_kind
  selection_policy_name/version/hash
  digest_hash
```

ContextBuilder 依 operation 選最小項目並保存 selection manifest；`omitted_counts_by_kind` 讓模型知道 digest 被裁切，不能
把「沒看到」推論成「不存在」。同一 canonical state + policy 必須產 byte-identical digest。

### 10.3 Episode Coder packet

只給：

- 該 episode 全部 active employee evidence；
- contextual support bundles；
- contradictions／corrections；
- 現有 episode candidates；
- 必要且已 snapshot 的 reference snippets。

### 10.4 K/S drafting operation packet

依 operation 最小化：

- confirmed current task、outputs、indicators 與直接支持 evidence；
- 必要的工作情境／policy artifact；
- bounded public-reference candidates（若本次有查）；
- immutable retrieval snapshot；
- K/S authoring rules 與本文件已存在 requirements（只為 document-local dedup）。

不給完整 transcript、不給未選中的整個 taxonomy。第一版以一次 `requirements.draft` call 同時輸出 coverage 與 K/S
typed 區塊；只有 eval 證明分開能顯著改善品質或失敗歸因，才拆成兩個 operation。

### 10.5 Global consolidation packet

只給 candidate/inference/evidence closure，不重送完整 transcript；需要驗證時可按 evidence ID 回取原 quote。

### 10.6 長對話

conversation transcript 是 audit source，不是 working memory。工作記憶使用 persisted state：

- active QuestionFrame；
- Episode；
- Gap；
- Evidence；
- Inference；
- CandidateJobItem；
- JobRequirementItem；
- DocumentRevision／AI Proposal／EmployeeDecision 的 bounded digest。

provider conversation ID、server-side compaction 或 prompt cache 只能是 adapter optimization，不能取代 app-owned state。

## 11. 公版 retrieval 與 document-local K/S

### 11.1 公版的角色

公版只負責：

- 提醒可能漏掉的 task/output/indicator/K/S；
- 提供較專業、標準化的候選措辭；
- 提供 source URI/version，讓員工能展開查看「AI 為何建議」；
- 協助比較這份 JD 與職能基準的覆蓋程度。

公版不能限制實際工作，也不能證明員工有做某 task 或具備某能力。客戶是不是公司不影響這條規則。

### 11.2 最小 K/S model

本階段不建立 CapabilityConcept、namespace、alias graph 或跨 JD catalog。`CurrentJobDocument` 分別保存
`JobKnowledgeRequirement[]`、`JobSkillRequirement[]`、`TaskKnowledgeLink[]` 與 `TaskSkillLink[]`。Knowledge 與
Skill 各有自己的 application UUID；link 使用真正 `task_id`，並保存 relevance reason／support。

`linked_task_ids` 若出現在 API 讀模型，只能是由 association links 聚合出的 UUID tuple，不能保存成資料庫 array，更
不能使用 `T1/T2` publication code。

同一份 JD 內可以把一個 K/S 連到多個 task，也可以按輸出格式展開成每個 competency block；是否跨任務共用只是一份
文件內的 normalization，不形成企業資產。

### 11.3 Coverage 與 drafting

對 confirmed task：

1. 可選擇查 selected public sources；
2. LLM 在 bounded candidates 上判 `usable/partial/no_match/ambiguous`；
3. deterministic gate 驗證候選 ID、版本與 snapshot closure；
4. usable：可引用或改寫，但保留來源與適用理由；
5. partial/no-match：依 task、output、indicator、tools/context 起草 document-local K/S；
6. verifier 檢查 K/S 定義、單一性、可觀察性、tool/trait 混淆與 evidence/support closure；
7. 員工以白話 accept/edit/reject；
8. 寫入本 CurrentJobDocument，不發布到其他職務。

LLM 可以利用通用專業知識提出 K/S 候選，但此時 `support_basis=task_inference`，不是 employee fact、company fact 或
official reference；必須讓員工看得出來並審核。LLM 不得產 official code。

### 11.4 Retrieval index 不是 source of truth

公版來源的原始結構化資料與版本是 authority；向量 index 只是可重建搜尋 projection。搜尋結果必須帶 source identity、
版本與 task bundle，再形成 immutable `ReferenceSnapshot`，不能直接把向量 payload 投影進 JD。

### 11.5 現有 Qdrant／BGE-M3 的處置

現有 BGE-M3 dense+sparse + Qdrant RRF 是可用 baseline，但不是永久結論：

- 保留 `ReferenceSearchPort`，Qdrant 只是 adapter；
- 不讓 interview/job domain import indexer DTO；
- 只 index 公版 reference corpus，不 index 使用者的 JD 或建立公司 skills catalog；
- selected source/version/chunk type 先 filter；
- top-k、reranker、embedding text 與 engine 都由 retrieval eval 決定。

若現有方案在繁中 recall、latency、維運成本勝出就保留；否則可替換。這項決策不影響 Job Model。

### 11.6 Contextual indexing experiment

可比較：

```text
baseline: task/K/S 原始文字

contextual:
  occupation + duty + task
  output/indicator
  K/S item
```

context 只用於 indexing，不改寫公版 payload。只有 blind retrieval eval 顯著勝出才 promote。

### 11.7 Quality gates

- public candidate relevance precision/recall；
- usable/partial/no-match confusion matrix；
- K/S classification accuracy；
- tool-to-skill 與 task-to-knowledge false upgrade；
- unsupported K/S rate；
- task-link precision/recall；
- wrong-source/wrong-version contamination（critical = 0）；
- employee accept/edit/reject rate與平均 review 時間。

## 12. Canonical authoring core 與 delivery surfaces

### 12.1 共編是產品骨架，不是訪談完成後的附加功能

OpenAI Canvas、Anthropic Artifacts、Gemini in Docs 與 Microsoft Copilot in Word 的官方產品都採相近模式：對話或
指令與可編輯畫布並存；AI 對指定範圍提出修改；使用者可以直接編輯、接受／取代／拒絕，並可回看版本。這不是要
複製任何一家 UI，而是確認目前成熟的人機共編邊界：**人可以直接寫，AI 必須留下可審查的變更。**

桌面第一版建議雙欄：左側 AI 顧問對話，右側 live JD canvas；行動裝置可切成「訪談／文件」兩個頁籤，但必須共享
同一個 session 與 current document。員工可在任何時點切到文件修改，不需要等 AI 宣告一個 episode 結束。

### 12.2 三種寫入 authority

| Writer | 寫入語意 | 是否再審 | 可否改 accepted truth |
|---|---|---:|---:|
| Employee direct edit | 員工明確要文件呈現的內容 | 否，欄位 commit 後立即成 current truth | 可以，更新 current rows |
| AI operation | 專業顧問建議的新增／修改／刪除／link | 必須；只能建立 pending proposal | 不可直接改 |
| Deterministic projector | 編號、排序、schema normalization、匯出格式 | 不作語意審查 | 不可創造或改寫語意 |

「員工直接編輯」與「員工修改 AI 建議後採用」都算 employee-authored final value。AI 後續可以再提出 proposal，但不能
因為重新跑模型就覆蓋。`accepted` 不是永遠鎖死；它代表只有員工命令或另一筆經員工決定的 proposal 才能改。

### 12.3 現有深文件適合 exchange，不足以直接作產品核心

目前 `ocs_doc` 與 `packages/ocs-contract` 對公版匯入／匯出很實用，但 active `CodeName` 主要只有 code/name，
`CompetencyBlock` 內重複 K/S 陣列；`_pending` 又把 review UI metadata 嵌在待輸出的文件樹。這造成：

- K/S requirement identity 與顯示位置 code 混合；
- 同一份 JD 內的 K/S 與 task linkage 難以清楚表示；
- task–K/S linkage 沒有獨立 status/rationale/provenance；
- proposal、accepted truth 與 export shape 耦合；
- final strip metadata 後，不能只靠文件重建完整 review/audit history。

因此 OCS JSON 應降為 publication/export contract，不再預設為 greenfield authoring source of truth。

### 12.4 Canonical Job Model

推薦 authoring domain：

```text
CurrentJobDocument
Duty
Task
Output
BehaviorIndicator
JobRequirementItem（K/S；document-local）
RequirementLevel
AiDocumentProposal
JobStateDigest
PublicationView
```

所有 domain entity 使用 application identity；T1/T1.1/O01/P01/K01/S01 是 deterministic publication position code，
不是永久 ID。第一個成品只保存每份文件的 current relational state；公版 JSON／PDF／XLSX 是 export projection，
不是另一份可寫真相。第一版只有一名本機操作者，不加入 tenant、多人權限、comment thread、presence、CRDT 或
revision history。

### 12.5 最小 command/proposal contracts

`EmployeeDocumentEdit.v2`：

```text
document_id
operation: add | revise | remove | move | link | unlink
target_entity_id | parent_entity_id
target_field | null
base_value | null              # revise/remove 時避免覆蓋較新的人工內容
employee_value | null
```

`AiDocumentProposal.v2`：

```text
proposal_id                    # application 派生，不由模型產生
document_id
operation: add | revise | remove | move | link | unlink | merge | split
target_entity_id | parent_entity_id
target_field | null
before_value | null
proposed_value | null
plain_language_reason          # 可顯示依據，不保存 hidden chain-of-thought
status: pending | accepted | edited | rejected | stale
```

`EmployeeProposalDecision.v2`：

```text
proposal_id
action: accept | edit | reject
final_value | null             # edit 必填；accept 必須等於 proposed value
decided_at
```

第一版應限制一筆 proposal 只改一個可理解的 entity／field 或一組不可分割 link；不要讓模型用單筆 proposal 重寫整份
JD。若員工要求「重寫整份」，系統要產 section-level proposal group，仍讓員工逐組決定，不得以 whole-document
overwrite 失去控制。

### 12.6 Apply 與 conflict protocol

Employee direct edit：

1. UI 先保留本地輸入；欄位 commit／debounce 後送 command，不在每個 key stroke 觸發 AI；
2. application 驗證 document／target identity、schema、same-document FK 與 domain invariants；
3. 同一 transaction 更新 current rows；
4. pending AI proposal 的 `before_value` 若已不等於 current target，就標成 `stale`，不自動套用；
5. 重新投影 `JobStateDigest`，讓 gap/question policy 在下一 operation 看見更新。

AI proposal decision：

1. proposal 必須仍為 pending，target scope 完整；
2. edit/delete 比對 proposal `before_value` 與 current target；
3. 不相關的其他編輯不必阻擋；target 有變則回 typed stale conflict；
4. accept 使用 proposed value；edit 使用 employee final value；reject 不改文件；
5. accept/edit 在同一 transaction 更新 current rows + proposal decision；
6. reject 建 suppression fact，除非出現新 evidence、target 已重大變更或員工主動要求，AI 不得立刻重提同義內容。

新核心以 entity/field edit 表達修改，不把整份深 JSON 最後寫入者勝出。第一版是單一本機操作者，不建立 generic
revision CAS、多人合併或 Google Docs 等級的同步機制。

### 12.7 Context 與 provenance 規則

- R5 只處理聊天 turn；文件 command 不經過 Turn Interpreter。
- 員工 direct edit 足以成為該文件欄位的 accepted content。
- direct edit 不是 transcript quote；若 AI 要從它推導 K/S、indicator 或另一個 task，必須建立新 proposal。
- AI proposal 的 `plain_language_reason` 只說可驗證依據，例如「你提到每週彙整缺貨明細」，不顯示或保存模型思考鏈。
- 公版內容只保存既有 Indexer stable ID `ref_urn`；AI 自行依 task 推導的 custom item 不得偽裝成公版。
- AI 每次 operation 讀 latest accepted `JobStateDigest`；pending proposal 不是 accepted truth，必要時只以 pending 摘要防止重複提案。

2026-07-24 第一個本機成品範圍已進一步收斂：上述來源區分仍可供 LLM operation／verifier 在當次執行使用，但
Job Authoring entity rows 暫不持久化逐欄 writer、editor、Evidence refs、source hash 或完整 provenance。既有 Proposal／
Decision／Revision command 足以維持 AI 不得直接寫入與版本歷史；公版只保存既有 Indexer stable ID
`ref_urn TEXT NULL`。日後有稽核或可解釋性產品需求再升版，不先建立 generic source graph。資料庫 authority 見
[Job Authoring v2 關聯式儲存研究](2026-07-24-job-authoring-v2-relational-storage-research.md)。

### 12.8 API 與模組邊界

一人團隊推薦 **modular monolith + background workers**，不要為每個 operation 拆微服務：

```text
Interview module       session/turn/question frame/Evidence(literal|contextual support)/gap
Job Authoring module   duty/task/output/indicator/K/S/revision/command/proposal/decision/publication
Reference module       public sources/import/snapshots/search port
LLM Runtime module     operations/provider port/executor/conformance
Evaluation module      capture/replay/eval（不被 production import）

Workers
  public-reference ingest/index/export/long-running eval
```

外部 API 按 use case 暴露 commands/queries，不直接把資料表或完整深 JSON 當 CRUD：

- append interview turn；
- get conversation state／agenda／current QuestionFrame；
- issue employee document command；
- list/get/decide AI proposal；
- get revision/diff/provenance／JobStateDigest；
- suggest finish、finish、publish/export；
- search selected public references。

### 12.9 Editor 保留或重做的 decision gate

現有 editor 值得保留的能力：task/duty/O/P/K/S pool、來源保留、任務改名不丟 source、`選同主要職責／工作任務`、
相似任務提示、直接 inline edit、autosave、optimistic conflict 與 deterministic renumber/export。這些是產品資產，不等於
必須保留現在的深文件資料模型。

需要重做或至少改造的部分：

- `_pending` 不再是唯一 proposal store；
- hover 才出現 ✓／✗ 對非專業員工不夠明顯，也不利鍵盤／行動裝置操作；
- 全文件 PATCH 不得覆蓋 entity-level revision/conflict；
- 全域「接受全部」第一版不預設開放；若之後要做，只能按同一 episode/section 分組、顯示摘要，並以 pilot 證明不造成
  approval fatigue；
- UI 不能要求員工理解 OCU、O/P/K/S linkage、taxonomy alignment 才能完成審核。

vertical slice 必須讓一名非職務分析專業的員工完成：訪談產 3–5 tasks、直接改一項、接受一項、修改後採用一項、
拒絕一項、處理一筆 stale conflict、接受一項 no-match custom K/S，最後匯出。若現有 editor 可用薄 adapter 無損做到，
就先沿用；若必須持續把新 core 壓回 `_pending` 深樹 hack，就建立新 workspace。

### 12.10 員工可理解的 UI 語言

內部 contract 可用 `accept/edit/reject`，畫面建議用：

- **符合我的工作**；
- **修改後採用**；
- **不符合**；
- **為什麼建議這項？**；
- **這項工作還缺什麼？**。

每筆 AI 變更常駐顯示 target、before/after、影響範圍與三個決定；來源與詳細限制可展開，不要一次塞滿。員工審的是
工作事實與是否適合這份文件；系統負責專業寫法、K/S 類型、linkage、來源 closure 與格式驗證。

### 12.11 完成與匯出

員工可以隨時按「準備完成」。AI 也可以建議結束，但不能自行發布。`CompletionAssessment` 至少檢查：

- 是否有足夠的 current tasks 與主要職責 coverage；
- 重要 task 是否至少有可理解的 action/object，並有 output 或成功標準的合理資訊；
- critical contradiction／critical gap 是否仍未解；
- 是否仍有會改變核心內容的 pending/stale proposals；
- K/S 是否有 task linkage，且 custom/public 來源標示正確；
- schema/domain invariants 與 export projection 是否通過；
- interview budget／fatigue 是否已達上限。

最後畫面用白話列「已完成、建議再補、仍有衝突」，讓員工選擇繼續訪談或照目前版本完成。內部 canonical model 不採
政府表格 shape；政府公版格式、簡化 JD、PDF/XLSX 都是 deterministic export profile，可在完成時選擇。

## 13. LLM operations，而不是多 Agent 角色

第一版建議 operations：

| Operation | 職責 | 可讀來源 | 不可做 |
|---|---|---|---|
| `turn.interpret/2.x` | dialogue act、literal observation、answer binding | turn packet | 查 OCS、寫 JD、選下一題 |
| `episode.code/1.x` | task/output/indicator hypothesis、gaps | episode evidence + bounded reference | 直接 mutation |
| `question.select/1.x` | 選 gap、產 response text + QuestionFrame | agenda state | 產 employee facts |
| `job.consolidate/1.x` | duty grouping、跨 episode dedupe/conflict | candidates + evidence closure | 補不存在的 facts |
| `requirements.draft/1.x` | 判公版 usable/partial/no-match，並提出本 JD 的 K/S + task links + support basis | confirmed job model + optional snapshot | 強迫 nearest match、發布官方 code、證明個人能力 |
| `job.compose/1.x` | 工作摘要／招募 JD wording | accepted candidates | 變更 canonical truth |

同一 provider/model 可以實作全部 operation；operation separation 是為了 schema、context、eval 與 failure attribution，
不是要求多個 autonomous agents。先以同一 provider 與獨立 schema/eval 實作；只有 profile 證明 latency/cost/quality
需要，才讓某個 operation 使用不同模型。

## 14. R5 應如何改版

### 14.1 保留

- provider-neutral Structured Output；
- application ordinal identity；
- literal quote/span verification；
- qualifier support；
- correction、duplicate all-drop、injection boundary；
- schema gate 與 semantic gate 分離；
- one provider call；
- no semantic auto-repair；
- Capture/eval/replay。

### 14.2 修正

1. `TurnInterpretInput` 加 persisted QuestionFrame，而不是只有 preceding question text；
2. output 加 dialogue act 與 `answer_bindings`；
3. literal observation 與 contextual binding 分開驗證；
4. `Evidence.v3` 以 `literal_employee_span | contextual_answer` 分型 support 保留兩種證明強度；不要把「是」偽裝成
   能逐字支持整個問題；
5. frequency marker 不直接證明 current time scope；
6. 「unknown qualifier 是否值得追問」移到 Gap/Question Policy；
7. 加短回答、stale frame、leading question、mixed answer eval；
8. `CandidateKind` 後續加 duty，不能等 projection 時臨時猜分組；
9. 後續 Job Model仍以 evidence ID閉合，consumer依 support kind分流；employee document edit是 Authoring Core 的獨立來源，
   不在 R5 偽裝成 Evidence。

Revision 4 的 separate type 能清楚表達證明強度，但 code audit 發現它會迫使所有現有 evidence consumers立即升級成
polymorphic SupportRef。Revision 5 的決定是讓 Evidence identity/lifecycle共用、support type分開：

```text
Evidence.v3
  common identity / claim / qualifiers / status / supersession
  support =
    literal_employee_span(employee turn + exact quote/span)
    | contextual_answer(question frame/target hash + employee answer quote/span + binding)
```

例如 AI 問「這項工作是每週進行嗎？」、員工答「是」，`是`只能證明員工接受該 frame proposition；它不是「每週」
的 literal quote。分型後，grader、UI 與最終 provenance 都能誠實區分；Episode/Gap/Inference/Candidate 仍只保存
`evidence_id`，由 application 驗證被指物件存在、active、same-session 與 closure；LLM 不產這些 ID。

### 14.3 R5 與共編的硬邊界

R5 必須知道：

- 這一輪是哪個 employee turn；
- 前一個 AI 問題與 application-validated QuestionFrame；
- frame 要確認的 proposition／slot／choice；
- active episode、必要的 correction candidates 與少量 recent support。

R5 不得知道：

- editor component、深 JSON path 或 React state；
- 完整 `CurrentJobDocument`；
- pending proposal 全文；
- OCS／向量檢索結果；
- 下一題或是否完成訪談。

若員工在文件區直接修改，Authoring Core 自行處理並更新 `JobStateDigest`。Question Policy 下一輪使用 digest；R5 不解析
該 document command。如此未來換 editor、API 或 export 都不需要重寫 R5。

### 14.4 R5 開工前必須凍結的 contract

以下四項已由 ADR 0037／R5 amendment 核准，R5 **Go**：

1. `QuestionFrame.v1` exact schema、hash、active/consumed/stale lifecycle 與 next-employee-turn scope；
2. `TurnInterpretOutput.v2` 的 `dialogue_act + literal_observations + answer_bindings` exact schema；
3. `Evidence.v3` contextual support、binding verifier、correction/supersession 與 Capture closure；
4. marker policy 修正為 frequency 與 time scope 分開，並增加「以前每週」等組合反例。

同時只凍結一個 authoring seam：Question Policy 可讀 bounded `JobStateDigest`，R5 不讀。以下項目**不阻塞 R5**：

- 舊 editor 或新 workspace 的選型；
- `AiDocumentProposal` 的最終資料表／API route；
- K/S drafting prompt 與 retrieval engine；
- 政府 OCS export 版面；
- SaaS、tenant、多使用者協作。

### 14.5 建議實作切片

若 owner 核准，不建議把所有變更塞進一個巨大 R5 commit。推薦：

1. **R5-A inactive contracts**：QuestionFrame、AnswerBinding、Evidence v3 support、receipt schema 與 pure validators；
2. **R5-B domain/state hard cut**：Evidence/State v3、question/employee/interpretation commands、reducers、persistence explicit reject；
3. **R5-C interpreter hard cut**：Context/Input/Output/Prompt/Verifier/Executor與minimum eval/provider schema migration；
4. **R5-D correctness closure**：frequency、mixed、stale CAS、recovery、Capture、bundle corruption；
5. **R5-E docs/status**：hash/catalog/README/mother plan；
6. **R6a grounding eval**：短回答專用 suite；
7. **R6b existing 12 cases migration**；
8. **post-R5 product vertical slice（編號待 mother plan 重排）**：canonical Job/Authoring contracts + employee direct edit +
   one AI proposal accept/edit/reject；不要把共編延到所有 K/S 完成後；
9. **後續 eval**：episode/job、no-match K/S、linkage、retrieval 與 authoring vertical slice。

每個 commit 必須保持完整 no-network suite 綠；若 active hard cut 無法拆綠，R5-B～R5-D 合併成一個原子 commit，禁止
相容 shim 同時支援兩個 active contract。

R5 的完成定義仍只到「自然且可信地理解一輪並形成 literal 或 contextual Evidence」。不得在 R5 順手修改
editor、深文件契約或 indexer。R5 已依 D1–D4 與 D15 寫成 active authority；Job/Authoring core 再依 D5–D14 寫獨立 implementation
authority。這是控制架構風險，
不是承諾沿用舊元件。

## 15. Eval design

### 15.1 Turn grounding suite

最低案例：

1. standalone long answer；
2. atomic yes；
3. atomic no；
4. frequency slot「每週」；
5. recipient slot「主管」；
6. single choice；
7. multi-select allowed／forbidden；
8. ambiguous numeric answer；
9. stale question frame；
10. frame/text hash mismatch；
11. composite leading question；
12. mixed「是，但…」；
13. correction「不是每週，是每天」；
14. pronoun/ellipsis；
15. stop/decline/dont-know；
16. prompt injection。

Hard metrics：

- binding precision；
- binding recall；
- false affirmation rate（critical，目標 0）；
- stale-frame acceptance rate（critical，目標 0）；
- unsupported qualifier rate；
- provenance closure rate；
- deterministic regrade byte equality。

### 15.2 Episode/job-field suite

每份 gold 要分開評：

- duty grouping；
- task precision/recall；
- output precision/recall；
- indicator condition/behavior/result completeness；
- unsupported threshold count；
- K linkage precision/recall；
- S linkage precision/recall；
- tool-to-skill false upgrade；
- reference laundering；
- final field evidence coverage。

不得把所有分數平均成一個漂亮總分後掩蓋 critical failure。

### 15.3 Retrieval suite

- query-to-task recall@5/10/20；
- MRR/nDCG；
- public candidate relevance ranking；
- usable/partial/no-match confusion matrix；
- wrong-version/foreign-source contamination；
- task bundle與 reference snapshot closure；
- baseline vs contextual projection blind comparison；
- latency/cost。

### 15.4 Employee pilot

至少分開記錄：

- employee：「AI 有沒有理解我的工作」；
- employee coediting：direct edit、accept/edit/reject、stale conflict 成功率與完成時間；
- employee comprehension：是否看得懂 AI 為何建議、是否知道接受後會改哪裡；
- final document：盲評 usefulness、specificity、completeness、unsupported claim；
- interaction：時間、回合數、疲勞、提前終止。

產品流程不依賴另一位顧問；但研發 eval 可以請獨立職務分析專家對去識別化結果做 blind quality audit。那是模型／產品
驗證，不是每份 JD 的必要審批者。

### 15.5 Authoring deterministic and UX gates

- AI 未經 decision 直接改 accepted truth：0；
- employee command idempotency／revision replay：100%；
- overlapping stale proposal 被自動套用：0；
- reject 後無新 support 立即重提率：0；
- direct edit 後下一題仍重問已填內容的比例；
- source channel／support closure 完整率：100%；
- 非專業員工在不看教學下完成 accept/edit/reject 的 task success；
- 全域／批次接受造成的錯誤接受率；第一版未有證據前不開全域 accept-all。

OpenAI 官方 meeting-intelligence 指引也建議以 human-reviewed transcript labels、holdout、exact/near-exact evidence
checks、precision/recall 及 reviewer override 持續評估。OpenAI hosted Evals platform 已公告 2026-11 關閉，因此
Caliburn 應繼續使用自己的 versioned harness/Capture，不依賴即將退役的平台。

## 16. 一人團隊的最低可行最強版

第一個可測產品不要一次完成所有 taxonomy 與所有投影，也不要等分析引擎全部完成才接 UI。建議以可垂直驗證的順序：

### Stage A：自然且可信地聽懂

- QuestionFrame；
- short-answer grounding；
- literal／contextual-support Evidence；
- correction；
- current 12 cases + grounding suite。

### Stage B：先打通最小共編垂直切片

- canonical draft revision 與 entity identity；
- employee direct edit；
- 一筆 AI task proposal 的 accept/edit/reject；
- stale/conflict 與 `JobStateDigest`；
- 雙欄或雙頁籤 prototype；
- 非專業員工 usability test。

Stage B 不需要先有完整 K/S。它用 scripted proposal 也可以驗證人機權限、版本與產品 loop，避免做到最後才發現
conversation 與 document 無法同步。

### Stage C：形成任務與產出

- Episode Coder；
- task/output candidates；
- gap priority；
- 將 candidates 轉成 AI document proposals；
- bounded reference task retrieval。

到這裡已有第一個可用測試品：員工可對話、看見 tasks/output 逐步形成、直接改、審 AI 修改，並繼續被追問。

### Stage D：形成指標與 K/S

- behavior indicator component support；
- optional public K/S coverage；
- no-match document-local K/S drafting；
- task–K/S linkage employee review；
- document-local dedup 與 retrieval eval。

### Stage E：完成與最終文件

- deterministic publication projector；
- final completion assessment；
- employee decision/audit closure；
- 新 workspace 或既有 editor thin adapter 的最終保留裁決；
- final OCS/JD outcome eval。

### Stage F：模型與成本優化

- 用同一 eval 比較 OpenRouter models/endpoints；
- 只有 failure trace 證明需要才拆第二 call／reranker／更大模型；
- 不先做 fine-tuning；
- 不先做 session vector memory；
- 不先做 multi-agent。

## 17. 明確不採用

- 單一 mega prompt 同時訪談、記憶、抽取、推論 K/S、寫 JD、自評；
- 每輪把完整 transcript + 全部 OCS chunk 丟入模型；
- 把 structured output schema success 當內容正確；
- 把 reference text 當 employee evidence；
- 把公版當 allow-list，找不到就強迫 nearest match；
- 把 custom K/S 存成沒有 support basis、task linkage、review status 的自由文字；
- 把職務需要某 K/S 當成受訪者已具備該能力；
- 把 API、indexer、authoring 各拆成獨立微服務增加一人團隊維運面；
- 從工具名直接推 skill；
- 從一句自評直接推 ability/attitude；
- 為了讓短回答通過而關閉 quote/provenance gate；
- 讓模型生成 DB IDs、OCS 最終位置碼或文件 mutation；
- 讓 AI 直接覆蓋 accepted document content，再要求員工事後找差異；
- 把員工直接編輯送進 R5 偽裝成 transcript evidence；
- 要求非專業員工理解 OCU/O/P/K/S taxonomy 才能接受或拒絕；
- 第一版先做 tenant、多人共編、權限矩陣、CRDT 或公司 capability catalog；
- 為追求「最潮」預先加入 graph framework、多 Agent、fine-tuning；
- 依賴將於 2026-11 關閉的 OpenAI hosted Evals platform。

## 18. 需要 owner 討論／核准的裁決

### D1 — contextual evidence contract

**Revision 5 已核准：`Evidence.v3` 使用 `literal_employee_span | contextual_answer` discriminated support。**

兩種證明強度仍是不同 type；共同的是 Evidence identity/lifecycle，讓既有 graph不用立刻改成多種頂層 support ID。完整欄位與
consumer規則以 ADR 0037／R5 amendment為準。平行 ContextualAssertion是被否決的 R4 proposal，不可再實作。

### D2 — R5 output

**推薦：同一 provider call 輸出 literal observations + answer bindings。**

不增加第二次 LLM call；兩條路徑由不同 deterministic verifier 處理。

### D3 — Question Policy ownership

**推薦：Question Policy 必須產生並持久化 QuestionFrame。**

只有自然語言 response text 不足以安全解析短回答。

### D4 — frequency/time

**推薦：每天／每週／每月只證明 frequency，不單獨證明 current。**

「以前每週」不可同時觸發 past 與 current。

### D5 — duty domain

**推薦：CandidateKind 增加 `duty`。**

主要職責是正式產品欄位，不應等到 projector 才用字串臨時分組。

### D6 — K/S authority

**推薦：K/S 是這份 JD 的 document-local requirement；可參考公版，也可由 task inference 形成 custom item。**

AI 根據已確認 task、output、indicator 與 optional public reference 起草；員工用白話接受、修改或拒絕「這份工作是否
需要這項 K/S」。系統以 definition/linkage/provenance gate 承擔專業品質，不能要求員工扮演 taxonomy 專家，也不能
因為 requirement 被接受就宣稱員工本人已具備。

### D7 — editor strategy

**修訂推薦：先建與 UI 無關的 canonical authoring core；舊 editor 只作 vertical-slice adapter candidate。**

舊 UI 若能以薄 adapter 無損處理 task/K/S linkage、proposal/revision/provenance 就保留；若需大量深文件 hack，
就建立新的 authoring workspace。不得先以沉沒成本裁決。

### D8 — K/S identity

**推薦：`JobRequirementItem` 使用這份 JobModel 內的 application ID；K01/S01 只是輸出位置碼。**

public source URI/version 是 optional alignment。沒有公版來源也合法；不建立跨 JD identity 或 catalog。

### D9 — public task/K/S no-match

**推薦：`no_match` 是一級正常 outcome，允許建立 document-local custom K/S。**

custom K/S 必經 authoring rule、support/linkage gate 與人審；LLM 不得創造官方 code。公版沒有的 task 直接保留為
這份 JD 的 truth，不提升成公司模板。

### D10 — reference index ownership

**推薦：公版結構化來源／版本是 authority，retrieval index 是可重建 adapter。**

Qdrant/BGE-M3 保留為 benchmark adapter，不是 Job Model authority；是否延用由繁中 retrieval quality、latency 與
一人維運成本決定。

### D11 — deployment topology

**推薦：先做 modular monolith + 必要 background workers，不先拆 editor/indexer 微服務。**

port 與 module boundary 先固定；只有獨立 scaling、failure isolation 或 deployment ownership 有實測需求才拆服務。

### D12 — product user and write authority

**推薦：唯一人工決策者是員工；AI 是顧問，不是文件 authority。**

員工 direct edit 立即成為 draft truth；AI 任何語意新增／修改／刪除都先形成 proposal。內部
accept/edit/reject 對外使用「符合我的工作／修改後採用／不符合」。

### D13 — live coediting timing

**推薦：共編 seam 在 R5 後第一個 product vertical slice 就實作，不延後到完整 K/S 之後。**

R5 不 import editor contract，只由 Question Policy 使用 `JobStateDigest`。這既防止 R5 被 UI 綁死，也能及早驗證真正
成品的 conversation-document loop。

### D14 — first-product scope

**已裁決：先做單一員工、單一 session／JobModel、單一 active draft 的本機 Web 應用程式。**

不先做 SaaS、tenant、多人權限、即時多人游標、CRDT、公司層共用 K/S 或版本歷史。核心 entity/proposal ID 與 module port
仍保持乾淨，未來需要時可擴充，不以當下未需求的基礎設施拖延成品。員工可由啟動流程進入 localhost Web UI，但不經
遠端網址、註冊、登入或帳密流程，也不自行設定 host／port；不要求原生桌面殼。

### D15 — R5 go/no-go

**已裁決：原 mother plan R5 No-Go；ADR 0037／R5 amendment 版本 Go。**

不需要等 editor 選型、K/S prompt、retrieval benchmark 或 export。新 authority 已固定短回答證明模型、QuestionFrame
lifecycle、Evidence/State v3、state CAS 與 frequency/current 語意。

### D16 — ADR 0030 compatibility

**推薦：保留「一條 conversation owner、AI 不可靜默修改、人可接受／拒絕」，以新 ADR supersede `_pending` 為
canonical proposal store 與「人改不告知模型」兩項。**

新核心以 current Job entity、proposal 與 employee decision 為 authority；舊 editor `_pending` 最多是 UI projection。員工 direct edit
透過 bounded `JobStateDigest` 進下一輪 Context Engine，而不是把完整文件或每個 keystroke 送給模型。

## 19. Sources

### 19.1 LLM architecture / conversation / evaluation

- OpenAI, [Structured model outputs](https://developers.openai.com/api/docs/guides/structured-outputs) — schema adherence、nullable/empty handling 與 schema 不等於 semantic truth。
- OpenAI, [Conversation state](https://developers.openai.com/api/docs/guides/conversation-state) — multi-turn state 與 context window management。
- OpenAI, [Evaluation best practices](https://developers.openai.com/api/docs/guides/evaluation-best-practices) — task-specific eval、production distribution、human calibration、continuous evaluation；頁面亦公告 hosted Evals platform 2026-11 關閉。
- OpenAI, [Optimizing LLM accuracy](https://developers.openai.com/api/docs/guides/optimizing-llm-accuracy) — 先建立 task-specific baseline/eval，再增加 optimization complexity。
- OpenAI, [Retrieval](https://developers.openai.com/api/docs/guides/retrieval) — semantic retrieval 與 vector store 基本模式。
- OpenAI, [Speaker-aware meeting intelligence](https://developers.openai.com/cookbook/examples/audio/speaker_aware_meeting_intelligence/speaker_aware_meeting_intelligence) — structured extraction、evidence references、deterministic grounding、human labels、precision/recall 與 optional LLM judge。
- Anthropic, [Building effective agents](https://www.anthropic.com/engineering/building-effective-agents) — simple composable workflow、single-call/retrieval baseline、programmatic gates、只有量測證明後才加複雜度。
- Anthropic, [Effective context engineering for AI agents](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents) — context 是有限 attention budget；每輪選最小高訊號 state。
- Anthropic, [Demystifying evals for AI agents](https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents) — 2026 多輪 eval 的 task/trial/transcript/outcome/harness 定義、code/model/human graders、人工閱讀 trace 與 grader 校準。
- Anthropic, [Harness design for long-running application development](https://www.anthropic.com/engineering/harness-design-long-running-apps) — 2026 harness 以 structured state handoff維持長任務，並以逐項 ablation而非盲目增加 scaffolding。
- Anthropic, [Contextual Retrieval](https://www.anthropic.com/engineering/contextual-retrieval) — chunk-specific context、BM25/embedding、reranking 與 retrieval eval。
- Anthropic, [Anthropic Interviewer](https://www.anthropic.com/research/anthropic-interviewer) — planning/interviewing/analysis 三階段、adaptive 10–15 分鐘訪談、illustrative quotations 與 human researcher collaboration。
- Google Cloud, [Dialogflow CX Parameters](https://docs.cloud.google.com/dialogflow/cx/docs/concept/parameter) — active form parameter、session parameter、slot/form filling 與 reprompt；證明短回答需綁定 active state。
- AWS, [Control agent session context](https://docs.aws.amazon.com/bedrock/latest/userguide/agents-session-state.html) — persisted session attributes、per-turn prompt attributes 與 confirmation state。

### 19.2 Job analysis / competency taxonomy

- 勞動部勞動力發展署 iCAP, [職能相關概念](https://icap.wda.gov.tw/ap/knowledge_introduction.php) — 職務基本資料、工作內涵、能力內涵與欄位定義。
- 勞動部勞動力發展署 iCAP, [職能基準發展指引](https://icap.wda.gov.tw/ap/get_file.php?c=%E8%81%B7%E8%83%BD%E5%9F%BA%E6%BA%96%E7%99%BC%E5%B1%95%E6%8C%87%E5%BC%95.pdf&e=20221026143138.pdf&t=download) — 訪談、功能分析、專家會議、工作產出、行為指標與 K/S/A 方法。
- 勞動部勞動力發展署 iCAP, [2026 職能基準品質認證作業手冊](https://icap.wda.gov.tw/ap/get_file.php?c=%E8%81%B7%E8%83%BD%E5%9F%BA%E6%BA%96%E5%93%81%E8%B3%AA%E8%AA%8D%E8%AD%89%E4%BD%9C%E6%A5%AD%E6%89%8B%E5%86%8A.pdf&e=20260311201400.pdf&t=download) — 現行表格、方法／流程／stakeholder／validation 要求與 K/S 定義。
- U.S. OPM, [Assessment and Selection / Job Analysis](https://www.opm.gov/policy-data-oversight/assessment-and-selection/) — duties、tasks、competencies、SME、critical incidents 與 linkage。
- U.S. OPM, [Six Steps to Conducting a Job Analysis](https://www.opm.gov/policy-data-oversight/assessment-and-selection/job-analysis/job_analysis_checklist.pdf) — critical tasks、critical competencies 與 task–competency rating。
- U.S. OPM, [Competency-Based Qualification Standard for IT Management](https://www.opm.gov/policy-data-oversight/classification-qualifications/competency-based-policy/general-schedule/2200/2210-competency-based-policy/competency-based-qualification-standard/) — 機構可依 job analysis 補充／修改 general 或 technical competencies，且需保存驗證依據。
- U.S. Department of Labor O*NET, [Content Model](https://www.onetcenter.org/content.html) — task/work activity 與 knowledge/skill/ability/work style 分層。
- NIST, [Playbook for Workforce Frameworks](https://www.nist.gov/itl/applied-cybersecurity/nice/nice-framework-resource-center/playbook-workforce-frameworks) — common 與 context-unique tasks、模組化 T/K/S building blocks、組織情境擴充與 interoperability。
- NIST, [NICE Framework Current Versions](https://www.nist.gov/itl/applied-cybersecurity/nice/nice-framework-resource-center/nice-framework-current-versions) — 分離維護、可版本化的 Work Role／Competency Area／T/K/S components；現行 component 版本 2.2.0（2025-04-28）。
- NIST, [Privacy Workforce Taxonomy](https://www.nist.gov/privacy-framework/workforce-advancement/privacy-workforce-taxonomy) — Task、Knowledge、Skill statement 定義、modular application 與非 one-size-fits-all 原則。
- European Commission ESCO, [About ESCO](https://esco.ec.europa.eu/en/about-esco) — occupation/skill/knowledge concepts 與關係資料。
- European Commission ESCO, [ESCO v1.2](https://esco.ec.europa.eu/en/about-esco/escopedia/escopedia/esco-v12) — AI-assisted extraction/linking + human expertise/quality improvement。

### 19.3 Employee-facing AI coediting / human control

- OpenAI, [Apps SDK UI guidelines — fullscreen](https://developers.openai.com/apps-sdk/concepts/ui-guidelines#fullscreen) — rich editing canvas／multi-step workflow 可與 conversation composer 並存，保留對話 context。
- OpenAI Help, [What is the canvas feature in ChatGPT and how do I use it?](https://help.openai.com/en/articles/9930697-what-is-the-canvas-feature-in-chatgpt-and-how-do-i-use-it) — 直接編輯、選取範圍要求 AI 處理、顯示差異、版本歷史與還原。
- Anthropic Help, [What are artifacts and how do I use them?](https://support.claude.com/en/articles/9487310-what-are-artifacts-and-how-do-i-use-them) — 對話旁的 dedicated artifact window、targeted update 與 version selector。
- Google Docs Help, [Collaborate with Gemini in Google Docs](https://support.google.com/docs/answer/13447609?hl=en) — 對選取文字 refine，建議可逐項／批次接受或拒絕，並可顯示來源。
- Microsoft Support, [Rewrite text with Copilot in Word](https://support.microsoft.com/en-us/word/copilot-rewrite-text-with-copilot-in-word) — 選取範圍後 rewrite、replace／insert／regenerate，使用者可先編輯 suggestion。
- Microsoft Support, [Welcome to Copilot in Word](https://support.microsoft.com/en-us/word/welcome-to-copilot-in-word) — document canvas + chat，變更先供 review／approval 再寫入共享文件。
- Microsoft, [Guidelines for Human-AI Interaction](https://www.microsoft.com/en-us/haxtoolkit/ai-guidelines/) — AI 能力、原因、控制與失敗處理應讓使用者理解；避免以解釋製造過度信任。
- Google PAIR, [Explainability + Trust](https://pair.withgoogle.com/guidebook-v2/chapter/explainability-trust/) — explanation 應對使用者決策有用，並保留 feedback、control 與 manual fallback。

## 20. Proposed decision

R5 不應直接照現有 literal-only contract 實作，也不應推翻 Evidence-first 主線。推薦的調整是：

```text
Evidence-first
  + explicit QuestionFrame
  + short-answer AnswerBinding
  + Evidence.v3 literal/contextual support 分型 provenance
  + employee direct document command
  + AI proposal -> employee accept/edit/reject
  + bounded JobStateDigest feedback loop
  + task/output/indicator synthesis
  + optional public-reference coverage
  + document-local K/S drafting + task linkage review
  + canonical JobModel revision/proposal authoring core
  + replaceable editor/index/API adapters
```

這能同時保住五個產品目標，而且不建立公司層系統：

1. 訪談自然、能理解短回答，不必強迫員工每次說完整句；
2. 員工可隨時直接編輯，AI 變更則永遠可接受、修改或拒絕；
3. 文件更新會回饋下一題選擇，不重問員工已經親手補上的內容；
4. 公版沒有的任務與 K/S 可以直接成為這份 JD 的 custom item，不會被迫錯配官方 taxonomy；
5. 最終主要職責、任務、產出、行為指標與 K/S 都能回答「為什麼有這一項、來源是員工原話、短答確認、員工文件編輯、公版或 AI task inference」。

Revision 5 不裁決舊 editor／API／indexer 一定刪除；它裁決的是 **canonical Job Model 不得依賴它們**。各舊元件
只有通過 vertical-slice quality/maintainability gate 才保留，否則可替換而不重做職務與職能核心。

因此目前回答是：**舊 R5 不可做，新 R5 authority 已可交實作者。**ADR 0037 與 detailed amendment 已完成 exact schema、
lifecycle、verifier、persistence/recovery、Capture 與 eval matrix。共編完整實作不塞進 R5，但 `JobStateDigest` seam、
frame invalidation 與員工 write authority 已凍結，避免 R5 做完後重構 Context Engine。
