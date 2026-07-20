# Interview vNext — eval-only provider adapters

**Status（2026-07-20）：V3-5A R4 complete；R5 grounded short-answer authority approved/planned，paid live/V3-6仍 blocked**

Owner已核准ADR 0036；實作authority為
[`V3-5A runtime contract reconstruction plan`](../../../../docs/plans/2026-07-18-interview-vnext-v3-5a-runtime-contract-reconstruction-plan.md)，
其中R3修正依
[`R3-C corrective plan`](../../../../docs/plans/2026-07-19-interview-vnext-v3-5a-r3-corrective-plan.md)、
R4 provider wire/evidence/conformance 依
[`R4 detailed implementation plan`](../../../../docs/plans/2026-07-19-interview-vnext-v3-5a-r4-provider-evidence-conformance-plan.md)
（含 §19 執行結果）。R4 commits 為 `aee798a`（pure `openrouter_routing` normalizer）、`a814789`
（OpenRouter wire/evidence 分離＋probe/scheduler vertical cut）、`067504b`（OpenAI mocked reference
對齊）；不得重跑舊v1 batch或paid live。
active target仍是`turn.interpret/2.0.0`、ProviderBinding/execution evidence/conformance與canonical regrade；
migration維持0010。

R5 exact authority已改由
[`ADR 0037`](../../../../docs/adr/0037-interview-vnext-question-frame-contextual-evidence-and-employee-authority.md)與
[`grounded short-answer amendment`](../../../../docs/plans/2026-07-20-interview-vnext-v3-5a-r5-grounded-short-answer-amendment-plan.md)
管理。R5 active hard cut會把minimum eval/provider fixtures機械遷移到QuestionFrame、Evidence/State v3與Turn Input/Output v2，
以保持每個commit完整suite綠；R6才負責grounded short-answer多trial、gold/grader與真模型品質，不得在R5跑paid live。

- **R4 語意**：adapter 只回 wire result + normalized execution evidence（`openrouter_routing.py` pure
  normalizer：official nested/legacy flat endpoints、pipeline stage 分類、official cache header、
  §6.4 endpoint attestation）；route/model/pipeline/cache 污染是 wire success＋誠實 evidence，
  eligibility 由 application `attribution-strict/1.0.0` 判定，executor terminal reason
  `provider.conformance_failed`＝harness invalid（scheduler stop-gap）。routing artifact 升
  `openrouter_routing.v2`（無 verdict）；兩個 probe 走 taxonomy v2、保存
  result/evidence/conformance closure、report v2。
- **R4 驗收（含 R4-C／R4-C2 correctives，見 R4 plan §19.1/§19.2）**：owner review 的三個 blocker
  （`"pipeline": null` 誤判 clean、attempt/attempts 筆數矛盾仍 eligible、blank-only metadata
  造成 typed evidence ValidationError 外洩）與 follow-up 的同類 usage/cost 數值外洩
  （科學記號 cost canonical 化、非法/負數 cost/token → null＋limitation）已修正，
  共補 24 個 regression tests（先紅後綠）。完整 no-network
  **951 passed, 197 skipped, 0 failed**；全部 `test_interview_vnext_*` + real PostgreSQL
  **760 passed, 0 skipped**；dependency/schema guard **14 passed**；Alembic **0010 (head)**；
  未跑任何 live。

- R3-C exact binding/projection、typed durable gate與terminal recovery已完成；missing/tampered
  binding/config/projection/result/evidence/conformance全部fail closed且不打HTTP。
- model-call events與manifest現在direct close over request/binding/config/projection，以及每個attempt的
  result/evidence/conformance；export會拒絕missing root、forged full ref/hash與nested-ref-only manifest。
- R3-C驗收：全部`test_interview_vnext_*.py` + real PostgreSQL **653 passed, 0 skipped**；完整API
  no-network **844 passed, 197 skipped, 0 failed**；dependency guard **5 passed**；Alembic **0010 (head)**。
- R3-C沒有改route contamination wire outcome；R4（`a814789`/`067504b`）已完成wire evidence與eligibility
  分離：contamination不再產生active `ModelFailure`，failure authority是conformance report。

- V3-5 turn eval harness(`contracts`/`loader`/`identities`/`fixture_builder`/`turn_eval_runner`/
  `capture_export`/`turn_graders`/`review`/`turn_report`/`scheduler`/`batch_orchestrator`/`live_wiring`/
  `turn_eval_cli`)已落地。focused 逐檔:contracts **32**、loader **62**、fixtures **9**、
  graders/review **26**、PG reference harness **5**、runner/report/export **8**、OpenRouter CLI/wiring **14**。
- 12 個繁中 pilot cases(8 dev + 4 challenge)已凍結;suite hash
  `sha256:ed51167d64a9887f7a119568ad501ea71e1edd63eace6e44ccba222b5d763d5a`;12/12 reference output 通過
  production ContextBuilder/verifier/reducer gate,mocked 12×3 batch 端到端在 real PostgreSQL 產出
  `TURN_GATE_PASS_ENGINEERING`(harness 自測,**非** promotion-eligible)。
- **E8 online orchestration 已實作且已嘗試**：clean canary `58843af0-...`通過wire/Capture；formal batch
  `5bad4e3f-...`在18 trials／27 inference calls後因`openrouter.route_contaminated`停線。另有model-generated
  `proposal_key` contract與offline grader drift，故只有diagnostic value、不得promotion；observed cost `US$0.499882`。
- E8 focused **125 passed**；adapter regression **229 passed**；完整 API + real PostgreSQL：
  **887 passed, 0 skipped**；`app/` 不 import `evals.*`(dependency guard 強制)。

## V3-4R 既有里程碑(保留)

- OpenRouter focused mocked suite:`model_catalog`(51)+`eval_adapter`(88)+`live_probe`(9)=
  **148 passed**；OpenAI direct reference regression **66 passed**;neutral/import/fixed-replay PostgreSQL
  **23 passed**。
- **OpenRouter live gate(§15.5)已通過**：run `921f71a9-850c-48de-b8ab-4a98efd24134`，
  `anthropic/claude-sonnet-5`、permanent canonical
  `anthropic/claude-sonnet-5-20260630`、endpoint `anthropic`；direct/attempt 1、pipeline空、
  strict schema與local `TurnInterpretOutput` validation通過、bundle/hash chain/secret scan通過。
- OpenAI direct live gate(舊規格§16.5)保留為 optional GPT direct comparison,不阻擋 V3-5(ADR 0035)。
- OpenRouter 上的 Claude／GPT／Gemini 共用這個 gateway adapter;只有官方直連才各自做 OpenAI／Anthropic／
  Google adapter。V3-4R 先不接 production route,後續 promotion 移動同一實作(§16.5),不複製第二份。
- **provider metadata 已真實核對**：本次回傳flat `endpoints[] + selected=true`，top-level
  `response.model`為request ID、selected model為permanent canonical slug；adapter同時保留對
  `{available:[...], selected:{...}}` additive shape的容忍，但兩種model identity都必須受snapshot綁定。

Live bundle只在gitignored `output/`，不提交。OpenRouter未回HTTP request ID，已有明確limitation；generation
ID、usage與cost皆存在。API無法完整讀取dashboard preset／account-wide Prevent Overrides，開始V3-5付費
multi-trial前，owner仍須人工確認§15.2 account checklist；本次實際metadata已證明route direct、無pipeline／cache。

本目錄是 ADR 0034 vNext 的 **eval-only** 邊界:驗證「官方 provider API 真實 shape 能否無損映射到
V2/V3 已發布的 provider-neutral contract(`app.interview_vnext.llm`)」。

- OpenRouter主線權威規格：
  `docs/plans/2026-07-17-interview-vnext-v3-4r-openrouter-first-adapter-plan.md`。
- OpenAI direct reference規格：
  `docs/plans/2026-07-17-interview-vnext-v3-4-openai-responses-adapter-plan.md`。
- V3-5 original harness規格：
  `docs/plans/2026-07-18-interview-vnext-v3-5-turn-eval-harness-plan.md`（E0–E8已落地；舊true-live不具品質裁決資格）。
- R5 contract migration與R6 grounding quality邊界：
  `docs/plans/2026-07-20-interview-vnext-v3-5a-r5-grounded-short-answer-amendment-plan.md`。
- **production `apps/api/app/` 不得 import 本目錄**;dependency guard 測試強制。
- 本目錄已有品質harness，但新contract尚未完成true-live multi-trial，因此目前沒有promotion verdict。

## V3-5 turn eval harness 檔案

| 檔案 | 責任 |
|---|---|
| `contracts.py` | case/transcript/initial-fixture/gold/reference-output/suite-manifest/batch-plan/trial/grader-result/review-decision/case-report/batch-report 的 strict 契約 + hash-bound 定義 + N/A-preserving metrics |
| `write_schemas.py` + `schemas/turn-eval-*.v1.schema.json` | 11 份可攜 JSON Schema 的 deterministic 匯出 + drift check |
| `loader.py` | path/byte(UTF-8/LF/無 BOM/無 symlink/無未知檔)、transcript 結構、overlapping-occurrence quote、三層 runtime/evaluation/content hash、gold 隔離、suite balance |
| `identities.py` | logical key → trial-scoped UUIDv5(tenant/user/profile/session/run/turn/episode/evidence/slot/trial) |
| `fixture_builder.py` | case → 公開 durable command 序列 + 純函式 reference gate(production context/verifier/reducer) |
| `turn_eval_runner.py` | 一個 trial 的 durable 執行(fresh session/run + 公開 command replay + `execute_turn_interpret` + 同-UoW finalize);tenant-scoped cleanup |
| `capture_export.py` | read-only PostgreSQL Capture bundle 匯出 + re-validation + event chain + secret/reasoning scan |
| `turn_graders.py` | 9 個 deterministic grader、candidate edges、一對一 maximum-cardinality matching、raw/committed precision/recall/qualifier metrics |
| `review.py` | 盲化 review queue(per-edge item、隱藏 provider identity、seed 重排)+ import(hash/identity/revision gate) |
| `turn_report.py` | per-case pass^3、batch hard/quality gate、decision enum、Markdown renderer |
| `scheduler.py` | disposition 分類、infrastructure replacement、budget、atomic trial bundle + integrity manifest |
| `batch_orchestrator.py` | run → export → grade → review → report 的完整 batch 組裝(mocked 自測 12×3) |
| `live_wiring.py` | 每 batch 一次 catalog snapshot + config + preflight;eval DB 名稱安全(只接受 `_test`/`_eval`) |
| `live_batch.py` | E8 真 12×3 orchestration、attempt route/cost ledger、blind review import、immutable trial regrade + final report |
| `turn_eval_cli.py` | validate-suite / reference-gate / mocked-batch / live-batch / export-review / import-review / report;§17.2 exit codes |
| `cases/{development,challenge}/TI-*/` | 12 個繁中 pilot cases(case/transcript/initial/reference-snapshot/gold/reference-output/adjudication) |

## V3-4R adapter 檔案

| 檔案 | 責任 |
|---|---|
| `schema_catalog.py` | `output_schema_id + hash` → exact published portable schema 的封閉映射(`format_name` 中性,OpenAI/OpenRouter 共用) |
| `openrouter_provider_config.py` | secret-free OpenRouter 主線 profile(exact model/endpoint、route/plugin/reasoning/privacy hard invariants、config hash);唯一建構路徑 `build_openrouter_eval_config()` 由 snapshot 派生 |
| `openrouter_model_catalog.py` | model/endpoints GET client + immutable snapshot + §6.2 preflight(exact catalog ID、permanent canonical slug、capability、唯一 base-slug endpoint、endpoint-level 能力);無 inference |
| `providers/openrouter_chat.py` | **OpenRouter 主線**:`POST /chat/completions` 的 exact request、single-call/deadline、response/error/routing normalization、raw/routing/visible/error artifacts |
| `openrouter_live_probe.py` | opt-in 單次 OpenRouter live conformance probe + immutable Capture bundle(catalog 與 inference 分離) |
| `provider_config.py` | (reference)secret-free OpenAI Responses profile + config hash |
| `providers/openai_responses.py` | (reference)`AsyncOpenAI.responses.create()` 的 request/response/error normalization |
| `live_probe.py` | (reference)opt-in OpenAI 單次 live probe + bundle |
| `probes/*.json` | synthetic test-only probe 輸入(OpenAI / OpenRouter identity 各自獨立) |

## 不變量(摘錄;完整見規格 §1)

OpenRouter 主線(V3-4R):

- 直接 `httpx` 打 `POST https://openrouter.ai/api/v1/chat/completions`;**不新增 Beta SDK**、不 follow redirect、
  transport/adapter 皆零 retry——一個 durable attempt 恰好一次 inference POST。
- exact Models API model ID + captured permanent canonical slug + exact upstream endpoint；`allow_fallbacks=false`、`require_parameters=true`、
  `stream=false`、單一 choice、無 tools;禁 auto/free/latest/nitro/floor/online alias。
- top-level resolved model只能exact等於request model ID；router selected/attempt model只能是snapshot綁定的
  request ID或permanent canonical slug，其他model仍fail closed。
- `X-OpenRouter-Metadata: enabled` 為 hard invariant;metadata 缺失、strategy 非 direct、attempt≠1、
  selected provider/model 與 snapshot 不符、或任何 pipeline stage → route contaminated(fail closed)。
- known mutating plugins(context-compression、response-healing、web、file-parser)顯式 disabled;
  不解析 markdown fence、不修 JSON、不降級 JSON mode;reasoning text 一律 redact,不進 Capture。
- 送出的 schema 是 V3-2 published portable schema(hash 驗證);adapter 成功只到 `StructuredPayload`,
  完整 Pydantic/semantic 驗證仍在既有 V3-3 executor。

OpenAI direct(reference):

- `openai==2.46.0`、`max_retries=0`;`store/background/stream=false`、`truncation=disabled`;
  typed traversal 全部 `response.output` items,禁 `output[0]`／`output_text` 串接。

## V3-5 turn eval CLI

```powershell
cd apps/api
# 只驗 case/schema/hash/cross refs,不需 DB/key
uv run --locked python -m evals.interview_vnext.turn_eval_cli validate-suite `
  --suite-version turn-interpret-pilot.v1
# known-good outputs 走純函式 production gate(不需 DB/key)
uv run --locked python -m evals.interview_vnext.turn_eval_cli reference-gate `
  --suite-version turn-interpret-pilot.v1
# mocked 12×3 batch(需 eval DB;harness 自測,非 promotion)
$env:INTERVIEW_VNEXT_EVAL_DATABASE_URL='postgresql+asyncpg://postgres:password@localhost:5432/caliburn_test'
uv run --locked python -m evals.interview_vnext.turn_eval_cli mocked-batch `
  --suite-version turn-interpret-pilot.v1 `
  --database-url-env INTERVIEW_VNEXT_EVAL_DATABASE_URL `
  --output-dir ../../output/interview_vnext/turn-eval
# 讀回既有 batch 的 decision
uv run --locked python -m evals.interview_vnext.turn_eval_cli report --batch-dir '<path>'
```

exit codes:`0` 通過、`1` gate fail/review incomplete/batch incomplete、`2` usage/缺
key/env/checklist/budget、`3` preflight/catalog/config/harness integrity、`4` runner/DB/Capture 例外。

### E8 true live batch（已嘗試；暫停重跑）

下列命令保留作操作reference，但在
[`V3-5A實作計畫`](../../../../docs/plans/2026-07-18-interview-vnext-v3-5a-runtime-contract-reconstruction-plan.md)
的harness determinism、ProviderBinding/conformance與ID-less C1 v2完成前**不得重跑**。既有 incomplete batch 不得續跑、
補trial或裁決成model verdict；新contract必須使用新operation/suite identity建立全新batch。

```powershell
cd apps/api
$env:OPENROUTER_API_KEY='<secret>'
$env:INTERVIEW_VNEXT_EVAL_DATABASE_URL='postgresql+asyncpg://.../<name>_eval'
uv run --locked python -m evals.interview_vnext.turn_eval_cli live-batch `
  --suite-version turn-interpret-pilot.v1 `
  --database-url-env INTERVIEW_VNEXT_EVAL_DATABASE_URL `
  --model anthropic/claude-sonnet-5 --upstream-endpoint anthropic `
  --data-collection deny --zdr-required false --reasoning-effort medium `
  --quality-slots 3 --max-trial-attempts-per-slot 3 --max-concurrency 1 `
  --max-inference-calls 120 --max-observed-cost-usd 10.00 --max-wall-clock-minutes 180 `
  --account-checklist-confirmed-at '<UTC>' --account-checklist-confirmed-by '<owner>' `
  --output-dir ../../output/interview_vnext/turn-eval
```

live batch 正常先回 `REVIEW_INCOMPLETE`；之後做盲化裁決(export-review → import-review → report)：

```powershell
uv run --locked python -m evals.interview_vnext.turn_eval_cli export-review `
  --batch-dir '<batch-dir>'
uv run --locked python -m evals.interview_vnext.turn_eval_cli import-review `
  --batch-dir '<batch-dir>' --decisions '<decisions.jsonl>' `
  --failure-traces-read '<count>' --passing-trace-sample-read '<count>'
uv run --locked python -m evals.interview_vnext.turn_eval_cli report `
  --batch-dir '<batch-dir>'
```

裁決完成後回寫真 batch ID/hash/模型/endpoint/trials/cost/gate。只有
`TURN_GATE_PASS_ENGINEERING` 或更高才可把 V3-6 標 unblocked。

## V3-4R 驗收命令(保留)

```powershell
cd apps/api
# OpenRouter 主線 focused
uv run --locked pytest -q `
  tests/test_interview_vnext_openrouter_model_catalog.py `
  tests/test_interview_vnext_openrouter_eval_adapter.py `
  tests/test_interview_vnext_openrouter_live_probe.py
# OpenAI direct reference regression
uv run --locked pytest -q `
  tests/test_interview_vnext_openai_eval_adapter.py `
  tests/test_interview_vnext_openai_live_probe.py
```

OpenRouter live gate(需 `OPENROUTER_API_KEY`;主線 gate,無 default model/endpoint):

```powershell
cd apps/api
$env:OPENROUTER_API_KEY='<secret>'
uv run --locked python -m evals.interview_vnext.openrouter_live_probe `
  --probe turn-interpret-openrouter-smoke.v1 `
  --model '<exact-model-id-from-models-api>' `
  --upstream-endpoint '<exact-provider-endpoint-slug>' `
  --data-collection deny `
  --zdr-required false `
  --reasoning-effort medium `
  --output-dir ../../output/interview_vnext/openrouter-live-probes
```

無 key:exit 2、不建 run、不打 network。輸出 bundle 已 gitignore(`output/`)。
本機開發可把key放在gitignored `apps/api/.env`，但probe本身只讀process environment；launcher需先以
`python-dotenv`或shell把`OPENROUTER_API_KEY`注入目前process，且不得把key改成CLI argument。CI／production
仍由secret manager注入，不依賴`.env`。

Optional direct OpenAI probe（需`OPENAI_API_KEY`；不再是主線gate）：

```powershell
cd apps/api
$env:OPENAI_API_KEY='<secret>'
uv run python -m evals.interview_vnext.live_probe `
  --probe turn-interpret-smoke.v1 `
  --model gpt-5.6 `
  --accepted-resolved-model gpt-5.6 `
  --accepted-resolved-model gpt-5.6-sol `
  --reasoning-mode standard `
  --reasoning-effort medium `
  --output-dir ../../output/interview_vnext/live-probes
```

無 key:exit 2、不建 run、不打 network。輸出 bundle 已 gitignore(`output/`),不進 Git。
