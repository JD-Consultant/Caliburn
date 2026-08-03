# R1 T3 六臂、Trial Manifest 與 capture 實作研究

- 日期：2026-08-03
- 狀態：Research complete；供 R1 T3 使用
- 範圍：A1～A6 registry、48／80 計數、三層 capture、immutable Trial Manifest、failure evidence
- 不含：blind grader、CLI、OpenRouter adapter／preflight、exact live model／endpoint 選擇、live 或付費呼叫

## 1. 結論

T3 應全部留在 `evals.professional_consultant.r1` 外圈，不改 T2 的 provider-neutral operation seam。以 strict／frozen
Pydantic value 建立六臂 registry、快篩計畫、artifact reference、trial evidence 與 manifest；capture writer 以 UTF-8 canonical
JSON 寫入三個 artifact，最後才以 create-only 方式發布 manifest。reader 必須重算 SHA-256、核對 artifact kind／ID／相對路徑，
任何缺檔、重複 trial、digest 不符或未列入 manifest 的輸入都 fail closed。

三層最小形狀如下：

1. `source_state_snapshot`：`R1CaseMetadata` 與實際 `TaskDiscoveryInput`；不含 expectations／adjudication。
2. `context_operation_input`：依呼叫順序保存 T2 的 neutral `StructuredOperationRequest`；一次呼叫一筆、兩階段兩筆。
3. `trial_evidence`：每次 attempt 的 output 或 typed failure、最終 `TaskDiscoveryOutput` 或 `OperationFailure`，以及**回應實際提供**的
   generation ID、resolved model、provider／endpoint evidence。

單一 `TrialManifest` 至少快照 `trial_id`、case／family／source type、arm 的完整配置、預期 generator calls，以及上述三層的
`artifact_id + kind + relative_path + sha256` reference。Pydantic `frozen=True` 只保護記憶體 value；磁碟不可變性仍需 create-only
publication 與讀回 digest 驗證共同承重。

## 2. 一手來源與實作含義

### Pydantic

- [Faux immutability](https://docs.pydantic.dev/latest/concepts/models/#faux-immutability)說明 `ConfigDict(frozen=True)` 會阻止
  attribute assignment，但巢狀可變物件仍可被改。因此 manifest／artifact contract 應沿用 repo 既有 frozen base，集合用 tuple、
  reference 用 frozen model，不放可變 `dict` 作核心欄位。
- [Serialization](https://docs.pydantic.dev/latest/concepts/serialization/#json-mode)說明 `model_dump(mode="json")`／
  `model_dump_json()` 會轉成 JSON-compatible value。writer 應先產生固定排序、無 NaN 的 canonical bytes，再對**實際寫入 bytes**計 digest；
  不對 Python object 的非固定呈現計算。

### Python 標準庫

- [`open()` modes](https://docs.python.org/3/library/functions.html#open)定義 `x` 為 exclusive creation、檔案已存在即失敗；這比
  `w` 的 truncate 語意適合一次 trial 一份且不可覆寫的 manifest。artifact 先寫、manifest 最後寫；沒有 manifest 的目錄視為未發布，
  reader 不把它算成 observation。
- [`hashlib`](https://docs.python.org/3/library/hashlib.html)保證提供 `sha256()` 並可輸出 `hexdigest()`。SHA-256 在此只驗證 reference
  指向的 bytes 未變，不宣稱機密性、簽章或完整 audit system。

### OpenRouter

- [Router Metadata](https://openrouter.ai/docs/guides/features/router-metadata)說明 routing metadata 必須 opt in 才會出現在 response，
  `requested` 可能與實際服務的 provider／model 不同，成功回應會標示 selected provider／model 與 attempts。metadata 可能缺席
  （例如 cache hit、部分早期 failure），shape 也可增加新 optional fields；因此 capture 應 permissive decode 未知欄位，但不可用 request
  補造 resolved facts。
- [Model Fallbacks](https://openrouter.ai/docs/guides/routing/model-fallbacks)明示最終使用模型由 response body 的 `model` 回報；
  [Generation metadata](https://openrouter.ai/docs/api/api-reference/generations/get-generation)則以 generation ID 回傳 `model` 與
  `provider_name`。目前所引官方契約未承諾一個可由 request 安全推得的獨立 permanent endpoint ID；若 response／generation evidence
  沒有足以辨識 exact endpoint 的欄位，T3 evidence 必須記為缺失，T4 preflight 應 fail closed，不得抄 requested provider slug。

## 3. Repo 現況診斷

- T1 的 `R1EvalModel` 已是 `extra="forbid"`、`frozen=True`、`strict=True`，runtime loader 已把
  expectations／adjudication 隔離；可直接作 T3 value base 與 source snapshot 輸入。
- T2 runner 只有 neutral request／response，且 provider response 只帶 `output_text`；`ScriptedProvider` 保存 neutral requests，尚無
  resolved response evidence、manifest、capture 或六臂 harness。resolved facts 應由 eval 外圈觀測 provider 包裝器保存，不回灌 core。
- 現有 minimal／full `PromptProfile` 不足以代表 ADR 0040 的 minimal／full **harness bundle**。T3 必須另有明確
  `HarnessProfile` 並把完整 arm 配置快照進 manifest；若執行只換 prompt，不得把 A1 vs A6 報告成已完成 harness ablation。
- repo 雖有 historical vNext capture／eval 程式，但 ADR 0040 禁止重用其 state、schema、loader、grader 或 capture authority；T3 採
  greenfield 小型 contract／writer／reader，不 import 或 wrap vNext。

## 4. 六臂 registry 與可稽核計數

registry 必須是固定、可逐欄 literal 比對的六筆資料，不以笛卡兒積動態多生 arm：

| Arm | Model tier | Schema | Runner | Harness | Calls/case |
|---|---|---|---|---|---:|
| A1 | strongest | light | once | minimal | 1 |
| A2 | strongest | light | two-stage | full | 2 |
| A3 | strongest | heavy | two-stage | full | 2 |
| A4 | cheap | light | two-stage | full | 2 |
| A5 | cheap | heavy | two-stage | full | 2 |
| A6 | strongest | light | once | full | 1 |

快篩 plan 在執行前固定 `6 arms × 8 case IDs = 48 trial slots`，以及
`(A1 + A6) × 8 × 1 + (A2～A5) × 8 × 2 = 80 expected generator calls`；grader calls 使用獨立欄位／流程，
不得混入 80。audit summary 另從 artifacts 計算 `terminal_trials`、`actual_generator_attempts`、`evaluable_observations` 與 failure counts，
不可直接回填計畫常數。

每個 trial 無論成功或失敗都應有 terminal evidence：provider failure 保存該 attempt 與安全 typed failure；JSON／schema／verifier failure
保存 T2 `OperationFailure`；capture/integrity failure 則是 harness failure，不假裝成模型品質。兩階段 stage 1 fail-fast 會使實際 calls 少於
80，summary 必須顯示矩陣未完整；不得以預期的第二次呼叫補數。只有 48 個 trial slots 都有可讀 manifest，且實際 attempt／可評 observation
符合政策時，才可稱快篩 execution complete；仍只能淘汰明顯錯誤，不能宣稱勝出。

## 5. 選項比對與 T3 裁決

| 選項 | 問題 | 裁決 |
|---|---|---|
| 單一巨大 `trial.json` | 三層無獨立 reference，無法確認 source/context/evidence 是否混寫 | 不採 |
| frozen Pydantic 就宣稱磁碟 immutable | 只是 faux immutability；既有檔仍可被 truncate | 不採 |
| 三層 canonical artifact + digest ref；manifest create-only 最後發布 | 形狀小、可讀回驗證、缺 manifest 可辨識未完成 publication | **採用** |
| `resolved_model = requested_model` 或 requested endpoint fallback | 路由／fallback 下會產生假證據 | 禁止 |
| expected 48／80 直接當 actual | provider fail-fast 或遺漏 trial 仍會被誤報完整 | 禁止；actual 從 evidence 計 |

這些都是 ADR 0040 已接受的六臂與 capture 邊界之局部實現，不新增不可逆決策，無需新 ADR。

## 6. 明確留給 T4

T3 不選 strongest／cheap 的 exact model slug，不建立 OpenRouter HTTP／SDK adapter，不送
`X-OpenRouter-Metadata`，不查 generation endpoint，不實作 `require_parameters`／fallback-off preflight，不做 blind grader 或 CLI，亦不做
live／paid call。T3 只讓 scripted response evidence 可明確提供與 request 不同的 resolved facts，並測出 harness 絕不由 request 推斷；
真正 OpenRouter 欄位 extraction、exact endpoint 可證性與缺欄位 failure policy由 T4 adapter/preflight 驗證。
