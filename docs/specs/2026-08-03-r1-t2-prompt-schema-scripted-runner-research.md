# R1 T2 prompt、portable schema 與 scripted runner 實作研究

- 日期：2026-08-03
- 狀態：Research complete；供 R1 T2 使用
- 範圍：版本化 prompt、light／heavy provider schema、provider-neutral seam、一次／兩階段 runner、failure taxonomy
- 不含：OpenRouter adapter/preflight、Trial Manifest/Capture、live call、DB、route、Web

## 1. 結論

T2 應維持 T1 Pydantic domain contracts 為解析後真相，另建立可替換的 provider schema projection；不可把
`model_json_schema()` 原樣傳給 provider，也不可讓 OpenRouter `messages`、`response_format`、routing 或 HTTP payload 進入
operation runner。一次與兩階段 runner 共用一個 async structural `Protocol`，scripted fake 只實作這個外部邊界。

light／heavy 兩個 schema 必須保持**相同 output value shape**，避免 schema ablation 同時改變語意契約。差異只放在 annotation
重量：light 只有 portable structural vocabulary；heavy 在同一 shape 上加入明確 property `description`。兩者都由同一 domain
model 投影、都由同一 Pydantic parser 與 deterministic verifier 承重。

## 2. 一手來源與實作含義

### Pydantic 2.13.4

- [JSON Schema concepts](https://docs.pydantic.dev/latest/concepts/json_schema/)與
  [`model_json_schema` API](https://docs.pydantic.dev/latest/api/json_schema/#pydantic.json_schema.model_json_schema)說明 Pydantic
  預設產生 Draft 2020-12 schema，並允許以自訂 generator／後處理改變輸出。repo 本機盤點顯示三個 R1 output schema 含
  `$defs`、`$ref`、`const`、`title`、長度／數值 constraints 等；這些不是 ADR 0040 承諾的 portable subset。
- 因此 projection 必須 inline local `$ref`、把 `const` 正規化為 singleton `enum`，並只保留 object／array／基本型別、
  `properties`、`required`、nullable `anyOf`、`enum`、`additionalProperties: false`、`items`；不得把 domain constraints
  誤當 endpoint 可攜保證。
- parsing 仍回到原 Pydantic output model。projection 是 provider guidance，不是第二份 domain authority。

### OpenRouter

- [Structured Outputs](https://openrouter.ai/docs/guides/features/structured-outputs)要求
  `response_format.type=json_schema`、`strict: true`，並建議 property descriptions 協助模型；同頁要求先核對模型支援並搭配
  `require_parameters: true`。
- [Provider Routing](https://openrouter.ai/docs/guides/routing/provider-selection)說明 provider 預設可依序 fallback；要固定單一
  provider 必須指定 provider 並令 `allow_fallbacks: false`。這些 wire/routing 欄位屬 T4 adapter/preflight，不應進入 T2 core。
- OpenRouter 沒承諾所有 endpoint 支援同一組完整 JSON Schema keyword。故 heavy schema 只增加 annotation，不增加 local-only
  validation constraints；真正有效性仍由 Pydantic + verifier 判斷。

### Python 標準庫

- [`typing.Protocol`](https://docs.python.org/3/library/typing.html#typing.Protocol)提供 structural subtyping，適合讓 runner 只依賴
  `async generate(request) -> response`，不依賴任何 SDK 或 adapter class。
- [`json`](https://docs.python.org/3/library/json.html)預設接受重複 key 並接受 `NaN` 等非標準常數；operation output parser 應先用
  `object_pairs_hook` 與 `parse_constant` 拒絕它們，再交 Pydantic `model_validate_json()`。
- [asyncio task cancellation](https://docs.python.org/3/library/asyncio-task.html#task-cancellation)說明取消由
  `CancelledError` 傳遞；runner 只捕捉 port 明定的 provider error，不捕捉 `BaseException` 或把 cancellation 改寫成一般失敗。

## 3. 選項比對

| 選項 | 優點 | 問題 | 裁決 |
|---|---|---|---|
| 原樣送 Pydantic schema | 零 projector code | 帶入 refs、constraints、title；把 local schema 誤稱 portable | 不採 |
| light／heavy 使用不同 output fields | 差異明顯 | 同時改變可表達語意與 normalization，model×schema 比較不可歸因 | 不採 |
| 同 shape；light structural-only、heavy + descriptions | 單一 domain parser；只改 schema annotation 重量；符合 OpenRouter建議 | heavy 不代表更多 deterministic enforcement | **採用** |
| runner 直接接受 OpenRouter payload／SDK response | adapter 薄 | provider wire 穿越 operation seam，T4 preflight 與核心耦合 | 不採 |
| neutral typed request/response + async Protocol | scripted fake 簡單；未來 adapter 可替換 | T4 仍需另做 wire normalization | **採用** |

這些是 ADR 0040 已接受的 portable schema、可比較 runner 與 provider boundary 的局部實現，且可替換；不新增 ADR。

## 4. Public seam 與 failure taxonomy

公開邊界固定為：

```text
PromptArtifact + ProviderSchemaArtifact + canonical operation input JSON
  -> StructuredOutputProvider.generate(StructuredOperationRequest)
  -> StructuredOperationResponse(output_json)
  -> strict JSON parse
  -> Pydantic operation output
  -> deterministic verifier
  -> TaskDiscoveryOutput 或 typed OperationRunError
```

T2 neutral request 不得出現 `messages`、`response_format`、model slug、endpoint、provider routing、HTTP headers/status 或 raw SDK
objects。T2 response 只提供 operation output JSON；resolved model/endpoint 與 capture 由 T3/T4 的外圈 evidence seam 增加，不從
request 推斷。

失敗碼預先固定為：

1. `provider_failed`：port 明定的 provider error；不保存 raw payload。
2. `output_json_invalid`：JSON syntax、duplicate key、BOM／非標準 constant 等 wire text 問題。
3. `output_schema_invalid`：JSON 合法，但不符合該 operation 的 Pydantic output contract。
4. `verification_failed`：shape 合法，但 source span、reference、correction、支持度或重問等 deterministic rule 失敗；附
   `VerificationReport`。

兩階段 runner 在 stage 1 parse／verify 失敗時不得呼叫 stage 2；stage 2 成功後組成完整 `TaskDiscoveryOutput`，再以原始
`TaskDiscoveryInput` 驗證。一次 runner 直接解析並驗證完整 output。

## 5. T2 停線條件

- light/heavy 改變 domain output fields、偷偷補出模型沒提供的 Task 或判斷；
- provider request 出現 OpenRouter/SDK wire vocabulary；
- stage 1 invalid 仍呼叫 stage 2；
- parse/schema/verifier/provider failure 混成無法診斷的單一例外；
- catch cancellation、重試、fallback 或選 model/endpoint；這些不屬 T2；
- import v3、vNext、Authoring、eval runtime、DB、FastAPI 或 agent/Graph framework。
