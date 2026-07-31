# Job Analysis attributed live smoke：執行結果

日期：2026-07-31
狀態：**run 1 於 turn 1 停線（400，US$0）；run 2 以精簡 wire 契約重跑，turn 1 通過（US$0.058195）**
計畫：[2026-07-31 attributed live smoke plan](../../plans/2026-07-31-job-analysis-attributed-live-smoke-plan.md)
研究：[OpenRouter 歸因與最小 live smoke](../../specs/2026-07-31-job-analysis-openrouter-attribution-and-live-smoke-research.md)

## 0. Run 2（2026-07-31 12:09 UTC）：wire 契約修正後，turn 1 通過

`compiled grammar is too large` 已解除。以下三節（§1–§5）保留 run 1 的原始紀錄，**不修改**。

| 項目 | 值 |
|---|---|
| commit | `97bca87`（`dirty: false`） |
| 指令 | `uv run python scripts/job_analysis_live_smoke.py --max-generation-calls 1 --budget-usd 0.20` |
| run id | `20260731T120931Z` |
| generation calls | **1**（本次授權上限 1） |
| retry | **0** |
| 實際支出 | **US$0.058195**（prompt 5,399 tok = US$0.026995；completion 1,248 tok 含 155 reasoning = US$0.0312） |
| HTTP | 200 |
| response id | `gen-1785499775-Vn5OY2FTlvgOKuKPDxwn` |
| schema | `task_analysis_result.v2`，`strict: true`，`sha256:0cbc27a5fc430357…`，**4,084 bytes** |
| prompt hash | `sha256:a7866627139d8107…`（5,090 bytes） |
| turn outcome | **committed**（verifier 通過、transition 套用、authority_generation 1） |
| 建立的文件 | `33a963c1-5d4a-4507-ba65-9b3c38f71ea2`（留在本機 dev DB） |
| raw capture | `output/job-analysis-live-smoke/20260731T120931Z/`（gitignored） |

`stopped_reason` 是 `turn 2 was not sent: already used 1 of 1 generation calls` —— 這是**預期的**，
本次授權只買一次呼叫來驗證 grammar，不是失敗。

### Route 歸因

`strategy: direct`、`attempt: 1`、`provider: Anthropic`、pipeline 空、`region: TPE`、
`endpoints.total: 7` 且 `available` 恰好一個 `selected: true`。

`quality_eligible = false`，**唯一一項 limitation**：

> `selected model did not match the preflight catalog endpoint`

catalog 報 `anthropic/claude-opus-5`，router 實際選 `anthropic/claude-opus-5-20260723`
（alias 背後的日期快照）。這是**已知的 fail-open 降級，不是路由問題**——路由本身完全乾淨。
判準刻意用精確比對，**本檔不放寬它**；要不要讓判準接受「alias → 其日期快照」是獨立決策。

### 這一輪模型實際產出了什麼

**這不是品質 gate**（單次、合成場景、無 rubric），只記錄觀測到的事實：

- 2 個 Task：`每週彙整服務錯誤與效能資料並產出營運週報…`（enablers: Python、Excel）、
  `維護門市資料匯入程式，確保每日門市資料準時進入系統`（enabler: Java）。
- 1 個 open issue（`責任邊界不明`）：員工說「版本上線時，我會協助正式環境部署」，
  模型判定無法分辨是本人責任的獨立工作或他人工作的支援步驟，逐字引用該句並追問。
- 0 個 exclude。next_question 指向該 open issue，問題具體到可以接短答。
- Enabler 硬規則有作用：Python／Excel／Java 都進了 `enablers`，沒有任何一個被升格成 Task。

### 仍未被本次觀測到的

三回合場景只跑了第一回合，因此**跨回合記憶、更正／撤回、merge／split、Proposal 決策**
都還沒有真模型的觀測。要驗證這些需要另外的授權。

---

## 1. 結論（run 1，2026-07-31 08:35 UTC）

三回合場景**沒有跑完**。第一回合的請求被 Anthropic 以 HTTP 400 拒絕，原因不是模型輸出不好，
而是**本產品的 strict output schema 編譯出的 grammar 過大**：

```text
{"type":"error","error":{"type":"invalid_request_error",
 "message":"The compiled grammar is too large, which would cause performance issues.
            Simplify your tool schemas or reduce the number of strict tools."},
 "request_id":"req_011CdZq1Xf7ubQGu1zGfADnz"}
```

請求在生成任何 token 之前就被拒絕，因此 **US$0**、沒有 transcript。

**產品層含意（強推論，非直接觀測）**：production 的 `get_job_analysis_adapter()` 與這次 smoke 走
同一個 `OpenRouterAdapter.build_body()`、同一份 `task_analysis_result_provider_schema()`
（schema `sha256:a233699…`）、同一組 provider 設定；兩者的 `response_format` 區塊逐位元組相同，
差別只有 smoke 多加的兩個診斷 header。因此**在這個 route 上，員工的每一個 AI 回合現在都會撞到同一個 400**。
本檔沒有另外對 production route 送請求來直接證明這一點。

**不得由本檔推得的結論**：模型品質、prompt 好壞、Task 邊界、工具處理、更正處理、跨回合記憶
——這些一項都沒有被觀測到。

## 2. 執行紀錄

| 項目 | 值 |
|---|---|
| commit | `9966255`（`dirty: false`） |
| 指令 | `uv run python scripts/job_analysis_live_smoke.py --budget-usd 0.75 --max-generation-calls 3` |
| run id | `20260731T083501Z` |
| generation calls | 1（上限 3） |
| 實際支出 | **US$0**（回應沒有 usage／cost；請求被拒，未生成 token） |
| 該次 reserve | US$0.174855（14,491 request bytes × 0.000005 + 4,096 × 0.000025） |
| retry | 0（停線後未重送，未改 prompt） |
| PostgreSQL migration | `0013 (head)` |
| 建立的文件 | `a6c7e248-efb1-42ab-be65-ff3aa68dc235`（title 含 `[synthetic live smoke]`，留在本機 dev DB） |
| 最終 state | 0 個 Task、1 個 conversation turn（只有開場白）；**沒有任何半套資料落地** |
| raw capture | `output/job-analysis-live-smoke/20260731T083501Z/`（gitignored；manifest / catalog / turn-01 / summary） |

先前 2026-07-31 稍早的一次 dry preflight 曾因 `anthropic` endpoint `status = -2` 停線
（0 call、US$0）；本次執行前重查已回到 `status = 0`，價格與能力不變，才進入付費步驟。

## 3. 請求事實

| 項目 | 值 |
|---|---|
| model | `anthropic/claude-opus-5`（provider `anthropic`、`allow_fallbacks: false`、`require_parameters: true`） |
| max output tokens | 4096；`reasoning.effort = high` |
| prompt hash | `sha256:43a03d3b18eaad99…` |
| schema hash | `sha256:a2336995ac69a737…`，`strict: true`，name `task_analysis_result.v1` |
| **schema 大小** | **6,818 bytes** |
| 整包 request | 14,491 bytes |
| 動態 packet | 551 字元 |
| 固定 instructions | 3,093 字元 |

Context 一點都不大（551 字元）。過大的是**輸出契約本身**，與對話長度無關——這代表它不會隨著
訪談變短而自行好轉。

## 4. Route 歸因

| 欄位 | 值 |
|---|---|
| strategy | `direct` |
| attempt | 1 |
| requested | `anthropic/claude-opus-5` |
| endpoints | `total: 7`，`available: [{provider: "Anthropic", model: "anthropic/claude-opus-5-20260723", selected: false}]` |
| region | `TPE` |
| pipeline | 空 |
| usage／cost | 無 |

`quality_eligible = false`，limitations 三項：cost 無法核算、response model 不符、沒有恰好一個
selected endpoint。這是**正確的 fail-closed**：請求被拒時本來就不該有可用的品質歸因。
路由本身沒有問題——它直達 Anthropic、第一次嘗試、沒有 fallback、沒有 pipeline 介入。
`available[0].model` 顯示 alias 背後的實際快照是 `anthropic/claude-opus-5-20260723`。

## 5. 失敗分類

依計畫 §Step 4 的順序，第一個適用類別是 **1 `provider_or_attribution`**：provider 回錯、
沒有 cost、沒有 selected endpoint，因此該 trial 無歸因資格。

但**可行動的根因在 schema 層**：Anthropic 拒絕的是 `response_format.json_schema` 的
`strict: true` 編譯結果，不是輸出內容。它不屬於類別 3 所指的「輸出 invalid／verifier rejected」
（那需要先有輸出），也完全不是類別 4 的 prompt／rubric 問題。

依計畫與 owner 指示，**本輪不修、不調 prompt、不重跑**。

## 6. 最小後續工作（run 1 當時的規劃；1 與 2 已於 run 2 完成，見 §0）

1. **確認限制的形狀。** 是 Anthropic 近期收緊 grammar 編譯上限，還是本 schema 一直就超過？
   查官方 structured output 限制，並量出目前 schema 觸發上限的是哪幾段（巢狀 union、
   `TaskChangePayload` 的多形載荷、多個 enum）。
2. **決定契約要往哪邊讓。** 兩條互斥方向：縮小 strict schema 的 grammar 體積，或改送
   非 strict 的 portable schema、把責任完全交給既有的 deterministic local verifier。
   後者會動到 ADR 0040 決定 26（portable structured output ＋ `strict: true`），
   **必須另開研究與 ADR，不能當成 bug fix 直接改**。
3. **修好後重跑同一支 CLI。** 本次的 budget、recording transport、三回合 driver 與 capture
   格式都沒有被否定，可原樣重用；場景不改，仍是 3 calls／US$0.75／零 retry。

## 7. 已知限制

- 本次沒有任何模型輸出，因此計畫 §Step 3 的八項語意判準（tools、work boundaries、correction、
  cross-turn memory、grounding、consultant question、durability、route）**只有 route 一項有結果**。
- 單次 trial 不能宣稱穩定性；本檔也不比較模型或 effort 設定。
- route 證據只說明 OpenRouter 回報了什麼，不是 Anthropic 的獨立簽章。
- 這不是瀏覽器 E2E：UI 點擊、CORS 與前端錯誤顯示都未驗證。
