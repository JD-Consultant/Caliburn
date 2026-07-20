---
title: Interview vNext 專業職務分析、短回答 grounding 與 OCS/JD 共編架構研究
status: proposed-research-not-implementation-authority
date: 2026-07-20
revision: 3
audience: owner, architect, implementer, evaluator
scope: R5 前置設計；當下單一職務的訪談證據、職務模型、document-local K/S、authoring 與交付 projection
---

# Interview vNext 專業職務分析、短回答 grounding 與 OCS/JD 共編架構研究

> 本文是 **R5 實作前的研究與提案**，不是新的 active implementation authority。現行實作 authority 仍是
> [`2026-07-18-interview-vnext-v3-5a-runtime-contract-reconstruction-plan.md`](../plans/2026-07-18-interview-vnext-v3-5a-runtime-contract-reconstruction-plan.md)。
> owner 核准本文的裁決後，才回寫 mother plan／ADR 並交給實作者；不得因本文存在就自行新增 migration、
> production route、Web wiring 或 paid live。
>
> **Revision 3（owner scope correction）**：現有 editor、深文件契約、API、indexer 與欄位都只是可盤點的既有資產，
> 不是必須整合的限制。目標架構先以產品品質、可追溯性與一人團隊可維護性設計，再用明確 gate 決定保留、
> 包裝、遷移或替換哪些既有元件。
>
> 本階段產品只處理「一個人當下的工作 → 這一份專屬職務說明書」。客戶可能是公司、個人或其他單位，但不建立
> 公司層 capability catalog、跨職務 K/S 共用、人才盤點或個人能力評分。這些都不是目前需求。

## 1. 結論先行

可以從訪談中建立以下正式交付欄位：

1. 主要職責；
2. 工作任務；
3. 工作產出；
4. 行為指標；
5. 職能內涵 K（knowledge）；
6. 職能內涵 S（skills）；
7. 必要時再加職能級別、態度、任職條件與整體工作描述。

但這些欄位**不能全部由 R5 單輪模型直接產生**。最佳架構是：

```text
訪談原話／短回答
  -> Conversation Grounding（知道這句在回答哪一題、哪個 slot）
  -> Employee Evidence（員工事實，保留可驗證 provenance）
  -> Episode / Task Model（同一工作片段的輸入、行動、產出、標準、例外）
  -> Candidate Job Model（主要職責、任務、產出、指標）
  -> Optional Reference Coverage（查公版，判定 usable/partial/no-match）
  -> Document-local K/S Drafting（公版不足時依已確認 task 產候選）
  -> Human Review（員工確認事實；顧問確認專業表述與 K/S linkage）
  -> Canonical Job Model Revision
  -> Authoring Workspace（新建或既有 UI adapter，由產品 gate 決定）
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
┌───────────────────────────────────────────────────────────────┐
│ Conversation Owner                                            │
│ Question Policy -> response_text + persisted QuestionFrame    │
└──────────────────────────────┬────────────────────────────────┘
                               │
                 employee answer: long or short
                               │
┌──────────────────────────────▼────────────────────────────────┐
│ R5 Turn Grounder / Interpreter                                │
│ dialogue act + literal observations + answer bindings         │
└──────────────────────────────┬────────────────────────────────┘
                               │ typed proposal
┌──────────────────────────────▼────────────────────────────────┐
│ Local gates                                                   │
│ schema -> frame scope -> span -> binding -> semantic verifier │
└──────────────────────────────┬────────────────────────────────┘
                               │
┌──────────────────────────────▼────────────────────────────────┐
│ Deterministic Reducers                                        │
│ Evidence / contextual assertion / correction / gap state      │
└──────────────────────────────┬────────────────────────────────┘
                               │ episode boundary
┌──────────────────────────────▼────────────────────────────────┐
│ Episode Coder                                                 │
│ task/output/behavior candidates + unresolved gaps             │
└──────────────────────────────┬────────────────────────────────┘
                               │ selected task query
┌──────────────────────────────▼────────────────────────────────┐
│ Optional Official Reference Search                           │
│ selected public sources -> hybrid retrieval -> bounded set    │
└──────────────────────────────┬────────────────────────────────┘
                               │ immutable candidate snapshot
┌──────────────────────────────▼────────────────────────────────┐
│ Document-local Requirement Drafting                           │
│ usable/partial/no-match -> K/S items grounded in this job     │
└──────────────────────────────┬────────────────────────────────┘
                               │ reviewed K/S + task links
┌──────────────────────────────▼────────────────────────────────┐
│ Canonical Job Authoring Core                                  │
│ revisions + proposals + decisions + provenance + publication │
└──────────────────────────────┬────────────────────────────────┘
                               │ deterministic projections
┌──────────────────────────────▼────────────────────────────────┐
│ Delivery Surfaces                                            │
│ new workspace / legacy adapter / API / OCS / JD / PDF / XLSX │
└───────────────────────────────────────────────────────────────┘
```

這是 deterministic workflow with semantic decision points，不是一組角色互相聊天的 multi-agent system。
任何 editor、API 或 retrieval engine 都是上述 domain ports 的 adapter，不得反過來決定 canonical model。

## 6. 四種來源必須分開

| Source channel | 能證明什麼 | 不能證明什麼 |
|---|---|---|
| Employee literal evidence | 員工這一輪明說的事實與限定條件 | 未說出的 currentness、ownership、K/S、KPI |
| Employee contextual answer | 員工對一個已持久化、可驗證 question frame 的確認／否認／slot value | 任意舊問題、複合 leading question 中未被清楚確認的所有假設 |
| Reference knowledge | 官方名稱、定義、相似任務、O/P/K/S 候選及來源 | 員工實際有做、員工一定具備某技能 |
| Human/policy | 顧問批准的表述、組織標準、人工輸入 KPI | 不可被偽裝成員工 quote |

任何 projected job claim 都要保存來源類型。reference relevance、employee actuality、human approval 是三個不同
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
  valid_for_next_employee_turn: true
```

`QuestionProposition` 不是 employee evidence。它至少保存：

```text
ordinal
subject
kind
claim
existing_employee_evidence_ids
reference_urns
introduced_dimensions
```

ID 由 application 派生；模型不得產 DB identity 或任意 cross-reference key。

### 7.3 confirmation 防 leading 規則

`atomic_confirmation` 只有在以下條件全部成立時可用：

1. frame 只有一個清楚 proposition；
2. proposition 只確認一個工作事實，或所有其他欄位已有 employee evidence；
3. 一題不得同時首次引入 action、ownership、frequency、output、recipient 等多個未知事實；
4. reference-derived proposition 要標示來源，不得偽裝成員工先前說過；
5. frame 只對緊接的下一個 employee turn 有效；
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
frame_id
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

模型只提 binding；application 驗證 frame scope、ordinal、quote、slot type、single-target 與 expiry。

### 7.5 contextual evidence 需要 composite provenance

目前 `Evidence.v2` 只有一個 employee quote/span，無法誠實表示：「語意來自問題 frame，權威來自員工短答」。
推薦在 R5 核准後升版為 `Evidence.v3`，不要把完整 proposition 偽裝成由「是」字面支持。

```text
Evidence.v3
  ...existing evidence fields...
  support_basis:
    literal_employee_span
    contextual_slot_binding
    contextual_confirmation
  support_segments[]:
    turn_id
    role
    span | null
    text_hash
    contribution: semantic_context | employee_authority | literal_content
  question_frame_id | null
  proposition_hash | null
```

不變量：

- 每筆 evidence 至少有一個 employee-authority segment；
- reference snippet 永遠不可進 `support_segments`；
- contextual evidence 必須同時閉合到 frame hash 與 employee answer span；
- full claim 不需是「是」的 substring，但必須等於已驗證 frame proposition／slot resolution；
- correction、withdraw、supersede 語意仍由 deterministic reducer 處理。

如果不願升 `Evidence` contract，替代方案只能是把短回答保存成非投影的 `GroundedAnswer`，之後再問完整句；這會保留
精度但無法解決訪談過長，因此不推薦作最終產品架構。

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
4. K/S 主要靠 reference retrieval + reviewer selection，不要求員工自己背 taxonomy；
5. 數字 KPI、能力級別、態度只在產品需要且證據不足時追問；
6. unknown 是合法狀態，不用為填滿每一格無限追問；
7. 在 authoring workspace 一次審多筆候選，避免聊天逐筆確認。

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

員工可立即更正，但不要求每輪回答「確認」。更完整的 task/output/indicator/K/S 候選進 authoring workspace，以結構化 review
一次處理。

### 8.4 interview budget

Anthropic Interviewer 的公開測試採 10–15 分鐘 adaptive interview，並以 plan、interview、analysis 三階段加上
human collaboration。Caliburn 不必硬鎖相同時間，但第一版應把下列指標列為 release metric：

- 中位訪談時間；
- 每個 accepted task 所需回合數；
- clarification rate；
- 使用者提前停止率；
- 「被正確理解」評分；
- reviewer override rate；
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
5. 顧問可重分組、改名、合併、拆分；
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
- 數值 threshold 只能來自 employee evidence、approved organization policy 或 human input；
- reference indicator 可以作候選措辭，不可自動成為 employee fact；
- 不產生「積極負責、溝通良好」等不可觀察口號；
- 不把 ability/attitude 標籤直接當 indicator。

現有 `QuantitativeThreshold.source_type` 已有 employee/policy/human 分流，應保留。

### 9.5 K（Knowledge）

iCAP 2026 手冊定義為執行任務所需理解、可應用於該領域的原則與事實。K linkage 需要：

- 明確 task candidate；
- OCS/ESCO/NICE/其他公版候選，或根據本職務 task 形成的 document-local K；
- task–knowledge relevance reason；
- 這份 JD 內的 requirement ID；有公版來源才帶 reference URI/version；
- reviewer decision。

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
skill candidate；reference 可提出候選，仍需 task linkage 與 human review。

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
  -> consultant review
  -> save in this JobModelRevision and link to its task
```

禁止的捷徑：

- nearest vector 一定要選一筆；
- 把自訂 wording 覆蓋到官方 URI；
- AI 自創 `icap_ref`、ESCO URI 或官方 code；
- 把「這個職務需要某技能」誤寫成「受訪員工已具備某技能」。

這份 JD 內的最小 requirement：

```text
JobRequirementItem
  requirement_id               # 只在本 JobModel 中穩定
  kind: knowledge | skill
  statement
  linked_task_ids[]
  support_basis: task_inference | employee_statement | policy | public_reference | human
  support_refs[]
  public_alignment | null       # source URI/version + usable/partial；沒有也合法
  status: proposed | accepted | edited | rejected
```

只做同一份 JD 內的重複檢查與 task linkage，不做跨 JD alias、全公司 concept identity、發布或 deprecation lifecycle。

後兩者是不同 domain：

```text
JobRequirement: 這個 task 要求哪些 K/S
PersonCapabilityAssessment: 某個人目前具備到什麼程度
```

本產品目前先做 JobRequirement。除非另有 assessment evidence、rubric 與授權，不從工作訪談順便建立個人能力評分。

### 9.8 Ability、Attitude、Level

- Ability 應由跨 episode pattern 或員工明確確認產生，不由單輪工具使用推斷；
- Attitude 高度容易受語氣偏誤影響，應以跨情境可觀察行為 + human review 為主；
- competency level 不由模型憑措辭直接猜，可取 approved reference level、rubric rating 或 human decision；
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

R5 不讀 OCS reference，避免 reference laundering。

### 10.2 Episode Coder packet

只給：

- 該 episode 全部 active employee evidence；
- contextual support bundles；
- contradictions／corrections；
- 現有 episode candidates；
- 必要且已 snapshot 的 reference snippets。

### 10.3 K/S drafting operation packet

依 operation 最小化：

- confirmed task revision、outputs、indicators 與直接支持 evidence；
- 必要的工作情境／policy artifact；
- bounded public-reference candidates（若本次有查）；
- immutable retrieval snapshot；
- K/S authoring rules 與本文件已存在 requirements（只為 document-local dedup）。

不給完整 transcript、不給未選中的整個 taxonomy。第一版以一次 `requirements.draft` call 同時輸出 coverage 與 K/S
typed 區塊；只有 eval 證明分開能顯著改善品質或失敗歸因，才拆成兩個 operation。

### 10.4 Global consolidation packet

只給 candidate/inference/evidence closure，不重送完整 transcript；需要驗證時可按 evidence ID 回取原 quote。

### 10.5 長對話

conversation transcript 是 audit source，不是 working memory。工作記憶使用 persisted state：

- active QuestionFrame；
- Episode；
- Gap；
- Evidence；
- Inference；
- CandidateJobItem；
- JobRequirementItem；
- ReviewDecision。

provider conversation ID、server-side compaction 或 prompt cache 只能是 adapter optimization，不能取代 app-owned state。

## 11. 公版 retrieval 與 document-local K/S

### 11.1 公版的角色

公版只負責：

- 提醒可能漏掉的 task/output/indicator/K/S；
- 提供較專業、標準化的候選措辭；
- 提供 source URI/version 讓顧問知道參考來源；
- 協助比較這份 JD 與職能基準的覆蓋程度。

公版不能限制實際工作，也不能證明員工有做某 task 或具備某能力。客戶是不是公司不影響這條規則。

### 11.2 最小 K/S model

本階段不建立 CapabilityConcept、namespace、alias graph 或跨 JD catalog。只在 `JobModelRevision` 保存：

```text
JobRequirementItem
  requirement_id
  kind: knowledge | skill
  statement
  linked_task_ids[]
  support_basis
  support_refs[]
  public_alignment | null
  status
  reviewer_edit | null
```

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
7. 顧問 accept/edit/reject；
8. 寫入本 JobModelRevision，不發布到其他職務。

LLM 可以利用通用專業知識提出 K/S 候選，但此時 `support_basis=task_inference`，不是 employee fact、company fact 或
official reference；必須讓顧問看得出來並審核。LLM 不得產 official code。

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
- reviewer accept/edit/reject rate與平均 review 時間。

## 12. Canonical authoring core 與 delivery surfaces

### 12.1 現有深文件適合 exchange，不足以直接作產品核心

目前 `ocs_doc` 與 `packages/ocs-contract` 對公版匯入／匯出很實用，但 active `CodeName` 主要只有 code/name，
`CompetencyBlock` 內重複 K/S 陣列；`_pending` 又把 review UI metadata 嵌在待輸出的文件樹。這造成：

- K/S requirement identity 與顯示位置 code 混合；
- 同一份 JD 內的 K/S 與 task linkage 難以清楚表示；
- task–K/S linkage 沒有獨立 status/rationale/provenance；
- proposal、accepted truth 與 export shape 耦合；
- final strip metadata 後，不能只靠文件重建完整 review/audit history。

因此 OCS JSON 應降為 publication/export contract，不再預設為 greenfield authoring source of truth。

### 12.2 Canonical Job Model

推薦 authoring domain：

```text
JobProfile
JobModelRevision
Duty
Task
Output
BehaviorIndicator
JobRequirementItem（K/S；document-local）
RequirementLevel
SourceAssertion / Evidence / Inference
Proposal
ReviewDecision
Publication
```

所有 domain entity 使用 application identity；T1/T1.1/O01/P01/K01/S01 是 deterministic publication position code，
不是永久 ID。revision 發布後 immutable；修改建立新 draft revision，不能在已發布 JSON 上原地覆寫。

### 12.3 Proposal 與 accepted truth 分離

AI 不直接修改 canonical revision，而是建立 typed proposal：

```text
target entity/path
operation: add | revise | remove | link | unlink | merge | split
proposed value
evidence/inference/reference closure
conflicts/uncertainty
model operation identity
status: pending | accepted | edited | rejected | superseded
review decision + reviewer-authored final value
```

這保留現有 `_pending` 的正確人機邊界，但不要求沿用其文件內嵌實作。任何 editor 都只透過 command/query API 操作
proposal 與 revision；人工 accepted/edited 內容不被後續 AI 靜默覆蓋。

### 12.4 API 與模組邊界

一人團隊推薦 **modular monolith + background workers**，不要為每個 operation 拆微服務：

```text
Interview module       session/turn/question frame/evidence/gap
Job Authoring module   episode/duty/task/output/indicator/K/S/revision/proposal/review/publication
Reference module       public sources/import/snapshots/search port
LLM Runtime module     operations/provider port/executor/conformance
Evaluation module      capture/replay/eval（不被 production import）

Workers
  public-reference ingest/index/export/long-running eval
```

外部 API 按 use case 暴露 commands/queries，不直接把資料表或完整深 JSON 當 CRUD：

- append interview turn、answer/revise question；
- get grounded state/gaps；
- review proposal；
- accept/edit/reject document-local K/S 與 task link；
- get revision/diff/provenance；
- publish/export；
- search selected public references。

### 12.5 Editor 保留或重做的 decision gate

不先裁決「沿用」或「全部重做」。用一個 vertical slice 比較：

1. 一段訪談建立 3–5 tasks；
2. 至少一個 usable public K/S；
3. 至少一個 no-match document-local K/S；
4. 顧問完成 K/S edit、task-link review 與 publication；
5. 可回看 evidence、reference、reasoning limitation 與完整 diff。

評估現有 editor adapter 與新 authoring workspace：

- 是否能無損呈現 canonical entities與 task/K/S links；
- 顧問完成時間與操作錯誤；
- provenance 可理解性；
- custom K/S edit 與 linkage 體驗；
- conflict/revision handling；
- 前後端改造量與後續維護成本。

若舊 editor 需要把 canonical model 壓回大量 `_pending` 深樹 hack 才能工作，就重做；若薄 adapter 即可滿足 vertical
slice，則可先留作 migration surface。產品架構不依賴這項 UI 決定。

### 12.6 UI 最低產品能力

不論新舊 UI，顧問至少能回答：

- AI 為何提出這一項？
- 哪些是員工原話／contextual confirmation？
- 哪些來自官方公版、工作情境、policy、AI task inference 或人工？
- 公版是 usable、partial 還是 no-match？
- 這項 K/S 是公版候選還是本文件 custom item？
- 哪些 task 要求此 K/S，link 的理由是什麼？
- 接受後會改哪個 revision，發布到哪些 delivery formats？

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
4. `Evidence.v3` 支援 composite provenance；
5. frequency marker 不直接證明 current time scope；
6. 「unknown qualifier 是否值得追問」移到 Gap/Question Policy；
7. 加短回答、stale frame、leading question、mixed answer eval；
8. `CandidateKind` 後續加 duty，不能等 projection 時臨時猜分組。

### 14.3 建議實作切片

若 owner 核准，不建議把所有變更塞進一個巨大 R5 commit。推薦：

1. **R5a inactive contracts**：QuestionFrame、AnswerBinding、Evidence v3 schema 與 pure validators，active runtime 暫不切；
2. **R5b question frame persistence**：Question Policy contract、state/reducer、recovery/Capture roots；
3. **R5c interpreter hard cut**：turn operation/output/prompt/verifier 一次切到新 active contract；
4. **R5d contextual reducer**：literal/contextual evidence、correction、gap transition；
5. **R5e docs/status**：hash/catalog/README/mother plan；
6. **R6a grounding eval**：短回答專用 suite；
7. **R6b existing 12 cases migration**；
8. **post-R5 architecture slice（編號待 mother plan 重排）**：canonical Job/Authoring contracts；
9. **後續 eval**：episode/job、no-match K/S、linkage、retrieval 與 authoring vertical slice。

每個 commit 必須保持完整 no-network suite 綠；若 active hard cut 無法拆綠，R5b–R5d 合併成一個原子 commit，禁止
相容 shim 同時支援兩個 active contract。

R5 的完成定義仍只到「自然且可信地理解一輪並形成 evidence」。不得在 R5 順手修改 editor、深文件契約或 indexer；
Job/Authoring core 需先由本文 D5–D11 核准，再寫獨立 implementation authority。這是控制架構風險，
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

### 15.4 Human pilot

至少分開記錄：

- employee：「AI 有沒有理解我的工作」；
- consultant：欄位正確性、改寫時間、override severity；
- final document：盲評 usefulness、specificity、completeness、unsupported claim；
- interaction：時間、回合數、疲勞、提前終止。

OpenAI 官方 meeting-intelligence 指引也建議以 human-reviewed transcript labels、holdout、exact/near-exact evidence
checks、precision/recall 及 reviewer override 持續評估。OpenAI hosted Evals platform 已公告 2026-11 關閉，因此
Caliburn 應繼續使用自己的 versioned harness/Capture，不依賴即將退役的平台。

## 16. 一人團隊的最低可行最強版

第一個可測產品不要一次完成所有 taxonomy 與所有投影。建議順序：

### Stage A：自然且可信地聽懂

- QuestionFrame；
- short-answer grounding；
- literal/contextual evidence；
- correction；
- current 12 cases + grounding suite。

### Stage B：形成任務與產出

- Episode Coder；
- task/output candidates；
- gap priority；
- canonical Job Model draft revision；
- bounded reference task retrieval。

### Stage C：形成指標與 K/S

- behavior indicator component support；
- optional public K/S coverage；
- no-match document-local K/S drafting；
- task–K/S linkage review；
- document-local dedup 與 retrieval eval。

### Stage D：共編與最終文件

- canonical authoring core；
- proposal/revision/review API；
- 新 workspace 或既有 editor thin adapter 的 vertical-slice 決策；
- deterministic publication projector；
- human review events；
- final OCS/JD outcome eval。

### Stage E：模型與成本優化

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
- 為追求「最潮」預先加入 graph framework、多 Agent、fine-tuning；
- 依賴將於 2026-11 關閉的 OpenAI hosted Evals platform。

## 18. 需要 owner 討論／核准的裁決

### D1 — contextual evidence contract

**推薦：核准 `Evidence.v3` composite provenance。**

替代方案是維持 literal-only，所有「是」都要再問完整句；工程簡單但與自然訪談目標衝突。

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

員工可提供工作佐證與修正，但「職務需要什麼」由後續 coverage/drafting operation + 顧問判定；
不能把它當 R5 employee fact，也不能因此宣稱員工本人已具備。

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

## 20. Proposed decision

R5 不應直接照現有 literal-only contract 實作，也不應推翻 Evidence-first 主線。推薦的調整是：

```text
Evidence-first
  + explicit QuestionFrame
  + short-answer AnswerBinding
  + composite employee provenance
  + task/output/indicator synthesis
  + optional public-reference coverage
  + document-local K/S drafting + task linkage review
  + canonical JobModel revision/proposal authoring core
  + replaceable editor/index/API adapters
```

這能同時保住三個產品目標，而且不建立公司層系統：

1. 訪談自然、能理解短回答，不必強迫員工每次說完整句；
2. 公版沒有的任務與 K/S 可以直接成為這份 JD 的 custom item，不會被迫錯配官方 taxonomy；
3. 最終主要職責、任務、產出、行為指標與 K/S 都能回答「為什麼有這一項、來源是員工、公版、task inference、policy 還是人工」。

Revision 3 不裁決舊 editor／API／indexer 一定刪除；它裁決的是 **canonical Job Model 不得依賴它們**。各舊元件
只有通過 vertical-slice quality/maintainability gate 才保留，否則可替換而不重做職務與職能核心。
