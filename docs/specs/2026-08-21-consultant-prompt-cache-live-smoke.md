# Consultant Prompt Cache 實作與真實 Provider Smoke

- 日期：2026-08-21
- 狀態：**通過；本地 deterministic gates 與 GPT-5.6 Luna 真實 provider write→read 均有證據**
- 性質：成本／延遲整合 smoke，不是正式品質 eval
- 範圍：stable prompt prefix、OpenRouter content-block passthrough、cache usage receipt；不接 RAG、不生成能力級別／A、不啟用 auto-accept 或 response caching
- 研究依據：[`2026-08-21-provider-neutral-virtual-jd-editor-and-evidence-anchor-research.md`](2026-08-21-provider-neutral-virtual-jd-editor-and-evidence-anchor-research.md#67-prompt-caching值得加但只作-provider-最佳化)

## 1. 實作內容

`ConsultantContextMiddleware` 不再把 framework system prompt 與每一步動態 Context 壓成一個字串；它改送兩個有序 `SystemMessage` content blocks：

1. stable block：同一 run 不變的顧問、authority 與 Skill catalog 規則，帶 `cache_control={"type":"ephemeral"}`；
2. dynamic block：每一步從 PostgreSQL／LangGraph 重建的 employee／approved／pending／focus／gap／candidate context，不帶 cache marker。

dynamic block 保留原本位於兩段之間的所有字元（通常是前導 `\n\n`），因此 `SystemMessage.text` 與舊版「先合併、最後只 `.strip()` 一次」逐字相同。這次沒有新增 cache service、資料表、provider-specific domain DTO 或記憶層。cache miss、過期或 provider 不支援時仍會看到完整相同 prompt，只是不省成本／延遲。

本 repo 鎖定的 `langchain-openrouter==0.2.7` 已原生保留 content-block `cache_control`，也會把 OpenRouter `prompt_tokens_details.cached_tokens／cache_write_tokens` 正規化成 LangChain `input_token_details.cache_read／cache_creation`。既有 `AttemptUsage` 已保存這兩欄，因此 application 沒有重寫 adapter，只加 characterization／receipt canary。OpenRouter 對 OpenAI 採自動 prompt caching；本輪不能把命中單獨歸因於 `cache_control`。marker 保留的價值是讓需要 explicit breakpoint 的其他 provider 使用同一 content-block wire，而 OpenAI 的實證重點是穩定共同前綴、自然超過 1,024-token 門檻，以及 receipt 確實回報 write→read。

不新增 `session_id` 命中宣稱：現行 profile 手動指定 `provider.order`，OpenRouter 官方明示此時不使用 sticky routing；而本產品又固定 exact provider、禁止 fallback。也不啟用 OpenRouter response caching，避免同一舊回答或 Tool call 被完整重播。

## 2. TDD 與本地驗證

### 2.1 Stable／dynamic boundary RED→GREEN

先在真正的 PostgreSQL context middleware integration test 斷言：

- `SystemMessage.content` 必須是兩個 blocks；
- 只有第一個 stable block 有 `cache_control`；
- 完整員工原話只出現在第二個 dynamic block；
- `SystemMessage.text` 與舊版文字相同。

第一個可計入的 RED 精確失敗於：

```text
assert isinstance(actual.system_message.content, list)
False: current content was one concatenated string
```

最小 production 改動後，同一測試 `1 passed in 2.71s`。第一次嘗試連線 `caliburn_reviewed` 因該 DB 不存在而中止，未把環境錯誤冒充 RED；之後另建並遷移本機 disposable `caliburn_prompt_cache`，才取得上述正確失敗。

後續 production diff 自審又發現第一版對 stable／dynamic 各自 `.strip()`，在 stable 尾端有空白時會改變舊 prompt。先把既有整合測試改成保留兩個尾端空白，得到第二個精確 RED（預期文字有兩個空白，實際被移除）；再改成先依舊規則計算完整 prompt 的左右邊界、最後於原 stable／dynamic 分界切塊。同一回歸測試轉綠 `1 passed in 2.61s`，完整 prompt、cache breakpoint 與動態內容邊界三者同時保留。

### 2.2 Framework／receipt canary

- `langchain-openrouter` 的 `_create_message_dicts()` 保留第一個 block 的 `cache_control`，且不會替 dynamic block加 marker；
- synthetic OpenRouter usage 的 `cached_tokens=96／cache_write_tokens=24` 會映成 `cache_read=96／cache_creation=24`；
- callback 最後保存 `AttemptUsage.cache_read_tokens=96／cache_write_tokens=24`。

結果：`16 passed in 1.00s`。這是 pinned framework 的 characterization，不是自寫替代 adapter。

### 2.3 Gates 與殘留

| Gate | 結果 |
|---|---:|
| context＋model runtime focused | 34 passed |
| context＋model runtime＋run service＋agent/skills（自審修正後） | 70 passed in 22.40s |
| 完整 API，真 PostgreSQL，順序執行（自審修正後） | **269 passed in 153.33s** |

完整 suite 後：

```text
consultant_documents=0
checkpoints=0
checkpoint_blobs=0
checkpoint_writes=0
store=0
```

測試只使用新建的本機 disposable `caliburn_prompt_cache`，沒有碰既有 `caliburn` 開發資料。

## 3. GPT-5.6 Luna 真實 Provider 證據

### 3.1 執行邊界

linked worktree 不會帶入 ignored app env；經 owner 明確授權後，canary 只從主 checkout `apps/api/.env` 讀取 `OPENROUTER_API_KEY／OPENROUTER_BASE_URL` 兩個鍵。key 未複製、未輸出、未寫入 Git；舊 env 內其他欄位也沒有灌入 current strict `Settings`。payload 只含固定顧問規則、合成動態文字，以及 owner 另行核准的三個現行唯讀 Tool schema：`employee_source_get／employee_source_lineage／employee_source_search`。沒有真實員工資料、JD、Tool 執行或模型回答 capture。

canary 直接走 production `build_openrouter_chat_model` 與 `AttemptReceiptCallback`，requested model=`openai/gpt-5.6-luna`、provider allowlist=`OpenAI`、fallback disabled、reasoning=`low`。stable system prefix 三步完全相同：1,736 characters／2,948 UTF-8 bytes，SHA-256=`b80a795e7e41a24e3f87a85b66614e2ce28cdaf32572d25d90e7085ce3776b2c`；dynamic suffix 每步不同。

### 3.2 門檻診斷

第一個診斷 probe 刻意不帶 Tool schema，整個 input 只有 877 tokens。三步皆為 `cache_write=0／cache_read=0`，每步 USD 0.000185，合計 USD 0.000555。這與 OpenRouter 對 OpenAI 公開的 1,024-token minimum 一致。沒有用重複 filler 硬湊；改為補上產品實際本來就會送的固定 Tool schema。

### 3.3 自然超過門檻後的 write→read

三個 production 唯讀 Tool schema 讓每步 input 自然成為 1,072 tokens：

| Step | Route | Input | Output | Cache write | Cache read | Latency | Cost |
|---:|---|---:|---:|---:|---:|---:|---:|
| 1 | `OpenAI / openai/gpt-5.6-luna` | 1,072 | 8 | 1,069 | 0 | 1,735 ms | USD 0.00027745 |
| 2 | `OpenAI / openai/gpt-5.6-luna` | 1,072 | 8 | 39 | **1,030** | 891 ms | USD 0.00004055 |
| 3 | `OpenAI / openai/gpt-5.6-luna` | 1,072 | 8 | 39 | **1,030** | 1,065 ms | USD 0.00004055 |

成功 probe 合計 USD 0.00035855；包含先前門檻診斷在內，本輪所有付費呼叫合計 USD 0.00091355。warm 後單步成本相較首筆下降約 85.4%；latency 也較低，但三筆樣本不足以宣稱穩定延遲改善。第二、三步仍各有 39 個新 write token，receipt 已照實保留，不把它說成 100% cache hit。

通過判準全部成立：首步有 cache write、後續有 cache read、requested／actual route 一致、每步 usage／cost／latency 完整，且沒有 silent fallback。canary 本身不建立文件或連線 PostgreSQL，所以沒有 smoke-owned document 可刪；先前完整 API gate 後五張表已為 0，本輪不會改變它們。產品語意等價由 stable/dynamic RED→GREEN 的逐字 prompt regression 與既有 Hybrid Candidate Loop 真模型 smoke共同覆蓋，不拿這個成本 canary 重做正式品質 eval。

## 4. 產品方向複核

- 同一位 AI 職務顧問、動態 Task／Duty／OPKS、Focus／Gap／Progress 語意不變；
- 員工原話、核准 JD、pending、candidate 與 Tool result 仍每步重建並放在 dynamic suffix；
- cache 不持有產品 truth，不影響自然關頁／下次繼續；continuation 仍只由 PostgreSQL／LangGraph 承接；
- LLM 產生內容仍只進候選／待審，員工接受或修改後接受才寫核准 JD；
- Evidence、read-set、deterministic verifier 與來源可信度沒有改；
- RAG／Reference consumer、能力級別／A、auto-accept、multi-agent 與正式 eval 仍不在本輪。

目前沒有發現需要修改產品大方向的證據；這是 provider execution optimization，不是新產品元件。

## 5. 第一方來源

- [OpenAI — GPT-5.6 model guidance](https://developers.openai.com/api/docs/guides/latest-model)
- [Anthropic — Prompt caching](https://platform.claude.com/docs/en/build-with-claude/prompt-caching)
- [Google — Context caching](https://ai.google.dev/gemini-api/docs/caching)
- [OpenRouter — Prompt caching](https://openrouter.ai/docs/guides/best-practices/prompt-caching)
- [LangChain — ChatOpenRouter integration](https://docs.langchain.com/oss/python/integrations/chat/openrouter)
- [OpenRouter — Response caching](https://openrouter.ai/docs/guides/features/response-caching)
