# Phase ③ 深問子圖（deep_interview）+ OpenRouter LLM — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:subagent-driven-development（建議）或 superpowers:executing-plans。步驟用 `- [ ]` 追蹤。
> **本地記錄（untracked，不 commit 進 git）。** 日期：2026-06-16。依據 spec `2026-06-16-jobintel-ai-v3-architecture.md` §2/§4.1/§4.5/§8/§9、決策 `2026-06-16-refactor-decision-log.md` D8/D10。

**Goal:** 在 `feat/v3` 接上「逐任務深問」：以 **interrupt 驅動**的 `star → five_w2h → indicator` 三個階段節點，對 `tasks[current_task_index]` 逐一深問，產出 STAR 案例 + 5W2H 細節 + 行為指標，寫進 graph state；並引入 **OpenRouter per-role LLM gateway**（D10）。所有產出留在 state（checkpointer 為工作態 of-record）；豐欄位的關聯式持久化留 Phase ④。

**Architecture:**
- **一階段 = 一節點**，每節點內用 `interrupt(ask_human)` 迴圈逐題問人（取代舊的關鍵字路由 / 輪詢重入）。LangGraph 語意：節點內多個 `interrupt()` 以「呼叫順序索引」對應 resume 值；同一節點執行的 replay 會把先前已答的 interrupt 依序回填、停在下一個未答的 → 只要節點內 interrupt 序列在 replay 間穩定就安全（我們的 prefill 在 interrupt 之前算好且 idempotent，故穩定）。
- **逐任務迴圈 = 單層 node loop**（非 nested-subgraph-in-loop）：每個任務都「重新進入 `star` 節點」→ 全新的 interrupt 計數器，徹底避開巢狀子圖在迴圈中的 interrupt 傳遞風險。迴圈以 `deep.current_task_index` 前進。
- **D8 子圖可獨立測**：在 Task 5 用「只含 3 個深問節點的測試用小圖」獨立驗證一條完整單任務深問，**不在 app code 出貨未用的子圖殼**（YAGNI）。
- **D10 LLM gateway**：`get_chat_llm(role)` → OpenAI 相容 `ChatOpenAI(base_url=OpenRouter)`，role→model 三階（deep / indicator / cheap，settings 可配）。`LlmPort` 介面注入 `Deps.llm`，測試用 `FakeLlm`。STAR 整理用 **deep 階**（best-effort，失敗保留原答）；indicator 生成用 **indicator 階**。
- **重用**既有調好的 prompt / 常數（`app.graph.prompts.star` / `app.graph.prompts.indicator` / `app.graph.constants` 皆為純資料模組，其 `__init__` 為空，import 不觸發舊重鏈）；**僅重寫節點控制流**為 interrupt 風格。`app.graph.nodes.*`、`icap_retriever`、`llm_gateway` 一律不 import（含 pgvector/被移除鏈）。
- **持久化**：深問豐欄位（star_case / 5W2H / behavior_indicators）只進 state；不動 schema、不擴 `TaskRepo`。`company_tasks` 行已在 Phase ② `build_task_pool` flush。**豐欄位關聯式持久化＝Phase ④ 範圍**（spec §12 已將 5W2H→JSONB 微重構列為未來）。

**Tech Stack:** langgraph 1.2.5（`interrupt`/`Command`/`StateGraph`，已裝）+ **langchain-openai**（D10 新增，OpenRouter）+ pydantic + pytest。沿用 Phase ①② 的 `KnowledgeClient`、`Deps`、venv（`backend/.venv`，python 3.13）、docker Postgres、`TEST_DATABASE_URL`。

**前置：** 在 `feat/v3`；Phase ①②②-FE 已完成（22 tests 綠）。

> ⚠️ **已知取捨**
> 1. STAR 整理的 deep-LLM 呼叫在 4 個 interrupt 之後 → 只在「R 已答」那次 invoke 跑一次（前幾次 invoke 停在更早的 interrupt，不會到達 LLM 呼叫）。冪等、無副作用。
> 2. catalog prefill（`tasks_by_id`）在 five_w2h 入口呼叫一次；read-only、idempotent，replay 重跑可接受。
> 3. indicator 品質重試上限 1 次（沿用舊行為）→ 迴圈必終止。
> 4. 若 langgraph 1.2.5 實測中「單層 node loop + interrupt」對某拓樸有非預期行為：節點函式不變，只調 `graph.py` 邊；本計畫拓樸刻意只用單層迴圈與條件邊，風險已最小化。

---

## 檔案結構

| 檔案 | 責任 | 動作 |
|---|---|---|
| `backend/app/config.py` | 加 OpenRouter / 三階模型 settings | Modify |
| `backend/app/graph_v3/deps.py` | 加 `LlmPort` Protocol + `Deps.llm` | Modify |
| `backend/app/graph_v3/llm.py` | OpenRouter gateway：`model_for_role` / `get_chat_llm` / `OpenRouterLlm`(LlmPort 實作) | Create |
| `backend/app/graph_v3/deep_nodes.py` | `star_node` / `five_w2h_node` / `indicator_node`（interrupt 風格）+ 純 helper | Create |
| `backend/app/graph_v3/graph.py` | 接上深問迴圈（route_deep / advance / finish_deep / route_after_indicator + 邊） | Modify |
| `backend/app/graph_v3/stubs.py` | 加 `StubLlm`、`StubKnowledge.tasks_by_id` 回真資料 | Modify |
| `backend/app/graph_v3/serving.py` | `Deps(..., llm=StubLlm())` | Modify |
| `backend/requirements.txt` | 加 `langchain-openai`（實測版本） | Modify |
| `backend/tests/conftest_graph.py` | `FakeKnowledge` 加可配 `tasks_by_id`；新增 `FakeLlm` | Modify |
| `backend/tests/test_llm_gateway.py` | gateway 測 | Create |
| `backend/tests/test_deep_star.py` | star 測 | Create |
| `backend/tests/test_deep_five_w2h.py` | five_w2h 測 | Create |
| `backend/tests/test_deep_indicator.py` | indicator 測 | Create |
| `backend/tests/test_deep_subgraph.py` | 單任務深問端到端（D8 隔離測） | Create |
| `backend/tests/test_graph_v3_e2e.py` | 既有：改成期待深問 interrupt | Modify |
| `backend/tests/test_graph_v3_deep_loop.py` | 雙任務整合（迴圈 + index 前進） | Create |

---

### Task 1：OpenRouter LLM gateway（D10）+ LlmPort 注入

**Files:** Modify `backend/requirements.txt`、`backend/app/config.py`、`backend/app/graph_v3/deps.py`；Create `backend/app/graph_v3/llm.py`、`backend/tests/test_llm_gateway.py`

- [ ] **Step 1: 裝 langchain-openai（OpenRouter = OpenAI 相容）**

Run（venv）：
```
backend/.venv/Scripts/python -m pip install "langchain-openai"
backend/.venv/Scripts/python -c "import langchain_openai, importlib.metadata as m; print('langchain-openai', m.version('langchain-openai'))"
```
記下實測版本（下一步 pin 進 requirements）。若與 langchain-core 1.4.7 衝突，pip 會提示 → 改裝相容版本再記錄。

- [ ] **Step 2: 失敗測試（鎖定 gateway 介面 + role→model 映射，無網路）**

Create `backend/tests/test_llm_gateway.py`:
```python
import pytest

from app.config import settings
from app.graph_v3 import llm as llm_mod
from app.graph_v3.deps import LlmPort


def test_model_for_role_maps_three_tiers():
    settings.model_deep = "vendor/deep"
    settings.model_indicator = "vendor/mid"
    settings.model_cheap = "vendor/cheap"
    assert llm_mod.model_for_role("deep") == "vendor/deep"
    assert llm_mod.model_for_role("indicator") == "vendor/mid"
    assert llm_mod.model_for_role("cheap") == "vendor/cheap"
    # 未知 role → 退回 cheap
    assert llm_mod.model_for_role("???") == "vendor/cheap"


def test_get_chat_llm_uses_openrouter_base_url():
    settings.openrouter_base_url = "https://openrouter.ai/api/v1"
    settings.openrouter_api_key = "sk-test"
    chat = llm_mod.get_chat_llm("indicator")
    # langchain_openai ChatOpenAI 暴露 model_name 與 openai_api_base
    assert chat.model_name == settings.model_indicator
    assert "openrouter.ai" in str(chat.openai_api_base)


def test_openrouter_llm_satisfies_port_and_parses_json():
    impl = llm_mod.OpenRouterLlm()
    assert isinstance(impl, LlmPort)  # runtime_checkable Protocol

    # 不打網路：覆寫 complete_text 驗 complete_json 解析路徑。
    # 注意 safe_parse_json 只吃「純 JSON」或「markdown ```json 圍欄」，不從雜訊抽 {...}。
    class _Stub(llm_mod.OpenRouterLlm):
        async def complete_text(self, prompt, *, role="cheap"):
            return '```json\n{"a": 1, "b": [2, 3]}\n```'

    import asyncio
    out = asyncio.run(_Stub().complete_json("p", role="indicator", default=None))
    assert out == {"a": 1, "b": [2, 3]}
```
Run：`cd backend && .venv/Scripts/python -m pytest tests/test_llm_gateway.py -q`
Expected：FAIL（`app.graph_v3.llm` 不存在、settings 缺欄、`LlmPort` 缺）。

- [ ] **Step 3: 加 settings（config.py）**

在 `backend/app/config.py` 的 `class Settings` 內，`indexer_*` 區塊之後加：
```python
    # OpenRouter LLM gateway（D10）— per-role 模型分層，OpenAI 相容
    openrouter_api_key: str = ""
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    model_deep: str = "deepseek/deepseek-chat"       # 強階：STAR 整理（OpenRouter slug，可改）
    model_indicator: str = "deepseek/deepseek-chat"  # 中階：行為指標生成
    model_cheap: str = "deepseek/deepseek-chat"      # 便宜：措辭/雜項
```

- [ ] **Step 4: 加 `LlmPort` + `Deps.llm`（deps.py）**

`backend/app/graph_v3/deps.py`：
1. 頂部 import 改成：
```python
from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import JobProfile
from app.services.knowledge.base import KnowledgeClient
from app.services.persistence import TaskRepo
```
2. 在 `PersistPort` 之後加：
```python
@runtime_checkable
class LlmPort(Protocol):
    """per-role LLM 介面（D10）。role ∈ {"deep","indicator","cheap"}。"""
    async def complete_text(self, prompt: str, *, role: str = "cheap") -> str: ...
    async def complete_json(self, prompt: str, *, role: str = "cheap", default: Any = None) -> Any: ...
```
3. `Deps` dataclass 改成（**additive：llm 預設 None，不破壞既有呼叫**）：
```python
@dataclass
class Deps:
    knowledge: KnowledgeClient
    persist: PersistPort
    llm: LlmPort | None = None
```

- [ ] **Step 5: 實作 gateway（llm.py）**

Create `backend/app/graph_v3/llm.py`:
```python
"""OpenRouter LLM gateway（D10）：per-role 模型分層 + JSON 解析重試。
OpenRouter 為 OpenAI 相容端點 → 用 langchain_openai.ChatOpenAI(base_url=...)。"""
import asyncio
import logging
from functools import lru_cache

from langchain_core.messages import HumanMessage
from langchain_openai import ChatOpenAI

from app.config import settings
from app.utils import safe_parse_json

logger = logging.getLogger("jobintel")

_MISSING = object()


def model_for_role(role: str) -> str:
    return {
        "deep": settings.model_deep,
        "indicator": settings.model_indicator,
        "cheap": settings.model_cheap,
    }.get(role, settings.model_cheap)


@lru_cache(maxsize=8)
def _build_chat(model: str, temperature: float) -> ChatOpenAI:
    return ChatOpenAI(
        model=model,
        api_key=settings.openrouter_api_key,
        base_url=settings.openrouter_base_url,
        temperature=temperature,
    )


def get_chat_llm(role: str, temperature: float = 0.2) -> ChatOpenAI:
    return _build_chat(model_for_role(role), temperature)


class OpenRouterLlm:
    """LlmPort 實作（網路）。retries 涵蓋網路錯誤與 JSON 解析失敗。"""

    def __init__(self, retries: int = 2):
        self._retries = retries

    async def complete_text(self, prompt: str, *, role: str = "cheap") -> str:
        llm = get_chat_llm(role)
        for attempt in range(self._retries):
            try:
                resp = await llm.ainvoke([HumanMessage(content=prompt)])
                return resp.content
            except Exception as exc:  # noqa: BLE001
                if attempt < self._retries - 1:
                    logger.warning("OpenRouterLlm text attempt %d failed: %s", attempt + 1, exc)
                    await asyncio.sleep(0.5 * (attempt + 1))
                else:
                    logger.error("OpenRouterLlm text exhausted: %s", exc)
        return ""

    async def complete_json(self, prompt: str, *, role: str = "cheap", default=None):
        for attempt in range(self._retries):
            text = await self.complete_text(prompt, role=role)
            parsed = safe_parse_json(text, default=_MISSING)
            if parsed is not _MISSING:
                return parsed
            if attempt < self._retries - 1:
                await asyncio.sleep(0.3)
        return default
```

- [ ] **Step 6: pin requirements + 跑測試**

在 `backend/requirements.txt` 的 langchain 區塊加一行（版本用 Step 1 實測值，例）：
```
langchain-openai==<實測版本>
```
Run：`cd backend && .venv/Scripts/python -m pytest tests/test_llm_gateway.py -q`
Expected：3 passed。

- [ ] **Step 7: Commit**
```bash
git add backend/requirements.txt backend/app/config.py backend/app/graph_v3/deps.py backend/app/graph_v3/llm.py backend/tests/test_llm_gateway.py
git commit -m "feat(graph_v3): OpenRouter per-role LLM gateway + LlmPort injection (D10)"
```

---

### Task 2：STAR 節點（interrupt 逐槽 + deep 階 LLM 整理）

**Files:** Create `backend/app/graph_v3/deep_nodes.py`、`backend/tests/test_deep_star.py`；Modify `backend/tests/conftest_graph.py`（加 `FakeLlm`）

- [ ] **Step 1: 加 `FakeLlm`（conftest_graph.py）**

在 `backend/tests/conftest_graph.py` 末尾加：
```python
class FakeLlm:
    """可配的 LlmPort 假件。json/text 可給 callable 或固定值；raises=True 模擬失敗。"""
    def __init__(self, json=None, text="", raises=False):
        self._json = json
        self._text = text
        self._raises = raises
        self.calls = []

    async def complete_text(self, prompt, *, role="cheap"):
        self.calls.append(("text", role))
        if self._raises:
            raise RuntimeError("llm down")
        return self._text(prompt) if callable(self._text) else self._text

    async def complete_json(self, prompt, *, role="cheap", default=None):
        self.calls.append(("json", role))
        if self._raises:
            return default
        if self._json is None:
            return default
        return self._json(prompt) if callable(self._json) else self._json
```

- [ ] **Step 2: 失敗測試（S→T→A→R 四 interrupt → 整理 → 寫回 task）**

Create `backend/tests/test_deep_star.py`:
```python
import pytest
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import Command

from app.graph_v3.state import new_state, InterviewState
from app.graph_v3.deep_nodes import star_node
from app.graph_v3.deps import Deps
from tests.conftest_graph import FakeKnowledge, SpyPersist, FakeLlm


def _star_graph():
    g = StateGraph(InterviewState)
    g.add_node("star", star_node)
    g.add_edge(START, "star")
    g.add_edge("star", END)
    return g.compile(checkpointer=MemorySaver())


def _state_with_one_task():
    s = new_state(job_profile_id="p1", job_title="設備維護工程師")
    s["tasks"] = [{"task_name": "例行設備巡檢", "source": "catalog",
                   "indexer_ref": {"ocs_code": "OC1", "task_id": "T1.1"}}]
    return s


@pytest.mark.asyncio
async def test_star_collects_four_slots_then_refines():
    refined = {"S": "產線A晨班", "T": "確保設備可用", "A": "依點檢表逐項檢查", "R": "停機率下降"}
    llm = FakeLlm(json=refined)
    graph = _star_graph()
    cfg = {"configurable": {"thread_id": "t1",
                            "deps": Deps(knowledge=FakeKnowledge(), persist=SpyPersist(), llm=llm)}}

    out = await graph.ainvoke(_state_with_one_task(), cfg)
    assert out["__interrupt__"][0].value["stage"] == "star"
    assert out["__interrupt__"][0].value["slot"] == "S"

    for raw in ["晨班巡檢", "設備可用", "逐項點檢", "停機下降"]:
        out = await graph.ainvoke(Command(resume=raw), cfg)

    star = out["tasks"][0]["star_case"]
    assert star == {"situation": "產線A晨班", "task": "確保設備可用",
                    "action": "依點檢表逐項檢查", "result": "停機率下降"}
    assert "T1.1" in out["deep"]["slots_by_task"]
    assert ("json", "deep") in llm.calls  # 用 deep 階整理


@pytest.mark.asyncio
async def test_star_keeps_raw_when_llm_fails():
    llm = FakeLlm(raises=True)
    graph = _star_graph()
    cfg = {"configurable": {"thread_id": "t2",
                            "deps": Deps(knowledge=FakeKnowledge(), persist=SpyPersist(), llm=llm)}}
    out = await graph.ainvoke(_state_with_one_task(), cfg)
    for raw in ["a原始", "b原始", "c原始", "d原始"]:
        out = await graph.ainvoke(Command(resume=raw), cfg)
    star = out["tasks"][0]["star_case"]
    assert star == {"situation": "a原始", "task": "b原始", "action": "c原始", "result": "d原始"}
```
Run → Expected：FAIL（`deep_nodes` 不存在）。

- [ ] **Step 3: 實作 star_node（deep_nodes.py）**

Create `backend/app/graph_v3/deep_nodes.py`:
```python
"""v3 深問三階段節點（interrupt 驅動）：star / five_w2h / indicator。
重用 app.graph.prompts.* 與 app.graph.constants（純資料模組）；控制流為新寫。"""
import json
import logging

from langgraph.types import interrupt

from app.graph_v3.state import InterviewState

logger = logging.getLogger("jobintel")

# ---- STAR 槽位（domain 資料；自舊 app.graph.nodes.star 移植） ----
_SLOT_ORDER = ["S", "T", "A", "R"]
_SLOT_KEY = {"S": "situation", "T": "task", "A": "action", "R": "result"}
_SLOT_LABELS = {
    "S": "情境（Situation）", "T": "任務目標（Task）",
    "A": "行動步驟（Action）", "R": "結果產出（Result）",
}
_SLOT_QUESTIONS = {
    "S": "針對「{task_name}」，最近一次比較典型或複雜的情況，當時的背景是什麼？",
    "T": "在那件事中，你的目標是什麼？哪些具體事項是你負責的？",
    "A": "你實際怎麼一步一步處理的？用了哪些工具或系統？遇到困難怎麼解決？",
    "R": "最後產出了什麼？是否達成目標、縮短時間或改善了什麼？",
}

_STAR_REFINE = """把工作者對「{task_name}」任務的 STAR 四槽口語回答，整理成精煉的第一人稱描述。
原始回答：
- 情境(S)：{S}
- 任務(T)：{T}
- 行動(A)：{A}
- 結果(R)：{R}

只輸出 JSON（不要其他文字）：
{{"S":"精煉後情境","T":"精煉後任務","A":"精煉後行動","R":"精煉後結果"}}
規則：保留原意、勿杜撰未提及的工具/對象/數字；每槽 15〜60 字。"""


def _current_task(state: InterviewState) -> tuple[int, dict, str]:
    idx = state["deep"]["current_task_index"]
    task = dict(state["tasks"][idx])
    task_id = (task.get("indexer_ref") or {}).get("task_id") or task["task_name"]
    return idx, task, task_id


async def star_node(state: InterviewState, config) -> dict:
    deps = config["configurable"]["deps"]
    idx, task, task_id = _current_task(state)
    task_name = task["task_name"]

    raw: dict[str, str] = {}
    for slot in _SLOT_ORDER:
        answer = interrupt({
            "kind": "ask_human", "stage": "star", "slot": slot,
            "task_id": task_id, "task_name": task_name,
            "label": _SLOT_LABELS[slot],
            "question": _SLOT_QUESTIONS[slot].format(task_name=task_name),
        })
        raw[slot] = answer if isinstance(answer, str) else str(answer)

    # deep 階 LLM 整理（best-effort；失敗或缺鍵 → 保留原答）
    refined = raw
    if deps.llm is not None:
        prompt = _STAR_REFINE.format(task_name=task_name, **raw)
        got = await deps.llm.complete_json(prompt, role="deep", default=None)
        if isinstance(got, dict) and all(got.get(s) for s in _SLOT_ORDER):
            refined = {s: str(got[s]) for s in _SLOT_ORDER}

    star_case = {_SLOT_KEY[s]: refined[s] for s in _SLOT_ORDER}
    task["star_case"] = star_case
    tasks = list(state["tasks"])
    tasks[idx] = task

    deep = dict(state["deep"])
    slots_by_task = dict(deep["slots_by_task"])
    slots_by_task[task_id] = star_case
    deep["slots_by_task"] = slots_by_task

    logger.info("star_node: task=%s STAR complete -> five_w2h", task_name)
    return {"tasks": tasks, "deep": deep}
```
Run → Expected：2 passed。

- [ ] **Step 4: Commit**
```bash
git add backend/app/graph_v3/deep_nodes.py backend/tests/conftest_graph.py backend/tests/test_deep_star.py
git commit -m "feat(graph_v3): STAR deep-interview node (interrupt per slot + deep-tier refine)"
```

---

### Task 3：five_w2h 節點（star + catalog prefill，逐缺欄 interrupt）

**Files:** Modify `backend/app/graph_v3/deep_nodes.py`、`backend/tests/conftest_graph.py`（`FakeKnowledge.tasks_by_id` 可配）；Create `backend/tests/test_deep_five_w2h.py`

- [ ] **Step 1: `FakeKnowledge` 加可配 tasks_by_id（conftest_graph.py）**

把 `backend/tests/conftest_graph.py` 的 `FakeKnowledge` 改成（**additive**：新增 `tasks` 參數與真回傳；其餘不變）：
```python
class FakeKnowledge:
    def __init__(self, search=None, pool=None, tasks=None):
        self._search = search or SearchResult(mode="dense", hits=[])
        self._pool = pool or TaskPool(groups=[])
        self._tasks = tasks  # TasksByIdResult | None
        self.calls = []

    async def search(self, query, **kw):
        self.calls.append(("search", query)); return self._search

    async def task_pool(self, ocs_codes, **kw):
        self.calls.append(("task_pool", ocs_codes)); return self._pool

    async def pairs(self, ocs_code):
        self.calls.append(("pairs", ocs_code)); return Pairs(ocs_code=ocs_code)

    async def tasks_by_id(self, ids):
        from app.services.knowledge.models import TasksByIdResult
        self.calls.append(("tasks_by_id", list(ids)))
        return self._tasks or TasksByIdResult(tasks=[])

    async def healthz(self):
        return True
```
並確認檔案頂部 import 含 `Pairs`：
```python
from app.services.knowledge.models import SearchResult, TaskPool, Pairs
```

- [ ] **Step 2: 失敗測試（star 預填 situation/workflow、catalog 預填 outputs → 跳過該題；其餘逐欄問）**

Create `backend/tests/test_deep_five_w2h.py`:
```python
import pytest
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import Command

from app.graph_v3.state import new_state, InterviewState
from app.graph_v3.deep_nodes import five_w2h_node
from app.graph_v3.deps import Deps
from app.services.knowledge.models import TasksByIdResult, TaskDetail, Pair
from tests.conftest_graph import FakeKnowledge, SpyPersist, FakeLlm
from app.graph.constants import FIVE_W2H_REQUIRED


def _graph():
    g = StateGraph(InterviewState)
    g.add_node("five_w2h", five_w2h_node)
    g.add_edge(START, "five_w2h")
    g.add_edge("five_w2h", END)
    return g.compile(checkpointer=MemorySaver())


def _state():
    s = new_state(job_profile_id="p1", job_title="設備維護工程師")
    s["tasks"] = [{
        "task_name": "例行設備巡檢", "source": "catalog",
        "indexer_ref": {"ocs_code": "OC1", "task_id": "T1.1"},
        "star_case": {"situation": "晨班產線A", "task": "確保可用",
                      "action": "逐項點檢、記錄異常", "result": "停機下降"},
    }]
    return s


@pytest.mark.asyncio
async def test_five_w2h_prefills_then_asks_remaining():
    # catalog 供 outputs → outputs 不再問；star 供 situation+workflow_steps
    detail = TaskDetail(id="T1.1", ocs_code="OC1", task_id="T1.1", task_title="例行設備巡檢",
                        output_pairs=[Pair(code="O1", name="點檢表"), Pair(code="O2", name="異常通報")])
    fake = FakeKnowledge(tasks=TasksByIdResult(tasks=[detail]))
    graph = _graph()
    cfg = {"configurable": {"thread_id": "t1",
                            "deps": Deps(knowledge=fake, persist=SpyPersist(), llm=FakeLlm())}}

    out = await graph.ainvoke(_state(), cfg)
    asked = []
    # 逐欄回答直到節點完成（無 __interrupt__）
    while "__interrupt__" in out:
        payload = out["__interrupt__"][0].value
        assert payload["kind"] == "ask_human" and payload["stage"] == "five_w2h"
        asked.append(payload["field"])
        out = await graph.ainvoke(Command(resume="作業員、ERP系統"), cfg)

    # 被預填者不應被問
    assert "situation" not in asked        # star 預填
    assert "workflow_steps" not in asked    # star.action 預填
    assert "outputs" not in asked           # catalog 預填
    # 其餘必填欄都問到
    remaining = [f for f in FIVE_W2H_REQUIRED if f not in {"situation", "workflow_steps", "outputs"}]
    assert asked == remaining

    task = out["tasks"][0]
    assert task["outputs"] == ["點檢表", "異常通報"]            # catalog 預填
    assert task["workflow_steps"]                               # star 預填
    assert task["collaborators"] == ["作業員", "ERP系統"]       # list 欄位切分
    assert task["purpose"] == "作業員、ERP系統"                 # 純字串欄位


@pytest.mark.asyncio
async def test_five_w2h_company_task_no_catalog_prefill():
    s = new_state(job_profile_id="p1", job_title="X")
    s["tasks"] = [{"task_name": "公司自訂任務", "source": "company"}]  # 無 indexer_ref
    fake = FakeKnowledge()  # tasks_by_id → 空
    graph = _graph()
    cfg = {"configurable": {"thread_id": "t2",
                            "deps": Deps(knowledge=fake, persist=SpyPersist(), llm=FakeLlm())}}
    out = await graph.ainvoke(s, cfg)
    # 無 catalog → 不應呼叫 tasks_by_id（無 indexer_ref 時跳過）
    assert not any(c[0] == "tasks_by_id" for c in fake.calls)
    assert "__interrupt__" in out  # 直接開始逐欄問
```
Run → Expected：FAIL（`five_w2h_node` 不存在）。

- [ ] **Step 3: 實作 five_w2h_node（append 到 deep_nodes.py）**

在 `deep_nodes.py` 頂部 import 區下方加：
```python
from app.graph.constants import FIVE_W2H_REQUIRED, FIVE_W2H_LIST_FIELDS
```
檔案末尾 append：
```python
def _prefill_from_star(task: dict) -> dict:
    """S → situation；A → workflow_steps（以「、」「；」拆分）。"""
    star = task.get("star_case") or {}
    if not task.get("situation") and star.get("situation"):
        task["situation"] = star["situation"]
    if not task.get("workflow_steps") and star.get("action"):
        action = star["action"]
        steps = [s.strip() for s in action.replace("；", "、").split("、") if s.strip()]
        task["workflow_steps"] = steps if len(steps) > 1 else [action]
    return task


async def _prefill_from_catalog(task: dict, deps) -> dict:
    """catalog k/s/output 當 just-in-time prefill：目前實填 outputs（output_pairs 名稱）。"""
    ref = task.get("indexer_ref") or {}
    task_id = ref.get("task_id")
    if not task_id or deps.knowledge is None:
        return task
    res = await deps.knowledge.tasks_by_id([task_id])
    detail = next((t for t in res.tasks if t.task_id == task_id), None)
    if detail and not task.get("outputs") and detail.output_pairs:
        task["outputs"] = [p.name for p in detail.output_pairs if p.name]
    return task


def _store_answer(task: dict, field: str, answer: str) -> dict:
    if field in FIVE_W2H_LIST_FIELDS:
        task[field] = [s.strip() for s in answer.replace("、", ",").replace("，", ",").split(",")
                       if s.strip()] or [answer]
    else:
        task[field] = answer
    return task


async def five_w2h_node(state: InterviewState, config) -> dict:
    deps = config["configurable"]["deps"]
    idx, task, _ = _current_task(state)
    task = _prefill_from_star(task)
    task = await _prefill_from_catalog(task, deps)
    task_name = task["task_name"]

    for field, (label, question) in FIVE_W2H_REQUIRED.items():
        if task.get(field):
            continue
        answer = interrupt({
            "kind": "ask_human", "stage": "five_w2h", "field": field,
            "task_name": task_name, "label": label,
            "question": f"關於「{task_name}」：{question}",
        })
        task = _store_answer(task, field, answer if isinstance(answer, str) else str(answer))

    tasks = list(state["tasks"])
    tasks[idx] = task
    logger.info("five_w2h_node: task=%s complete -> indicator", task_name)
    return {"tasks": tasks}
```
Run → Expected：2 passed。

- [ ] **Step 4: Commit**
```bash
git add backend/app/graph_v3/deep_nodes.py backend/tests/conftest_graph.py backend/tests/test_deep_five_w2h.py
git commit -m "feat(graph_v3): five_w2h node (star+catalog prefill, interrupt per missing field)"
```

---

### Task 4：indicator 節點（indicator 階 LLM 生成 + 品質評分 + 重試訊號）

**Files:** Modify `backend/app/graph_v3/deep_nodes.py`；Create `backend/tests/test_deep_indicator.py`

- [ ] **Step 1: 失敗測試（好品質 → 寫指標、無重試；低品質+有預算 → 清弱欄、發重試訊號）**

Create `backend/tests/test_deep_indicator.py`:
```python
import pytest
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver

from app.graph_v3.state import new_state, InterviewState
from app.graph_v3.deep_nodes import indicator_node
from app.graph_v3.deps import Deps
from tests.conftest_graph import FakeKnowledge, SpyPersist, FakeLlm


def _graph():
    g = StateGraph(InterviewState)
    g.add_node("indicator", indicator_node)
    g.add_edge(START, "indicator")
    g.add_edge("indicator", END)
    return g.compile(checkpointer=MemorySaver())


def _full_task():
    return {
        "task_name": "例行設備巡檢", "source": "catalog",
        "indexer_ref": {"ocs_code": "OC1", "task_id": "T1.1"},
        "situation": "晨班", "purpose": "確保可用", "collaborators": ["作業員"],
        "stakeholders": ["產線主管"], "tools": ["ERP"], "workflow_steps": ["逐項點檢"],
        "outputs": ["點檢表"], "quality_standards": ["零漏檢"], "time_standards": ["當日完成"],
        "star_case": {"situation": "晨班", "task": "可用", "action": "點檢", "result": "下降"},
    }


def _state_with(task):
    s = new_state(job_profile_id="p1", job_title="X")
    s["tasks"] = [task]
    return s


_GOOD_DIMS = {"has_situation": True, "has_purpose": True, "has_collaborators": True,
              "has_tools": True, "has_action": True, "has_output": True, "has_standard": True}


@pytest.mark.asyncio
async def test_indicator_accepts_good_quality():
    results = [{"output_name": "點檢表", "indicator_5w2h": "在晨班…產出點檢表…",
                "indicator_abcd": "面對產線…", "quality_dims": _GOOD_DIMS}]
    llm = FakeLlm(json=results)
    graph = _graph()
    cfg = {"configurable": {"thread_id": "t1",
                            "deps": Deps(knowledge=FakeKnowledge(), persist=SpyPersist(), llm=llm)}}
    out = await graph.ainvoke(_state_with(_full_task()), cfg)
    inds = out["tasks"][0]["behavior_indicators"]
    assert inds and inds[0]["output_name"] == "點檢表"
    assert out["deep"]["missing_fields"] == []          # 無重試
    assert ("json", "indicator") in llm.calls           # 用 indicator 階


@pytest.mark.asyncio
async def test_indicator_low_quality_signals_retry_and_clears_weak():
    # 4 個維度為 False → 命中 3/7 ≈ 0.43 < 0.60 門檻 → 觸發重試
    bad_dims = dict(_GOOD_DIMS, has_tools=False, has_action=False,
                    has_output=False, has_standard=False)
    results = [{"output_name": "點檢表", "indicator_5w2h": "薄弱",
                "indicator_abcd": "薄弱", "quality_dims": bad_dims}]
    llm = FakeLlm(json=results)
    graph = _graph()
    cfg = {"configurable": {"thread_id": "t2",
                            "deps": Deps(knowledge=FakeKnowledge(), persist=SpyPersist(), llm=llm)}}
    out = await graph.ainvoke(_state_with(_full_task()), cfg)
    deep = out["deep"]
    assert deep["missing_fields"]            # 有重試訊號（→ route_after_indicator 會回 five_w2h）
    assert deep["retry"]["T1.1"] == 1        # 重試計數 +1（task_id 鍵）
    task = out["tasks"][0]
    # 弱欄位被清空（將由 five_w2h 重問）
    assert "tools" in deep["missing_fields"]
    assert not task.get("tools")
```
Run → Expected：FAIL（`indicator_node` 不存在）。

- [ ] **Step 2: 實作 indicator_node（append 到 deep_nodes.py）**

在 `deep_nodes.py` import 區加：
```python
from app.graph.constants import INDICATOR_REQUIRED_FIELDS
import app.graph.prompts.indicator as ind_prompts
```
末尾 append：
```python
_QUALITY_THRESHOLD = 0.60
_MAX_QUALITY_RETRIES = 1
_DIM_TO_FIELDS = {
    "has_situation": ["situation"], "has_purpose": ["purpose"],
    "has_collaborators": ["collaborators"], "has_tools": ["tools"],
    "has_action": ["workflow_steps"], "has_output": ["outputs"],
    "has_standard": ["quality_standards", "time_standards"],
}


def _score_quality(dims: dict) -> tuple[float, list[str]]:
    weak: list[str] = []
    hits = 0
    for dim, fields in _DIM_TO_FIELDS.items():
        if dims.get(dim):
            hits += 1
        else:
            weak.extend(fields)
    return round(hits / len(_DIM_TO_FIELDS), 3), weak


def _avg_quality(results: list[dict]) -> tuple[float, list[str]]:
    if not results:
        return 0.0, list({f for fs in _DIM_TO_FIELDS.values() for f in fs})
    total = 0.0
    weak: set[str] = set()
    for r in results:
        sc, wk = _score_quality(r.get("quality_dims", {}))
        total += sc
        weak.update(wk)
    return round(total / len(results), 3), list(weak)


def _build_indicator_prompt(task: dict) -> tuple[str, bool]:
    """回 (prompt, is_per_output)。catalog/iCAP 參考段落留空（檢索已外包/移除）。"""
    common = dict(
        task_name=task["task_name"], situation=task.get("situation", ""),
        purpose=task.get("purpose", ""),
        collaborators=", ".join(task.get("collaborators") or []),
        stakeholders=", ".join(task.get("stakeholders") or []),
        tools=", ".join(task.get("tools") or []),
        workflow_steps="\n".join(task.get("workflow_steps") or []),
        quality_standards=", ".join(task.get("quality_standards") or []),
        time_standards=", ".join(task.get("time_standards") or []),
        star_case=json.dumps(task.get("star_case", {}), ensure_ascii=False),
        icap_ref_section="",
    )
    outputs = task.get("outputs") or []
    if outputs:
        prompt = ind_prompts.PER_OUTPUT.format(
            outputs_numbered="\n".join(f"{i}. {o}" for i, o in enumerate(outputs, 1)),
            icap_ref_rule="", **common)
        return prompt, True
    return ind_prompts.SINGLE.format(**common), False


async def indicator_node(state: InterviewState, config) -> dict:
    deps = config["configurable"]["deps"]
    idx, task, task_id = _current_task(state)
    task_name = task["task_name"]
    deep = dict(state["deep"])
    retry = dict(deep.get("retry") or {})

    # Guardrail：必填欄缺 → 退回 five_w2h
    missing = [f for f in INDICATOR_REQUIRED_FIELDS if not task.get(f)]
    if missing:
        deep["missing_fields"] = missing
        logger.warning("indicator_node: guardrail missing=%s -> five_w2h", missing)
        return {"deep": deep}

    prompt, per_output = _build_indicator_prompt(task)
    raw = await deps.llm.complete_json(prompt, role="indicator", default=[] if per_output else {})
    results = raw if per_output and isinstance(raw, list) else ([raw] if raw else [])
    score, weak = _avg_quality(results)

    if score < _QUALITY_THRESHOLD and retry.get(task_id, 0) < _MAX_QUALITY_RETRIES:
        retry[task_id] = retry.get(task_id, 0) + 1
        for f in weak:
            task.pop(f, None)
        tasks = list(state["tasks"]); tasks[idx] = task
        deep["retry"] = retry
        deep["missing_fields"] = weak
        logger.warning("indicator_node: task=%s score=%.2f weak=%s retry#%d -> five_w2h",
                       task_name, score, weak, retry[task_id])
        return {"tasks": tasks, "deep": deep}

    status = "ok" if score >= _QUALITY_THRESHOLD else "force_accepted"
    indicators = [{
        "task_id": task_id, "task_name": task_name,
        "output_name": r.get("output_name", ""),
        "indicator_5w2h": r.get("indicator_5w2h", ""),
        "indicator_abcd": r.get("indicator_abcd", ""),
        "quality_score": score, "quality_status": status,
    } for r in results] or [{
        "task_id": task_id, "task_name": task_name, "output_name": "",
        "indicator_5w2h": "", "indicator_abcd": "",
        "quality_score": 0.0, "quality_status": "force_accepted",
    }]
    task["behavior_indicators"] = indicators
    tasks = list(state["tasks"]); tasks[idx] = task
    deep["retry"] = retry
    deep["missing_fields"] = []
    logger.info("indicator_node: task=%s accepted score=%.2f", task_name, score)
    return {"tasks": tasks, "deep": deep}
```
Run → Expected：2 passed。

- [ ] **Step 3: Commit**
```bash
git add backend/app/graph_v3/deep_nodes.py backend/tests/test_deep_indicator.py
git commit -m "feat(graph_v3): indicator node (per-output gen + quality score + retry signal)"
```

---

### Task 5：單任務深問端到端（D8 隔離子圖測，僅測試）

**Files:** Create `backend/tests/test_deep_subgraph.py`

> 用「只含 3 深問節點 + 重試邊」的測試用小圖，獨立驗一條完整單任務深問（含 star→five_w2h→indicator 與品質重試回 five_w2h）。**不在 app code 出貨子圖殼**（main graph 於 Task 6 以單層迴圈內聯同樣 3 個節點）。

- [ ] **Step 1: 失敗測試（完整單任務：四 STAR + 缺欄 5W2H + 指標 → task 全填）**

Create `backend/tests/test_deep_subgraph.py`:
```python
import pytest
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import Command

from app.graph_v3.state import new_state, InterviewState
from app.graph_v3.deep_nodes import star_node, five_w2h_node, indicator_node, route_after_indicator
from app.graph_v3.deps import Deps
from app.services.knowledge.models import TasksByIdResult, TaskDetail, Pair
from tests.conftest_graph import FakeKnowledge, SpyPersist, FakeLlm

_GOOD = {"has_situation": True, "has_purpose": True, "has_collaborators": True,
         "has_tools": True, "has_action": True, "has_output": True, "has_standard": True}


def _deep_graph():
    g = StateGraph(InterviewState)
    g.add_node("star", star_node)
    g.add_node("five_w2h", five_w2h_node)
    g.add_node("indicator", indicator_node)
    g.add_edge(START, "star")
    g.add_edge("star", "five_w2h")
    g.add_conditional_edges("indicator", route_after_indicator,
                            {"five_w2h": "five_w2h", "advance": END})
    return g.compile(checkpointer=MemorySaver())


@pytest.mark.asyncio
async def test_single_task_deep_interview_completes():
    detail = TaskDetail(id="T1.1", ocs_code="OC1", task_id="T1.1", task_title="例行設備巡檢",
                        output_pairs=[Pair(code="O1", name="點檢表")])
    star_refine = {"S": "晨班A線", "T": "確保可用", "A": "逐項點檢、記錄", "R": "停機下降"}
    indicators = [{"output_name": "點檢表", "indicator_5w2h": "在晨班…點檢表…",
                   "indicator_abcd": "面對…", "quality_dims": _GOOD}]

    def _json(prompt):
        return star_refine if "STAR 四槽" in prompt else indicators
    llm = FakeLlm(json=_json)
    fake = FakeKnowledge(tasks=TasksByIdResult(tasks=[detail]))

    s = new_state(job_profile_id="p1", job_title="設備維護工程師")
    s["tasks"] = [{"task_name": "例行設備巡檢", "source": "catalog",
                   "indexer_ref": {"ocs_code": "OC1", "task_id": "T1.1"}}]
    graph = _deep_graph()
    cfg = {"configurable": {"thread_id": "t1",
                            "deps": Deps(knowledge=fake, persist=SpyPersist(), llm=llm)}}

    out = await graph.ainvoke(s, cfg)
    # 一路回答所有 interrupt 直到完成
    guard = 0
    while "__interrupt__" in out:
        out = await graph.ainvoke(Command(resume="作業員、ERP、零漏檢、當日完成"), cfg)
        guard += 1
        assert guard < 20, "interrupt 迴圈未收斂"

    task = out["tasks"][0]
    assert task["star_case"]["situation"] == "晨班A線"
    assert task["outputs"] == ["點檢表"]
    assert task["behavior_indicators"][0]["output_name"] == "點檢表"
    assert out["deep"]["missing_fields"] == []
```
Run → Expected：FAIL（`route_after_indicator` 不存在）。

- [ ] **Step 2: 實作 route_after_indicator（append 到 deep_nodes.py）**

在 `deep_nodes.py` 末尾加：
```python
def route_after_indicator(state: InterviewState) -> str:
    """indicator 後分流：有未填弱欄 → 回 five_w2h 重補；否則 → advance（推進下一任務）。"""
    return "five_w2h" if state["deep"].get("missing_fields") else "advance"
```
> 註：`_STAR_REFINE` prompt 內含字串「STAR 四槽」，測試以此辨識 star vs indicator 的 LLM 呼叫；勿移除該字樣。
Run → Expected：1 passed。

- [ ] **Step 3: Commit**
```bash
git add backend/app/graph_v3/deep_nodes.py backend/tests/test_deep_subgraph.py
git commit -m "feat(graph_v3): route_after_indicator + isolated single-task deep-interview test"
```

---

### Task 6：接上主圖深問迴圈 + 雙任務整合

**Files:** Modify `backend/app/graph_v3/graph.py`、`backend/tests/test_graph_v3_e2e.py`；Create `backend/tests/test_graph_v3_deep_loop.py`

- [ ] **Step 1: 失敗測試（雙任務：選 profile → 編 2 任務 → 各跑深問 → 收尾 assemble_ksa）**

Create `backend/tests/test_graph_v3_deep_loop.py`:
```python
import pytest
from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import Command

from app.graph_v3.graph import build_graph_v3
from app.graph_v3.state import new_state
from app.graph_v3.deps import Deps
from app.services.knowledge.models import (
    SearchResult, Hit, TaskPool, PoolGroup, PoolUnit, PoolTask, TasksByIdResult)
from tests.conftest_graph import FakeKnowledge, SpyPersist, FakeLlm

_GOOD = {"has_situation": True, "has_purpose": True, "has_collaborators": True,
         "has_tools": True, "has_action": True, "has_output": True, "has_standard": True}


@pytest.mark.asyncio
async def test_two_task_deep_loop_reaches_assemble():
    indicators = [{"output_name": "", "indicator_5w2h": "x", "indicator_abcd": "y",
                   "quality_dims": _GOOD}]
    star_refine = {"S": "s", "T": "t", "A": "a", "R": "r"}

    def _json(prompt):
        return star_refine if "STAR 四槽" in prompt else indicators
    llm = FakeLlm(json=_json)
    fake = FakeKnowledge(
        search=SearchResult(mode="dense", hits=[Hit(id="p1", ocs_code="OC1", chunk_level="profile")]),
        pool=TaskPool(groups=[PoolGroup(ocs_code="OC1", units=[PoolUnit(tasks=[
            PoolTask(id="x1", task_id="T1.1", task_title="任務一"),
            PoolTask(id="x2", task_id="T1.2", task_title="任務二")])])]),
        tasks=TasksByIdResult(tasks=[]),  # 無 catalog outputs → 5W2H 全問
    )
    graph = build_graph_v3(checkpointer=MemorySaver())
    cfg = {"configurable": {"thread_id": "t1",
                            "deps": Deps(knowledge=fake, persist=SpyPersist(), llm=llm)}}

    out = await graph.ainvoke(new_state(job_profile_id="p1", job_title="工程師"), cfg)
    assert out["__interrupt__"][0].value["kind"] == "select_profile"

    out = await graph.ainvoke(Command(resume={"ocs_code": "OC1"}), cfg)
    assert out["__interrupt__"][0].value["kind"] == "edit_tasks"
    edited = [{"task_name": "任務一", "source": "catalog",
               "indexer_ref": {"ocs_code": "OC1", "task_id": "T1.1"}},
              {"task_name": "任務二", "source": "catalog",
               "indexer_ref": {"ocs_code": "OC1", "task_id": "T1.2"}}]
    out = await graph.ainvoke(Command(resume={"tasks": edited}), cfg)

    # 深問所有 interrupt：固定 answer 餵到結束
    guard = 0
    while "__interrupt__" in out:
        out = await graph.ainvoke(Command(resume="作業員、ERP、零漏檢、當日完成"), cfg)
        guard += 1
        assert guard < 60, "深問迴圈未收斂"

    assert out["current_step"] == "assemble_ksa"
    assert all(t.get("behavior_indicators") for t in out["tasks"])
    assert len(out["tasks"]) == 2
```
Run → Expected：FAIL（主圖尚未接深問迴圈，resume 後不會進深問）。

- [ ] **Step 2: 改寫 graph.py 接上單層深問迴圈**

把 `backend/app/graph_v3/graph.py` 整檔換成：
```python
from langgraph.graph import StateGraph, START, END

from app.graph_v3.state import InterviewState
from app.graph_v3.nodes import pick_profile, build_task_pool
from app.graph_v3.deep_nodes import (
    star_node, five_w2h_node, indicator_node, route_after_indicator)


def route_deep(state: InterviewState) -> str:
    """還有未處理任務 → 進 star（深問）；否則 → 收尾。"""
    if state["deep"]["current_task_index"] < len(state["tasks"]):
        return "star"
    return "finish_deep"


def advance_deep(state: InterviewState) -> dict:
    """一任務深問完成：標記 completed + index 前進。"""
    idx = state["deep"]["current_task_index"]
    deep = dict(state["deep"])
    completed = list(deep["completed_task_ids"])
    task = state["tasks"][idx]
    task_id = (task.get("indexer_ref") or {}).get("task_id") or task["task_name"]
    if task_id not in completed:
        completed.append(task_id)
    deep["completed_task_ids"] = completed
    deep["current_task_index"] = idx + 1
    deep["missing_fields"] = []
    return {"deep": deep}


def finish_deep(state: InterviewState) -> dict:
    """全部任務深問完 → 交棒 Phase ④（assemble_ksa）。"""
    return {"current_step": "assemble_ksa"}


def build_graph_v3(checkpointer=None):
    """v3 骨幹 + 逐任務深問迴圈（單層 node loop，interrupt 驅動）。
    Phase ④ 會把 finish_deep 後接 assemble_ksa/build_doc。"""
    g = StateGraph(InterviewState)
    g.add_node("pick_profile", pick_profile)
    g.add_node("build_task_pool", build_task_pool)
    g.add_node("star", star_node)
    g.add_node("five_w2h", five_w2h_node)
    g.add_node("indicator", indicator_node)
    g.add_node("advance_deep", advance_deep)
    g.add_node("finish_deep", finish_deep)

    g.add_edge(START, "pick_profile")
    g.add_edge("pick_profile", "build_task_pool")
    g.add_conditional_edges("build_task_pool", route_deep,
                            {"star": "star", "finish_deep": "finish_deep"})
    g.add_edge("star", "five_w2h")
    g.add_conditional_edges("indicator", route_after_indicator,
                            {"five_w2h": "five_w2h", "advance": "advance_deep"})
    g.add_conditional_edges("advance_deep", route_deep,
                            {"star": "star", "finish_deep": "finish_deep"})
    g.add_edge("finish_deep", END)
    return g.compile(checkpointer=checkpointer)
```
Run：`pytest tests/test_graph_v3_deep_loop.py -q` → Expected：1 passed。

- [ ] **Step 3: 更新 Phase ② e2e 測試（task_pool resume 後現在會進深問 interrupt）**

`backend/tests/test_graph_v3_e2e.py` 最後一段（resume edit_tasks 後 assert current_step=="deep"）改成期待第一個 STAR interrupt。把該檔最後的 ainvoke 區塊：
```python
    out = await graph.ainvoke(Command(resume={"tasks": [{"task_name": "巡檢", "source": "catalog"}]}), cfg)
    assert out["current_step"] == "deep"
    assert spy.selected == ("p1", "OC1") and spy.flushed[0] == "p1"
```
改為：
```python
    out = await graph.ainvoke(Command(resume={"tasks": [{"task_name": "巡檢", "source": "catalog"}]}), cfg)
    # Phase ③：task_pool 後直接進深問，停在第一個 STAR 提問
    assert out["__interrupt__"][0].value["stage"] == "star"
    assert spy.selected == ("p1", "OC1") and spy.flushed[0] == "p1"
```
並確認該測試的 `Deps(...)` 有帶 `llm`（star 需要）；若無則改成 `Deps(knowledge=fake, persist=spy, llm=FakeLlm())` 並在 import 區加 `from tests.conftest_graph import FakeLlm`。
Run：`pytest tests/test_graph_v3_e2e.py -q` → Expected：pass。

- [ ] **Step 4: 全套件**

Run：`cd backend && TEST_DATABASE_URL=postgresql+asyncpg://postgres:password@localhost:5432/jobintel .venv/Scripts/python -m pytest -q`
Expected：全綠（22 + 本 phase 新測）。

- [ ] **Step 5: Commit**
```bash
git add backend/app/graph_v3/graph.py backend/tests/test_graph_v3_e2e.py backend/tests/test_graph_v3_deep_loop.py
git commit -m "feat(graph_v3): wire per-task deep-interview loop into main graph + 2-task integration"
```

---

### Task 7：demo serving 接齊（stub LLM/catalog）+ 全套件 + 記憶更新

**Files:** Modify `backend/app/graph_v3/stubs.py`、`backend/app/graph_v3/serving.py`、`backend/tests/test_serving_smoke.py`

- [ ] **Step 1: 失敗測試（demo SDK 仍建得起來且 deps.llm 存在）**

把 `backend/tests/test_serving_smoke.py` 改成：
```python
from app.graph_v3.serving import AGENT_NAME, build_demo_sdk


def test_demo_sdk_builds_and_registers_agent():
    sdk = build_demo_sdk()
    names = [a.name for a in sdk.agents]
    assert AGENT_NAME in names


def test_demo_agent_has_llm_dep():
    from app.graph_v3.stubs import StubLlm
    from app.graph_v3.serving import build_demo_deps
    deps = build_demo_deps()
    assert isinstance(deps.llm, StubLlm)
```
Run → Expected：FAIL（`StubLlm` / `build_demo_deps` 不存在）。

- [ ] **Step 2: 加 StubLlm + catalog 細節（stubs.py）**

`backend/app/graph_v3/stubs.py`：
1. `tasks_by_id` 改成回真資料（讓 demo 深問有 outputs 預填）：
```python
    async def tasks_by_id(self, ids) -> TasksByIdResult:
        from app.services.knowledge.models import TaskDetail, Pair
        return TasksByIdResult(tasks=[
            TaskDetail(id=str(i), ocs_code="KRM2421-001v4", task_id=str(i),
                       task_title="（demo）", output_pairs=[Pair(code="O1", name="點檢表")])
            for i in ids])
```
2. 檔末加 StubLlm：
```python
class StubLlm:
    """Demo 用 LlmPort：固定回傳，不打網路。"""
    async def complete_text(self, prompt, *, role="cheap") -> str:
        return "（demo）"

    async def complete_json(self, prompt, *, role="cheap", default=None):
        if "STAR 四槽" in prompt:
            return {"S": "（demo情境）", "T": "（demo任務）", "A": "（demo行動）", "R": "（demo結果）"}
        return [{"output_name": "點檢表", "indicator_5w2h": "（demo指標）",
                 "indicator_abcd": "（demo ABCD）",
                 "quality_dims": {k: True for k in
                    ("has_situation", "has_purpose", "has_collaborators", "has_tools",
                     "has_action", "has_output", "has_standard")}}]
```

- [ ] **Step 3: serving.py 注入 StubLlm + 抽出 build_demo_deps**

把 `backend/app/graph_v3/serving.py` 改成：
```python
from copilotkit import CopilotKitRemoteEndpoint, LangGraphAGUIAgent
from langgraph.checkpoint.memory import MemorySaver

from app.graph_v3.deps import Deps
from app.graph_v3.graph import build_graph_v3
from app.graph_v3.stubs import InMemoryPersist, StubKnowledge, StubLlm

AGENT_NAME = "jd_authoring"


def build_demo_deps() -> Deps:
    return Deps(knowledge=StubKnowledge(), persist=InMemoryPersist(), llm=StubLlm())


def build_demo_sdk() -> CopilotKitRemoteEndpoint:
    graph = build_graph_v3(checkpointer=MemorySaver())
    agent = LangGraphAGUIAgent(
        name=AGENT_NAME,
        description="JD 撰寫顧問（v3 stub demo）",
        graph=graph,
        config={"configurable": {"deps": build_demo_deps()}},
    )
    return CopilotKitRemoteEndpoint(agents=[agent])
```
Run：`pytest tests/test_serving_smoke.py tests/test_copilotkit_endpoint.py -q` → Expected：pass。

- [ ] **Step 4: 全套件 + 提交**

Run：`cd backend && TEST_DATABASE_URL=postgresql+asyncpg://postgres:password@localhost:5432/jobintel .venv/Scripts/python -m pytest -q`
Expected：全綠。
```bash
git add backend/app/graph_v3/stubs.py backend/app/graph_v3/serving.py backend/tests/test_serving_smoke.py
git commit -m "feat(graph_v3): wire StubLlm + catalog detail into demo serving (deep-interview demo)"
```

- [ ] **Step 5: 更新專案記憶**

更新 `C:\Users\chenb\.claude\projects\s--jd-ocs-indexer\memory\project_jobintel_ai_refactor.md`：記 Phase ③ DONE（deep_nodes star/five_w2h/indicator + OpenRouter gateway + 主圖深問迴圈 + commit 範圍 + 測試數）；「下一步」改為 Phase ④（assemble_ksa + build_doc）與 live-wire。

---

## 完成後
- **產出**：interrupt 驅動的逐任務深問（star→five_w2h→indicator）接進主圖單層迴圈；OpenRouter per-role gateway（D10）；豐欄位留 state（checkpointer of-record）。舊 `app/graph/` 仍未移除（移除排在 live-wire phase）。
- **下一步**：
  - **Phase ④**：`assemble_ksa`（`KnowledgeClient.pairs()`+`tasks_by_id()` → interrupt 改 K/S/A → flush `ksa_items`）+ `build_doc`（`ocs_builder` 組裝 → `document_versions`）。`finish_deep` → `assemble_ksa`。
  - **live-wire**：StubKnowledge→HttpIndexerClient、InMemoryPersist→DbPersist（每請求 session）、MemorySaver→AsyncPostgresSaver（深問豐欄位序列化驗證）、orchestrator 改用 graph_v3、移除舊 `app/graph/`+`icap_*`+`llm_gateway`。
  - **前端**（最後做、使用者瀏覽器驗）：CopilotKit 接 `ask_human`（star/five_w2h 提問）/`select_profile`/`edit_tasks` 三類 interrupt。
- **eval/OTel**（Phase ⑤）：換 OpenRouter 模型前過 eval 閘門。

## Self-Review
- **Spec 覆蓋**：§2 流程③深問迴圈 ✓、§4.1 interrupt 取代關鍵字路由 ✓、§4.5 D10 per-role gateway（deep/indicator 階皆有消費者）✓、§8 重用 star/five_w2h/indicator domain（prompt/常數）✓、§9.3 catalog prefill（outputs from output_pairs）✓、§10 子圖可獨立測（Task 5）✓。
- **無 placeholder**：每 task 皆真 test + 完整實作碼；唯一「實測值」點為 langchain-openai 版本（Task 1 Step 1 量測 + pin）。
- **不破壞**：`Deps.llm` 預設 None（additive）；deep_nodes 只 import 純資料模組（`app.graph.prompts.*`/`app.graph.constants`，其 `__init__` 為空）→ 不拉 pgvector/icap_retriever/langchain 重鏈；豐欄位不動 schema（Phase ④ 再持久化）。
- **型別一致**：`LlmPort.complete_text/complete_json(role=…)`、`_current_task` 回 `(idx, task, task_id)`、interrupt kinds `ask_human`(stage `star`/`five_w2h`)、`route_after_indicator`→`{"five_w2h","advance"}`、`route_deep`→`{"star","finish_deep"}` 跨 task 對齊。
- **風險最小化**：逐任務迴圈用單層 node loop（每任務重進 star＝全新 interrupt 計數器）而非巢狀子圖在迴圈；品質重試上限 1 → 收斂；測試用 `guard` 上限防無限迴圈。
```