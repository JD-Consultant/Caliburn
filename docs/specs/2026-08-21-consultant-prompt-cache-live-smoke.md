# Consultant Prompt Cache 實作與真實 Provider Smoke

- 日期：2026-08-21
- 狀態：**本地實作與 deterministic gates 通過；真實 provider write→read 證據待本機注入 `OPENROUTER_API_KEY`**
- 性質：成本／延遲整合 smoke，不是正式品質 eval
- 範圍：stable prompt prefix、OpenRouter content-block passthrough、cache usage receipt；不接 RAG、不生成能力級別／A、不啟用 auto-accept 或 response caching
- 研究依據：[`2026-08-21-provider-neutral-virtual-jd-editor-and-evidence-anchor-research.md`](2026-08-21-provider-neutral-virtual-jd-editor-and-evidence-anchor-research.md#67-prompt-caching值得加但只作-provider-最佳化)

## 1. 實作內容

`ConsultantContextMiddleware` 不再把 framework system prompt 與每一步動態 Context 壓成一個字串；它改送兩個有序 `SystemMessage` content blocks：

1. stable block：同一 run 不變的顧問、authority 與 Skill catalog 規則，帶 `cache_control={"type":"ephemeral"}`；
2. dynamic block：每一步從 PostgreSQL／LangGraph 重建的 employee／approved／pending／focus／gap／candidate context，不帶 cache marker。

dynamic block 保留原本位於兩段之間的所有字元（通常是前導 `\n\n`），因此 `SystemMessage.text` 與舊版「先合併、最後只 `.strip()` 一次」逐字相同。這次沒有新增 cache service、資料表、provider-specific domain DTO 或記憶層。cache miss、過期或 provider 不支援時仍會看到完整相同 prompt，只是不省成本／延遲。

本 repo 鎖定的 `langchain-openrouter==0.2.7` 已原生保留 content-block `cache_control`，也會把 OpenRouter `prompt_tokens_details.cached_tokens／cache_write_tokens` 正規化成 LangChain `input_token_details.cache_read／cache_creation`。既有 `AttemptUsage` 已保存這兩欄，因此 application 沒有重寫 adapter，只加 characterization／receipt canary。

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

## 3. 真實 Provider 待補證據

目前 process、Windows User／Machine environment 與 repo-local `.env` 都沒有 `OPENROUTER_API_KEY`。只檢查存在性，沒有搜尋 shell history、log、舊報告或其他可能含憑證的位置，也沒有把 key 寫進 Git。因此本文件現在**不能宣稱 prompt cache 已在 GPT-5.6 Luna 命中**。

補跑時使用合成職務資料、exact model `openai/gpt-5.6-luna`、actual provider `OpenAI`、fallback disabled，順序完成 3–5 個 model steps。通過條件：

1. 第一個可快取 attempt 有 `cache_write_tokens > 0`；
2. 後續至少一個 attempt 有 `cache_read_tokens > 0`；
3. 每步都記 requested／actual route、input／output／cache write／cache read、latency 與 cost；
4. candidate／final／員工 authority 結果與 cache-disabled 語意等價；
5. 精確刪除 smoke-owned document，五張表回到執行前計數。

若沒有 cache read，依序檢查 stable prefix byte identity、provider 最低 cacheable token、TTL 與 route；不得增加假內容湊 token、放寬 verifier 或改 employee／JD context 只為提高命中率。

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
