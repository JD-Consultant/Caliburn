# Interview AI vNext V3 Fixed Replay 實作計畫

- 日期：2026-07-17
- 狀態：**已核准執行；研究定稿，實作進行中**
- 權威規格：[`../specs/2026-07-17-interview-vnext-v3-fixed-replay-research.md`](../specs/2026-07-17-interview-vnext-v3-fixed-replay-research.md)
- 前置完成：V0、V1、V2-A、V2-B、V3-0、V3-1、V3-2與V3-3；目前 head含 migration 0010、durable UoW/Capture/outbox/recovery、pure ContextBuilder、turn proposal verifier與顯式fixed-replay executor。V3-4 已實作（mocked complete, live gate pending，見 V3-4 交接規格狀態列）；下一步：取得官方 `OPENAI_API_KEY` 補跑 live gate，然後 V3-5。

---

## 1. 完成定義與停線規則

V3完成時必須能以同一套正式 application workflow完成：

```text
fixed transcript
 -> durable turn
 -> ContextBuilder
 -> real structured model call
 -> verification
 -> Evidence/Job Model reducer or explicit no-op
 -> preview
 -> Capture + component graders + report
```

本工作包不接 route/Web，不做 adaptive question，不改 v3。若 `turn_interpret` 12-case gate未過，不開始 episode coder；若全部20個component task的V3 gate未過，不進 V4。

所有 pure/DB tests不得需要 API key。Live eval是獨立明確 command；沒有 key時必須顯示 `NOT RUN`並阻止 V3 completion report宣稱通過，不能用 skip數混成綠燈。

---

## 2. Commit切片

| 切片 | 內容 | 可接真模型 | Gate |
|---|---|---:|---|
| V3-0A（完成） | OpenAI SDK freshness lock（2.44.0 -> 2.46.0） | 否 | dependency diff + full API regression |
| V3-0B（完成） | typed no-op result與durable commit use case | 否 | v1 schema不變 + DB round trip/crash/idempotency |
| V3-1（完成） | Context contracts、policy documents與 ContextBuilder | 否 | 15 focused + 515 full API/PostgreSQL passed |
| V3-2（完成） | turn_interpret contracts、prompt、proposal mapping與 verifier | 否 | focused 36 + full API/PostgreSQL 536 passed |
| V3-3（完成） | durable operation executor、partial/no-op commit | 否 | 9個fixed-replay PostgreSQL cases + recovery regression |
| V3-4 | eval-only OpenAI Responses adapter | 是，opt-in | mocked API matrix + one live probe |
| V3-5 | vNext eval harness + 12 turn tasks + 3-trial turn gate | 是 | turn report通過才繼續 |
| V3-6 | episode_code、Job Model verifier/reducer、preview + 8 tasks | 是 | candidate hard gates |
| V3-7 | full 20-case experiment、failure review、decision report | 是 | V3 promotion gate |
| V3-8 | docs、full regression、scope/dependency audit | 否 | clean worktree + user review |

不得把 contracts、live adapter、20 cases與 report塞成單一 commit。每一切片失敗時能獨立回退，且不得使用 `git reset --hard`清除他人工作。

---

## 3. V3-0——Dependency freshness與 no-op persisted contract

### 3.0 已完成的 contract spike

研究階段已讀完 checkpoint model、exported `operation-checkpoint.v1` schema與migration 0010。結論是現有v1的 `domain_result_artifact`為通用 `ArtifactRef`，可以指向明確的 `operation.noop_result.v1`；`mark_committed()`只要求artifact存在與after hash存在，不限定ReductionResult。因此：

- 不建立 `operation_checkpoint.v2`；
- 不修改已發布v1 schema；
- 不做migration 0011；
- application以typed no-op result補齊語意，state hash保持不變。

截至2026-07-17，官方OpenAI Python SDK最新stable是2.46.0，專案lock仍是2.44.0。先獨立完成V3-0A，避免之後把SDK升級回歸與adapter bug混在一起。

### 3.1 先讀與測

閱讀：

- `observability/checkpoint.py`；
- `application/durable_operations.py`；
- checkpoint committed JSON schema；
- migration 0010 checkpoint constraints；
- `test_interview_vnext_recovery_postgres.py`。

先新增 failing tests證明兩件事：

1. verified operation可以在不建立 command的情況下 committed，且 state hash不變；
2. 相同 no-op重送冪等，不同 response/verification conflict。

### 3.2 V3-0A dependency修改

```text
apps/api/pyproject.toml          # openai==2.46.0，避免無上限範圍在未驗證時漂移
apps/api/uv.lock
```

只更新OpenAI SDK與解析器必須連動的transitive lock；先跑SDK import/typed Responses surface測試，再跑完整API regression，獨立commit。不得在此切片修改prompt、adapter或domain。

### 3.3 V3-0B預期修改

```text
apps/api/app/interview_vnext/application/noop_result.py
apps/api/app/interview_vnext/application/schema_exports.py
apps/api/app/interview_vnext/application/write_schemas.py
apps/api/app/interview_vnext/application/schemas/operation-noop-result.v1.schema.json
apps/api/app/interview_vnext/application/durable_operations.py
apps/api/tests/test_interview_vnext_noop_result.py
apps/api/tests/test_interview_vnext_recovery_postgres.py
```

`OperationNoopResult.v1`至少包含 `schema_version`、`operation_id`、`completion_event_id`、`reason_code`、`state_before_hash`、`state_after_hash`、accepted/dropped counts與verification artifact ref；validator強制before/after相同、accepted count為0、reason code非空。completion event ID進入artifact content hash，換ID不得冒充相同重送。它是domain outcome artifact，不是假command/reducer結果。

### 3.4 API

```python
async def commit_verified_noop_operation(
    uow_factory,
    *,
    tenant_id: UUID,
    operation_id: UUID,
    response_artifact: ArtifactRecord,
    verification_artifact: ArtifactRecord,
    noop_result_artifact_id: UUID,
    step_event_id: UUID,
    committed_at: datetime,
    dropped_count: int,
    reason_code: str = "no_domain_mutation",
) -> tuple[OperationCheckpoint, OperationNoopResult]: ...
```

同 transaction驗 artifact scope/state hash、保存 artifacts、CAS checkpoint、append event/outbox、commit。先取得run row lock，鎖序與command commit一致。完全相同的IDs、timestamp、response、verification與no-op語意才是冪等重送；任一不同皆conflict。不得寫 command row或 fake ReductionResult。

### 3.5 Gate

- V3-0A只產生預期dependency/lock diff，OpenAI SDK 2.46.0 typed Responses surface可import，完整API regression通過；
- `operation-checkpoint.v1` schema export byte-for-byte不變；
- no-op result serialization/schema測試；
- PostgreSQL fresh-session hydrate；
- failpoint後無半套 artifact/checkpoint/event/outbox；
- concurrent no-op只能一個 transition成功，另一個冪等或明確 conflict；
- full V2-B focused suite仍全綠。

---

## 4. V3-1——Context contracts與 ContextBuilder

### 4.1 新增檔案

```text
apps/api/app/interview_vnext/llm/context.py
apps/api/app/interview_vnext/llm/context_policies/
  turn-interpret.1.0.0.json
  episode-code.1.0.0.json
apps/api/app/interview_vnext/llm/write_context_policies.py
apps/api/app/interview_vnext/llm/schemas/
  context-packet.v1.schema.json
  context-selection-manifest.v1.schema.json
  context-budget-report.v1.schema.json
  reference-snapshot.v1.schema.json
apps/api/app/interview_vnext/application/context_builder.py
apps/api/tests/test_interview_vnext_context_builder.py
```

`write_schemas.py`/schema exports同步更新；JSON由 Pydantic source產生，不手寫兩份真相。Context policy document要有 semver、canonical hash與完整 caps/ordering。

### 4.2 型別

至少建立：

- `ContextPolicyIdentity`；
- `ContextSourceRef`；
- `ContextItemDecision`；
- `ContextSelectionManifest`；
- `ContextBudgetReport`；
- `TurnInterpretContextPacket`；
- `EpisodeCodeContextPacket`；
- `ContextBuildResult`。

所有集合有 canonical ordering validator；所有 source ref要能回到 persisted turn/evidence/reference artifact。Manifest要記 selected與excluded，不可只列 selected。

### 4.3 Builder API

```python
class ContextBuilder:
    def build_turn_interpret(
        self,
        *,
        state: InterviewState,
        employee_turn_id: UUID,
        operation_id: UUID,
        operation_definition_hash: Sha256,
        policy: TurnInterpretContextPolicy,
    ) -> ContextBuildResult: ...

    def build_episode_code(
        self,
        *,
        state: InterviewState,
        episode_id: UUID,
        reference_snapshot: ReferenceSnapshot,
        operation_id: UUID,
        operation_definition_hash: Sha256,
        policy: EpisodeCodeContextPolicy,
    ) -> ContextBuildResult: ...
```

Builder是 pure function/service，不查 DB、不呼 provider、不讀環境變數。Application先 hydrate後傳入。

固定 policy `1.0.0`：

- `turn_interpret`：65,536 UTF-8 bytes、保留8,192 output tokens；contradiction 4；correction candidates有cue 8、無cue 4；recent active evidence 6並跨區去重；
- `episode_code`：262,144 UTF-8 bytes、保留12,288 output tokens；episode evidence 256、contradiction 64、candidate 128、reference 8；任何一項超限都完整失敗，不做 first-N或摘要；
- estimator `utf8-codepoint-heuristic/1.0.0`：`max(code_points, ceil(utf8_bytes / 4))`，只作preflight；
- `ReferenceSnapshot`按URN canonical排序並以整份內容hash定址；packet/source ref同時保存snapshot hash，禁止把reference冒充 working state；
- `operation_definition_hash`由上游versioned operation document提供，Builder只保存與傳遞，不自行猜測或計算prompt identity。

### 4.4 測試矩陣

-相同 state/policy得到 byte-identical packet/manifest/hash；
-打亂 tuple輸入後仍 canonical，或 domain已保序時明確拒絕亂序；
- current turn與 preceding consultant正確；
- correction cue有/無時候選 cap為8/4；
- inactive/withdrawn evidence不進 active section；
- denied/past/hypothetical/other role在 episode context分區；
- turn context永無 reference/candidate/gold；
- duplicate evidence只出現一次並保留所有 selection reasons；
-必選內容超 budget hard fail；
- episode evidence超 budget hard fail，不靜默截斷；
- Unicode、CRLF、NFKC相似字不改原文；
- policy hash錯誤拒絕。

---

## 5. V3-2——`turn_interpret` contracts、prompt與 verifier

### 5.1 新增檔案

```text
apps/api/app/interview_vnext/llm/turn_interpret.py
apps/api/app/interview_vnext/llm/portable_schema.py
apps/api/app/interview_vnext/llm/prompts/turn-interpret.1.0.0.md
apps/api/app/interview_vnext/llm/operations/turn-interpret.1.0.0.json
apps/api/app/interview_vnext/llm/verifier_policies/turn-interpret-verifier.1.0.0.json
apps/api/app/interview_vnext/llm/operation_documents.py
apps/api/app/interview_vnext/llm/write_operation_documents.py
apps/api/app/interview_vnext/llm/write_verifier_policies.py
apps/api/app/interview_vnext/llm/schemas/
  turn-interpret-input.v1.schema.json
  turn-interpret-output.v1.schema.json
  turn-interpret-verification-report.v1.schema.json
apps/api/app/interview_vnext/application/turn_interpret.py
apps/api/tests/test_interview_vnext_turn_interpret.py
```

### 5.2 Schema portability lint

新增 CI test限制 provider-facing schema使用兩家目前可攜交集：

- root/object/array/string/number/boolean/null；
- required fields；
- `additionalProperties=false`；
-有限 enum；
-低量 `anyOf`/nullable；
-不依賴 provider會執行 `minLength/minimum/pattern`等所有 constraint。

完整 constraint仍由本地 Pydantic執行。所有可為空欄位盡量 required並用空 array/null表達，降低 optional grammar複雜度。

V3-2實際provider-facing output只有兩個nullable union（frequency value/verbatim），所有object properties皆required + `additionalProperties=false`；portable projection移除local-only`pattern/minLength/minimum/format/default`，遞迴lint nested `$defs`。Schema通過不代表proposal可寫domain，仍必須走verifier。

### 5.3 Prompt

依 reference §8建立最小 prompt，先寫3–5個 canonical examples：

-原子 action + exact quote；
-同句 action/output拆分；
-明確 correction；
-dont-know零 observations；
-工具名稱不升 skill。

Prompt fixture test確認不含 OCS/reference、JD欄位、gold label或 chain-of-thought要求。

V3-2 prompt提供5個semantic shorthand examples（atomic action、action/output拆分、correction、dont-know零observations、tool不升skill），不複製完整schema。Prompt raw bytes、input/output schema、context policy都進committed operation definition hash。

### 5.4 Proposal mapper/verifier

實作：

```python
def verify_turn_interpret_output(
    *, output: TurnInterpretOutput, context: TurnInterpretContextPacket,
    operation_id: UUID,
) -> TurnInterpretVerificationReport: ...

def accepted_evidence(
    *, report: TurnInterpretVerificationReport, session_id: UUID,
    turn_id: UUID, operation_id: UUID,
) -> tuple[Evidence, ...]: ...
```

Quote span只能由 exact substring + occurrence計算。UUIDv5固定 test vectors寫進 test。Verifier回 accepted/dropped，不 mutation input。

Verification report另保存`turn-interpret-verifier/1.0.0` policy hash；policy document固定number/non-atomic regex、reference markers、reject order與duplicate correction target=`reject_all`。Emergent topics同樣驗exact quote/occurrence。Deterministic hard rules不宣稱能證明完整自然語言entailment，unsupported-claim品質留給V3-5 dataset grader與human review。

### 5.5 測試

-所有 reason codes各一個 case；
-相同 quote重複出現時 occurrence正確；
-emoji、組合字、全形字元使用 Unicode code point；
-model偽造外部 evidence ID拒絕；
-更正 inactive或不在 context target拒絕；
-空 observations + decline合法；
-同 proposal key不同 payload失敗；
-數值 claim沒有數值 quote時拒絕；
-prompt injection文字只當 transcript；
-Pydantic schema round trip。

---

## 6. V3-3——Durable operation executor

### 6.1 新增/修改

```text
apps/api/app/interview_vnext/application/operation_executor.py
apps/api/app/interview_vnext/application/durable_operations.py
apps/api/app/interview_vnext/llm/port.py
apps/api/app/interview_vnext/llm/testing.py
apps/api/app/interview_vnext/llm/operation_documents.py
apps/api/tests/test_interview_vnext_fixed_replay_postgres.py
apps/api/tests/test_interview_vnext_recovery_postgres.py
apps/api/tests/test_interview_vnext_llm.py
```

### 6.2 Executor責任

`execute_turn_interpret()`固定組合：

1. hydrate state；
2. ContextBuilder；
3. build/persist prompt/schema/context/manifest/request artifacts；
4. prepare checkpoint；
5. start attempt；
6. transaction外呼叫 `LlmPort`；
7.驗`ModelCallEnvelope`並將完整`ModelCallResult`與visible/error supporting artifacts同transaction保存；
8.由 outcome決定 retry/fail/provider_completed；
9. parse + verify；
10. accepted Evidence建立 command，否則 no-op；
11. commit；
12.回 typed `TurnInterpretExecutionOutcome`，含 checkpoint、accepted/dropped、state hashes與 artifacts。

不要寫一個可以任意 stage/callback的「萬用 agent executor」。共用部分可抽 private helper，但 turn operation本身保持顯式。

### 6.3 retry/repair

- max attempts讀 `OperationSpec`；
- provider retry只針對 typed retryable failure；
- schema repair最多一次，且只處理provider succeeded但本地contract invalid；
- semantic repair在`turn.interpret/1.0.0`固定為0，待V3-5證據與新transition規格；
-每次 repair request有新 request artifact、attempt ID與 idempotency key suffix；
-原始 context hash不變；若 state變了，整個 operation重 prepare，不 repair舊結果。

### 6.4 PostgreSQL tests

- happy path完整 state/evidence/checkpoint/event/outbox hydrate；
- zero Evidence no-op state hash不變且無 command row；
- partial accept只寫通過 Evidence；
- duplicate request不重打 scripted port；
- crash at prepare/start/provider-result/verification/commit每點可恢復；
- provider call不在 DB transaction（用阻塞 fake + 第二 connection證明）；
- state moved during call拒絕 stale result；
- refusal/incomplete/nonretryable不進 reducer；
- retry保存每次 result，不覆寫；
- fresh process replay仍可完成。

### 6.5 落地裁決與實際gate（完成，2026-07-17）

- `claim_attempt_for_provider()`把attempt冪等重入與network-call ownership分開；雙worker只有CAS/insert贏家可呼叫provider。
- fresh process看見未過deadline的既有`CALLING`只回`PENDING`；不以相同`started_at`或attempt ID作為重打依據。
- deadline後先保存typed timeout/lost result，再以新request artifact/attempt ID/idempotency suffix重試。
- crash發生在retryable result已保存、next attempt未建立時，executor從persisted request/result重做deterministic classification並續跑，不依賴記憶體旗標。
- schema repair request包含canonical local validation errors；refusal不再被錯分為schema failure。
- ContextBuilder到prepare之間、provider call到commit之間都各有state-hash gate；stale結果不寫Evidence/no-op。
- `ModelCallEnvelope`要求所有result refs有實體artifact且scope完全相同；attempt result event索引supporting/result refs。
- focused gate：`test_interview_vnext_llm.py + test_interview_vnext_fixed_replay_postgres.py`共18 passed；recovery + fixed-replay PostgreSQL共22 passed；完整API + PostgreSQL regression為547 passed、0 skipped。

---

## 7. V3-4——Eval-only OpenAI Responses adapter

本節只保留切片摘要。已研究SDK 2.46.0實際surface並裁決schema resolver、single-call retry ownership、status/error/usage mapping、artifact格式、mocked HTTP matrix與live Capture bundle的逐步實作權威是：

[`2026-07-17-interview-vnext-v3-4-openai-responses-adapter-plan.md`](2026-07-17-interview-vnext-v3-4-openai-responses-adapter-plan.md)

實作者必須完整閱讀該文件；不得只按下列舊摘要自行補決策。

### 7.1 新增檔案

```text
apps/api/evals/interview_vnext/__init__.py
apps/api/evals/interview_vnext/README.md
apps/api/evals/interview_vnext/providers/__init__.py
apps/api/evals/interview_vnext/providers/openai_responses.py
apps/api/evals/interview_vnext/provider_config.py
apps/api/evals/interview_vnext/schema_catalog.py
apps/api/evals/interview_vnext/live_probe.py
apps/api/evals/interview_vnext/probes/turn-interpret-smoke.v1.json
apps/api/tests/test_interview_vnext_openai_eval_adapter.py
apps/api/tests/test_interview_vnext_openai_live_probe.py
apps/api/tests/fixtures/interview_vnext/openai_responses/*.json
```

直接使用官方 `openai` SDK，不經 LangChain/OpenRouter。`langchain-openai`仍可能被 v3使用，本切片不移除。

Adapter使用`responses.create(text.format=...)`送出與request artifact hash一致的portable schema，不使用`responses.parse`重生完整Pydantic schema。client固定`max_retries=0`；一個durable attempt只做一個HTTP call。

### 7.2 Config

```text
provider=openai
model=gpt-5.6                 # 研究日預設，可由 CLI/env覆寫
reasoning_effort=medium
reasoning_mode=standard
store=false                  # hard invariant，不可覆寫
truncation=disabled           # hard invariant
connect_timeout_seconds=10.0 # 不得超過request剩餘deadline
sdk_max_retries=0             # hard invariant
```

模型設定寫入 eval run artifact與 config hash；不得修改 operation definition hash來換模型。

`request.deadline_at`是總wall-clock timeout的authority，不另設可漂移的operation timeout。config只保留connect timeout；hard invariants與`max_retries=0`也必須進secret-free config dump/hash。

### 7.3 Mocked matrix

- success structured output；
- output array前面有非 message item；
- refusal；
- max output incomplete；
- content-filter incomplete與context-length 400 error；
- 400 invalid schema；
- 401 auth；
- 429 rate limit；
- 5xx；
- client timeout；
- completed但無 parsed output；
- multiple parsed messages；
- resolved model mismatch；
- usage缺欄位 limitation。

每個 fixture只保留測 adapter需要的 provider shape，標記擷取日期/API版本；不得含真 key。

### 7.4 Live probe

CLI顯式命令，例如：

```powershell
uv run python -m evals.interview_vnext.run_live `
  --case TI-001 --trials 1 --model gpt-5.6 --reasoning-effort medium
```

Probe必須實際寫 Capture run/artifacts/report，確認 resolved model、request ID、usage與 schema path；只在 console印成功不算。

---

## 8. V3-5——Turn component eval

### 8.1 新增結構

```text
apps/api/evals/interview_vnext/
  README.md
  contracts.py
  loader.py
  runner.py
  graders.py
  report.py
  cases/
    development/TI-*/
    challenge/TI-*/
  schemas/
  reports/
```

每個 case目錄：

```text
case.json
transcript.jsonl
initial_state.json
reference_snapshot.json       # turn case可為明確空 snapshot
gold.json
adjudication.md
```

Loader做 path traversal防護、schema validate、content hash、gold/transcript quote完整性與禁止 runtime讀 gold測試。

### 8.2 12 cases

依 reference §10.2建立12類，每類至少一個；development/challenge至少8/4。可從 synthetic session切片，但每 case要有不同 failure purpose。

### 8.3 Graders

- output schema；
- quote/occurrence/span；
- required/forbidden Evidence matching；
- qualifier exactness；
- correction target；
- unsupported quantification；
- no-reference leakage；
- no-op state；
- trace completeness；
- latency/token diagnostics。

Semantic match不能只用 statement exact string。Gold以 label + kind + source quote + qualifier為主；claim wording可用 normalized tokens/rubric，任何模糊 match進人工 review，不自動 pass。

### 8.4 Gate與停線

先用 ScriptedLlmPort跑 deterministic harness，再用 live adapter每 case 3 trials。Turn gate未過時：

1.逐 failure標 `context|prompt|schema|provider|verifier|reducer|gold|runner`；
2.一次只改一個 component；
3.重跑全部12 cases，不只失敗 case；
4.保存前後 config/report；
5.未過不得做 V3-6。

---

## 9. V3-6——Episode coder、Job Model verifier與 preview

### 9.1 新增檔案

```text
apps/api/app/interview_vnext/llm/episode_code.py
apps/api/app/interview_vnext/llm/prompts/episode-code.1.0.0.md
apps/api/app/interview_vnext/llm/operations/episode-code.1.0.0.json
apps/api/app/interview_vnext/llm/schemas/
  episode-code-input.v1.schema.json
  episode-code-output.v1.schema.json
  episode-code-verification-report.v1.schema.json
apps/api/app/interview_vnext/application/episode_code.py
apps/api/app/interview_vnext/application/preview.py
apps/api/tests/test_interview_vnext_episode_code.py
apps/api/tests/test_interview_vnext_episode_code_postgres.py
```

### 9.2 Proposal mapping

Candidate/inference/gap仍用 operation-local key + UUIDv5。Reference URN只可從 input snapshot選；model新增不存在URN hard reject。

Application把 accepted proposals分成：

- verified command payload；
- insufficient/conflicted candidate payload；
- rejected proposals只留 verification artifact；
- cross-episode hypotheses只留 response artifact，V5前不寫正式 candidate。

### 9.3 Neutral preview

Preview是 pure function，輸出按 CandidateKind分組的 evidence-linked JSON/Markdown，僅顯示 verified candidates。它不寫現有 JD document、不產 OCS path/op，也不把 insufficient/conflicted改寫成肯定句。

### 9.4 8 cases與 gate

依 reference §10.2建立8個 episode tasks；每個3 trials。硬檢：task/output、tool/skill、indicator三部分、reference-only、contradiction、ability/attitude。任何單 episode ability/attitude被 commit即整個 config fail。

---

## 10. V3-7——完整實驗與報告

### 10.1 Run matrix

固定：

- 20 cases；
-每 case 3 trials；
-同一 prompt/context/schema/operation hashes；
- primary config `gpt-5.6` standard/medium（或執行日官方可用且使用者核准的 quality-first model）；
-只對預先定義 failure subset做 high reasoning ablation；不得用不同 config挑各 case最佳結果拼報告。

若執行時 current official model已變，先更新 research日期/來源與 config decision，不能靜默換 model。

### 10.2 Report內容

`docs/specs/results/`或 plan核准的 results目錄新增 immutable report，至少包含：

- git SHA、dirty flag、dataset/config/prompt/context/schema hashes；
- source composition與 annotation limitations；
- case × trial hard gate matrix；
- precision/recall/qualifier與 candidate metrics；
- pass^3/variance；
- latency、input/output/cache/reasoning tokens；
- provider failure/retry；
- failure taxonomy與每個 critical trace連結；
-人工 review範圍與結論；
- `PROMOTE_TO_V4 | REVISE_V3 | REJECT_ARCHITECTURE`。

### 10.3 禁止的報告方式

-只報平均分；
-刪除失敗 trial；
-把 parse failure當0輸出後繼續；
-用 model judge總分蓋過 code hard failure；
-把同一 synthetic session切片說成20個獨立真人案例；
-沒有 domain reviewer卻宣稱專業 JD品質已證明。

---

## 11. V3-8——Final verification與文檔

### 11.1 Focused tests

實作者把實際命令回寫；至少包含：

```powershell
cd apps/api
uv run pytest -q `
  tests/test_interview_vnext_context_builder.py `
  tests/test_interview_vnext_turn_interpret.py `
  tests/test_interview_vnext_fixed_replay_postgres.py `
  tests/test_interview_vnext_openai_eval_adapter.py `
  tests/test_interview_vnext_episode_code.py `
  tests/test_interview_vnext_episode_code_postgres.py
```

再跑既有 vNext/V2-B focused PostgreSQL suite與完整 API suite。Live 60-trial command/結果與 API成本另列，不混進 unit test pass count。

### 11.2 Dependency/scope audit

- `domain/`與 `application/`不 import OpenAI SDK；
- production composition root不 import `evals.interview_vnext`；
- vNext不 import v3 `app/interview` internals；
-沒有 route、migration 0011、Web或 feature flag；
- prompt/schema/policy文件都在 registry且 hash正確；
-沒有 API key、raw secret或 gold進 Capture context。

### 11.3 回寫

- `apps/api/app/interview_vnext/README.md`；
- `apps/api/evals/interview_vnext/README.md`；
- `docs/plans/2026-07-16-interview-ai-vnext-implementation-plan.md`狀態表；
-本計畫 commit/result表；
- `docs/README.md`索引；
- results report。

只有 reference §13全部達成才標 V3完成。完成後下一步是 V4 Sufficiency Engine + Question Policy + branching simulator，不是直接 production。

---

## 12. Code review checklist

### Context

- [ ] current turn與preceding question是否永不截斷？
- [ ] turn context是否完全沒有 reference/gold/candidate？
- [ ] selection manifest是否同時列 selected/excluded與 stable reason？
- [ ] episode evidence超 budget是否 hard fail而非摘要猜測？

### Model boundary

- [ ] 模型是否只產 local proposal key，不產 domain UUID/span/DB action？
- [ ] strict schema與完整本地 Pydantic是否都存在？
- [ ] refusal/incomplete/multiple output item是否正規化？
- [ ] provider call是否永遠在 transaction外？

### Verification/state

- [ ] quote是否由原始 turn exact match後由程式算 span？
- [ ] dropped proposal是否有 stable reason且不可被 parser修補？
- [ ] 零 Evidence是否走 no-op、無 fake command/state mutation？
- [ ] stale state是否拒絕 model result？
- [ ] ability/attitude是否不會由 episode coder commit？

### Evaluation

- [ ] 20 cases是否真有20個不同 failure purposes？
- [ ] 每 case 3 trials是否全部保存？
- [ ] code hard gate是否優先於 model judge？
- [ ] gold是否不可能進 ContextBuilder？
- [ ] report是否揭露 synthetic/one-person annotation限制？

### Scope

- [ ] 無 route/Web/v3改動？
- [ ] 無 OpenAI Evals平台依賴？
- [ ] eval-only adapter未被 production import？
- [ ] 未因流行而加入 graph/multi-agent/RAG/fine-tuning？

任一答案不符合，V3不得標完成或進 V4。
