# Interview AI vNext：Production OpenRouter 與最小顧問 Loop 研究

- 狀態：implemented and live-smoke verified
- 日期：2026-07-23
- 產品範圍：本機 Web、單一員工、單一職務說明書
- 上位決策：[ADR 0035](../adr/0035-interview-vnext-openrouter-first-provider-boundary.md)、[ADR 0036](../adr/0036-interview-vnext-provider-binding-conformance-and-idless-turn-v2.md)、[ADR 0038](../adr/0038-interview-vnext-context-engine-and-professional-consultant-workflow.md)
- 前置：[question.select research](2026-07-23-interview-vnext-question-selection-context-loop-research.md)
- 實作計畫：[production loop plan](../plans/2026-07-23-interview-vnext-production-openrouter-consultant-loop-plan.md)

## 1. 這一步解決什麼

目前已有：

- `turn.interpret`：把員工回答轉成可追溯 Evidence 與 interpretation receipt；
- `QuestionAgenda + ContextBuilder + question.select`：從少量高價值缺口選下一題；
- Authoring Core：保存 task／output，並讓員工接受、修改、拒絕 AI proposal；
- durable operation／Capture／provider conformance：可驗證模型實際怎麼被呼叫。

但 `question.select` 仍只跑 scripted model，OpenRouter adapter 仍放在 `evals/`，也沒有一個 production application service
把解讀、控制判斷與下一題接成一輪。因此本切片的目標是完成「真實訪談後端」，不是做完整 UI。

```text
committed employee turn
  -> durable turn.interpret
  -> application-owned STOP / episode control
  -> deterministic JobStateDigest + QuestionAgenda
  -> bounded question.select context
  -> production OpenRouter LlmPort
  -> local schema + semantic verification
  -> atomic durable command plan
  -> committed consultant question + QuestionFrame
```

## 2. 2026-07-23 官方介面核對

### 2.1 保留 Chat Completions，不改用 Beta Responses

OpenRouter 的 Responses API 文件仍明確標示 Beta，且目前只支援 stateless；Chat Completions 的 structured outputs 已有正式
`response_format.type=json_schema`、`strict=true`，並建議配合 `provider.require_parameters=true`。本專案現有 Chat adapter
已經以真實 wire capture 驗證 routing metadata、error、usage、cache 與 conformance，現在改 Responses 只會重新引入未知，
不會直接提高訪談品質。

裁決：

- production 第一版沿用 `POST /api/v1/chat/completions`；
- structured output 使用 strict JSON schema；
- Responses API 等離開 Beta，且本 operation 的 eval 證明有品質或成本收益後再評估；
- provider conversation state 不作為產品記憶，context 仍由 application 每輪重建。

來源：

- [OpenRouter — Responses API Beta](https://openrouter.ai/docs/api/reference/responses/overview)
- [OpenRouter — Structured Outputs](https://openrouter.ai/docs/guides/features/structured-outputs)

### 2.2 路由與資料處理維持 fail closed

OpenRouter 官方 provider routing 支援 `order`、`only`、`allow_fallbacks`、`require_parameters`、`data_collection` 與 ZDR。
Router Metadata 必須用 `X-OpenRouter-Metadata: enabled` 明確要求；plugin 可能改寫 request／response；response caching 仍為
Beta。產品第一版的可重現品質比省少量 token 更重要。

因此維持：

- exact model slug + exact upstream endpoint；
- `allow_fallbacks=false`、`require_parameters=true`；
- router metadata enabled；
- mutating plugins顯式 disabled；
- response cache disabled；
- adapter 零 retry，retry 只由 durable executor掌握；
- wire result與route conformance分離，metadata不足即不宣稱 eligible；
- API key只由composition root從環境讀取，不進config hash、artifact或log。

來源：

- [OpenRouter — Provider Routing](https://openrouter.ai/docs/guides/routing/provider-selection)
- [OpenRouter — Router Metadata](https://openrouter.ai/docs/guides/features/router-metadata)
- [OpenRouter — Plugins](https://openrouter.ai/docs/guides/features/plugins/overview)
- [OpenRouter — Response Caching](https://openrouter.ai/docs/guides/features/response-caching)
- [OpenRouter — ZDR](https://openrouter.ai/docs/guides/features/zdr)
- [OpenRouter — Data Collection](https://openrouter.ai/docs/guides/privacy/data-collection)
- [OpenRouter — Errors](https://openrouter.ai/docs/api/reference/errors-and-debugging)

### 2.3 第一版成本／品質 profile

Owner 指定先使用較便宜的模型。2026-07-23 以 OpenRouter 官方 Models API 查得：

- request model：`openai/gpt-5.4-mini`；
- permanent canonical slug：`openai/gpt-5.4-mini-20260317`；
- development endpoint tag：`openai/flex`，provider identity為`OpenAI`；
- 400K context、128K max completion；
-支援`structured_outputs`、`response_format`、`reasoning`與`reasoning_effort`；
- OpenRouter標價為每百萬token US$0.75 input／US$4.50 output。

標準`openai`endpoint為每百萬token US$0.75／US$4.50；`openai/flex`目前半價。Owner裁決開發與paid smoke先
使用flex節省成本，正式互動版再以實測延遲決定是否切回standard。第一版開發profile採：

```text
model = openai/gpt-5.4-mini
endpoint = openai/flex
reasoning_effort = low
reasoning_exclude = true
```

`low`與flex都是起始profile，不是永久品質結論。後續以真實員工回答比較`none|low|medium`及`flex|standard`的問題品質、
Evidence precision、延遲與成本，再調整binding；domain與operation contract不綁死模型。

來源：

- [OpenRouter — GPT-5.4 Mini](https://openrouter.ai/openai/gpt-5.4-mini/api)
- [OpenRouter — Models API](https://openrouter.ai/docs/guides/overview/models)

## 3. Provider 升格方式

不得讓 production `app/` import `evals.*`，也不得複製一份 OpenRouter response parser。正確依賴方向是：

```text
app.interview_vnext.llm.LlmPort
             ^
             |
app.interview_vnext.providers.openrouter
             ^
             |
evals.interview_vnext (fixtures / batch / quality gates)
```

將已驗證的下列能力移到 production package：

- output schema catalog；
- model／endpoint catalog snapshot與preflight；
- secret-free OpenRouter config與binding builder；
- router metadata normalizer；
- Chat Completions adapter。

`evals/` 保留相容 import wrapper與 eval orchestration，但不再擁有第二份 provider wire implementation。production命名拿掉
`Eval`；舊eval名稱只作相容 alias。`contains_test_data`改成config中的明確布林，adapter建立artifact時不可再硬編碼`true`。

## 4. `question.select` durable executor

不建立萬用 agent runner，也不複製整份 `execute_turn_interpret()`。共用的是已存在的 durable primitives：

1. build與保存 prompt／schema／context／manifest／binding／config／projection／request artifacts；
2. `prepare_operation`；
3. `claim_attempt_for_provider`；
4. transaction外呼叫 `LlmPort`；
5. `record_attempt_result`保存wire result、execution evidence、conformance；
6. parse `QuestionSelectOutput`；
7. application verifier；
8. materialize既有domain command plan；
9. 同一transaction順序reduce全部command並commit checkpoint。

`question.select` 保持顯式 executor。它不需要繼承或動態註冊 arbitrary node；operation-specific context、output、verifier與
materializer仍直接可讀。

### 4.1 為什麼 command plan 要原子提交

一次選題通常產生：

- `AppendConsultantQuestionCommand`；
- 加上 `TransitionGapCommand(...ASKED...)`，或 `OpenEpisodeCommand`。

若各自commit，第一步成功、第二步失敗會留下「畫面有問題但gap仍未asked」的半套狀態。因此新增的最小durable能力只做一件事：
在同一UoW內按既定順序套用一個非空command tuple，全部成功後才把operation標為committed。不是建立通用graph engine。

## 5. Loop control

模型不決定流程 mutation。最新 `TurnInterpretationRecord` 是上層 Loop 的判斷輸入。

### 5.1 STOP

`dialogue_act=stop` 時：

- 不呼叫 `question.select`；
- 以既有 `TransitionSessionCommand` 將 active／paused session轉為`finishing`；
- 不在同一動作直接聲稱JD完成；文件整理與員工確認是後續節點。

### 5.2 episode換題

第一版只處理可確定的控制：

- `explicit_shift`：把當前 `open|asked` gap轉`deferred`，原因固定為員工明確換題；
- active episode依序 `open -> closing -> closed`，closed turn使用觸發shift的employee turn；
- 然後在無active episode的state上建立agenda，讓`question.select`以`broaden_coverage`問下一項主要工作。

`possible_shift`與`possible_close`不自動關閉episode；它們只是訊號，避免模型一句不確定判斷造成不可逆流程切換。
episode budget耗盡時由agenda提供`offer_finish`，先問員工，不自動完成。

## 6. 這一版明確不做

- Web頁面與API route；
- K/S、行為指標、主要職責與匯出；
- `episode.code`或文件proposal生成；
- SaaS、登入、組織、權限、billing；
- LangGraph／multi-agent／provider-owned memory；
- direct OpenAI／Anthropic production adapter；
- 大型quality eval或自動模型切換；
- migration或新table。

## 7. 驗收

- production package沒有`evals.*` import；
- eval adapter測試重用production implementation且保持綠；
- output schema catalog同時支援`turn.interpret`與`question.select`；
- scripted real-PostgreSQL vertical能durably commit consultant question + QuestionFrame；
- STOP不呼叫question model；
- explicit shift能先關閉舊episode，再產生下一工作問題；
- OpenRouter live smoke成功回傳可通過local verifier的`QuestionSelectOutput`；
- API key不出現在git、artifact、bundle或輸出；
- no migration、無Web／SaaS擴張。

## 8. 實作後核對

2026-07-23 實作結果符合本文裁決：Chat Completions、application-owned context、exact provider route、
structured output、本地 semantic verification、durable command plan與 deterministic loop control均已落地。
GPT-5.4 mini 的 `openai/flex` 真實 smoke 以一個 upstream attempt通過，成本
`US$0.000558375`；沒有靠 fallback、cache、plugin mutation或 provider-held conversation state。

這證明的是 wire/runtime 主線可用，不是「已達專業顧問品質」。問題品質仍需在 local Web 有真實多輪訪談後，
以員工回答、Evidence precision、追問價值、JD task/output完整性與訪談負擔評估。下一步應做可見產品 vertical，
不應再延伸底層框架。
