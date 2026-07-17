# Interview AI vNext Greenfield 實作計畫

- 日期：2026-07-16
- 狀態：**執行中；V0 + V1 + V2-A + V2-B與V3-0/V3-1/V3-2已完成(2026-07-17)，下一步V3-3 durable operation executor；尚未接 runtime route**
- 目標架構：[`../specs/2026-07-16-interview-ai-vnext-greenfield-architecture.md`](../specs/2026-07-16-interview-ai-vnext-greenfield-architecture.md)
- V2-B persistence reference：[`../specs/2026-07-16-interview-vnext-v2b-durable-persistence-research.md`](../specs/2026-07-16-interview-vnext-v2b-durable-persistence-research.md)
- V2-B 可執行交接：[`2026-07-16-interview-vnext-v2b-durable-persistence-plan.md`](2026-07-16-interview-vnext-v2b-durable-persistence-plan.md)
- V3 fixed replay reference：[`../specs/2026-07-17-interview-vnext-v3-fixed-replay-research.md`](../specs/2026-07-17-interview-vnext-v3-fixed-replay-research.md)
- V3 可執行計畫：[`2026-07-17-interview-vnext-v3-fixed-replay-plan.md`](2026-07-17-interview-vnext-v3-fixed-replay-plan.md)
- 團隊：一人開發；每個工作包必須可獨立 review、測試、保留或刪除
- 核心限制：不 import、包裝或雙寫 v3 LLM internals；v3 只作黑箱 baseline/fallback

---

## 1. 完成順序

```text
V0  凍結邊界與建立品質基線規則
 ↓
V1  Domain contracts + reducers + invariant tests
 ↓
V2  Provider-neutral LLM port + Capture vNext
 ↓
V3  Offline Turn Interpreter → Evidence → Episode Coder → Job Model
 ↓
V4  Sufficiency Engine + adaptive Question Policy
 ↓
V5  Finish/Consolidate/OCS Projector + 現有 Web seam
 ↓
V6  OpenAI/Anthropic model bake-off + 三層 eval
 ↓
V7  Pilot、切換、觀測、rollback window
 ↓
V8  刪除 v3 internals 與更新現行 design
```

不可跳過 V1/V2 直接寫一個聊天 prompt，也不可在 V3 fixed replay 尚未達 hard gate 前進入 production route。

### 1.1 2026-07-16 實作進度

| Slice | 狀態 | 已完成 | 明確未完成 |
|---|---|---|---|
| V0 | 完成 | `interview_vnext` 隔離 package、package 規則、AST dependency tests、production 零接線 | v3 刪除與 route 切換屬 V7/V8 |
| V1-A | 完成 | session/transcript/evidence/inference/episode/gap/candidate/review/state contracts；append/session/evidence reducers；stable reason codes/hash；13 份 committed schema；unit/property-like/schema tests | 不代表可上線，也不代表已完成全 event replay protocol |
| V1-B | 完成 | episode/gap/inference/candidate/withdraw/review lifecycle reducers；Evidence/Inference 雙向 correction lineage；Gap resolution evidence；deterministic invalidation；human review；共 24 份 schema | 不含 provider、DB、route 或正式 prompt |
| V2-A | 完成 | provider-neutral request/result/failure、hash-addressed operation registry、strict scripted fake；immutable artifact、version-addressed execution taxonomy/event/hash chain/manifest、outbox 與 multi-attempt operation checkpoint contracts；9 份 committed schema、1 份 taxonomy document、22 個 focused tests | 只有 in-memory contract fake；沒有 DB transaction、外部 exporter、live provider、正式 prompt 或 route |
| V2-B | 完成(2026-07-17) | migration 0010 八張 `interview_vnext_*` 表(introspection test 逐 constraint 驗)、canonical TEXT serialization + corruption 檢查、async repositories/UoW、atomic command commit(run-lock 鎖序)、durable capture(create_run/append/finalize/manifest)、outbox lease CTE、checkpoint crash recovery;focused Postgres suite 50 passed/0 skip、完整 suite 含 DB 499 passed;commit SHA 與差異註記見 V2-B plan §11 | 無 live provider/route/ContextBuilder;typed `ModelCallResult` 接線屬 V3;tenant/auth seam 屬 V5 |
| V3 | 執行中（V3-0/V3-1/V3-2完成） | OpenAI SDK 2.46.0與typed no-op atomic commit；deterministic ContextBuilder；portable all-required turn output schema、5-example prompt、hash-addressed operation/verifier policy、exact quote/Unicode span/correction/numeric/partial-accept verifier與typed report；V3-2 focused 36 passed、完整含PostgreSQL 536 passed | V3-3 workflow executor、eval-only live adapter、episode coder與20-case多trial gate尚未完成 |
| V4+ | 未開始 | — | adaptive workflow、Web seam、雙provider bake-off、pilot與切換 |

V1 的 event 是 domain change notification／artifact index，payload 只有 object ID；目前可重現的是相同初始 state + command stream 的 state/hash。V2-B 已把 execution event + immutable artifact + outbox + checkpoint protocol 接上 PostgreSQL transaction:跨 process crash recovery 由「commit → 丟棄所有 in-memory objects → fresh session 重讀 committed rows」的 integration tests 證明。完整 event sourcing 仍**不**宣稱——execution event 只帶 ID/hash,完整重播 payload 在 command/reduction artifacts(§4.1 資料角色不得混用)。實作細節與完整 lifecycle matrix 見 [`../../apps/api/app/interview_vnext/README.md`](../../apps/api/app/interview_vnext/README.md)。

V1-B 的 breaking semantic changes 已依版本規則把 Evidence、Inference、Gap、InterviewState、ApplyEvidenceCommand 升為 v2。因 vNext 尚未接 route／DB，V1-A v1 只存在 Git history，不新增 runtime backward reader；從 V2 durable persistence 開始，major upgrade 必須有 migration／dual reader／explicit rejection 三者之一。

---

## 2. 全工作包共同規則

### 2.1 每個 PR 必須回答

- 本 PR 驗證哪個架構假設？
- 成功 metric 與 hard gate 是什麼？
- 新增哪個 schema/event/prompt version？
- 出錯時 trace 能否定位？
- 如何 rollback，是否會破壞已保存 session？
- 哪個既有功能明確不在本 PR 範圍？

### 2.2 版本規則

- domain schema：`<name>.vN`，破壞性語意改動升 major；
- prompt：內容檔 + canonical hash，不靠檔名猜版本；
- workflow：semver，任何 step order/meaning 改變至少升 minor；
- stage taxonomy：只追加名稱；既有名稱不得改語意；
- eval case：gold 與 input 分版；不得覆寫已跑 promotion 的 held-out case；
- provider/model：每個 run 固定 resolved ID 和 generation/reasoning settings。

### 2.3 transaction 與 idempotency

- 收到 employee turn 後先 durable write，再做 provider call；
- 每個 command 需要 idempotency key；
- domain mutation 使用 optimistic state version；
- provider call、step、artifact 都有 stable operation/attempt ID；
- capture/telemetry 走 outbox，不以外部觀測服務可用性決定 turn transaction；
- retry 不得重複 evidence、candidate、question 或 `_pending` suggestion。

### 2.4 測試層級

| 層 | 每個 PR | promotion 前 |
|---|---:|---:|
| pure unit/property tests | 必跑 | 必跑 |
| schema golden/diff | 有 schema 就跑 | 必跑 |
| provider contract fake | 有 LLM operation 就跑 | 必跑 |
| fixed replay | operation 完成後跑 | 全 development/validation |
| live provider smoke | 變更 adapter/prompt 時 | 固定 snapshot report |
| multi-trial eval | 可延後到 V6 | held-out 必跑 |
| manual trace review | 抽樣 | failure + promotion subset |
| Web contract/E2E | seam 變更時 | 必跑 |

---

## 3. V0——凍結舊架構與建立新目錄

### 3.1 目的

防止實作期間繼續把 v3 當成要逐步改造的目標，並讓所有新 code review 都能檢查依賴方向。

### 3.2 變更

1. 建立 `apps/api/app/interview_vnext/` package 與各空白子 package。
2. 新增 package-level `AGENTS.md`，明列：
   - 禁止 import `app.interview.consultant/scribe/harvest/select`；
   - domain 不 import provider/framework/ORM；
   - LLM 只能回傳 proposal，reducers 才能改 state；
   - 所有 projection 需 evidence lineage。
3. 建立 architecture dependency test，可用 AST/import-linter 或純 pytest 掃 import graph。
4. production route 保持 v3；新增 code 不由現行 request path import，避免半成品影響使用者。
5. 現有 `evals/interview_v4` 標記為 portable foundation + v3 baseline，不再替 v3 增加 provider-level 深度 instrumentation。

### 3.3 驗收

- 空 package 可 import；
- dependency test 能對刻意加入的 v3 import 失敗；
- 現有 API/Web/eval tests 全綠；
- production 行為零變化；
- docs index 指向 vNext spec/plan，舊 C0→C1 計畫標示被取代範圍。

### 3.4 停止條件

若現有 HTTP/Web seam 無法在不 import v3 中間物件的情況下描述，先新增純外部 contract test，不在 vNext 內複製 v3 object。

---

## 4. V1——Domain contracts、reducers 與 invariants

### 4.1 新增檔案

```text
interview_vnext/domain/
├─ identifiers.py
├─ session.py
├─ transcript.py
├─ evidence.py
├─ episode.py
├─ job_model.py
├─ review.py
├─ events.py
├─ reducers.py
└─ invariants.py
```

### 4.2 實作順序

1. 定義 branded/validated IDs 和 UTC timestamp 規則。
2. 實作 `InterviewSession` 與合法 transition table。
3. 實作 `TranscriptTurn` append-only contract。
4. 實作 Evidence/Inference/Gap/CandidateJobItem schema。
5. 實作 domain events；event payload 不含 provider SDK object。
6. 實作 pure reducers：輸入 old state + command/proposal，輸出 new state + events。
7. 實作 hard invariants，錯誤回 stable reason code。
8. 產生 committed JSON Schema；CI 比對 Pydantic codegen output。

### 4.3 必要 invariant tests

- exact/normalized quote span valid/invalid；
- 一個 turn 多 observation；
- current/past/hypothetical 分離；
- affirmed/denied/uncertain 分離；
- owner/shared/assists/other-role 分離；
- correction supersedes 舊 evidence，但歷史仍可查；
- duplicate proposal idempotent；
-不存在 evidence ID 的 inference/candidate 被拒絕；
- reference-only candidate 被拒絕；
- ability 只有一個 episode evidence 時 `insufficient`；
-數字 indicator 沒有 employee/policy source 時被拒絕；
- accepted/rejected human content 不可被 model reducer 改寫；
- optimistic state version conflict；
- finish 後拒收新 turn。

### 4.4 Property tests

- 同一 initial state + ordered command fixture 重播永遠得到同一 state/hash；V2 再以 durable command/result artifact + checkpoint 驗證 crash recovery；
- duplicate command 不增加 item 數；
- supersede 不造成 active lineage cycle；
-任何 projected candidate 的 evidence closure 都存在；
- reducer 不修改 input object；
- event serialization round-trip 不丟資訊。

### 4.5 驗收

- 此階段完全不呼叫 LLM，仍能建立、更新、更正、關閉一個 session；
- schemas 可由獨立 fixture 驗證；
- mutation code 只存在 reducers/repository unit of work；
- mutation failure 有 deterministic reason code，不靠 exception string。

---

## 5. V2——LLM port、operation registry 與 Capture vNext

### 5.1 新增檔案

```text
interview_vnext/llm/
├─ port.py
├─ result.py
├─ operation.py
├─ registry.py
├─ testing.py
├─ schema_exports.py
└─ write_schemas.py
interview_vnext/observability/
├─ events.py
├─ artifacts.py
├─ outbox.py
├─ checkpoint.py
├─ capture.py
├─ taxonomy.py
├─ schema_exports.py
├─ write_schemas.py
└─ write_taxonomies.py
```

### 5.2 `OperationSpec`

至少包含：

- stable operation name；
- input/output schema name；
- prompt template/hash；
- context policy name/version；
- quality profile；
- timeout、max attempts、max output tokens；
- allowed tools；
- repair policy；
-安全 policy flags。

### 5.3 fake provider

`ScriptedLlmPort` 可依 operation/case 回：

- valid structured output；
- schema invalid；
- safety refusal；
- transport timeout；
- rate limit；
- partial output；
- provider resolved-model mismatch；
- first attempt fail、second attempt success。

所有 application tests 先用 fake；不得為測 workflow 強迫 live API。

### 5.4 Capture vNext

1. 定義 open-string `stage` 與 versioned taxonomy registry。
2. 實作 workflow/step/model/tool/state/verification/outcome events。
3. 大 payload 存 immutable artifact，event 只存 reference + canonical hash。
4. outbox writer 可重試且不重複 event。
5. 保存 request/visible response/parsed output；不要求 hidden chain-of-thought。
6. provider usage 不提供時保存 `null + limitation`，不得當 0。
7. 實作 run manifest 與 hash-chain validator。

### 5.5 persistence migration

在確認 domain/event schema 後才寫 migration。V2-B 已完成 persistence 研究與交接裁決：使用全新八表，不共用 v3 mutable row：

- `interview_vnext_sessions`（canonical materialized aggregate）；
- `interview_vnext_runs`；
- `interview_vnext_artifacts`；
- `interview_vnext_commands`；
- `interview_vnext_execution_events`；
- `interview_vnext_outbox`；
- `interview_vnext_operation_checkpoints`；
- `interview_vnext_operation_attempts`。

V2-B 不先建立 evidence/inference/episode/candidate 的第二套權威表；完整歷史由 immutable command/reduction artifact保存，當前 graph由 session aggregate保存。V5 有實際 read query時才加可由 state hash重建的 projection tables。精確欄位、constraints/indexes、transaction順序、lease SQL與 recovery matrix以 [`../specs/2026-07-16-interview-vnext-v2b-durable-persistence-research.md`](../specs/2026-07-16-interview-vnext-v2b-durable-persistence-research.md) 為準；逐 commit實作順序見 [`2026-07-16-interview-vnext-v2b-durable-persistence-plan.md`](2026-07-16-interview-vnext-v2b-durable-persistence-plan.md)。migration 不刪 v3 表。

### 5.6 驗收

- 一個 fake workflow run 可產生完整、可驗 hash 的 capture；
-新增 stage 不改 event envelope schema；
- capture service 故障後 outbox 可補送；
- provider retry 每次 attempt 可見；
- state transition 前後 hash 對得回 artifact；
- capture 不 import OpenAI/Anthropic dashboard client。

### 5.7 V2-A／V2-B 切片邊界

V2-A 已完成純 contract 與 in-memory fake：可以驗證 operation definition hash、四種 model outcome、retry attempt identity、artifact immutable ID、execution hash chain、outbox retry 與 multi-attempt checkpoint transition。這些測試只證明 deterministic contract，不證明資料庫或網路 durability。

2026-07-16 驗證結果：V2 focused suite `22 passed`；完整 API regression `337 passed, 111 skipped`。skipped項目是既有環境／optional tests，不是 V2 新增 skip。

V2-B 已實作 5.5 的 migration、repository/unit-of-work 與 process-crash recovery
(2026-07-17;commits `5bb72be`→`d73ea79`→`5db1e43`→`11c4ada`→`73998a7`→`4d8edbd`
+ 文檔回寫)。以下六項摘要 hard gate 全部以真 PostgreSQL 16 實跑通過
(`require_postgres` 使 CI 未設 `TEST_DATABASE_URL` 直接 fail,skip 不可能當通過):

1. domain state + command/result artifact + checkpoint + outbox 在同一 DB transaction commit ✅(§12 case 2 + §7.8 commit_verified);
2. transaction rollback 不留下半套 artifact/event ✅(四個 flush-point failpoints + finalize rollback);
3. worker lease 到期後另一 process 可接手，event ID 不重複 ✅(expiry takeover、attempts+1、同 event ID 重送);
4. `calling` checkpoint 依 provider capability reconcile 或建立新 attempt，舊 attempt 不覆寫 ✅(lost+retry 恰 +1 attempt、result 不可換 artifact;reconcile 留 optional `RecoverableLlmPort`/V6);
5. `provider_completed|verified|committed` recovery 不重新呼叫 provider ✅(scripted provider 計數 0、committed 回同一 response artifact/hash);
6. migration upgrade/downgrade 只碰全新 vNext tables，不刪改 v3 rows ✅(0009→0010→0009 循環,v3 byte 級快照不變)。

---

## 6. V3——離線分析垂直切片

### 6.1 範圍

只處理固定 transcript，不生成下一題、不接 production Web：

```text
turn_interpret
→ evidence reducer
→ episode_code
→ job model reducer/verifier
→ deterministic projection preview
```

### 6.2 operation contracts

建立：

- `TurnInterpretInput/Output.v1`；
- `EpisodeCodeInput/Output.v1`；
- 對應 ContextPolicy；
- prompts 與 fixtures；
- operation-specific semantic validators。

### 6.3 prompt 規則

`turn_interpret`：

- 只抽 current turn 支持的 observation/correction；
- 保留 exact quote/span；
- 明示 unknown，不填滿欄位；
- 不看 taxonomy/reference，避免 anchoring；
- 不產生 JD 文案或下一題。

`episode_code`：

- 只看 verified evidence；
- reference 分區且有 URN；
- 每個 candidate 引 evidence IDs；
- task/output/knowledge/skill/ability/attitude/indicator 走不同規則；
- 能輸出 `insufficient/conflicted`，不強制每類都有結果。

### 6.4 ContextBuilder v1

固定 transcript eval 也要走正式 ContextBuilder：

- current turn + preceding question；
- active episode evidence；
- correction targets；
- metadata selection manifest；
- reference snapshot；
- token count/budget artifact。

V3-1已完成。正式固定值為：turn 65,536 UTF-8 bytes／8,192 output reserve／contradiction 4／correction 8或4／recent evidence 6；episode 262,144 bytes／12,288 reserve／evidence 256／contradiction 64／candidate 128／reference 8。每個build產生typed packet、所有source selected/excluded manifest與budget report；超限攜完整未截斷內容hard fail。`ReferenceSnapshot`以URN排序並獨立hash定址，不與working state混權威。估算公式與限制見V3 reference §5.5；改值要新policy semver與eval證據。

### 6.5 Dataset

先完成 20–50 個 component tasks 中的最小 20 個，覆蓋 spec 第 14.3 節 balanced matrix。每個 case：

- input transcript/turn；
- initial state/reference snapshot；
- required/forbidden evidence；
- qualifier gold；
- candidate gold 或明示不唯一的 rubric；
- 至少一個 known-good reference solution；
- annotation status/owner/review date。

### 6.6 graders

- schema/quote/span/lineage；
- evidence precision/recall；
- qualifier exactness；
- correction application；
- required/forbidden candidates；
- unsupported claim；
- task/output separation；
- reference leakage；
- ability/indicator hard gates。

### 6.7 驗收

- 20 個 development tasks 可完整跑完並產 artifacts；
- hard-gate failure 都能定位到 operation/reducer/verifier；
- 同一模型至少 3 trials，報 variance，不只挑最佳一次；
- maintainer 逐讀所有 failure trace；
- 未達 hard gate 時只修 V1–V3，不進 V4 adaptive conversation。

---

## 7. V4——Sufficiency Engine 與 adaptive interview

### 7.1 新增檔案

```text
interview_vnext/application/
├─ workflow.py
├─ context_builder.py
├─ sufficiency.py
├─ question_policy.py
└─ recovery.py
```

### 7.2 Sufficiency Engine

輸入 verified evidence/episode/asked history/session budget，輸出：

- coverage dimensions；
- open/answered/declined/not-applicable gaps；
- contradiction list；
- candidate actions；
- episode-code/close/session-stop eligibility；
- deterministic feature manifest。

初版 priority 排序只使用可解釋 features；LLM 不直接改 priority state。

### 7.3 Question Policy

實作 `QuestionPolicyInput/Output.v1`，輸出 action、selected gap、reason code、response text、question count。Verifier 檢查：

- gap 存在且 open；
- 一般最多一題；
- 不重問已 answered/declined；
- correction/stop/decline 優先尊重；
- emergent gap 有 current evidence/span；
- response 不洩漏內部 taxonomy 或 model reasoning；
- question 不把 reference suggestion 當既定事實。

### 7.4 branching simulator

重寫／新增受控 simulated user：

- `fact_world` 是 hidden immutable fixture；
- simulator 只能依已問問題揭露對應 facts；
- 不得臨場發明工作內容；
- 有 refusal/dont-know/correction/stop policy；
- 每個 trial 使用固定 persona policy version；
- evaluator 可直接檢查最後 state 與 hidden facts，不只讀文字。

### 7.5 adaptive metrics

- hidden-fact coverage；
- unsupported-fact rate；
- information gain per turn；
- repeat/leading/double-question rate；
- decline/stop respect；
- episode shift correctness；
- unnecessary turns；
- final JD outcome；
- pass@1、pass^3 或預註冊的 consistency metric。

### 7.6 驗收

- 至少 10 個 branching scenarios、每個至少 3 trials；
- positive/negative behavior cases 平衡；
- 任何拒答後重複逼問、停止後續問或 reference leading 都是 hard failure；
- trace 可重建「為何有這個 gap、為何選這題、回答後 state 如何變」；
- Question Policy 與 response composer 合併版達標；未達時才做 two-call ablation。

---

## 8. V5——Finish、Global Consolidator、OCS Projector 與 Web seam

### 8.1 Global Consolidator

先做最小 pass，只允許：

- 跨 episode duplicate merge proposal；
- candidate conflict；
- 多事件支持的 ability/attitude hypothesis；
- unresolved gap/uncertainty；
- naming normalization。

每個輸出引用既有 candidate/evidence。若 deterministic merge 在 eval 已足夠，刪除這個 LLM operation。

### 8.2 OCS/JD Projector

以 pure function 起步：

```text
Verified Candidate Job Model
 + Current accepted/rejected/human-authored document state
 + OCS contract version
 → ProjectionProposal[]
```

ProjectionProposal 至少含 path/op/value、candidate IDs、evidence IDs、reference URNs、qualifiers、reason code。Projector 不呼叫 provider。

### 8.3 projector tests

- T/P/O/K/S/A 正確 cardinality/path；
- no-op/idempotency；
- accepted/rejected/human content protection；
- stale candidate 不投影；
- current/past/denied/reference-only 排除；
- duplicate merge；
- unresolved conflict 不自動定案；
-所有 suggestion 可回 evidence quote；
- schema upgrade fixture。

### 8.4 Web seam

建立薄 adapter，把 vNext ProjectionProposal 映射成現有 `_pending` review contract。不得讓 vNext domain import Web DTO，也不得把 v3 state 注入 vNext。

新 session start 時由 feature flag 選 runtime；同一 session 固定 runtime。Web 必須能顯示：

- suggestion statement/type；
- employee quote(s)；
- reference；
- uncertainty/conflict；
- accept/edit/reject。

### 8.5 驗收

- 完整 synthetic session 可 finish 並在現有 Web 被逐項審閱；
-人工接受／修改／拒絕事件回寫 vNext review state；
- 重送 finish 不重複 suggestion；
- Web contract/E2E 與既有手動編輯 tests 全綠；
- v3 session 不被中途轉為 vNext。

---

## 9. V6——Provider/model bake-off 與 promotion eval

### 9.1 adapters

#### OpenAI

- 使用 Responses API；
- strict structured outputs；
- `store`/conversation/previous response 只作可選傳輸最佳化；
- business context 可在 `store=false` 或 response ID 遺失時完整重建；
- 不使用 Assistants API；
- 捕捉 resolved model、usage、request/response IDs 與可見 output。

#### Anthropic

- 使用當前 Messages API/官方 SDK；
- structured output/tool schema 由 adapter 映射到共同 contract；
- provider prompt caching/context feature 只作 adapter optimization；
-不把 Anthropic session/message object 放入 domain；
- 捕捉同等 normalized result/usage/failure。

### 9.2 bake-off 方法

1. 先用各 provider 的最強合適模型跑 quality ceiling。
2. operation 分開比較，不把四個 operation 綁同一模型。
3. 同 input/context/schema、固定 reasoning/generation config。
4. 每 case 多 trial；報 pass distribution、latency、tokens、cost。
5. 先過 hard gates，再做 pairwise/weighted quality。
6. 較快模型只有在該 operation 不造成顯著 regression 才晉級。

### 9.3 human calibration

- 至少兩位 reviewer 的小型 promotion subset，或一位 domain reviewer + maintainer；
- reviewer 不知道 provider/model/architecture；
- 先獨立評，再 adjudicate disagreement；
- model grader 與 human 計算 false positive/negative；
- judge rubric/version/model/artifact 全保存；
- 無 domain reviewer 時只可宣布 engineering/safety gate，不宣稱專業 JD 品質已證明。

### 9.4 promotion report

必含：

- dataset composition/limitations；
-每個 operation/provider/model config；
- hard gate matrix；
- case-level v3/vNext win/tie/loss；
- failure severity 與 trace location；
- multi-trial variance/pass^k；
- latency/token/cost distribution；
- human/model grader agreement；
- known unknowns；
- `PROMOTE|REVISE|REJECT` 決定與理由。

---

## 10. V7——Pilot、切換與 rollback

### 10.1 pilot 順序

1. local/offline synthetic；
2. isolated API environment；
3. owner-controlled test sessions；
4. 小型真人 pilot（有同意、可人工接管）；
5. opt-in tenant/profile；
6. default new session；
7. rollback window 結束。

### 10.2 feature flags

- `INTERVIEW_RUNTIME_DEFAULT=v3|vnext`；
- per-session runtime 固定欄位；
- `INTERVIEW_VNEXT_ENABLED` kill switch；
- model routing config 可獨立 rollback；
- Capture 永遠不以 flag 關掉 hard failure/outcome metadata，內容保存依既有資料政策。

### 10.3 production monitoring

- operation success/failure/repair rate；
- p50/p95 latency 與 time-to-first-response；
- tokens/cost；
- verifier rejection reason；
- duplicate/idempotency conflict；
- unsupported claim incident；
- review accept/edit/reject；
- average turns、decline、stop；
- crash recovery/outbox lag；
- runtime/model/workflow version slices。

### 10.4 rollback

- 只影響**新 session**的 default runtime；
- active vNext session 優先恢復 vNext，不熱轉 v3；
- 若 vNext 嚴重故障，可暫停該 session並人工處理，不把 state 猜譯成 v3；
- rollback 不刪 vNext events/artifacts；
-每次 rollback 產 decision/incident record並加入 eval case。

### 10.5 切換 gate

架構 spec 第 14.6 節全部通過，且：

- migration/restore 演練通過；
- kill switch 與 runtime default 切換測試通過；
-現有 Web 手動 JD 路徑無 regression；
- runbook 有具體排錯 query/event reason code；
- owner 看過 promotion report 並核准。

---

## 11. V8——刪除 v3 internals

### 11.1 前置條件

- 沒有 active v3 session，或已有明確 completion/archive 處置；
- vNext rollback window 完成；
-必要 audit/eval artifacts 已保存；
- production default 已穩定；
- dependency scan 知道所有 v3 consumers。

### 11.2 刪除範圍

- v3 consultant/scribe/harvest/select prompts 與 runtime；
- 只服務 v3 的 tool schemas/intermediate state；
- v3-only flags、dead routes、tests；
- 舊 DB object 的另行 migration；
- `docs/design/interview-engine.md` 的 v3 現行描述移 archive。

### 11.3 保留範圍

- migration history；
-匿名／測試 eval artifacts；
- v3 black-box result report；
- architecture decision/research；
-必要 incident records。

### 11.4 驗收

- `rg` 找不到 vNext production 對 v3 internals 的 import/call；
- clean database upgrade 和已存在 database upgrade 都通過；
-全測試綠；
- ARCHITECTURE、app README、design、runbook、eval README 全部指向 vNext；
- dead config/env documentation 清除。

---

## 12. 第一個實作 PR 的精確內容

下一個 PR 只做 V0 + V1 的第一半，不呼叫 live LLM：

1. 建 `interview_vnext/domain` package 與依賴禁止測試。
2. 定義 `InterviewSession`、`TranscriptTurn`、`Evidence`、`Inference`、`EpisodeState`、`Gap`、`CandidateJobItem`。
3. 定義 session/evidence transition reason codes。
4. 實作 quote/span、time/polarity/ownership、correction/supersede pure validators。
5. 實作 reducers 的 append/correct/idempotency 最小切片。
6. 產生 committed JSON Schema。
7. 加 unit/property/schema tests。
8. 不加 route、不加 migration、不改 v3 runtime、不選模型。

完成條件：domain object 不靠任何 v3/provider/ORM class 即可從 fixture 建立、序列化、以相同 command fixture replay、correct 並得到穩定 state hash。這是後續所有 LLM 品質工作的地基；若這層語意不穩，後面的 prompt 再強也無法可靠累積工作事實。

---

## 13. 開發者每階段不要猜的清單

| 實作遇到的疑問 | 規則 |
|---|---|
| 模型回 schema 外欄位怎麼辦？ | strict reject；最多一次 schema repair，不由 parser 保留未知欄位。 |
| quote 大意相同但不是原文？ | 不作 exact evidence；可要求模型重抽 span，不自動改寫 quote。 |
| 員工更正舊說法？ | 新 evidence + `supersedes`；舊 evidence 改 inactive，不刪除。 |
| reference 說此職位通常有某 task？ | 只能開 gap或 taxonomy candidate，不能建立 employee fact。 |
| 不知道 frequency/importance？ | 保存 unknown；可依資訊價值追問，不從措辭猜。 |
| 一句話有三個 task？ | 拆三個 atomic observations，共用同一 turn/spans 可重疊。 |
| 工具名稱算 skill 嗎？ | 先是 tool；需有熟練行為 evidence 才是 skill。 |
| ability 只有一次事件？ | hypothesis/insufficient，不投影。 |
| indicator 沒有數字？ | 可有 qualitative observable indicator；不可虛構數字。 |
| 使用者拒答？ | gap=declined，Question Policy 不重問；保留 unresolved reason。 |
| 是否每回合一定問？ | 否；可確認、轉題、處理拒答或收尾。一般最多一個主問題。 |
| provider session 丟失？ | 用自有 state/context 重建；provider ID 不是 source of truth。 |
| Capture 寫失敗？ | domain transaction 完成，outbox retry；不可悄悄永久漏失。 |
| v3 某函式剛好可重用？ | 不 import；若是通用純邏輯，重新抽成無 v3 語意的 shared primitive並以 contract 證明。 |
| 要不要加 Agent/Graph/RAG/fine-tune？ | 先提出具體 failure case、ablation 與 kill condition；沒有就不加。 |
