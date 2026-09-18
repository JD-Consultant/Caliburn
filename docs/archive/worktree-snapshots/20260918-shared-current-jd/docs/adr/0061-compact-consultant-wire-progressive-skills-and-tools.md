# 0061. 精簡顧問 provider wire；Skill／Tool 邊界另議

- **狀態**：Accepted
- **日期**：2026-08-14
- **Owner 核准範圍**：先解決 schema；Tool 種類、按需載入與排程留待下一輪討論
- **研究**：[`2026-08-12-ai-job-analysis-consultant-product-flow-working-research.md`](../specs/2026-08-12-ai-job-analysis-consultant-product-flow-working-research.md) §9.15–§9.16
- **修正**：ADR 0060 的 model-facing result contract；不改其產品北極星、LangChain／LangGraph runtime、單一 durable authority、員工審核、動態 Task／Duty／OPKS、自然續談、匯出與延後項目

## Context

Task 10 的真模型路徑在生成 token 前收到 `compiled grammar is too large`。當時 rich `ConsultantResult` minified JSON Schema 約 10,317 bytes；bytes 不是 Anthropic 公布的限制，真正可直接否證的結構問題是：

| 維度 | rich schema | Anthropic 公開上限 |
|---|---:|---:|
| optional parameters | 28 | 24 |
| union／`anyOf` sites | 20 | 16 |
| open-ended document payload | 有 | 會增加 grammar 與跨 provider 差異 |

公開上限計算同一 request 內 JSON output 與 strict tool schemas 的合併總數。因此即使不改任何 Tool，輸出 schema 本身也已超限；先修 model-facing contract 才是最小根因修正。把 byte 數當硬門檻、直接刪產品欄位或先拆成更多模型呼叫，都不能由這個診斷推出。

本 repo 在 2026-07-31 已有同類真機證據：rich schema 失敗後，改成 union-free compact provider wire＋pure mapper，Opus 5 真實 HTTP request 成功。官方做法也一致：以 Pydantic 等 application type 保留完整語意，provider-facing schema 另做簡化；輸出回來後再由本機型別與 deterministic rule 驗證，而不是把 rich domain object 原封不動暴露給 grammar compiler。

本輪另確認 LangChain 會把 Pydantic `$ref` 轉成 provider function schema。若每個 effect 都內嵌同形的 Evidence basis，來源／quote／Skill 結構會被重複展開；這是 wire 重複，不是產品能力。應以正規化 basis table 承載一次，再由 1-based ordinal 引用。

## Decision

1. **model-facing contract 與 application result 分離。** LangChain 的 `response_format` 改用 compact Pydantic `ConsultantModelOutput`；rich `ConsultantResult` 只存在 application boundary 之後，不直接送 provider。
2. **provider schema 全欄 required。** absence 以空字串、空陣列、明確 `none` enum、`-1` 排序 sentinel 或 `0` 無問題 basis ordinal 表示；provider schema 不含 optional、nullable union、`anyOf`／`oneOf` 或 open-ended object。
3. **不讓模型撰寫自由 JSON Pointer／任意 `after` JSON。** 文件候選改輸出 typed `target`＋stable `target_id`＋`field` 與固定 payload slots；pure mapper 才建立既有 review path 與 rich after value。Task／Duty／OPKS 新增、修改、撤回、合併、拆分、重新歸類與排序能力不減。
4. **Evidence 在 wire 正規化一次。** `analysis_bases` 保存 employee source IDs、exact quote anchors 與實際 Skill IDs；回覆、理解、注意力、Gap、文件變更、問題及充分性以 1-based ordinal 引用。越界、0 用錯、未引用 basis 或重複 payload 夾帶一律拒絕，不靜默丟棄。
5. **Pydantic 與 LangChain 承接通用機制。** Pydantic 生成 schema 並驗證 provider output，LangChain 承接 structured-output transport；Caliburn 只保留必要的 pure shape mapper 與產品 deterministic verifier。不新增 JSON repair、手寫 parser、第二份 document store 或 framework state owner。
6. **完整產品效果不因 schema 修正縮水。** wire 仍能表達員工可見回覆、可修訂理解、動態注意力／待處理、具體 Gap、待員工審核的文件變更、一般下一題／必要澄清二選一，以及可重算的充分性建議。模型結果仍須經員工審核才能改核准文件。
7. **本 ADR 不決定 Tool。** 目前 Tool 集合、Skill 載入方式與 lookup wave 行為保持原狀；Tool 是否重組、按需載入或改描述，另行研究討論後再決策。也不在本 ADR 先固定兩段式 finalization。
8. **live canary 是後續明示授權。** 本輪只跑離線 schema／mapper／runtime regression；付費 Opus 5／OpenRouter exact conformance 必須再取得 owner 明確授權，不能把未執行的 canary 寫成已通過。

## Consequences

LangChain 實際轉換後的 provider schema 已凍結以下結構量測：

| 維度 | rich schema | compact provider schema |
|---|---:|---:|
| optional parameters | 28 | 0 |
| union sites | 20 | 0 |
| open objects | 有 | 0 |
| object depth | 約 15 | 4 |
| minified bytes | 約 10,317 | 約 9,754 |

最後一列只作粗略回歸訊號，不是 provider 上限。compact schema 的 property 數較多，因為任意 JSON 被換成 typed slots；這是刻意用明確形狀換掉 grammar 分支與開放物件，不代表增加產品複雜度。

- `test_consultant_model_output.py` 凍結 Pydantic 與 LangChain 轉換後的結構量測，並覆蓋 scalar／Duty／Task／OPKS payload、Evidence ordinal、必要澄清與矛盾夾帶。
- pure mapper 產出的仍是現有 `ConsultantResult`，後續 source／quote／Skill、document path、authority、Task／Duty／OPKS 規則繼續由 deterministic verifier 與 authority seam 防守。
- 產品大方向不變：一位顧問、動態 Task／Duty／OPKS、員工原話可找回、LLM 內容先審後入、必要澄清與一般 Gap 分流、可信進度、自然離開／續談及單一可強制匯出；第一版仍不接 RAG、不讓 LLM 產生能力級別或 A、不做正式 eval。

## Rejected alternatives

- **直接刪產品欄位以縮 schema**：犧牲效果，且不是本次根因需要。
- **把 10,317 bytes 當硬上限**：官方限制按 grammar 結構與交互作用，不是單一 byte threshold。
- **繼續把 rich `ConsultantResult` 直接送 provider**：已確定超過公開 optional／union 上限。
- **把任意 `after` 改成 JSON 字串**：雖短，但會把型別錯誤推遲到自寫 parser，降低模型可理解性與跨 provider strictness。
- **未測先固定兩段式 finalization**：會增加推論、handoff 與失敗面；是否需要只能由 exact conformance 決定。
- **順便更改 Tool／Skill 排程**：超出 owner 本輪「先解 schema、Tool 之後討論」的授權。

## Sources

- [Anthropic — Structured outputs](https://platform.claude.com/docs/en/build-with-claude/structured-outputs)
- [OpenAI — Structured Outputs](https://developers.openai.com/api/docs/guides/structured-outputs)
- [Google Gemini — Structured output](https://ai.google.dev/gemini-api/docs/structured-output)
- [LangChain — Structured output](https://docs.langchain.com/oss/python/langchain/structured-output)
- [Pydantic — JSON Schema](https://docs.pydantic.dev/latest/concepts/json_schema/)
- [`2026-07-31-anthropic-strict-schema-grammar-limit-research.md`](../specs/2026-07-31-anthropic-strict-schema-grammar-limit-research.md)
- [`2026-07-31-context-engineering-model-facing-contract-research.md`](../specs/2026-07-31-context-engineering-model-facing-contract-research.md)
- [`2026-07-31-task-analysis-compact-wire-contract-plan.md`](../plans/2026-07-31-task-analysis-compact-wire-contract-plan.md)
- [`2026-07-31-job-analysis-attributed-live-smoke`](../experiments/2026-07-31-job-analysis-attributed-live-smoke/README.md)
