# Consultant Prompt Caching Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 讓同一顧問 run 的固定 prompt prefix 由 OpenRouter／provider prompt caching 重用，同時保持每一步動態 JD context、員工原話、candidate 與 Tool observation 不進固定前綴。

**Architecture:** `ConsultantContextMiddleware` 將 framework 組出的固定 system prompt 與 application 每步重建的 dynamic context 改成兩個有序 content blocks；只在第一個 block 加 OpenRouter 可跨 provider 轉譯的 `cache_control`。既有 `langchain-openrouter` 負責序列化與 cache usage normalization，既有 `AttemptUsage` 負責 durable receipt；不新增 cache service、資料表、記憶層或 response caching。

**Tech Stack:** Python 3.12、LangChain 1.x、`langchain-openrouter==0.2.7`、OpenRouter Chat Completions、pytest。

**Spec:** `docs/specs/2026-08-21-provider-neutral-virtual-jd-editor-and-evidence-anchor-research.md` §6.7

## Global Constraints

- Prompt caching 只影響成本／延遲；cache miss、過期或停用不得改變模型可見內容與產品結果。
- stable prefix 只能包含固定顧問／authority 規則、固定 Tool schema 與本 run 不變的 Skill catalog；employee／approved／pending／focus／gap／candidate／Tool results 都留在 dynamic suffix。
- 使用 framework 原生 content-block `cache_control: {"type": "ephemeral"}`；不把 provider-specific cache DTO 放進 domain model。
- 不啟用 OpenRouter response caching，不新增持久 cache，不以 prompt cache 取代 PostgreSQL／LangGraph continuation。
- 不修改 owner 既有未提交的 `docs/adr/0060-langchain-langgraph-consultant-runtime-and-durable-authority.md`。
- 真模型只做 GPT-5.6 Luna 窄 smoke；正式品質 eval、RAG、能力級別／A、auto-accept 仍不在本輪。

---

### Task 1: Stable／dynamic system content blocks

**Files:**
- Modify: `apps/api/app/consultant/context.py:1362-1366`
- Test: `apps/api/tests/test_consultant_context.py:642-751`

**Interfaces:**
- Consumes: LangChain `ModelRequest.system_message` 與 `ContextBundle.system_prompt`。
- Produces: 一個 `SystemMessage`，第一個 content block 是 cacheable stable prefix，第二個是未標記的 dynamic suffix；`SystemMessage.text` 與舊版合併字串逐字相同。

- [x] **Step 1: 在既有 middleware integration test 加入 provider-facing block 斷言**

```python
assert isinstance(actual.system_message.content, list)
assert actual.system_message.content[0] == {
    "type": "text",
    "text": "非權威摘要可以保留，但不能取代來源。",
    "cache_control": {"type": "ephemeral"},
}
dynamic = actual.system_message.content[1]
assert dynamic["type"] == "text"
assert "cache_control" not in dynamic
assert dynamic["text"].startswith("\n\n")
assert "這是必須從 Store 重載的完整員工原話。" in dynamic["text"]
assert actual.system_message.text == (
    "非權威摘要可以保留，但不能取代來源。\n\n"
    + dynamic["text"].removeprefix("\n\n")
)
```

- [x] **Step 2: 用 disposable PostgreSQL 跑單一測試並確認 RED**

Run:

```powershell
$env:DEBUG='false'
$env:TEST_DATABASE_URL='postgresql+asyncpg://postgres:password@localhost:5432/caliburn_prompt_cache'
$env:UV_CACHE_DIR='S:\caliburn\.uv-cache-prompt-caching'
uv run pytest -p no:cacheprovider tests/test_consultant_context.py::test_context_middleware_rebinds_tagged_source_without_reordering_tool_loop -q
```

Expected: FAIL，因現行 `SystemMessage.content` 仍是單一字串。

- [x] **Step 3: 實作最小 message assembly**

```python
stable_prompt = request.system_message.text.strip() if request.system_message else ""
dynamic_prompt = bundle.system_prompt.strip()
content: list[dict[str, Any]] = []
if stable_prompt:
    content.append(
        {
            "type": "text",
            "text": stable_prompt,
            "cache_control": {"type": "ephemeral"},
        }
    )
if dynamic_prompt:
    content.append(
        {
            "type": "text",
            "text": ("\n\n" if stable_prompt else "") + dynamic_prompt,
        }
    )
system_message = SystemMessage(content=content)
```

- [x] **Step 4: 重跑單一測試確認 GREEN，再跑完整 context/model-runtime focused gate**

Run the RED command again, then:

```powershell
uv run pytest -p no:cacheprovider tests/test_consultant_context.py tests/test_consultant_model_runtime.py -q
```

Expected: focused tests 全通過；DB fixture 無殘留。

- [x] **Step 5: Commit**

```powershell
git add apps/api/app/consultant/context.py apps/api/tests/test_consultant_context.py
git commit -m "feat: cache stable consultant prompt prefix"
```

### Task 2: OpenRouter serialization and receipt canaries

**Files:**
- Test: `apps/api/tests/test_consultant_model_runtime.py:168-247`

**Interfaces:**
- Consumes: Task 1 的 LangChain content-block shape，以及 OpenRouter usage `prompt_tokens_details.cached_tokens／cache_write_tokens`。
- Produces: characterization tests，凍結 `cache_control` passthrough 與 `AttemptUsage.cache_read_tokens／cache_write_tokens` normalization；不重寫 framework adapter。

- [x] **Step 1: 加入 content-block passthrough characterization**

```python
message_dicts, _ = model._create_message_dicts(
    [
        SystemMessage(
            content=[
                {
                    "type": "text",
                    "text": "stable consultant rules",
                    "cache_control": {"type": "ephemeral"},
                },
                {"type": "text", "text": "\n\ndynamic document context"},
            ]
        )
    ],
    None,
)
assert message_dicts[0]["content"][0]["cache_control"] == {
    "type": "ephemeral"
}
assert "cache_control" not in message_dicts[0]["content"][1]
```

This is a deliberate upstream characterization test and may pass immediately; it protects the pinned framework boundary rather than inventing application code.

- [x] **Step 2: 擴充 synthetic OpenRouter response 並斷言 normalized usage**

```python
"prompt_tokens_details": {
    "cached_tokens": 96,
    "cache_write_tokens": 24,
}

assert message.usage_metadata["input_token_details"] == {
    "cache_read": 96,
    "cache_creation": 24,
}
```

- [x] **Step 3: 擴充 callback test，確認 durable receipt 保留 cache usage**

```python
"input_token_details": {"cache_read": 96, "cache_creation": 24}

assert receipt.usage.cache_read_tokens == 96
assert receipt.usage.cache_write_tokens == 24
```

- [x] **Step 4: 跑 focused test 並做 mutation check**

Run:

```powershell
$env:UV_CACHE_DIR='S:\caliburn\.uv-cache-prompt-caching'
uv run pytest -p no:cacheprovider tests/test_consultant_model_runtime.py -q
```

Mutation check: 移除 stable block 的 `cache_control` 會讓 passthrough test 失敗；把 `cached_tokens`／`cache_write_tokens` 任一映射成錯欄位會讓 receipt assertion 失敗。

- [x] **Step 5: Commit**

```powershell
git add apps/api/tests/test_consultant_model_runtime.py
git commit -m "test: preserve consultant prompt cache usage"
```

### Task 3: Live cache proof and delivery record

**Files:**
- Modify: `docs/specs/2026-08-21-provider-neutral-virtual-jd-editor-and-evidence-anchor-research.md`
- Create: `docs/specs/2026-08-21-consultant-prompt-cache-live-smoke.md`
- Modify if required by behavior seam: `docs/design/consultant-runtime.md`

**Interfaces:**
- Consumes: Task 1 provider-facing prefix、Task 2 durable usage fields、owner local `OPENROUTER_API_KEY`、local disposable PostgreSQL。
- Produces: 一次可複核的 GPT-5.6 Luna write→read receipt，以及失敗時的精確診斷；不建立正式 eval。

- [x] **Step 1: 跑非付費完整相關 gate**

```powershell
$env:DEBUG='false'
$env:TEST_DATABASE_URL='postgresql+asyncpg://postgres:password@localhost:5432/caliburn_prompt_cache'
$env:UV_CACHE_DIR='S:\caliburn\.uv-cache-prompt-caching'
uv run pytest -p no:cacheprovider tests/test_consultant_context.py tests/test_consultant_model_runtime.py tests/test_consultant_run_service.py tests/test_consultant_agent_and_skills.py -q
```

- [ ] **Step 2: 用合成資料順序跑 3–5 個 GPT-5.6 Luna model steps**

固定 requested／actual model=`openai/gpt-5.6-luna`、provider=`OpenAI`、fallback disabled；第一個 attempt 應有 `cache_write_tokens > 0`，後續至少一個 attempt 應有 `cache_read_tokens > 0`。若 route、最低 prefix token 或 TTL 導致 miss，記錄實際欄位與原因，不放寬產品 verifier、不重送真實員工資料。

- [ ] **Step 3: 清除精確 disposable document，確認五張表回到前值**

只刪本 smoke 建立的 document ID；檢查 `consultant_documents／checkpoints／checkpoint_blobs／checkpoint_writes／store` 前後計數相同。

- [x] **Step 4: 寫 smoke report 與產品方向複核**

報告必須列每 step 的 input／output／cache write／cache read／latency／cost／actual route，並確認：員工 authority、動態 context、Evidence、自然關頁續談、RAG 延後範圍都未改變。若 provider 沒回 cache usage，狀態寫「未證明」，不可寫通過。

- [ ] **Step 5: Final gate 與 Commit**

```powershell
git diff --check
git status --short
git add docs/plans/2026-08-21-consultant-prompt-caching-plan.md docs/specs/2026-08-21-provider-neutral-virtual-jd-editor-and-evidence-anchor-research.md docs/specs/2026-08-21-consultant-prompt-cache-live-smoke.md docs/design/consultant-runtime.md
git commit -m "docs: record consultant prompt cache verification"
```

只加入實際存在且本輪改動的文件；不得 stage ADR 0060。

## Self-Review Notes

- Spec coverage：stable／dynamic 邊界、framework-first passthrough、usage receipt、短 TTL、cache miss 等價與禁止 response caching 都有 task。
- Text equivalence：後續自審用 stable 尾端空白取得額外 RED，修正成保留舊版「合併後只 strip 一次」的逐字語意；不再對兩個 block 各自 strip。
- Scope：沒有 session stickiness、1h TTL、cache DB、provider-specific domain contract 或正式 eval；現行手動 `provider.order` 下不宣稱 `session_id` 能提高命中。
- Type consistency：OpenRouter 的 `cached_tokens／cache_write_tokens` 只在 adapter 層正規化為 LangChain `cache_read／cache_creation`，再由既有 `AttemptUsage` 保存。
- Placeholder scan：無 TBD／TODO；live key 不寫入 repo，缺 key 時只能記錄 blocker，不能偽造結果。
