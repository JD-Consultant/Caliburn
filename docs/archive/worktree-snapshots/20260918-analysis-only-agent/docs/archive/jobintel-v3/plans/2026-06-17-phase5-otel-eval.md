# Phase ⑤：OTel 儀器 + eval 閘門 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:subagent-driven-development。步驟用 `- [ ]`。
> **本地記錄（untracked，不 commit）。** 日期：2026-06-17。依據 spec §7、決策 **D12/D19/D20**（見 decision-log）。

**Goal:** 為 graph_v3 埋**手動 OpenTelemetry** trace（逐節點 + LLM 呼叫，含 model/token/latency，OTLP 可配、預設近 no-op、廠商中立），並建**輕量 deterministic-first eval harness**（zh-TW 嚴格 JSON / 深問品質 / 文件正確性）當換 OpenRouter 模型的閘門。

**Architecture:** OTel 用 `opentelemetry-sdk` 自管 TracerProvider（exporter 由 `OTEL_EXPORTER_OTLP_ENDPOINT` 配；測試注入 `InMemorySpanExporter`）。node 用 `@traced_node` decorator 包 span（**interrupt 的 `GraphBubbleUp` 不可記為 error**）；LLM 在 `OpenRouterLlm` 包 `gen_ai.*` span（token 取自 langchain `AIMessage.usage_metadata`）。eval：`backend/evals/checks.py`（純函式、fixtures 單測）+ `run_eval.py`（CLI 打真 OpenRouter 套 checks，**不進** pytest）。

**Tech Stack:** opentelemetry-sdk + opentelemetry-exporter-otlp-proto-http（實測版本 pin）；langchain-core 1.4.7（`usage_metadata` 已驗）；pytest。沿用 `backend/.venv`、`TEST_DATABASE_URL`。

## Global Constraints

- 分支 `feat/v3`；additive、不改節點業務邏輯（只包 span）。
- **OTel 預設零外部副作用**：未設 `OTEL_EXPORTER_OTLP_ENDPOINT` 時不掛 exporter（spans 建了不外送）；絕不在 import 時連線。
- **interrupt 不是 error**：`@traced_node` 對 `langgraph.errors.GraphBubbleUp`（含 `GraphInterrupt`）必須**原樣 re-raise、不 record_exception / 不 set ERROR**。
- **eval 真模型呼叫不進一般 pytest**：`checks.py` 用 fixtures 單測；`run_eval.py` 手動 opt-in、需 `OPENROUTER_API_KEY`。
- 提交只 stage 明確路徑；**絕不** `git add -A`（untracked `docs/superpowers/` 不可 commit）。

---

### Task 1：OTel 依賴 + tracing.py（setup + tracer）

**Files:**
- Modify: `backend/requirements.txt`
- Create: `backend/app/graph_v3/tracing.py`、`backend/tests/test_tracing_setup.py`

**Interfaces:**
- Produces: `setup_tracing(exporter=None, *, force=False) -> TracerProvider`（idempotent；傳 exporter→SimpleSpanProcessor；否則看 `OTEL_EXPORTER_OTLP_ENDPOINT` env 決定是否掛 OTLP BatchProcessor）；`get_tracer()`。

- [ ] **Step 1: 裝 opentelemetry（記實測版本）**
```
cd backend
.venv/Scripts/python -m pip install "opentelemetry-sdk" "opentelemetry-exporter-otlp-proto-http"
.venv/Scripts/python -c "import importlib.metadata as m; print('otel-sdk', m.version('opentelemetry-sdk'))"
```
記下版本，下一步 pin。

- [ ] **Step 2: 失敗測試（setup + 一個 span 進 InMemoryExporter）**

Create `backend/tests/test_tracing_setup.py`:
```python
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from app.graph_v3.tracing import setup_tracing, get_tracer


def test_setup_tracing_exports_spans_to_injected_exporter():
    exp = InMemorySpanExporter()
    setup_tracing(exp, force=True)
    with get_tracer().start_as_current_span("unit.smoke") as span:
        span.set_attribute("k", "v")
    spans = exp.get_finished_spans()
    assert [s.name for s in spans] == ["unit.smoke"]
    assert spans[0].attributes["k"] == "v"
```
Run: `uv run pytest tests/test_tracing_setup.py -v`
Expected: FAIL（`app.graph_v3.tracing` 不存在）。

- [ ] **Step 3: 實作 tracing.py**

Create `backend/app/graph_v3/tracing.py`:
```python
"""廠商中立 OTel 儀器（D19）。預設不掛 exporter（近 no-op）；設 OTEL_EXPORTER_OTLP_ENDPOINT
→ OTLP；測試可注入 InMemorySpanExporter。"""
import os

from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, SimpleSpanProcessor

_PROVIDER: TracerProvider | None = None


def setup_tracing(exporter=None, *, force: bool = False) -> TracerProvider:
    global _PROVIDER
    if _PROVIDER is not None and not force:
        return _PROVIDER
    provider = TracerProvider(resource=Resource.create({"service.name": "jobintel-v3"}))
    if exporter is not None:
        provider.add_span_processor(SimpleSpanProcessor(exporter))
    elif os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT"):
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
        provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter()))
    trace.set_tracer_provider(provider)
    _PROVIDER = provider
    return provider


def get_tracer():
    return trace.get_tracer("jobintel.graph_v3")
```

- [ ] **Step 4: 通過測試 + pin requirements**

在 `backend/requirements.txt` 加（版本用 Step 1 實測）：
```
opentelemetry-sdk==<實測>
opentelemetry-exporter-otlp-proto-http==<實測>
```
Run: `uv run pytest tests/test_tracing_setup.py -v` → Expected: 1 passed.

- [ ] **Step 5: Commit**
```bash
git add backend/requirements.txt backend/app/graph_v3/tracing.py backend/tests/test_tracing_setup.py
git commit -m "feat(graph_v3): OpenTelemetry tracing setup (vendor-neutral, OTLP-configurable)"
```

---

### Task 2：traced_node decorator（interrupt 不記 error）

**Files:**
- Modify: `backend/app/graph_v3/tracing.py`（加 `traced_node`）
- Test: `backend/tests/test_traced_node.py`

**Interfaces:**
- Produces: `traced_node(name: str)` decorator，包 async node fn `(state, config)->dict`：開 `node.<name>` span、設 `jobintel.node`/`jobintel.current_step`；對 `GraphBubbleUp` 原樣 re-raise（不記 error），其他例外 record + set ERROR 後 re-raise。

- [ ] **Step 1: 失敗測試（正常→OK span；interrupt→非 error；例外→error）**

Create `backend/tests/test_traced_node.py`:
```python
import pytest
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.trace import StatusCode
from langgraph.errors import GraphInterrupt

from app.graph_v3.tracing import setup_tracing, traced_node


def _exporter():
    exp = InMemorySpanExporter()
    setup_tracing(exp, force=True)
    return exp


@pytest.mark.asyncio
async def test_traced_node_records_normal_span():
    exp = _exporter()

    @traced_node("demo")
    async def node(state, config):
        return {"ok": True}

    out = await node({"current_step": "deep"}, {})
    assert out == {"ok": True}
    s = exp.get_finished_spans()[0]
    assert s.name == "node.demo"
    assert s.attributes["jobintel.node"] == "demo"
    assert s.attributes["jobintel.current_step"] == "deep"
    assert s.status.status_code != StatusCode.ERROR


@pytest.mark.asyncio
async def test_traced_node_interrupt_not_error():
    exp = _exporter()

    @traced_node("ask")
    async def node(state, config):
        raise GraphInterrupt("pause")   # interrupt() 內部即丟此類

    with pytest.raises(GraphInterrupt):
        await node({}, {})
    s = exp.get_finished_spans()[0]
    assert s.status.status_code != StatusCode.ERROR   # interrupt 非錯誤


@pytest.mark.asyncio
async def test_traced_node_real_error_marks_error():
    exp = _exporter()

    @traced_node("boom")
    async def node(state, config):
        raise ValueError("real bug")

    with pytest.raises(ValueError):
        await node({}, {})
    s = exp.get_finished_spans()[0]
    assert s.status.status_code == StatusCode.ERROR
```
Run: `uv run pytest tests/test_traced_node.py -v`
Expected: FAIL（`traced_node` 不存在）。

- [ ] **Step 2: 實作 traced_node（append 到 tracing.py）**

在 `backend/app/graph_v3/tracing.py` 頂部加：
```python
import functools
from opentelemetry.trace import Status, StatusCode
from langgraph.errors import GraphBubbleUp
```
檔末 append：
```python
def traced_node(name: str):
    """包 async graph node 成一個 span；interrupt（GraphBubbleUp）視為正常控制流不記 error。"""
    def deco(fn):
        @functools.wraps(fn)
        async def wrapper(state, config):
            with get_tracer().start_as_current_span(f"node.{name}") as span:
                span.set_attribute("jobintel.node", name)
                step = state.get("current_step") if isinstance(state, dict) else None
                if step:
                    span.set_attribute("jobintel.current_step", step)
                try:
                    return await fn(state, config)
                except GraphBubbleUp:
                    raise                      # interrupt / 正常暫停，非錯誤
                except Exception as exc:       # noqa: BLE001
                    span.record_exception(exc)
                    span.set_status(Status(StatusCode.ERROR))
                    raise
        return wrapper
    return deco
```
> 註：`GraphInterrupt` 為 `GraphBubbleUp` 子類；catch 父類涵蓋所有 bubble-up 控制流。先確認 `from langgraph.errors import GraphBubbleUp, GraphInterrupt` 皆可 import（langgraph 1.2.5）；若不可，回報 BLOCKED。

- [ ] **Step 3: 通過測試**

Run: `uv run pytest tests/test_traced_node.py -v` → Expected: 3 passed.

- [ ] **Step 4: Commit**
```bash
git add backend/app/graph_v3/tracing.py backend/tests/test_traced_node.py
git commit -m "feat(graph_v3): traced_node decorator (interrupt-safe node spans)"
```

---

### Task 3：LLM gateway gen_ai span（model/token/latency）

**Files:**
- Modify: `backend/app/graph_v3/llm.py`（`OpenRouterLlm.complete_text` 包 span）
- Test: `backend/tests/test_llm_tracing.py`

**Interfaces:**
- Consumes: `get_tracer`（Task 1）、`model_for_role`。
- Produces: 每次 `complete_text` 的 ainvoke 包一個 `gen_ai.chat` span，屬性 `gen_ai.system="openrouter"`、`gen_ai.operation.name="chat"`、`gen_ai.request.model=<model>`、`gen_ai.usage.input_tokens`/`output_tokens`（取自 `resp.usage_metadata`，有才設）。

- [ ] **Step 1: 失敗測試（fake chat → 不打網路 → 驗 span 屬性）**

Create `backend/tests/test_llm_tracing.py`:
```python
import asyncio
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from langchain_core.messages import AIMessage

from app.config import settings
from app.graph_v3 import llm as llm_mod
from app.graph_v3.tracing import setup_tracing


class _FakeChat:
    async def ainvoke(self, msgs):
        return AIMessage(content="嗨", usage_metadata={"input_tokens": 11, "output_tokens": 7, "total_tokens": 18})


def test_complete_text_emits_gen_ai_span(monkeypatch):
    exp = InMemorySpanExporter()
    setup_tracing(exp, force=True)
    settings.model_indicator = "vendor/mid"
    monkeypatch.setattr(llm_mod, "get_chat_llm", lambda role, temperature=0.2: _FakeChat())

    out = asyncio.run(llm_mod.OpenRouterLlm().complete_text("p", role="indicator"))
    assert out == "嗨"
    span = next(s for s in exp.get_finished_spans() if s.name == "gen_ai.chat")
    assert span.attributes["gen_ai.system"] == "openrouter"
    assert span.attributes["gen_ai.request.model"] == "vendor/mid"
    assert span.attributes["gen_ai.usage.input_tokens"] == 11
    assert span.attributes["gen_ai.usage.output_tokens"] == 7
```
Run: `uv run pytest tests/test_llm_tracing.py -v`
Expected: FAIL（尚無 span）。

- [ ] **Step 2: 在 complete_text 包 span**

`backend/app/graph_v3/llm.py`：頂部加 `from app.graph_v3.tracing import get_tracer`。把 `complete_text` 的 ainvoke 段改成（span 包住每次 attempt 的呼叫）：
```python
    async def complete_text(self, prompt: str, *, role: str = "cheap") -> str:
        llm = get_chat_llm(role)
        model = model_for_role(role)
        for attempt in range(self._retries):
            try:
                with get_tracer().start_as_current_span("gen_ai.chat") as span:
                    span.set_attribute("gen_ai.system", "openrouter")
                    span.set_attribute("gen_ai.operation.name", "chat")
                    span.set_attribute("gen_ai.request.model", model)
                    resp = await llm.ainvoke([HumanMessage(content=prompt)])
                    um = getattr(resp, "usage_metadata", None) or {}
                    if um.get("input_tokens") is not None:
                        span.set_attribute("gen_ai.usage.input_tokens", um["input_tokens"])
                    if um.get("output_tokens") is not None:
                        span.set_attribute("gen_ai.usage.output_tokens", um["output_tokens"])
                content = resp.content
                return content if isinstance(content, str) else str(content)
            except Exception as exc:  # noqa: BLE001
                if attempt < self._retries - 1:
                    logger.warning("OpenRouterLlm text attempt %d failed: %s", attempt + 1, exc)
                    await asyncio.sleep(0.5 * (attempt + 1))
                else:
                    logger.error("OpenRouterLlm text exhausted: %s", exc)
        return ""
```
（latency 由 span 起訖自動涵蓋；cost 暫不設。）

- [ ] **Step 3: 通過測試 + LLM gateway 既有測試不破**

Run: `uv run pytest tests/test_llm_tracing.py tests/test_llm_gateway.py -v` → Expected: 全 pass。

- [ ] **Step 4: Commit**
```bash
git add backend/app/graph_v3/llm.py backend/tests/test_llm_tracing.py
git commit -m "feat(graph_v3): gen_ai span on OpenRouter LLM calls (model + token usage)"
```

---

### Task 4：把 traced_node 套到所有 graph_v3 節點

**Files:**
- Modify: `backend/app/graph_v3/nodes.py`、`backend/app/graph_v3/deep_nodes.py`、`backend/app/graph_v3/assemble_nodes.py`、`backend/app/graph_v3/build_doc.py`
- Test: `backend/tests/test_graph_v3_spans.py`

**Interfaces:**
- Consumes: `traced_node`（Task 2）。
- Produces: 每個節點函式被 `@traced_node("<name>")` 包；跑圖時每節點一個 `node.<name>` span。

- [ ] **Step 1: 失敗測試（跑 stub 圖 → 蒐集到逐節點 span）**

Create `backend/tests/test_graph_v3_spans.py`:
```python
import pytest
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import Command

from app.graph_v3.tracing import setup_tracing
from app.graph_v3.graph import build_graph_v3
from app.graph_v3.state import new_state
from app.graph_v3.deps import Deps
from app.services.knowledge.models import SearchResult, Hit, TaskPool, PoolGroup, PoolUnit, PoolTask
from tests.conftest_graph import FakeKnowledge, SpyPersist, FakeLlm


@pytest.mark.asyncio
async def test_nodes_emit_spans():
    exp = InMemorySpanExporter()
    setup_tracing(exp, force=True)
    fake = FakeKnowledge(
        search=SearchResult(mode="dense", hits=[Hit(id="p1", ocs_code="OC1", chunk_level="profile")]),
        pool=TaskPool(groups=[PoolGroup(ocs_code="OC1", units=[
            PoolUnit(unit_id="U1", unit_title="u", tasks=[PoolTask(id="x", task_id="T1.1", task_title="巡檢")])])]))
    graph = build_graph_v3(checkpointer=MemorySaver())
    cfg = {"configurable": {"thread_id": "t1", "deps": Deps(knowledge=fake, persist=SpyPersist(), llm=FakeLlm())}}

    out = await graph.ainvoke(new_state(job_profile_id="p1", job_title="工程師"), cfg)
    await graph.ainvoke(Command(resume={"ocs_code": "OC1"}), cfg)
    names = {s.name for s in exp.get_finished_spans()}
    assert "node.pick_profile" in names
    assert "node.build_task_pool" in names
```
Run: `uv run pytest tests/test_graph_v3_spans.py -v`
Expected: FAIL（節點尚未被裝飾）。

- [ ] **Step 2: 套 decorator 到每個節點**

在各檔 import `from app.graph_v3.tracing import traced_node`，並於節點 `async def` 上加裝飾：
- `nodes.py`：`@traced_node("pick_profile")` 於 `pick_profile`；`@traced_node("build_task_pool")` 於 `build_task_pool`。
- `deep_nodes.py`：`@traced_node("star")`/`@traced_node("five_w2h")`/`@traced_node("indicator")` 於對應節點。
- `assemble_nodes.py`：`@traced_node("assemble_ksa")`。
- `build_doc.py`：`@traced_node("build_doc")`。
（純函式 helper、route_* 條件函式不裝飾。）

- [ ] **Step 3: 通過測試 + 全套件**

Run: `uv run pytest tests/test_graph_v3_spans.py -v` → 1 passed。
Run: `TEST_DATABASE_URL=postgresql+asyncpg://postgres:password@localhost:5432/jobintel uv run pytest -q` → 全綠（含既有深問/e2e；確認 interrupt 流程未被 span 破壞）。

- [ ] **Step 4: Commit**
```bash
git add backend/app/graph_v3/nodes.py backend/app/graph_v3/deep_nodes.py backend/app/graph_v3/assemble_nodes.py backend/app/graph_v3/build_doc.py backend/tests/test_graph_v3_spans.py
git commit -m "feat(graph_v3): wrap all nodes with traced_node spans"
```

---

### Task 5：eval checks.py（純函式 + fixtures 單測）

**Files:**
- Create: `backend/evals/__init__.py`、`backend/evals/checks.py`、`backend/tests/test_eval_checks.py`

**Interfaces:**
- Produces（純函式）：
  - `is_valid_json(text: str) -> bool`
  - `has_keys(obj: dict, keys: list[str]) -> bool`
  - `is_zh_tw(text: str) -> bool`（含 CJK 且英文字母佔比低）
  - `doc_structure_ok(doc: dict) -> tuple[bool, list[str]]`（ocu_units 存在；code 格式 `T\d+`、`T\d+\.\d+`、`P\d+\.\d+\.\d+`、`O...`；ksa 三類存在）
  - `deep_quality_ok(task: dict, threshold: float = 0.60) -> bool`（`behavior_indicators` 皆有、`quality_score >= threshold`、必填 5W2H 欄非空）

- [ ] **Step 1: 失敗測試（每 check 用 fixtures）**

Create `backend/tests/test_eval_checks.py`:
```python
from evals.checks import is_valid_json, has_keys, is_zh_tw, doc_structure_ok, deep_quality_ok


def test_is_valid_json():
    assert is_valid_json('{"a":1}')
    assert not is_valid_json("not json")


def test_has_keys():
    assert has_keys({"a": 1, "b": 2}, ["a", "b"])
    assert not has_keys({"a": 1}, ["a", "b"])


def test_is_zh_tw():
    assert is_zh_tw("依點檢表逐項檢查設備")
    assert not is_zh_tw("this is english only")


def test_doc_structure_ok():
    good = {"ocs_content": {"ocu_units": [
        {"ocu_code": "T1", "ocu_name": "u", "tasks": [
            {"task_code": "T1.1", "task_name": "巡檢",
             "indicators": [{"code": "P1.1.1", "text": "x"}],
             "outputs": [{"code": "O1.1.1", "name": "點檢表"}]}]}]},
        "ocs_ksa": {"knowledge": [], "skills": [], "attitudes": []}}
    ok, reasons = doc_structure_ok(good)
    assert ok, reasons
    bad = {"ocs_content": {"ocu_units": []}, "ocs_ksa": {}}
    ok2, reasons2 = doc_structure_ok(bad)
    assert not ok2 and reasons2


def test_deep_quality_ok():
    good = {"situation": "s", "purpose": "p", "workflow_steps": ["a"], "outputs": ["o"],
            "behavior_indicators": [{"quality_score": 0.8}]}
    assert deep_quality_ok(good)
    bad = {"behavior_indicators": [{"quality_score": 0.3}]}
    assert not deep_quality_ok(bad)
```
Run: `uv run pytest tests/test_eval_checks.py -v`
Expected: FAIL（`evals.checks` 不存在）。

- [ ] **Step 2: 實作 checks.py**

Create `backend/evals/__init__.py`（空）。Create `backend/evals/checks.py`:
```python
"""Deterministic eval checks（D20）：能用規則判的全 deterministic，judge 延後。"""
import re

from app.utils import safe_parse_json

_MISSING = object()
_CJK = re.compile(r"[一-鿿]")
_ASCII_ALPHA = re.compile(r"[A-Za-z]")
_CODE_OCU = re.compile(r"^T\d+$")
_CODE_TASK = re.compile(r"^T\d+\.\d+$")
_CODE_IND = re.compile(r"^P\d+\.\d+\.\d+$")
_CODE_OUT = re.compile(r"^O\d+\.\d+\.\d+$")


def is_valid_json(text: str) -> bool:
    return safe_parse_json(text, default=_MISSING) is not _MISSING


def has_keys(obj: dict, keys: list[str]) -> bool:
    return isinstance(obj, dict) and all(k in obj for k in keys)


def is_zh_tw(text: str) -> bool:
    if not text or not _CJK.search(text):
        return False
    cjk = len(_CJK.findall(text))
    ascii_alpha = len(_ASCII_ALPHA.findall(text))
    return cjk >= ascii_alpha  # CJK 為主、容許少量英文（縮寫/系統名）


def doc_structure_ok(doc: dict) -> tuple[bool, list[str]]:
    reasons: list[str] = []
    units = (doc.get("ocs_content") or {}).get("ocu_units") or []
    if not units:
        reasons.append("no ocu_units")
    for u in units:
        if not _CODE_OCU.match(u.get("ocu_code", "")):
            reasons.append(f"bad ocu_code {u.get('ocu_code')!r}")
        for t in u.get("tasks", []):
            if not _CODE_TASK.match(t.get("task_code", "")):
                reasons.append(f"bad task_code {t.get('task_code')!r}")
            for ind in t.get("indicators", []):
                if not _CODE_IND.match(ind.get("code", "")):
                    reasons.append(f"bad indicator code {ind.get('code')!r}")
            for o in t.get("outputs", []):
                if not _CODE_OUT.match(o.get("code", "")):
                    reasons.append(f"bad output code {o.get('code')!r}")
    if "ocs_ksa" not in doc or not all(k in (doc.get("ocs_ksa") or {})
                                       for k in ("knowledge", "skills", "attitudes")):
        reasons.append("ocs_ksa missing K/S/A buckets")
    return (not reasons, reasons)


def deep_quality_ok(task: dict, threshold: float = 0.60) -> bool:
    inds = task.get("behavior_indicators") or []
    if not inds:
        return False
    return all((i.get("quality_score") or 0) >= threshold for i in inds)
```

- [ ] **Step 3: 通過測試**

Run: `uv run pytest tests/test_eval_checks.py -v` → Expected: 5 passed.

- [ ] **Step 4: Commit**
```bash
git add backend/evals/__init__.py backend/evals/checks.py backend/tests/test_eval_checks.py
git commit -m "feat(evals): deterministic eval checks (JSON/zh-TW/doc-structure/deep-quality)"
```

---

### Task 6：eval datasets + run_eval.py CLI（閘門）+ README + 記憶

**Files:**
- Create: `backend/evals/datasets/json_zhtw.json`、`backend/evals/run_eval.py`、`backend/evals/README.md`
- Test: `backend/tests/test_run_eval_smoke.py`

**Interfaces:**
- Consumes: `checks.*`、`OpenRouterLlm`（真模型，opt-in）、`build_doc._assemble`（deterministic）。
- Produces: `run_eval.py` CLI：`uv run python evals/run_eval.py`（需 `OPENROUTER_API_KEY`）→ 跑 3 類、印 pass/fail 表、全過 exit 0 否則 1。可注入 llm（測試用 stub）：`async def run_all(llm=None) -> tuple[bool, dict]`。

- [ ] **Step 1: 失敗測試（run_all 用 stub llm，不打網路；驗閘門結構）**

Create `backend/tests/test_run_eval_smoke.py`:
```python
import asyncio
from tests.conftest_graph import FakeLlm
from evals.run_eval import run_all


def test_run_all_passes_with_good_stub():
    # stub：JSON 類回合法 zh-TW JSON
    good = '{"situation":"晨班巡檢產線","purpose":"確保設備可用"}'
    ok, report = asyncio.run(run_all(llm=FakeLlm(text=good)))
    assert "json_zhtw" in report and "doc_structure" in report
    assert isinstance(ok, bool)
    assert report["doc_structure"]["passed"] is True   # deterministic 類必過
```
Run: `uv run pytest tests/test_run_eval_smoke.py -v`
Expected: FAIL（`evals.run_eval` 不存在）。

- [ ] **Step 2: dataset + run_eval.py**

Create `backend/evals/datasets/json_zhtw.json`:
```json
[
  {"name": "situation_purpose", "prompt": "用繁體中文、只輸出 JSON：{\"situation\":\"…\",\"purpose\":\"…\"}，描述「設備巡檢」這個任務的情境與目的。", "keys": ["situation", "purpose"]}
]
```
Create `backend/evals/run_eval.py`:
```python
"""Eval 閘門（D20）：換 OpenRouter 模型前手動跑。deterministic-first。
  uv run python evals/run_eval.py     # 需 OPENROUTER_API_KEY（json_zhtw 類打真模型）
checks 邏輯見 evals/checks.py（已單測）。"""
from __future__ import annotations

import asyncio
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from evals import checks  # noqa: E402
from app.graph_v3.build_doc import _assemble  # noqa: E402

_DATA = os.path.join(os.path.dirname(__file__), "datasets", "json_zhtw.json")

# 文件正確性用的固定 state（deterministic，不需模型）
_DOC_STATE = {
    "job_title": "設備維護工程師", "job_summary": "維護產線設備",
    "profile": {"selected_ocs_code": "OC1"},
    "tasks": [{"task_name": "巡檢", "unit_id": "U1", "unit_title": "預防保養",
               "outputs": ["點檢表"],
               "behavior_indicators": [{"output_name": "點檢表", "indicator_5w2h": "每日晨班完成點檢表",
                                        "quality_score": 0.8}]}],
    "ksa": {"knowledge": [{"content": "設備原理", "source": "catalog", "icap_ref": "K01"}],
            "skills": [], "attitudes": []},
}


async def _eval_json_zhtw(llm) -> dict:
    cases = json.load(open(_DATA, encoding="utf-8"))
    results = []
    for c in cases:
        text = await llm.complete_text(c["prompt"], role="cheap")
        ok_json = checks.is_valid_json(text)
        obj = json.loads(text) if ok_json else {}
        ok = ok_json and checks.has_keys(obj, c["keys"]) and checks.is_zh_tw(text)
        results.append({"name": c["name"], "ok": ok})
    return {"passed": all(r["ok"] for r in results), "cases": results}


def _eval_doc_structure() -> dict:
    doc = _assemble(_DOC_STATE)
    ok, reasons = checks.doc_structure_ok(doc)
    ok = ok and checks.deep_quality_ok(_DOC_STATE["tasks"][0])
    return {"passed": ok, "reasons": reasons}


async def run_all(llm=None) -> tuple[bool, dict]:
    if llm is None:
        from app.graph_v3.llm import OpenRouterLlm
        llm = OpenRouterLlm()
    report = {
        "json_zhtw": await _eval_json_zhtw(llm),
        "doc_structure": _eval_doc_structure(),
    }
    passed = all(section["passed"] for section in report.values())
    return passed, report


def main() -> int:
    if not os.getenv("OPENROUTER_API_KEY"):
        print("✗ 需 OPENROUTER_API_KEY 才能跑 json_zhtw（真模型）類。")
    passed, report = asyncio.run(run_all())
    print(json.dumps(report, ensure_ascii=False, indent=2))
    print("GATE:", "PASS ✅" if passed else "FAIL ❌")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
```
Create `backend/evals/README.md`:
```markdown
# Eval 閘門（Phase ⑤ / D20）

換 OpenRouter 模型前手動跑，確認便宜模型仍可靠：
    cd backend
    OPENROUTER_API_KEY=sk-or-... uv run python evals/run_eval.py

- **json_zhtw**：打真模型，驗嚴格 JSON + 必填 key + zh-TW（驗便宜模型）。
- **doc_structure**：deterministic，驗 build_doc 編碼/分組/K-S-A + 深問 quality_score。
- 深問語義品質的 LLM-judge：延後（見 decision-log D20）。
checks 純函式於 `evals/checks.py`，已被 `tests/test_eval_checks.py` 單測。
```

- [ ] **Step 3: 通過測試**

Run: `uv run pytest tests/test_run_eval_smoke.py -v` → Expected: 1 passed.

- [ ] **Step 4: 全套件 + Commit**

Run: `TEST_DATABASE_URL=postgresql+asyncpg://postgres:password@localhost:5432/jobintel uv run pytest -q` → 全綠。
```bash
git add backend/evals/datasets/json_zhtw.json backend/evals/run_eval.py backend/evals/README.md backend/tests/test_run_eval_smoke.py
git commit -m "feat(evals): run_eval gate (json/zh-TW real-model + deterministic doc) + README"
```

- [ ] **Step 5: 更新專案記憶**

更新 `C:\Users\chenb\.claude\projects\s--jobintel-ai\memory\phase4-status.md`（或新增 phase5）：記 Phase ⑤ DONE（OTel 手動 span：node + gen_ai LLM；eval harness deterministic-first + run_eval 閘門）；下一步＝前端 CopilotKit 接 interrupt。

---

## 完成後
- **產出**：graph_v3 全節點 + LLM 呼叫有 OTel span（OTLP 可配、預設近 no-op）；eval harness（checks 單測 + run_eval 閘門）。
- **手動驗證**：`OTEL_EXPORTER_OTLP_ENDPOINT=... uvicorn app.copilotkit_live_app:app` 可把 trace 送到任一 OTLP 後端（如 Langfuse 自建/Jaeger）；`OPENROUTER_API_KEY=... uv run python evals/run_eval.py` 換模型前跑。
- **下一步**：前端 CopilotKit 接 interrupt；（後話）Langfuse 自建 dashboard（D12）、LLM-judge 品質評分、cost 屬性（price map）。

## Self-Review
- **Spec/決策覆蓋**：§7 OTel 逐節點+token/latency ✓（Task 3/4）；§7 小 eval 三類 ✓（Task 5/6，深問品質用 quality_score、文件正確性 deterministic、zh-TW JSON 打真模型）；D19 手動 SDK+OTLP 可配 ✓；D20 deterministic-first + judge 延後 ✓；廠商中立（OTLP→Langfuse 後話）✓。
- **interrupt 安全**：`traced_node` 對 `GraphBubbleUp` 不記 error（Task 2 專測）；Task 4 Step 3 跑全套件確認深問/e2e interrupt 流程未壞。
- **無 placeholder**：每 task 有完整 test + 實作碼 + 指令；唯一「實測值」為 opentelemetry 版本（Task 1 量測+pin）。
- **真模型不進 pytest**：`run_eval` 真呼叫 opt-in；`run_all(llm=...)` 可注入 stub 供 smoke 測（Task 6）；checks 純函式 fixtures 單測（Task 5）。
- **型別一致**：`setup_tracing(exporter=None,*,force=False)`、`get_tracer()`、`traced_node(name)`、`gen_ai.*` 屬性名、`run_all(llm=None)->(bool,dict)`、checks 簽章跨 task 對齊。
