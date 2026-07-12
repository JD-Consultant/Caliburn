"""T6:顧問 READ 工具層(spec §4.1、§16.6;Anthropic《Writing tools》檢核)。
2 工具(search_occupations/occupation_brief);dispatcher 純呼 KnowledgePort、壓縮回傳。
fake knowledge;無真 LLM/indexer。"""
import pytest

from app.interview.tools import CONSULTANT_TOOLS, dispatch_tool


class _Hit:
    def __init__(self, code, name, score):
        self.ocs_code, self.ocs_name, self.score = code, name, score
        self.urn, self.job_description, self.ocs_level = "", "", None


class _Item:
    def __init__(self, code, name=None, text=None):
        self.code, self.name, self.text = code, name, text


class _TaskRef:
    def __init__(self, code, name):
        self.task_code, self.task_name, self.urn = code, name, ""


class _Unit:
    def __init__(self, name, tasks):
        self.ocu_code, self.ocu_name, self.urn = "U1", name, ""
        self.tasks = tasks


class FakeKnowledge:
    def __init__(self):
        self.calls = []

    async def search_occupations(self, query, *, top_k=10):
        self.calls.append(("search", query, top_k))
        hits = [_Hit(f"C{i}", f"職類{i}", 1.0 - i * 0.1) for i in range(8)]
        return type("R", (), {"hits": hits})()

    async def occupation_tasks(self, ocs_code):
        self.calls.append(("tasks", ocs_code))
        return type("R", (), {"ocs_code": ocs_code, "ocs_name": "軟體測試工程師",
                              "units": [_Unit("測試規劃", [_TaskRef("T1.1", "測試案例設計")])]})()

    async def competencies(self, ocs_code):
        self.calls.append(("comp", ocs_code))
        return type("R", (), {"ocs_code": ocs_code,
                              "knowledge": [_Item("K01", "測試設計技術")],
                              "skills": [_Item("S01", "測試工具使用")],
                              "outputs": [_Item("O01", "測試計畫")],
                              "indicators": [_Item("P01", text="能設計覆蓋案例")],
                              "attitudes": [_Item("A01", "謹慎細心")]})()


def test_tools_are_openai_shaped_and_namespaced():
    names = {t["function"]["name"] for t in CONSULTANT_TOOLS}
    assert names == {"knowledge_search_occupations", "knowledge_occupation_brief",
                     "read_document"}   # v3(ADR 0030 T5):四態視圖工具
    for t in CONSULTANT_TOOLS:
        assert t["type"] == "function"
        assert "description" in t["function"] and "parameters" in t["function"]


@pytest.mark.asyncio
async def test_search_returns_semantic_names_and_truncates():
    k = FakeKnowledge()
    out = await dispatch_tool("knowledge_search_occupations",
                              {"query": "軟體測試", "top_k": 3}, k)
    assert len(out["occupations"]) == 3                       # top_k 截斷
    assert out["occupations"][0] == {"ocs_code": "C0", "name": "職類0", "score": 1.0}


@pytest.mark.asyncio
async def test_search_default_top_k():
    k = FakeKnowledge()
    out = await dispatch_tool("knowledge_search_occupations", {"query": "x"}, k)
    assert len(out["occupations"]) == 5                       # 預設 top_k=5


@pytest.mark.asyncio
async def test_occupation_brief_merges_tasks_and_competencies():
    k = FakeKnowledge()
    out = await dispatch_tool("knowledge_occupation_brief", {"ocs_code": "ISD1"}, k)
    assert ("tasks", "ISD1") in k.calls and ("comp", "ISD1") in k.calls   # 合併呼
    assert out["ocs_name"] == "軟體測試工程師"
    assert out["tasks"][0] == {"unit": "測試規劃", "code": "T1.1", "name": "測試案例設計"}
    assert out["competencies"]["knowledge"] == [{"code": "K01", "name": "測試設計技術"}]
    assert out["competencies"]["indicators"] == [{"code": "P01", "text": "能設計覆蓋案例"}]


@pytest.mark.asyncio
async def test_unknown_tool_returns_actionable_error():
    out = await dispatch_tool("knowledge_delete_all", {}, FakeKnowledge())
    assert "error" in out and "knowledge_search_occupations" in out["error"]   # 提示可用工具


@pytest.mark.asyncio
async def test_port_exception_becomes_actionable_error():
    class Boom:
        async def search_occupations(self, q, *, top_k=10):
            raise RuntimeError("indexer down")
    out = await dispatch_tool("knowledge_search_occupations", {"query": "x"}, Boom())
    assert "error" in out and "indexer down" in out["error"]
