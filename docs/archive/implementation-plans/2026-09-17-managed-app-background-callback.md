# Managed App Background Callback Implementation Plan

> **完成封存（2026-09-17）：**下列 Tasks 1–4 已由線性 commits `6e322fe5`、`f920f010`、`0c742248`、`a1157325` 完成；final lifecycle review 的 MABC-F1／F2／F3 亦已由 Task 5 commit `9dbef03d` 關閉。下方未勾選 checkbox 保留為當時的歷史施工稿與 RED／GREEN 指令，不代表待辦；最新效果、驗證與限制以同名 design、`docs/current-decisions.md` 及 Task 5 report 為準。

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 將既有 A 顧問、B1／B2 背景 workflow、dispatcher 與 App 資源接成一個可恢復的本機 managed App，且共用 A graph 不綁死文件或 DB reader。

**Architecture:** App 建立一個 process-owned `BackgroundCoordinator`，按 `document_id` 延遲組裝既有 dispatcher／workflow，並在 Runtime ready 後依 durable state 恢復背景。共用 A graph 永遠安裝無資源綁定的 `BackgroundAvailability`；每次 invoke 由 `ConsultantContext` 注入 local availability provider，模型只看到 provider 產生的最小 notice。

**Tech Stack:** Python 3.13、LangChain 1.4.0、LangGraph 1.2.11、langchain-openrouter 0.2.7、langgraph-checkpoint-postgres 3.1.2、SQLAlchemy／PostgreSQL、pytest、uv。

**Spec:** `docs/specs/2026-09-17-managed-app-background-callback-design.md`

## Global Constraints

- 一個 managed App process 只建立一個共用 A graph，以及一組共用 A／B1／B2 model objects。
- `document_id`、Memory head、DB readers 與 coordinator 只經 per-invocation Runtime context／App composition 傳遞；不得建立 mutable global current document。
- 模型只能看到最小 availability notice；provider、DB handle、callable 與 coordinator 不得進模型訊息或 checkpointed 業務狀態。
- middleware 只讀 availability；不得 wake、重試、等待、更新 cursor 或啟動背景工作。
- 前景回合完成既有 settle 後才 wake；startup 必須先完成 foreground/manual recovery 並設為 ready，再恢復背景。
- durable authority 仍是 admission、Saver checkpoint、publication CAS／receipt 與 canonical source；process map 只作 keyed single-flight cache。
- 維持單一 OpenRouter credential、`openai/gpt-5.6-luna` 與既有正式 A／B1／B2 profiles；本計畫不得送 provider request、讀正式 key或產生費用。
- 不改 Prompt、Skills、Memory／B1／B2／C 語意、compaction、引用、JD 規則、DB schema、migration 或 production authority。
- 不新增 queue、scheduler、polling loop、外部 runtime、distributed CAS、文件封存或 artifact GC。
- 施工工作目錄為 `experiments/jd-relational-app`；每項先寫反例、確認紅燈，再做最小修改。

---

## File Structure

| 檔案 | 責任 |
|---|---|
| `src/jd_relational/consultant_context.py` | 宣告每次 A invoke 可選的 local availability provider，並驗證它只能是 callable 或 `None`。 |
| `src/jd_relational/background_availability.py` | 從 `ConsultantContext` 取得 provider；每個 employee input 只讀一次，將結果保存到 turn state，再投影最小 system block。 |
| `src/jd_relational/consultant_app.py` | 無條件把 stateless availability middleware 裝入共用 A graph，不再在 graph 建構時接 DB readers。 |
| `src/jd_relational/background_coordinator.py` | 新增 App-owned coordinator；延遲建立每文件 dispatcher／workflow、提供 availability、在 ready 後掃描 catalog 恢復背景。 |
| `src/jd_relational/ai_runtime.py` | 將 coordinator 的 availability provider 放入每次 `ConsultantContext`；保留 turn settle 後 wake，移除 startup recovery 內的過早 wake。 |
| `src/jd_relational/managed_app.py` | 用正式 host 資源與 B1／B2 models 建立 coordinator；在 `finish_startup()` 後呼叫 `resume_pending()`。 |
| `src/jd_relational/__main__.py` | AI-enabled serve 將 `RoleModels.case／understanding` 傳給 managed App；無 key 路徑維持人工模式。 |
| `tests/test_background_availability.py` | 固定 per-invocation scope、一次讀取、跨文件隔離與無 provider 行為。 |
| `tests/test_consultant_app.py`、`tests/test_consultant_runtime.py` | 固定 graph 建構不需 App readers，且共用 graph 已包含 stateless middleware。 |
| `tests/test_background_coordinator.py` | 新增 coordinator 組裝、cache、catalog recovery、ready gate 與失敗隔離測試。 |
| `tests/test_background_wakeup.py` | 固定低層 AiRuntime startup recovery 不再過早 wake；turn settle 後 wake 行為不變。 |
| `tests/test_managed_app.py` | 固定正式組裝、startup 順序、manual/no-key 邊界與 CLI 傳參。 |
| `docs/specs/2026-09-17-managed-app-background-callback-design.md`、`docs/current-decisions.md`、`docs/README.md` | 完成後寫入實際結果與仍未完成事項。 |

---

### Task 1: 將背景 availability 改為 per-invocation Runtime context

**Files:**
- Modify: `experiments/jd-relational-app/tests/test_background_availability.py`
- Modify: `experiments/jd-relational-app/tests/test_consultant_app.py`
- Modify: `experiments/jd-relational-app/tests/test_consultant_runtime.py`
- Modify: `experiments/jd-relational-app/src/jd_relational/consultant_context.py:91-122`
- Modify: `experiments/jd-relational-app/src/jd_relational/background_availability.py:49-91`
- Modify: `experiments/jd-relational-app/src/jd_relational/consultant_app.py:36-65`

**Interfaces:**
- Consumes: 既有 `MemoryReadSession.document_id／dataset_id／run_id／head` 與 `availability_notice(admissions, windows, document_id, published_head) -> str`。
- Produces: `ConsultantContext.background_availability: Callable[[str, object | None], str] | None`、零參數 `BackgroundAvailability()`，以及永遠包含該 stateless middleware 的 `build_consultant(model, ...)`。

- [ ] **Step 1: 寫出共享 middleware 的紅燈反例**

在 `tests/test_background_availability.py` 將 `_runtime` 擴充為可傳 provider，並加入兩份文件交錯使用同一 middleware 的測試：

```python
def _runtime(document=DOCUMENT, *, head=None, background_availability=None):
    dataset, run = str(uuid4()), str(uuid4())
    boundary = NoticeBoundary(uuid4(), 1)
    notice = NoticeMaterial(document, None, boundary, (), 0, 0, 0)
    session = MemoryReadSession(dataset, document, run, object(), object(), head, "", object())
    context = ConsultantContext(
        dataset, document, run, object(), ReferenceCodec(b"x" * 32, dataset), notice,
        memory_session=session, background_availability=background_availability,
    )
    return SimpleNamespace(context=context)


def test_one_shared_middleware_uses_each_invocations_own_provider_once():
    other = str(uuid4())
    calls = []

    def provider(document_id, head):
        calls.append((document_id, head))
        return f"notice:{document_id}"

    middleware = BackgroundAvailability()
    first = middleware.before_agent(
        {"messages": [HumanMessage(id="turn-a", content="a")]},
        _runtime(DOCUMENT, head="head-a", background_availability=provider),
    )
    second = middleware.before_agent(
        {"messages": [HumanMessage(id="turn-b", content="b")]},
        _runtime(other, head="head-b", background_availability=provider),
    )

    assert first == {"background_turn_id": "turn-a", "background_notice": f"notice:{DOCUMENT}"}
    assert second == {"background_turn_id": "turn-b", "background_notice": f"notice:{other}"}
    assert calls == [(DOCUMENT, "head-a"), (other, "head-b")]


def test_missing_provider_records_an_empty_notice_without_reading_resources():
    middleware = BackgroundAvailability()
    assert middleware.before_agent(
        {"messages": [HumanMessage(id="turn", content="a")]}, _runtime(),
    ) == {"background_turn_id": "turn", "background_notice": ""}


def test_provider_cannot_project_a_non_string_notice():
    middleware = BackgroundAvailability()
    with pytest.raises(ConsultantContextError, match="^background_notice_not_available$"):
        middleware.before_agent(
            {"messages": [HumanMessage(id="turn", content="a")]},
            _runtime(background_availability=lambda *_: {"not": "text"}),
        )


def test_provider_read_failure_omits_only_the_optional_notice():
    middleware = BackgroundAvailability()

    def unavailable(*_):
        raise OSError("synthetic background read failure")

    assert middleware.before_agent(
        {"messages": [HumanMessage(id="turn", content="a")]},
        _runtime(background_availability=unavailable),
    ) == {"background_turn_id": "turn", "background_notice": ""}
```

在 `tests/test_consultant_app.py` 把原本「有 readers 才包含 middleware」改成以下契約，刪除 partial reader 組裝案例：

```python
def test_shared_consultant_always_contains_stateless_background_availability(model):
    agent = build_consultant(model)
    assert any("BackgroundAvailability" in node for node in agent.nodes)
    assert _tools(agent) == TOOLS
```

在 `tests/test_consultant_runtime.py` 補一個 assertion，證明 process graph 在 App／DB resources 尚未開啟時已帶 middleware：

```python
assert any("BackgroundAvailability" in node for node in runtime.graph.nodes)
```

- [ ] **Step 2: 執行精確測試並確認失敗原因**

Run:

```powershell
uv run pytest tests/test_background_availability.py tests/test_consultant_app.py tests/test_consultant_runtime.py -q
```

Expected: FAIL，包含 `BackgroundAvailability.__init__()` 缺少 `admissions／windows`，或 `ConsultantContext` 不接受 `background_availability`；不得因 provider／網路錯誤失敗。

- [ ] **Step 3: 在 ConsultantContext 增加 local provider**

在 `ConsultantContext` 最後加入欄位，避免改變既有 positional callers：

```python
background_availability: Callable[[str, object | None], str] | None = None
```

在 `__post_init__` 的既有驗證加入：

```python
if self.background_availability is not None and not callable(self.background_availability):
    raise ValueError()
```

這個 callable 是 local dependency，不得加入 `ConsultantState`、`ModelView`、checkpoint 或 system JSON。

- [ ] **Step 4: 將 BackgroundAvailability 改成 stateless runtime reader**

移除 `__init__(admissions, windows)`；保留既有 `availability_notice()` 供 coordinator 使用。把 `_scope()` 與 `before_agent()` 收斂為：

```python
@staticmethod
def _scope(runtime):
    from .consultant_context import ConsultantContext, ConsultantContextError
    from .memory_context import MemoryReadSession

    context = getattr(runtime, "context", None)
    session = getattr(context, "memory_session", None)
    if (not isinstance(context, ConsultantContext)
            or not isinstance(session, MemoryReadSession)
            or session.document_id != context.document_id
            or session.dataset_id != context.dataset_id
            or session.run_id != context.run_id):
        raise ConsultantContextError("invalid_background_scope")
    return context.document_id, session.head, context.background_availability

def before_agent(self, state, runtime):
    current = next((message.id for message in reversed(state["messages"])
                    if isinstance(message, HumanMessage)), None)
    if current is None or state.get("background_turn_id") == current:
        return None
    document_id, head, provider = self._scope(runtime)
    try:
        notice = provider(document_id, head) if provider is not None else ""
    except Exception:
        notice = ""
    if type(notice) is not str:
        from .consultant_context import ConsultantContextError
        raise ConsultantContextError("background_notice_not_available")
    return {"background_turn_id": current, "background_notice": notice}
```

`wrap_model_call()` 維持只投影 `background_notice` 的現有行為。

- [ ] **Step 5: 共用 graph 永遠安裝 stateless middleware**

將 `build_consultant()` 的 `admissions／windows` 參數與 partial wiring 檢查移除，middleware 組裝固定為：

```python
middleware = [AiToolMiddleware(), analysis_skills_middleware(), BackgroundAvailability()]
```

保留既有 tools、guidance 與 A compaction middleware，不調整 profile 或 Prompt。

- [ ] **Step 6: 跑窄回歸並提交**

Run:

```powershell
uv run pytest tests/test_background_availability.py tests/test_consultant_app.py tests/test_consultant_runtime.py tests/test_consultant_context.py tests/test_consultant_memory_context.py -q
uv run python -m compileall -q src tests
```

Expected: 全部 PASS，compileall exit 0，沒有 provider request。

Commit:

```powershell
git add src/jd_relational/consultant_context.py src/jd_relational/background_availability.py src/jd_relational/consultant_app.py tests/test_background_availability.py tests/test_consultant_app.py tests/test_consultant_runtime.py
git commit -m "refactor(memory): inject background availability per run"
```

---

### Task 2: 新增 App-owned BackgroundCoordinator

**Files:**
- Create: `experiments/jd-relational-app/src/jd_relational/background_coordinator.py`
- Create: `experiments/jd-relational-app/tests/test_background_coordinator.py`
- Read-only regression: `experiments/jd-relational-app/src/jd_relational/background_dispatch.py`
- Read-only regression: `experiments/jd-relational-app/src/jd_relational/background_memory_app.py`

**Interfaces:**
- Consumes: `ManualRuntime`、`BackgroundAdmissions`、`ConversationSourceService`、host `store／saver／memory_engine`、B1／B2 model objects、`FORMAL_BACKGROUND_MEMORY_LIMITS`。
- Produces: `BackgroundCoordinator.wake(document_id: str) -> str`、`availability(document_id: str, published_head: object | None) -> str`、`resume_pending() -> int`。

- [ ] **Step 1: 寫 coordinator 的紅燈契約測試**

建立 `tests/test_background_coordinator.py`。用合成 owner 與 monkeypatch 固定組裝，不開 DB 或 provider：

```python
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace
from uuid import uuid4

import pytest

import jd_relational.background_coordinator as module
from jd_relational.background_coordinator import BackgroundCoordinator


class Storage:
    def __init__(self, documents):
        self.documents = tuple(sorted(documents))

    def document_ids(self, *, after=None, limit=100):
        return tuple(value for value in self.documents if after is None or value > after)[:limit]


class Owner:
    def __init__(self, documents=()):
        self.ready = True
        self.storage = Storage(documents)


def coordinator(owner):
    return BackgroundCoordinator(
        owner=owner,
        engine=object(),
        service=object(),
        store=object(),
        checkpointer=object(),
        memory_engine=object(),
        case_model=object(),
        understanding_model=object(),
    )


def test_same_document_reuses_one_dispatcher_and_different_documents_stay_separate(monkeypatch):
    built = []

    def workflow(**kwargs):
        value = SimpleNamespace(publication=object())
        built.append((kwargs["document_id"], value))
        return value

    class Dispatcher:
        def __init__(self, owner, admissions, windows, document_id, **kwargs):
            self.document_id = document_id

        def wake(self):
            return self.document_id

    monkeypatch.setattr(module, "build_background_memory_workflow", workflow)
    monkeypatch.setattr(module, "BackgroundDispatcher", Dispatcher)
    first, second = str(uuid4()), str(uuid4())
    value = coordinator(Owner())

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = {pool.submit(value.wake, first).result(), pool.submit(value.wake, first).result()}
    assert results == {first}
    assert value.wake(second) == second
    assert [document for document, _ in built].count(first) == 1
    assert [document for document, _ in built].count(second) == 1


def test_availability_delegates_to_existing_read_only_rule(monkeypatch):
    calls = []
    monkeypatch.setattr(module, "availability_notice",
        lambda admissions, windows, document, head: calls.append(
            (admissions, windows, document, head)) or "notice")
    value = coordinator(Owner())
    document, head = str(uuid4()), object()
    assert value.availability(document, head) == "notice"
    assert calls[0][2:] == (document, head)


def test_resume_requires_ready_and_isolates_one_documents_failure(monkeypatch):
    documents = (str(uuid4()), str(uuid4()))
    owner = Owner(documents)
    value = coordinator(owner)
    called = []

    def wake(document):
        called.append(document)
        if document == documents[0]:
            raise RuntimeError("synthetic background failure")
        return "wait"

    monkeypatch.setattr(value, "wake", wake)
    assert value.resume_pending() == 2
    assert set(called) == set(documents)

    owner.ready = False
    with pytest.raises(RuntimeError, match="^background_recovery_before_runtime_ready$"):
        value.resume_pending()


def test_catalog_read_failure_stays_on_the_background_side():
    owner = Owner()
    owner.storage.document_ids = lambda **_: (_ for _ in ()).throw(
        RuntimeError("synthetic catalog failure"))
    assert coordinator(owner).resume_pending() == 0
```

另加一個 fresh coordinator 測試：同一組 durable ports 建立第二個 coordinator 時沒有沿用第一個 map，第二個第一次 `wake(document)` 會重新組裝 dispatcher；不要檢查或保存第一個 instance 的私有業務狀態。

- [ ] **Step 2: 執行新測試並確認 module 尚不存在**

Run:

```powershell
uv run pytest tests/test_background_coordinator.py -q
```

Expected: collection FAIL with `ModuleNotFoundError: jd_relational.background_coordinator`。

- [ ] **Step 3: 實作最小 coordinator 與 keyed cache**

建立 `src/jd_relational/background_coordinator.py`：

```python
"""App-owned lifecycle seam for existing document-scoped background work."""

from threading import Lock

from .background_admission import BackgroundAdmissions
from .background_availability import availability_notice
from .background_dispatch import BackgroundDispatcher
from .background_memory_app import build_background_memory_workflow
from .background_memory_limits import FORMAL_BACKGROUND_MEMORY_LIMITS


class BackgroundCoordinator:
    def __init__(self, *, owner, engine, service, store, checkpointer, memory_engine,
                 case_model, understanding_model,
                 limits=FORMAL_BACKGROUND_MEMORY_LIMITS):
        self._owner = owner
        self._engine = engine
        self._service = service
        self._store = store
        self._checkpointer = checkpointer
        self._memory_engine = memory_engine
        self._case_model = case_model
        self._understanding_model = understanding_model
        self._limits = limits
        self._admissions = BackgroundAdmissions(engine)
        self._dispatchers = {}
        self._lock = Lock()

    def _dispatcher(self, document_id):
        with self._lock:
            existing = self._dispatchers.get(document_id)
            if existing is not None:
                return existing
            workflow = build_background_memory_workflow(
                service=self._service,
                document_id=document_id,
                store=self._store,
                checkpointer=self._checkpointer,
                memory_engine=self._memory_engine,
                case_model=self._case_model,
                understanding_model=self._understanding_model,
                limits=self._limits,
            )
            dispatcher = BackgroundDispatcher(
                self._owner, self._admissions, self._service, document_id,
                workflow=workflow, publication=workflow.publication,
                max_windows=self._limits.case_max_windows,
                max_chars=self._limits.case_max_chars,
                context_chars=self._limits.case_context_chars,
            )
            self._dispatchers[document_id] = dispatcher
            return dispatcher

    def wake(self, document_id: str) -> str:
        return self._dispatcher(document_id).wake()

    def availability(self, document_id: str, published_head) -> str:
        return availability_notice(
            self._admissions, self._service, document_id, published_head,
        )

    def resume_pending(self) -> int:
        if not self._owner.ready:
            raise RuntimeError("background_recovery_before_runtime_ready")
        after, attempted = None, 0
        while True:
            try:
                documents = self._owner.storage.document_ids(after=after, limit=100)
            except Exception:
                return attempted
            for document_id in documents:
                try:
                    self.wake(document_id)
                except Exception:
                    pass
                attempted += 1
            if len(documents) < 100:
                return attempted
            after = documents[-1]
```

不得在此 class 增加 thread pool、timer、polling、DB setup、provider client、model retry 或 durable status。`_dispatchers` 只重用同一 process 的 dispatcher lock／future。

- [ ] **Step 4: 驗證 coordinator 與既有 dispatcher／workflow 邊界**

Run:

```powershell
uv run pytest tests/test_background_coordinator.py tests/test_layered_background_dispatch.py tests/test_background_memory_app.py tests/test_background_admission_responsibilities.py -q
```

Expected: 全部 PASS；既有 dispatcher 的同文件並行 single-flight、正式 B1 budgets 與 workflow model identity 測試維持通過。

- [ ] **Step 5: 提交 coordinator 單位**

```powershell
git add src/jd_relational/background_coordinator.py tests/test_background_coordinator.py
git commit -m "feat(memory): coordinate document background workflows"
```

---

### Task 3: 接上 AiRuntime、managed App 與 startup recovery

**Files:**
- Modify: `experiments/jd-relational-app/tests/test_background_wakeup.py`
- Modify: `experiments/jd-relational-app/tests/test_managed_app.py`
- Modify: `experiments/jd-relational-app/tests/test_ai_runtime.py`
- Modify: `experiments/jd-relational-app/src/jd_relational/ai_runtime.py:249-286,479-507,798-822`
- Modify: `experiments/jd-relational-app/src/jd_relational/managed_app.py:1-99`
- Modify: `experiments/jd-relational-app/src/jd_relational/__main__.py:110-130`

**Interfaces:**
- Consumes: Task 1 的 `ConsultantContext.background_availability`、Task 2 的 `BackgroundCoordinator.wake／availability／resume_pending`、既有 `RoleModels.case／understanding`。
- Produces: `AiRuntime(..., background=None, background_availability=None, ...)` 與 `open_managed_app(..., case_model=None, understanding_model=None)`；AI-enabled serve 接好兩個背景角色，manual/no-key 不建立 coordinator。

- [ ] **Step 1: 把 startup wake 的舊測試改成正確紅燈**

在 `tests/test_background_wakeup.py` 保留三個 turn-settle 測試不變，將兩個 startup 測試改為：

```python
def test_low_level_startup_recovery_does_not_wake_before_runtime_is_ready():
    woken = Woken()
    runtime, _, *_ = saved_turn(background=woken)
    assert runtime.owner.finish_startup() == 1
    assert runtime.owner.ready
    assert woken.documents == []
```

這個測試只固定「AiRuntime foreground recovery 不再過早 wake」；真正的 ready 後恢復由 managed App 測試固定。

- [ ] **Step 2: 寫 managed App 組裝與順序反例**

更新 `tests/test_managed_app.py` 的 `composed` fixture：fake host 加上 `store／saver`，fake `AiRuntime` 接受並記錄 `background／background_availability`。新增 fake coordinator：

```python
class Coordinator:
    def __init__(self, **kwargs):
        events.append(("background-owner", kwargs))

    def wake(self, document_id):
        events.append(("wake", document_id))

    def availability(self, document_id, head):
        return ""

    def resume_pending(self):
        assert opened.host.runtime.ready
        events.append("background-resume")
        return 0
```

讓 fixture 的 `startup()` 設 `opened.host.runtime.ready = True`，再新增：

```python
def test_ai_app_resumes_background_only_after_foreground_startup(composed, monkeypatch):
    events, opened = composed
    monkeypatch.setattr(managed, "BackgroundCoordinator", Coordinator)
    app = managed.open_managed_app(
        object(), consultant=object(), enable_chat=True,
        case_model="case", understanding_model="understanding",
    )
    with TestClient(app.app):
        pass
    assert events.index("startup") < events.index("background-resume") < events.index("close")
```

同檔再固定：

- `enable_chat=False` 且兩個 model 為 `None` 時，不建 coordinator；
- `enable_chat=True` 缺任一背景 model 時，在開始服務前以 sanitized composition error 拒絕；
- coordinator 收到的 `owner／engine／service／store／checkpointer／memory_engine` 均是已開 App 資源；
- `AiRuntime` 收到 `background=coordinator.wake` 與 `background_availability=coordinator.availability`；
- CLI 有 key 時傳 `runtime.role_models.case／understanding`，無 key 時維持 `enable_chat=False` 且不建立 model runtime。

- [ ] **Step 3: 執行反例並確認失敗位置**

Run:

```powershell
uv run pytest tests/test_background_wakeup.py tests/test_managed_app.py -q
```

Expected: FAIL；startup wake 測試顯示現況仍呼叫 background，managed App 不接受 `case_model／understanding_model` 或沒有 `BackgroundCoordinator`。

- [ ] **Step 4: 修改 AiRuntime 的兩個 callback 責任**

將 constructor 改為：

```python
def __init__(self, owner, codec, *, source_resolver=None,
             conversation_sources=None, memory_engine=None, background=None,
             background_availability=None, execution_enabled=True):
```

在既有 input validation 同時拒絕 non-callable provider，保存：

```python
self._background = background
self._background_availability = background_availability
```

建立 `ConsultantContext` 時加入：

```python
background_availability=self._background_availability,
```

把 `_recover_previous()` 改成只回傳 foreground recovery：

```python
def _recover_previous(self, document_id: str, timeout: float) -> int:
    return self._recover_previous_run(document_id, timeout)
```

保留 `_settle()` 成功關閉後既有 `_wake_background(record.document_id)`；保留它對 background 失敗的隔離，不新增重試。

- [ ] **Step 5: 在 managed App 建立 coordinator 並於 ready 後恢復**

在 `managed_app.py` import `BackgroundCoordinator`，將入口改為：

```python
def open_managed_app(file, *, consultant, enable_chat=False,
                     case_model=None, understanding_model=None) -> ManagedApp:
```

在開啟 host 後，嚴格要求兩個背景 model 同時存在且只在 `enable_chat=True` 使用：

```python
if enable_chat:
    if case_model is None or understanding_model is None:
        raise ManagedAppError("app_composition_failed")
    background = BackgroundCoordinator(
        owner=host.runtime,
        engine=host.engine,
        service=sources,
        store=host.store,
        checkpointer=host.saver,
        memory_engine=host.memory_engine,
        case_model=case_model,
        understanding_model=understanding_model,
    )
else:
    if case_model is not None or understanding_model is not None:
        raise ManagedAppError("app_composition_failed")
    background = None
```

建立 `AiRuntime` 時傳：

```python
background=background.wake if background is not None else None,
background_availability=background.availability if background is not None else None,
```

lifespan 的順序固定為；foreground recovery／ready precondition 的組裝錯誤沿既有 sanitized code 回覆：

```python
try:
    await run_in_threadpool(host.runtime.finish_startup, timeout=20)
    if background is not None:
        await run_in_threadpool(background.resume_pending)
except Exception:
    raise ManagedAppError("startup_recovery_failed") from None
yield services
```

`resume_pending()` 已逐文件隔離 wake 錯誤；若 ready precondition 或 assembly contract 自身失敗，沿既有 sanitized startup failure 結束，不以半開狀態服務。

- [ ] **Step 6: CLI 傳入已存在的 B1／B2 role models**

在 `__main__.py` 組裝 managed App 時使用：

```python
managed = open_managed_app(
    file,
    consultant=consultant,
    enable_chat=enable_chat,
    case_model=runtime.role_models.case if runtime is not None else None,
    understanding_model=runtime.role_models.understanding if runtime is not None else None,
)
```

不得讀第二把 key、重建 model、切換 provider 或加入 fallback。關閉順序維持 managed App 先 drain host，再由 process owner 關 shared model clients。

- [ ] **Step 7: 驗證接線、恢復與關閉相鄰行為**

Run:

```powershell
uv run pytest tests/test_background_wakeup.py tests/test_managed_app.py tests/test_ai_runtime.py tests/test_ai_restart.py tests/test_consultant_runtime.py tests/test_host_runtime.py tests/test_background_host.py -q
uv run python -m compileall -q src tests
```

Expected: 全部 PASS；startup 事件順序是 foreground recovery → Runtime ready → background resume → serve，turn settle wake 與 host drain 仍通過。

- [ ] **Step 8: 提交 managed assembly 單位**

```powershell
git add src/jd_relational/ai_runtime.py src/jd_relational/managed_app.py src/jd_relational/__main__.py tests/test_background_wakeup.py tests/test_managed_app.py tests/test_ai_runtime.py
git commit -m "feat(app): wire managed background recovery"
```

---

### Task 4: 完整離線回歸、文件證據與交付邊界

**Files:**
- Modify: `docs/specs/2026-09-17-managed-app-background-callback-design.md`
- Modify: `docs/current-decisions.md`
- Modify: `docs/README.md`
- Modify only if its next-gate text is stale: `docs/specs/2026-09-17-openrouter-role-model-factory.md`

**Interfaces:**
- Consumes: Tasks 1–3 的提交與實際測試輸出。
- Produces: G7 完成證據、仍未完成清單及下一個唯一 gate；不產生新產品決策。

- [ ] **Step 1: 執行受影響測試集合**

Run from `experiments/jd-relational-app`:

```powershell
uv run pytest tests/test_background_availability.py tests/test_consultant_app.py tests/test_consultant_runtime.py tests/test_background_coordinator.py tests/test_background_wakeup.py tests/test_managed_app.py tests/test_ai_runtime.py tests/test_ai_restart.py tests/test_layered_background_dispatch.py tests/test_background_memory_app.py tests/test_background_admission_responsibilities.py tests/test_host_runtime.py tests/test_background_host.py -q
```

Expected: 0 failed；記錄實際 passed／skipped，不把未執行的 PG／provider 情境寫成通過。

- [ ] **Step 2: 執行 fresh App 全套離線回歸與語法檢查**

Run:

```powershell
uv run pytest -q
uv run python -m compileall -q src tests
```

Expected: 0 failed、compileall exit 0。若環境型 PG 案例 skipped，記錄實際 skipped；不得為追求全綠讀 key 或呼叫 provider。

- [ ] **Step 3: 以實際結果更新 current authority**

在設計稿與 register 將 stage 更新為「G7 離線窄切片完成」，只記錄實際數字與以下效果：

- 共用 graph 不在建構時綁文件 readers；
- per-invocation provider 兩文件隔離且每個 employee input 只讀一次；
- coordinator map 只作 process-local single-flight，可由 durable state 重建；
- startup 不再過早 wake，ready 後才掃 catalog 恢復；
- turn settle 後 wake 與 shutdown drain 保持；
- 無 key/manual mode 不建立 coordinator；
- 零 provider request、零 key read、零付費、零 schema／migration。

仍未完成必須明列：layered C、自然模型／付費驗證、完整瀏覽器 App 旅程、production authority，以及多 process 拓撲下才需要的原子 admission claim。

- [ ] **Step 4: 檢查文件差異與連結**

Run from repo root:

```powershell
git diff --check
rg -n "managed App|BackgroundCoordinator|下一 gate|仍未完成" docs/current-decisions.md docs/README.md docs/specs/2026-09-17-managed-app-background-callback-design.md docs/specs/2026-09-17-openrouter-role-model-factory.md
```

Expected: `git diff --check` 無輸出；四份文件對同一 stage、未完成範圍與下一 gate 沒有互相矛盾。

- [ ] **Step 5: 驗證提交內容與署名後提交文件**

Run:

```powershell
git status --short
git diff --stat
git config user.name
git config user.email
```

Expected: 只有本計畫列出的程式、測試與文件；署名為 `ArIs0x145 <aris0x145@gmail.com>`，沒有 Claude author／co-author trailer。

Commit:

```powershell
git add docs/specs/2026-09-17-managed-app-background-callback-design.md docs/current-decisions.md docs/README.md docs/specs/2026-09-17-openrouter-role-model-factory.md
git commit -m "docs(memory): record managed callback verification"
```

此切片完成後先回報，不自動進入 C、provider smoke、完整 UI 驗收、merge 或 push。
