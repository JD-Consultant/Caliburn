# Memory Routing 與 Canonical Read 隔離 Spike 實作計畫

> **For agentic workers:** 執行前必須先用 `superpowers:using-git-worktrees` 建立隔離 worktree；逐 task 依 `superpowers:executing-plans` 與 `superpowers:test-driven-development` 施工；每個 review checkpoint 使用 `superpowers:requesting-code-review`，完成宣稱前使用 `superpowers:verification-before-completion`。

**狀態：** Product Owner 已於 2026-09-03 核准 Revision 2 進入 G5 隔離實驗。授權只涵蓋本計畫描述的實驗；不授權 production 整合、ADR 狀態改變、UI、JD 編輯、RAG、merge 或 push。

**目標：** 以最小但可信的隔離實驗，驗證在不替 raw conversation 建 semantic index、不複製員工來源、也不把完整歷史送入每次模型呼叫的條件下，LangGraph PostgreSQL Checkpointer＋Store 能否支撐：小型導覽、focused Semantic Memory 自然語言搜尋、依 stable message reference 回讀 canonical conversation，以及一個有成本上限的 Luna tool loop。

**架構：** 實驗程式全部放在 `docs/experiments/2026-09-03-memory-routing-canonical-read/`，以 `apps/api` 已鎖定的 Python 環境執行，不 import production composition root。PostgreSQL Checkpointer 保存完整、有序的 synthetic 員工↔顧問 canonical conversation；Store 只保存 synthetic、current、focused Semantic Memory。單次 read-tool graph 不掛 checkpointer，只把 canonical conversation 的有界投影放入暫態 agent state，避免把實驗 tool chatter 寫回訪談來源。模型先取得可重建的小型導覽，必要時呼叫兩個窄工具；scope、結果數、窗口、重試與 ID 由 Runtime 管理。實驗不實作 Memory Manager，不產生或修改 JD，也不宣稱已驗證 agent-run resume。

**技術棧：** Python 3.13；Pydantic 2.13.4；LangChain 1.3.15；LangGraph 1.2.11；LangGraph PostgreSQL Checkpointer／Store 3.1.2；langchain-openrouter 0.2.7；OpenRouter Python SDK 0.10.8；PostgreSQL；pytest／pytest-asyncio；live smoke 使用 `openai/gpt-5.6-luna`、`medium` 與 OpenRouter embeddings API。

**設計 authority：**

- [`MEM-Q004 read contract 與 G5 spike design`](../specs/2026-09-03-memory-routing-canonical-read-and-isolated-spike-research.md)，尤其 §6.4～§7.7。
- [`Framework-independent Memory contract`](../specs/2026-09-01-framework-independent-memory-contract.md)，尤其 M1～M11、§3.4、§3.5。
- [`Canonical conversation search/read reconciliation`](../specs/2026-09-03-memory-canonical-conversation-search-read-reconciliation.md)。
- [`Current decision register`](../current-decisions.md) 的 `MEM-Q001～MEM-Q004`。
- [`Consensus／framework final audit`](../specs/2026-09-03-memory-read-spike-consensus-and-framework-final-audit.md)。

## 0. 本計畫刻意不做什麼

- 不改 `apps/api/app`、`apps/web`、`packages/*`、production migration、Docker Compose、production dependency lock 或現有 ADR。
- 不實作 Memory admission、extraction、consolidation、add/update/remove/no-op manager，也不比較 C1／C2 writer。
- 不設計 production Semantic Memory schema；實驗 fixture 的 `title／content／message_refs` 只是 G5 read view。
- 不實作 final JD exact-scope full audit；本實驗只驗證日常 bounded recall。M9 仍未證明。
- 不建立 employee-source Store leaf、conversation summary、raw-message embedding、hybrid search、Qdrant、Reference RAG 或自製向量排名。
- 不使用 `SummarizationMiddleware` 改寫 canonical message channel。
- 不讓模型填 document／thread／namespace／limit／filter／window／retry／memory ID／message ID／timestamp／version。
- 不把模型隱藏 reasoning、API key 或完整環境變數寫入 Git。
- 不以增加重試、放大全部 Context、臨時新增索引或修改 rubric 讓失敗看起來通過。
- 不把暫態 read-tool graph 的成功冒充成 agent-run checkpoint／interrupt／resume 已通過。

## 1. 實驗目錄

```text
docs/experiments/2026-09-03-memory-routing-canonical-read/
├─ README.md
├─ rubric.md
├─ cases/
│  └─ long-thread-routing-v1.json
├─ src/
│  └─ memory_read_spike/
│     ├─ __init__.py
│     ├─ contracts.py
│     ├─ scope.py
│     ├─ settings.py
│     ├─ embeddings.py
│     ├─ canonical.py
│     ├─ fixtures.py
│     ├─ runtime.py
│     ├─ tools.py
│     ├─ graph.py
│     ├─ receipts.py
│     └─ live_smoke.py
├─ tests/
│  ├─ test_contracts.py
│  ├─ test_langmem_characterization.py
│  ├─ test_postgres_read_path.py
│  ├─ test_tool_graph.py
│  ├─ test_live_smoke_dry_run.py
│  └─ test_storage_growth.py
├─ trials/
│  ├─ .gitignore
│  └─ README.md
├─ results.csv             # 只由實際 run 產生
└─ report.md               # 只在所有已執行 gate 完成後撰寫
```

實驗不建立獨立 `pyproject.toml` 或 lock。所有 deterministic command 使用 `apps/api/uv.lock`；只有 LangMem helper characterization 以 `uv --with langmem==0.0.30` 暫時載入，不修改 lock。

## 2. 執行前共同 gate

- [x] Product Owner 已於 2026-09-03 明確核准 Revision 2；核准條件是由整體到細節均優先採可追溯的大廠／框架共識，不得把未討論的自訂作法當成共識。
- [ ] 使用 `superpowers:using-git-worktrees`，從已包含核准研究稿與本計畫的 commit 建立 `codex/memory-routing-canonical-read-spike`。不得從含未提交使用者修改的 main checkout 複製整個 working tree。
- [ ] 在 worktree 執行 `Get-Location`、`git branch --show-current`、`git status --short`；路徑或分支不符立即停止。
- [ ] 把實驗 source baseline commit、Python／uv／PostgreSQL 版本、鎖定套件版本寫進 README；不記錄密碼或 API key。
- [ ] 使用匿名 synthetic fixture；不得載入真實員工資料。
- [ ] 由操作者明確設定 `MEMORY_ROUTING_SPIKE_DATABASE_URL` 與 `MEMORY_ROUTING_SPIKE_EXPECTED_DATABASE`。程式不得 fallback 到 `DATABASE_URL`；必須拒絕非 loopback host、database name 不等於 expected、database name 不含 `memory_routing_spike`，以及 URL 與 app production URL 相同的情況。
- [ ] 程式不建立、不刪除 database。資料庫不存在、身份不符或無權建立 framework tables 時停止並回報。
- [ ] OpenRouter key 只從 `apps/api/.env`／process environment 讀取為 secret；dry run 與 deterministic tests 不需要 key。
- [ ] rubric、case fixture 與 live prompt 在任何模型 call 前先 commit。開始 live call 後不得原地修改；若 plumbing defect 需要修改，升 `experiment_revision`，重新 review，再決定是否重新付費執行。

README 的 baseline 必須有一行可由最終 verification 機器解析的實際 40 字元 commit：

```text
source_baseline_commit: 0123456789abcdef0123456789abcdef01234567
```

上例只是格式；執行時必須用 `git rev-parse HEAD` 的真值取代，不能照抄示例。

PowerShell 共用測試前綴：

```powershell
$env:UV_CACHE_DIR='S:\caliburn\.uv-cache-reviewed'
$spikeRoot=(Resolve-Path 'docs\experiments\2026-09-03-memory-routing-canonical-read').Path
$env:PYTHONPATH=(Join-Path $spikeRoot 'src')
```

## 3. 凍結的實驗資料與判定

`cases/long-thread-routing-v1.json` 固定為 40 組訪談 round，也就是 40 個 `HumanMessage`＋40 個 `AIMessage`。Runtime 為每則訊息配置穩定 ID。案例至少包含：

- **A 案／餐飲預約網站：** 三間分店；預約時記錄過敏備註；驗收包含行動版 Safari 與尖峰時段重複訂位檢查。早期員工原話另放一段只存在 canonical conversation、不逐字複製進 Semantic Memory 的獨特說法，供 deep-read 題核對。
- **B 案／健身會員網站：** 單一場館；會員名單整合一開始誤述為會員 API，後來明確更正為每日 CSV 匯入；驗收包含大量名單匯入與重複會員編號提示。
- **共同模式：** 兩案都有需求訪談、前端實作、資料串接、測試與客戶驗收；Semantic Memory 不得因共同模式把 A／B 獨有細節壓平。
- **未回答問題：** 「退款例外由誰核准？」conversation 中只有顧問提問，沒有員工答案；Store 不得捏造答案。
- **長距離：** A／B 的主要原話位於早期 round；最後六則 canonical messages 不含上述獨有細節。

Store 只 seed 三筆 current Semantic Memory：A 案、B 案與共同穩定工作模式。B Memory 只保存目前有效的 CSV 說法；舊 API 說法只留在 canonical conversation。每筆 fixture value 固定為：

```python
class SemanticMemoryFixture(BaseModel):
    model_config = ConfigDict(extra="forbid")

    memory_id: str          # Runtime fixture metadata；不進模型結果
    title: str
    content: str
    message_refs: tuple[str, ...]
```

`memory_id`、message IDs、document ID、thread ID、run ID 全由 deterministic fixture/runtime 產生；模型不生成。Store semantic index 只索引 `title` 與 `content`。

`rubric.md` 在 live 前固定下列 hard pass：

1. A 三個獨有細節全對，並正確核對那段只存在 canonical conversation 的員工原話；可由 tool result＋canonical deep-read 查到。
2. A／B 不混案；B 採 CSV，不把舊 API 當 current。
3. 「退款例外由誰核准」明確回答資料不足／需詢問員工，不捏造人員或流程。
4. 模型依題目與 tool description 自行選擇 search，並為精確原話核對選擇一次 deep-read；最多 3 次 model call、2 次 tool call，無 retry。
5. 模型從未收到完整 80-message conversation 或完整 Memory collection。
6. 任何跨 document 資料、Store key、namespace、score、timestamp、stack trace、SQL 或 secret 均未出現在模型可見內容。

## Task 1：凍結契約、案例與純框架 characterization

**Files:**

- Create: `docs/experiments/2026-09-03-memory-routing-canonical-read/README.md`
- Create: `docs/experiments/2026-09-03-memory-routing-canonical-read/rubric.md`
- Create: `docs/experiments/2026-09-03-memory-routing-canonical-read/cases/long-thread-routing-v1.json`
- Create: `docs/experiments/2026-09-03-memory-routing-canonical-read/trials/README.md`
- Create: `docs/experiments/2026-09-03-memory-routing-canonical-read/src/memory_read_spike/__init__.py`
- Create: `docs/experiments/2026-09-03-memory-routing-canonical-read/src/memory_read_spike/contracts.py`
- Create: `docs/experiments/2026-09-03-memory-routing-canonical-read/tests/test_contracts.py`
- Create: `docs/experiments/2026-09-03-memory-routing-canonical-read/tests/test_langmem_characterization.py`

### 1.1 先寫 RED tests

`contracts.py` 的公開型別固定為：

```python
class SearchSemanticMemoryInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    query: str = Field(min_length=1)


class ReadConversationContextInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    message_ref: str = Field(min_length=1)


class MemoryHit(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str
    content: str
    message_refs: tuple[str, ...]


class SearchSemanticMemoryResult(BaseModel):
    model_config = ConfigDict(extra="forbid")
    memories: tuple[MemoryHit, ...]


class ConversationItem(BaseModel):
    model_config = ConfigDict(extra="forbid")
    speaker: Literal["employee", "consultant"]
    text: str


class ReadConversationContextResult(BaseModel):
    model_config = ConfigDict(extra="forbid")
    context: tuple[ConversationItem, ...]
```

`test_contracts.py` 先失敗並逐條證明：

- `search_semantic_memory` input schema 只有 required `query: string`；`read_conversation_context` 只有 required `message_ref: string`；兩者 `additionalProperties` 都是 `false`。
- 空字串與未知欄位由 Pydantic 拒絕。
- success payload 只能有研究稿核准的欄位；空 `memories` 合法。
- 一個 dummy `StructuredTool` 回傳 Python dict 後，經 pinned `ToolNode` 變成可解析 JSON 的 `ToolMessage.content`，保留 `tool_call_id`，`status="success"`。
- `ToolMessage` 沒有虛構的頂層 `code` 欄位；error code 必須在 JSON `content`。
- `ensure_embeddings(async_callable)` 可被 pinned framework 接受，`aembed_documents` 保持輸入順序與固定維度。

`test_langmem_characterization.py` 只 characterise `langmem==0.0.30` 的公開 helper，不採用它：

- `create_search_memory_tool` 的模型 schema 確實包含 `query／limit／offset／filter`。
- helper 的結果是 framework Store item view，不是已核准的最小 `memories[]` view。
- test 只形成報告證據；不得把該 helper wrapper 成 production tool，也不得修改 app lock。
- 該 test 以 `pytest.importorskip("langmem")` 保持一般 locked suite 可執行；只有下方 `--with langmem==0.0.30` 命令必須實際跑過且通過，不能把 skip 當 characterization 完成。

### 1.2 執行 RED

```powershell
$env:UV_CACHE_DIR='S:\caliburn\.uv-cache-reviewed'
$spikeRoot=(Resolve-Path 'docs\experiments\2026-09-03-memory-routing-canonical-read').Path
$env:PYTHONPATH=(Join-Path $spikeRoot 'src')
uv run --project apps/api --locked pytest "$spikeRoot\tests\test_contracts.py" -q
uv run --project apps/api --locked --with langmem==0.0.30 pytest "$spikeRoot\tests\test_langmem_characterization.py" -q
```

預期：缺少 contracts／tools 時失敗；不得先寫 implementation 再補測試。

### 1.3 最小實作並轉綠

- 只實作上述 Pydantic 型別、穩定 JSON serializer 與測試需要的 dummy tool。
- 不加入 scope、PostgreSQL、模型、Memory Manager 或 JD 型別。
- README 記錄 pinned 與 2026-09-03 查得的 latest stable 版本差異；不在 spike 升級 production lock。

### 1.4 驗證、review、commit

重跑兩條命令，接著：

```powershell
git diff --check
git status --short
git add docs/experiments/2026-09-03-memory-routing-canonical-read
git commit -m "test: freeze memory read spike contracts"
```

**Review checkpoint A：** 核對案例、rubric、tool schema 與 G4；若出現第二個模型欄位、source Store leaf、conversation summary 或 writer，停止並退回 plan review。

## Task 2：建立隔離 PostgreSQL canonical conversation 與 focused Memory read substrate

**Files:**

- Create: `docs/experiments/2026-09-03-memory-routing-canonical-read/src/memory_read_spike/scope.py`
- Create: `docs/experiments/2026-09-03-memory-routing-canonical-read/src/memory_read_spike/settings.py`
- Create: `docs/experiments/2026-09-03-memory-routing-canonical-read/src/memory_read_spike/embeddings.py`
- Create: `docs/experiments/2026-09-03-memory-routing-canonical-read/src/memory_read_spike/canonical.py`
- Create: `docs/experiments/2026-09-03-memory-routing-canonical-read/src/memory_read_spike/fixtures.py`
- Create: `docs/experiments/2026-09-03-memory-routing-canonical-read/src/memory_read_spike/runtime.py`
- Create: `docs/experiments/2026-09-03-memory-routing-canonical-read/tests/test_postgres_read_path.py`

### 2.1 先寫 RED integration tests

固定介面：

```python
@dataclass(frozen=True)
class TrustedReadScope:
    run_id: UUID
    document_id: UUID
    thread_id: str

    @property
    def semantic_namespace(self) -> tuple[str, ...]:
        return (
            "memory-routing-spike",
            str(self.run_id),
            str(self.document_id),
            "semantic",
        )


async def open_spike_runtime(settings: SpikeSettings, *, embed: AEmbeddingsFunc): ...
async def append_canonical_round(runtime, scope, human, assistant) -> None: ...
async def latest_canonical_messages(runtime, scope) -> tuple[BaseMessage, ...]: ...
async def read_canonical_context(runtime, scope, message_ref) -> ReadConversationContextResult: ...
async def seed_current_memories(runtime, scope, memories) -> None: ...
async def search_current_memories(runtime, scope, query) -> SearchSemanticMemoryResult: ...
```

Tests 必須先紅，然後證明：

1. `SpikeSettings` 對 database identity 的四個拒絕條件全部成立，且永不讀 production `DATABASE_URL` 當 fallback。
2. `AsyncPostgresSaver.setup()`／`AsyncPostgresStore.setup()` 只在已核對的 disposable DB 執行。
3. 40 組 round 寫入後 latest checkpoint 有 80 則依序 messages；關閉並重開 saver/store 後內容、型別與 IDs 相同。
4. same-ID same-content intake 是 no-op；same-ID different-content 在寫 checkpoint 前由 guard 拒絕；員工更正是新的 `HumanMessage`，舊訊息仍存在。
5. Store 只含三筆 focused current Memory；沒有 employee-source text leaf、conversation summary 或舊 B API Memory。
6. deterministic async embedding spy 只收到由 `title／content` 組合的文字，未收到 message refs、namespace、metadata 或 raw conversation。
7. `AsyncPostgresStore.asearch` 回傳完整 stored value；無 index 的 control store 不得被包裝成 semantic search 成功。
8. current document query 不回傳另一 document 或目前 namespace 的 child namespace；adapter 對每個結果做 exact namespace equality guard。
9. valid `message_ref` 能在 latest canonical state 定位；對一個孤立短答，最小窗口是直接相鄰的 consultant question＋target employee answer。
10. missing、malformed 與 cross-scope ref 對模型端都正規化為 `reference_unavailable`；內部 assertion／trace 可區分原因，但不進 public payload。

### 2.2 實作方式

- Saver 與 Store 都使用 framework `from_conn_string`／`setup`；不建立自製 repository 或 table。
- Store 以 `index={"dims": D, "embed": async_callable, "fields": ["title", "content"]}` 啟用 isolated semantic index。
- deterministic tests 注入固定、可預測的向量 callable；不自己計算 similarity 或排序。
- `append_canonical_round` 只做 stable-ID collision guard，再交給 `MessagesState`／`add_messages` 與 Checkpointer；不複製 conversation 至 Store。
- `read_canonical_context` 從相同 thread latest state 讀完整 canonical messages，再依 stable ID 定位；第一個 spike 的相鄰政策只回「直接前一則 consultant message（若存在）＋目標 employee message」。這是要被 characterise 的 spike policy，不宣稱已定 production window。
- `search_current_memories` 固定最多 2 筆，且單筆完整、不截斷。`2` 是 frozen experiment variable，不是 production top-k 決策。
- backend diagnostic 留在 test trace／log capture；模型 success result 不含 key、score、namespace、timestamp。

### 2.3 RED／GREEN 命令

```powershell
if (-not $env:MEMORY_ROUTING_SPIKE_DATABASE_URL) { throw 'set MEMORY_ROUTING_SPIKE_DATABASE_URL' }
if (-not $env:MEMORY_ROUTING_SPIKE_EXPECTED_DATABASE) { throw 'set MEMORY_ROUTING_SPIKE_EXPECTED_DATABASE' }
$env:UV_CACHE_DIR='S:\caliburn\.uv-cache-reviewed'
$spikeRoot=(Resolve-Path 'docs\experiments\2026-09-03-memory-routing-canonical-read').Path
$env:PYTHONPATH=(Join-Path $spikeRoot 'src')
uv run --project apps/api --locked pytest "$spikeRoot\tests\test_postgres_read_path.py" -q
```

先觀察缺 implementation 的 RED，再做最小實作，重跑至 GREEN。

### 2.4 Review 與 commit

- 用 `superpowers:requesting-code-review` 只審 Task 2 diff。
- Reviewer 必須回答：是否存在第二份 canonical text、是否信任 model scope、是否自製 vector search、是否破壞完整 checkpoint、是否誤稱 M3／M9 已通過。
- 修正 review findings 後重跑 Task 1＋2 tests 與 `git diff --check`。

```powershell
git add docs/experiments/2026-09-03-memory-routing-canonical-read
git commit -m "test: prove durable scoped memory reads"
```

**Review checkpoint B：** 任一 durability、scope、stable ref 或 no-duplication 測試失敗即停止；不得進模型工具層。

## Task 3：以 framework-native ToolNode 組成兩工具 read graph

**Files:**

- Create: `docs/experiments/2026-09-03-memory-routing-canonical-read/src/memory_read_spike/tools.py`
- Create: `docs/experiments/2026-09-03-memory-routing-canonical-read/src/memory_read_spike/graph.py`
- Create: `docs/experiments/2026-09-03-memory-routing-canonical-read/tests/test_tool_graph.py`

### 3.1 先寫 RED tests

固定 public tools：

```python
search_semantic_memory(query: str, runtime: ToolRuntime) -> dict | Command
read_conversation_context(message_ref: str, runtime: ToolRuntime) -> dict
```

Runtime／暫態 graph state 隱藏：trusted `document_id／thread_id／run_id`、Store、canonical Saver reader，以及 search 在本次 run 實際揭露的 `message_refs`。模型 schema 仍只看一個字串。Read-tool graph 以 `compile(store=..., checkpointer=None)` 執行；canonical Checkpointer 是它的 read source，不是它的 agent-message sink。

兩個 tool description 凍結為下列語意，不讓實作者自行擴權：

```text
search_semantic_memory:
搜尋目前文件中少量、相關且目前有效的完整工作記憶。當近期對話與主題導覽不足以回答、比較相似案例或核對久遠細節時使用。這不是列舉全部記憶或最終 JD 完整性檢查。只提供自然語言 query；不要提供文件、員工、scope、limit 或 filter。

read_conversation_context:
依 search_semantic_memory 實際回傳的 message_ref，讀取目前文件中最小且完整的員工原話與相鄰顧問問題。只有需要核對原句或短答脈絡時使用；不要自行猜測 message_ref。
```

`test_tool_graph.py` 必須覆蓋：

- 工具名稱、description 與 exact schema；description 明示 search 是 bounded relevance search、不是 full audit，read 只核對前一工具提供的 reference。
- `ToolRuntime` 注入的 scope 不出現在 provider schema。
- search tool 回傳 `memories[]`，並把本次實際回傳的 refs 加入**本次暫態 graph execution** 的 `disclosed_message_refs`；read tool 只接受該集合內且屬 current thread 的 ref。graph 結束後該集合消失，不得寫回 canonical Checkpointer 或 Store。
- success／empty success／`invalid_input`／`reference_unavailable`／`temporary_failure` 都形成帶原 tool call ID 的 `ToolMessage`；public error 是可解析 JSON、沒有 exception message。
- validation error 與明列的 expected read errors 統一由一個 typed `ToolNode(handle_tool_errors=...)` handler 轉成穩定 JSON；前者是 `invalid_input`，後者依類型為 `reference_unavailable` 或 `temporary_failure`。
- 不再疊加 `ToolException／BaseTool.handle_tool_error` 或第二層 error middleware；未列入 handler type 的 `RuntimeError` 必須向外拋出並停止，不能被泛化吞掉。
- 不配置 `ToolRetryMiddleware` 或 custom retry loop；spike 自動 retry 數是 0。
- graph 由 `StateGraph`＋pinned `ToolNode` 執行 call/result linkage；不得手寫解析模型 tool call 的 agentic while loop。
- 每次 model call 的 transient input 只有 system instructions、最後 6 則 canonical messages、小型導覽，以及該 run 已回傳的 tool results。由於 tool graph 不掛 checkpointer，AI tool call／`ToolMessage` 只存在本次暫態 graph state；Task 2 的 canonical checkpoint 在前後都保持原 80 則內容、順序與 IDs 不變。
- 小型導覽由 exact-scope current Store items 的 `title` deterministic rebuild，沒有第二份 persisted guide。
- 負向測試確認沒有掛 `SummarizationMiddleware`；bounded projection 不寫回 trimmed messages。

### 3.2 Strict provider payload characterization

同一 test file 使用公開 `httpx.MockTransport` 注入 `openrouter.OpenRouter` SDK，再交給 `ChatOpenRouter`。Stub 回一個合法 chat-completion response，並捕捉實際 HTTP request JSON。必須直接 assert：

```text
tools[0].function.name == search_semantic_memory
tools[0].function.strict == true
tools[0].function.parameters.required == [query]
tools[0].function.parameters.additionalProperties == false
tools[1].function.name == read_conversation_context
tools[1].function.strict == true
tools[1].function.parameters.required == [message_ref]
tools[1].function.parameters.additionalProperties == false
parallel_tool_calls == false
```

不能只 assert `bound.kwargs`。這個測試專門防止 `create_agent` 對非 `BaseChatOpenAI` integration 沒有自動補 strict 的 pinned caveat；實作採明確 `ChatOpenRouter.bind_tools(strict=True, parallel_tool_calls=False)`，再把 bound model 放入 explicit graph。

### 3.3 有界 graph

- Graph path 固定為 `model → tools → model → tools → model → END` 的最大形狀。
- `parallel_tool_calls=False`；每個 model response 最多一個 tool call。
- `recursion_limit` 固定為只容納 3 model nodes＋2 tool nodes；超出即整個 trial fail，不提高限制重跑。
- `disclosed_message_refs` 使用 LangGraph state reducer，只在這次不掛 checkpointer 的 graph execution 內累積 framework 實際 search result 揭露的 refs；read 前同時做 current-thread scope 驗證。
- graph 不含 Memory writer、JD node、agent handoff、planner、subagent 或 background task。

Search tool 使用 LangGraph 公開 `Command(update=...)` 同步寫入模型可見 `ToolMessage` 與 hidden disclosure state；不得另建旁路 session cache。形狀固定為：

```python
return Command(
    update={
        "messages": [
            ToolMessage(
                name="search_semantic_memory",
                tool_call_id=runtime.tool_call_id,
                status="success",
                content=result.model_dump_json(),
            )
        ],
        "disclosed_message_refs": set(returned_message_refs),
    }
)
```

`disclosed_message_refs` 是本次 graph execution 的暫態 state，不是 Semantic Memory、來源資料、模型欄位或跨 run 狀態；reducer 只做 set union。Read tool 成功時可回普通 Pydantic/dict result，交由 ToolNode 產生對應 `ToolMessage`。

小型導覽的 model-visible 格式固定為：

```text
目前文件可搜尋的工作記憶主題：
- <title 1>
- <title 2>
- <title 3>
```

它只列 title、不列 ID、content、message refs 或分數，且每次由 current Store items 重建。

### 3.4 RED／GREEN／review

```powershell
$env:UV_CACHE_DIR='S:\caliburn\.uv-cache-reviewed'
$spikeRoot=(Resolve-Path 'docs\experiments\2026-09-03-memory-routing-canonical-read').Path
$env:PYTHONPATH=(Join-Path $spikeRoot 'src')
uv run --project apps/api --locked pytest "$spikeRoot\tests\test_tool_graph.py" -q
uv run --project apps/api --locked pytest "$spikeRoot\tests\test_contracts.py" "$spikeRoot\tests\test_postgres_read_path.py" "$spikeRoot\tests\test_tool_graph.py" -q
```

- 先紅後綠。
- 用 `superpowers:requesting-code-review` 審查：framework 是否真的負責 tool execution、strict 是否檢查實際 request、error hook 是否放對層、暫態 agent state 是否未寫進 canonical checkpoint，以及原 80 則來源是否完全未變。

```powershell
git diff --check
git add docs/experiments/2026-09-03-memory-routing-canonical-read
git commit -m "test: characterize bounded memory read tools"
```

**Review checkpoint C：** 若需要第三個模型工具、第二套 agent loop、raw-message index 或永久摘要才能通過，立即停止並依 `MEM-Q004` reopen；不得自行擴 scope。

## Task 4：量測 Checkpointer 成長與凍結 live dry run

**Files:**

- Create: `docs/experiments/2026-09-03-memory-routing-canonical-read/src/memory_read_spike/receipts.py`
- Create: `docs/experiments/2026-09-03-memory-routing-canonical-read/src/memory_read_spike/live_smoke.py`
- Create: `docs/experiments/2026-09-03-memory-routing-canonical-read/tests/test_live_smoke_dry_run.py`
- Create: `docs/experiments/2026-09-03-memory-routing-canonical-read/tests/test_storage_growth.py`

### 4.1 Storage growth RED tests

`test_storage_growth.py` 依序在 fresh run/thread IDs 建立 40／100／200 組 round，且每個級距至少量測三次 deterministic repetition。記錄而不預設通過：

- 每個 round 的 canonical append wall time（包含 stable-ID guard 的 latest-state read 與 framework checkpoint write；不得誤稱純 DB write latency）；
- restart 後 latest-state read wall time；
- `checkpoints`、`checkpoint_writes`、`checkpoint_blobs` 對該 thread 的 rows 與 `sum(pg_column_size(row))`；
- restart 後 message equality 與 stable IDs。

不得用整個 shared table 的 relation size冒充該 thread 成長；不得先引入 beta `DeltaChannel`。結果寫到測試產生的暫存 JSON，Task 5 才轉入 report。

### 4.2 Live harness 的 dry-run contract

`live_smoke.py` 只公開：

```python
async def run_live_smoke(settings: LiveSmokeSettings, *, dry_run: bool) -> LiveSmokeReceipt: ...
```

`LiveSmokeSettings` 固定：

- chat model：`openai/gpt-5.6-luna`
- reasoning：`medium`，不保存 reasoning content
- embedding model：`openai/text-embedding-3-small`
- embedding dimensions：1536（只屬本 spike，不是 production 選型）
- provider fallback：false；model/SDK automatic retry：0
- max model calls：3；max tool calls：2
- 每次 max completion tokens：1200；三次合計 completion cap：3600
- 全 run observed model input token stop cap：18,000；每次回應先如實記錄，超界後不得進下一 call
- chat＋embedding observed cost stop cap：USD 0.20；同樣在每次官方 usage 回傳後執行
- timeout：每個外部 request 60 秒；整個 smoke 180 秒

dry-run tests 證明：

1. 沒有 API key 時 deterministic tests 仍可跑；`dry_run=False` 才要求 key。
2. OpenRouter SDK chat 與 embedding clients 都設 retry disabled，且 key 不進 repr／receipt。
3. embedding adapter 呼叫公開 `embeddings.generate_async(input=texts, model=..., dimensions=1536, encoding_format="float")`，依 response `index` 還原輸入順序；缺 index、維度不符或數量不符停止。
4. 以 `httpx.MockTransport` 注入 OpenRouter SDK 的 async client，捕捉真實 embedding HTTP request；直接 assert `model／input／dimensions／encoding_format`，並用 SDK 的 typed response 驗證 `data[].index／embedding`，不能只 mock 自己的 adapter method。
5. 另以同一 adapter 實際接上 disposable PostgreSQL Store，證明 1536 維向量能 seed 並 semantic search；不能用兩個彼此分離的 unit test 冒充 wiring 已驗證。
6. live 前以官方 model／endpoint metadata 解析 chat／embedding 可用性與價格，並以已凍結的 input／output／reasoning／embedding caps 建立保守 preflight 估算。`prompt／completion` 等必要單價缺失即阻擋；官方 endpoint 未提供可選的固定 request price 時視為零，未另列 reasoning price 時依官方「reasoning 屬 output tokens」採 completion price。每次回應再以官方 `usage.cost` 核對，超界前不得進下一 call。
7. OpenRouter 的精確 native-token usage 與 cost 只在回應後提供，所以 18,000／USD 0.20 不得宣稱為第一個 request 付款前的數學 hard cap。Product Owner 未接受此 operational-cap 邊界時，不得發 live call。
8. receipts 只保存 requested/resolved model、provider、call/tool counts、input/output/cache/reasoning token counts（若 provider 有回）、latency、cost（若 provider有回）、HTTP/request ID 與**已移除 provider-private reasoning 的** model I/O 投影；秘密與 hidden reasoning 不保存。framework 可依 provider 契約在同一 tool loop 暫時續傳原 reasoning blocks，但不得寫入 receipt。
9. live prompt 是一個 scenario、同時詢問 A 三個細節、A/B 差異與 B 更正、退款核准缺口；不拆成三套最多 3-call scenario。
10. graph 不以程式或 prompt 強迫特定 tool；rubric 依實際任務需要判定模型是否先 search、再為精確原話核對 deep-read、最後回答。第三個 tool call或第四個 model call直接 fail。

Revision 1 的 model-visible prompt 內容凍結如下；實作只能加入上述 deterministic 導覽與最後六則近期訊息，不能偷偷加入完整 fixture：

```text
System:
你正在驗證長訪談的記憶讀取路徑。請只根據目前可見對話與工具結果回答。
目前可見內容不足時，依工具各自說明的使用時機自行取得必要資料；需要核對員工精確原話或短答脈絡時才讀 canonical conversation。
不得自行猜測 reference，不得呼叫其他工具。資料沒有說明時，直接寫「目前資料未說明，需要詢問員工」，不要補造答案。

User:
請一次回答：
1. 餐飲預約網站 A 案的三個獨有細節是什麼？並核對員工描述「過敏備註」做法時使用的精確原句。
2. A 案與健身會員網站 B 案如何區分？B 案目前採會員 API 還是 CSV？
3. 退款例外由誰核准？
```

### 4.3 RED／GREEN／review

```powershell
if (-not $env:MEMORY_ROUTING_SPIKE_DATABASE_URL) { throw 'set MEMORY_ROUTING_SPIKE_DATABASE_URL' }
if (-not $env:MEMORY_ROUTING_SPIKE_EXPECTED_DATABASE) { throw 'set MEMORY_ROUTING_SPIKE_EXPECTED_DATABASE' }
$env:UV_CACHE_DIR='S:\caliburn\.uv-cache-reviewed'
$spikeRoot=(Resolve-Path 'docs\experiments\2026-09-03-memory-routing-canonical-read').Path
$env:PYTHONPATH=(Join-Path $spikeRoot 'src')
uv run --project apps/api --locked pytest "$spikeRoot\tests\test_live_smoke_dry_run.py" "$spikeRoot\tests\test_storage_growth.py" -q
```

- 先紅後綠；此 Task 不得發真 API call。
- Reviewer 檢查付款前與回應後 cost control 是否被如實區分、是否偷開 provider fallback／retry、是否保存 hidden reasoning、是否把三題誤算成三個各自三 call 的 scenario。

```powershell
git diff --check
git add docs/experiments/2026-09-03-memory-routing-canonical-read docs/plans/2026-09-03-memory-routing-canonical-read-isolated-spike.md
git commit -m "test: bound memory read spike cost and growth"
```

**Review checkpoint D：** 案例、rubric、prompt、模型、reasoning、call/tool/token/cost caps 與 receipt schema 在此凍結。未通過 review 不可執行 live。

## Task 5：只執行一次 Tiny Luna smoke，保存真實結果並做 closure review

**Files:**

- Create from actual run: `docs/experiments/2026-09-03-memory-routing-canonical-read/trials/revision-1-luna-medium.json`
- Create from actual run: `docs/experiments/2026-09-03-memory-routing-canonical-read/results.csv`
- Create after observations: `docs/experiments/2026-09-03-memory-routing-canonical-read/report.md`
- Modify: `docs/experiments/2026-09-03-memory-routing-canonical-read/README.md`
- Modify: `docs/experiments/README.md`

### 5.1 Live preflight

1. 確認 Task 1～4 commits 已存在且 worktree clean。
2. 確認 case／rubric／prompt hash 與 README 凍結值相同。
3. 重跑所有 deterministic tests。
4. 確認 disposable DB identity；清理只限本次 fresh `run_id` namespace/thread，不能 drop database 或清別的 run。
5. 從 main checkout 的 `S:\caliburn\apps\api\.env` 讀 key 但不輸出；模型/embedding availability 或保守 cost estimate 不成立就記錄 `preflight_blocked`，不發 provider call。隔離 worktree 不複製該 untracked secret file。

```powershell
if (-not $env:MEMORY_ROUTING_SPIKE_DATABASE_URL) { throw 'set MEMORY_ROUTING_SPIKE_DATABASE_URL' }
if (-not $env:MEMORY_ROUTING_SPIKE_EXPECTED_DATABASE) { throw 'set MEMORY_ROUTING_SPIKE_EXPECTED_DATABASE' }
$env:UV_CACHE_DIR='S:\caliburn\.uv-cache-reviewed'
$spikeRoot=(Resolve-Path 'docs\experiments\2026-09-03-memory-routing-canonical-read').Path
$env:PYTHONPATH=(Join-Path $spikeRoot 'src')
$env:MEMORY_ROUTING_SPIKE_ENV_FILE='S:\caliburn\apps\api\.env'
if (-not (Test-Path -LiteralPath $env:MEMORY_ROUTING_SPIKE_ENV_FILE)) { throw 'missing approved env file' }
uv run --project apps/api --locked pytest "$spikeRoot\tests" -q
uv run --project apps/api --locked python -m memory_read_spike.live_smoke --env-file "$env:MEMORY_ROUTING_SPIKE_ENV_FILE" --revision 1
```

### 5.2 真實 trial 規則

- 只有一個 revision-1 live scenario；最多 3 model calls、2 tool calls，沒有 provider/framework retry。
- 模型第一次若未依題目需要與 tool description 搜尋、未為精確原句選合法 ref 深讀、或最終答案 fail rubric，保存失敗並停止；不可默默修改 prompt 重跑。
- 外部暫時失敗也保存 attempt 與錯誤分類。若在第一個 provider call 前即可確認是 harness plumbing defect，可修正後升 revision；一旦已有模型語意輸出，就不能把不理想結果稱為 plumbing defect。
- trials 保存模型實際看見的 system/user/tool content 與最終答案；不保存 chain-of-thought。
- `results.csv` 至少包含 revision、requested/resolved model、provider、reasoning、model_calls、tool_calls、input/output/cache/reasoning tokens、embedding tokens、latency、cost、A detail pass、A/B correction pass、unknown admission pass、scope pass、overall verdict。

### 5.3 Report 必須區分支持與未證明

只有實際證據允許支持：

- M1：同一 thread restart 後 canonical conversation 連續；
- M2：fixture 的重要久遠細節能透過 routing＋deep-read 找回；
- M4 的 read-side 部分：B current Memory 優先，舊原話仍可回查；
- M7：A／B 具體案例與共同模式沒有互相覆蓋；
- M8 的 read-side 代表情境：模型 Context 有界，且能依本題需要 search/read；
- M10：canonical source 能依 ref 回讀；
- M11：per-document scope 隔離。

報告必須明列尚未證明：M3 admission breadth、完整 M4 manager 更新、M5 未知／衝突 consolidation、M6 整體關係品質、M9 final exact full audit、真實員工資料品質、production scale 與 UI。

此外，這一個 task-driven scenario 只能支持模型在本題形成自然語言 query、選用 search／deep-read 並整合結果；不能泛化成所有訪談主題都會在正確時機自動召回。

### 5.4 Stop／reopen 條件

任一成立即 verdict `STOP_AND_REOPEN_MEM_Q003_Q004`：

- focused Memory semantic search＋deep-read 找不回 A／B 必要細節；
- B 舊 API 被當 current，或 A／B 被混成同一案例；
- 缺 route 時模型捏造；
- stable message ref 無法跨 restart 解析相鄰問答；
- bad／cross-scope ref 洩漏是否存在或內容；
- canonical state 被 Context projection 截短；
- 40／100／200 growth 出現不可接受但未被量測解釋的成長／延遲；
- 超過 model/tool/token/cost cap；
- 必須增加第三份 canonical text、raw-message index、第三個 tool 或無界 retry 才能通過。

失敗後只完成 report 與 decision-register 更新，不進 production、不臨時改方案。

### 5.5 最終 verification 與 review

```powershell
$env:UV_CACHE_DIR='S:\caliburn\.uv-cache-reviewed'
$spikeRoot=(Resolve-Path 'docs\experiments\2026-09-03-memory-routing-canonical-read').Path
$env:PYTHONPATH=(Join-Path $spikeRoot 'src')
uv run --project apps/api --locked pytest "$spikeRoot\tests" -q
git diff --check
git status --short
$readme='docs\experiments\2026-09-03-memory-routing-canonical-read\README.md'
$match=Select-String -LiteralPath $readme -Pattern '^source_baseline_commit: ([0-9a-f]{40})$'
if ($match.Matches.Count -ne 1) { throw 'missing unique source_baseline_commit' }
$spikeBase=$match.Matches[0].Groups[1].Value
git diff --name-only "$spikeBase..HEAD"
```

`git diff --name-only` 必須只包含本實驗、`docs/experiments/README.md`、依結果更新的研究稿／decision register；若包含 production path，停止。

- 使用 `superpowers:requesting-code-review` 做 branch review。
- 使用 `superpowers:verification-before-completion` 驗證所有宣稱。
- Product Owner review report 前，不寫 successor ADR、不 merge、不 push。

```powershell
git add docs/experiments/2026-09-03-memory-routing-canonical-read docs/experiments/README.md docs/specs/2026-09-03-memory-routing-canonical-read-and-isolated-spike-research.md docs/current-decisions.md
git commit -m "docs: report canonical memory read spike"
if (Select-String -LiteralPath 'docs\experiments\2026-09-03-memory-routing-canonical-read\report.md' -Quiet -Pattern '^Verdict: PASS$') {
  git tag memory-routing-canonical-read-spike-v1
} else {
  git tag memory-routing-canonical-read-spike-v1-failed
}
```

Tag 只在 report、review 與 deterministic verification 都完成後建立；live fail 也留下如實的 report/tag，且以 `-failed` 明示結果。

## 4. 計畫完成判準

本計畫的「完成」不是 production 可用，而是下列證據都有真實紀錄：

- pinned framework／provider contract 已 characterise；
- PostgreSQL canonical conversation 可重啟、stable-ID 冪等且未被縮短；
- focused Semantic Memory semantic search 有 exact-scope guard，且沒有 raw source 副本；
- 兩個一欄 strict tools 經實際 provider request 證明；
- A／B／更正／缺 route 的唯一 Luna smoke 有完整可見 input、tool results、輸出、成本與延遲；
- 40／100／200 round storage growth 有量測；
- report 清楚區分「支持」「不支持」「未證明」；
- 結果回到 `MEM-Q003／MEM-Q004` 做下一個單一決策，不由實作者自行擴大架構。

## 5. Plan review checklist（執行授權前）

- [ ] 是否逐條覆蓋研究稿 §6.4 的 input/result/error contract？
- [ ] 是否把 strict caveat、ToolNode validation boundary、async embedding callable 都放入 Stage 0 實測？
- [ ] 是否保留 Checkpointer canonical conversation、Store focused Semantic Memory 的唯一責任，沒有第二份來源，且暫態 tool graph 未污染 canonical checkpoint？
- [ ] 是否只用框架提供的 Saver、Store semantic search、embedding adapter、ToolNode、ToolRuntime 與 graph execution，沒有自製搜尋／agent loop？
- [ ] 是否把 experiment-only constants 明確隔離，沒有偷定 production top-k/window/model/schema？
- [ ] 是否只有一個 Luna live scenario、最多 3 model calls／2 tool calls、medium、零 retry、USD 0.20 cap？
- [ ] 是否在 live 前凍結 fixture/rubric/prompt，失敗不重跑美化？
- [ ] 是否測 scope、restart、stable refs、A/B、更正、unknown、storage growth 與真實 outgoing schema？
- [ ] 是否明列 M3/M5/M6/M9 與 Memory writer 不在本 spike 證明範圍？
- [ ] 是否每個 stage 都有 stop/review checkpoint，且沒有 production 寫入授權？
