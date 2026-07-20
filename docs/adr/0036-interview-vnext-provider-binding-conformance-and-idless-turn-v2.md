# 0036. Interview AI vNext：runtime binding/conformance 分層與 ID-less Turn Interpreter v2

日期：2026-07-18

狀態：Accepted（R1–R4 已實作；Turn Interpreter R5 部分由 ADR 0037／2026-07-20 amendment 修訂）

依據：

- [`../specs/2026-07-18-interview-vnext-llm-runtime-architecture-review.md`](../specs/2026-07-18-interview-vnext-llm-runtime-architecture-review.md)
- [`../plans/2026-07-18-interview-vnext-v3-5-turn-eval-harness-plan.md`](../plans/2026-07-18-interview-vnext-v3-5-turn-eval-harness-plan.md) §23 true-live 診斷

實作 authority：

- [`../plans/2026-07-18-interview-vnext-v3-5a-runtime-contract-reconstruction-plan.md`](../plans/2026-07-18-interview-vnext-v3-5a-runtime-contract-reconstruction-plan.md)

Refines：

- ADR 0034 的 deterministic Evidence workflow、app-owned state、typed operation、provider-neutral
  port、Capture/eval 與 no multi-agent 決策全部保留；
- ADR 0035 的 OpenRouter-first、exact model/endpoint、benchmark fallback/cache/plugin off、官方
  direct 只對 finalist 比較等決策全部保留；
- ADR 0035 中「route contamination 由 provider adapter直接正規化成 model failure」改為：adapter
  保存 wire outcome與execution facts，application conformance policy決定 eligibility；commit仍fail closed。

Supersedes：

- `TurnInterpretProviderProfile(provider, requested_model)` 作為完整 runtime selection contract；
- 模型輸出 `proposal_key`、以該 key 派生 Evidence ID及模型輸出 observation cross-reference；
- `turn.interpret/1.0.0` 作為 active operation；其已提交文件與Git歷史只保留追溯，不再接受新run；
- 把 provider-level schema成功、route eligibility、semantic truth與domain commit混成同一成功概念的做法。

---

## 脈絡

V3-4R 已證明 OpenRouter stable Chat、exact Claude model、exact Anthropic endpoint、single outbound
HTTP、structured output與Capture可以接通。V3-5建立repo-owned 12-case multi-trial harness後，第一次正式
true-live batch沒有得到模型品質結論，而是正確地暴露三個不同的系統缺口：

1. 模型反覆輸出underscore `proposal_key`，local contract要求kebab-case；provider portable schema
   已移除不支援的`pattern`，repair仍重犯。這是application identity責任錯交給模型；
2. exact Anthropic/direct/attempt 1的OpenRouter回應仍可能帶OpenAI moderation pipeline。wire成功與
   可宣稱「純模型benchmark」不是同一件事；
3. online grading與offline regrade建立不同`failure_reason_code` context，導致同一bundle被判grader
   drift。harness本身尚未達deterministic authority；
4. clean canary雖通過schema/local contract，仍在未明示支持時填出肯定qualifier，證明Structured
   Outputs只保證shape，不保證evidence-grounded truth。

如果只放寬regex、忽略pipeline或換成Anthropic direct，後三個問題仍存在。這次必須修正整體runtime
契約，而不是替單一test case打補丁。

---

## 決定

### 1. 保持 deterministic workflow，不改成 general agent/multi-agent runtime

固定流程仍由application掌控；模型只處理versioned typed operations。Context、Evidence、Episode、Gap、
Inference、Candidate與human review都是app-owned state。provider conversation、compaction、cache與gateway
pipeline不是business truth。

### 2. `OperationSpec`、`ProviderBinding`、adapter與conformance是四個責任

- `OperationSpec`：業務工作、input/output/prompt/context/quality/deadline/attempt identity；
- `ProviderBinding`：某部署如何以指定adapter/model/upstream/capability/policy執行operation；
- provider adapter：exact wire projection、single-call、response/error/usage/routing normalization；
- conformance policy：根據binding與normalized execution evidence判斷結果是否可用於指定用途。

provider/model/endpoint不得回填到`OperationSpec`；adapter不得自行選fallback或決定promotion eligibility。

### 3. own `LlmPort`保留，但升級為resolved-call contract

caller不能再自由填`provider/requested_model`。composition root／eval wiring先解析唯一binding，executor將
binding snapshot與schema projection存成immutable artifacts，再建立`ResolvedModelCall`交給adapter。
fresh-process recovery必須讀回原binding artifacts，不可依當下部署設定重新選模型。

### 4. wire outcome、execution evidence與conformance report分開保存

adapter即使看到route mismatch、pipeline或metadata缺失，也要在可以安全解析時保存：

- normalized wire result；
- `ProviderExecutionEvidence`；
- raw/sanitized routing artifacts。

application再產生hash-addressed `ConformanceReport`。成功wire若conformance不合格，checkpoint以
conformance artifact作failure authority，不能進local semantic verifier/reducer；raw payload仍保留診斷。

### 5. strict attribution與production-safe是不同policy identity

- `attribution-strict/1.0.0`：exact model/provider/endpoint、direct、upstream attempt 1、pipeline empty、
  cache absent/miss；unknown一律ineligible；
- `production-safe`未在本切片啟用。日後若允許已知non-mutating moderation，必須另發policy版本、
  allowlist/config hash、ablation與產品命名，不能放寬strict policy原義。

### 6. Turn Interpreter v2移除所有model-generated application identity

模型只輸出ordered observations與語意欄位，不輸出`proposal_key`、Evidence ID或observation cross-reference。
local schema通過後，application依原始array的一基ordinal，在filter/sort/dedup前派生：

```text
proposal_ref = p{ordinal:04d}
evidence_id = UUIDv5(operation_id, "observation/{ordinal:04d}")
```

被semantic verifier拒絕的proposal仍保留ref；accepted items不得因前項被drop而重新編號。模型只可從
Context Engine供應的既有opaque Evidence IDs選correction target。

### 7. Turn Interpreter先做C1 ID-less one-call，再以eval決定C2

第一個active candidate固定為`turn.interpret/2.0.0`：維持一個model call，移除identity burden，增加
unknown/unsupported qualifier規則與versioned verifier。只有C1完整12×3仍因instruction competition未達gate，
才實作T1 fact extraction → deterministic gate → T2 qualifier/signal classification。不得預設call越多越強。

### 8. Structured output、local schema、semantic verification、domain commit是四道gate

每道gate有獨立artifact/reason codes。schema valid不能直接commit；qualifier只有在employee quote明示支持
時可輸出specific value，且provider output必須為每個specific qualifier附一段該observation quote中的exact
support substring；否則必須用`unknown`、`uncertain`或`not_stated`及null support。第一版C1不以preceding
question補齊specific qualifier，短答情境列為後續獨立eval capability。

### 9. Context Engine與Capture保留；OTel只作export

現行deterministic `ContextBuilder`、selection manifest、budget與app-owned transcript保留。Binding、schema
projection、execution evidence、conformance、verification都進Capture。OpenTelemetry日後只能由Capture輸出
operational trace，不取代durable artifact/hash-chain contract。

### 10. OpenRouter仍是第一個adapter，finalist才做官方direct

本切片只改既有OpenRouter adapter與scripted port。C1先在OpenRouter完成模型初選；若Claude入選才做
Anthropic direct，若GPT入選才做OpenAI direct。不得同時建所有provider，也不得把OpenRouter綁進domain。

### 11. 不新增SQL migration 0011

Binding、provider config、schema projection、execution evidence與conformance都是immutable artifacts；既有
artifact/event/manifest表足以承載。`OperationCheckpoint`升為v2並在現有canonical JSON欄新增final-attempt
execution-evidence/conformance refs，不新增normalized DB欄。`OperationAttempt.provider/requested_model`保留作
查詢與assertion；authoritative binding仍是request引用的artifact。

vNext尚未接production route且沒有需續跑的production v1 checkpoint，因此採active contract hard cut；
不寫v1→v2資料migration。實作前若eval DB仍有v1 rows，使用既有tenant-scoped cleanup或重建eval DB，
不得偽造checkpoint升級。

### 12. V3-6保持blocked

只有以下全部成立才恢復episode coding：

1. 同一immutable trial bundle online/offline regrade byte-equivalent；
2. binding/execution evidence/conformance mocked matrix全綠；
3. C1 v2 reference gate、real PostgreSQL與full API regression全綠；
4. 新identity的完整clean 12×3 true-live batch通過engineering gate；
5. blind review與cost/route/Capture report完成。

---

## 被否決的選項

### 只放寬`proposal_key` regex

否決。這讓model繼續擁有application protocol identity，也無法解決provider schema移除pattern、qualifier
hallucination、route attribution或grader drift。

### 直接切Anthropic direct後重跑

否決作為下一步。direct可減少gateway變因，但不會修model/application contract與harness。只在Claude成為
finalist後作paired comparison。

### 建一個universal lowest-common-denominator provider client

否決。neutral contract只描述Caliburn需要的structured generation；routing、reasoning、cache、usage、
guardrail與provider config由adapter-specific contract保存，capability不足時fail fast，不靜默丟欄位。

### adapter直接拒絕並丟掉route-contaminated response

否決。commit必須fail closed，但診斷需要wire output、routing evidence與conformance reason同時存在；把它壓成
generic provider failure會失去gateway-effect ablation證據。

### 立刻拆成兩次或多次model call

否決。C2增加cost、latency與failure surface；只有C1同條件eval證明instruction competition後才取得資格。

### 新增binding/conformance資料表

否決。本階段不需要跨run SQL analytics或SLA索引；immutable artifacts與checkpoint refs已足夠。若production
證明需要按binding/provider/cost查詢，另提migration與索引，不提前正規化。

### 保留v1/v2雙active runtime

否決。vNext尚未承接production流量，雙active會讓operation registry、schema catalog、fixtures與recovery
分叉。v1 documents留作歷史，active registry、eval suite與new runs只用v2。

---

## 後果

- 短期需修改neutral LLM contracts、checkpoint JSON、OpenRouter adapter、Turn Interpreter、harness與12 cases；
  這是一次有邊界的greenfield contract cut，不是重寫domain/persistence/Web。
- migration仍停在0010；八張table、UoW、CAS、outbox與run manifest協定保留。
- `ModelCallResult`不再承擔route eligibility；execution evidence與conformance增加artifact數，但failure attribution
  與offline replay會清楚許多。
- active turn schema/operation/prompt/verifier/suite identities全部換版；舊incomplete batch永遠只有diagnostic
  value，不可補trial後混入新結果。
- OpenRouter可繼續提供一人團隊的多模型效率，又不會成為不可替換的核心依賴。
- C1若通過即可少一次model call；若不通過，C2有同一harness與binding作可信ablation，不靠直覺加複雜度。
- production promotion前仍需retry scheduling、composition root/secret wiring、shadow/canary；本ADR不提前授權route/Web。
