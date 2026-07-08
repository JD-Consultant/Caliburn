"""T4b:書記服務 scribe_pass(LLM 編排;spec §3.2、§16.4)。
fake LLM/knowledge:建池→select_schema→重試→apply。無真 LLM 無 DB。"""
import pytest

from app.interview.scribe import build_pool_inputs, scribe_pass


class FakeCitable:
    def __init__(self, code, name):
        self.code, self.name = code, name


class FakePool:
    def __init__(self):
        self.knowledge = [FakeCitable("K01", "測試設計技術")]
        self.skills = [FakeCitable("S01", "測試工具使用")]
        self.outputs = [FakeCitable("O01", "測試計畫")]
        self.attitudes = [FakeCitable("A01", "謹慎細心")]
        self.indicators = []


class FakeKnowledge:
    def __init__(self):
        self.calls = []

    async def competencies(self, ocs_code):
        self.calls.append(ocs_code)
        return FakePool()


class FakeLlm:
    """select_schema 依序吐 responses(模擬重試);invalid=拋以觸發重試路徑。"""
    def __init__(self, responses):
        self.responses = list(responses)
        self.prompts = []

    async def select_schema(self, prompt, schema, *, role="select", schema_name="output"):
        self.prompts.append(prompt)
        r = self.responses.pop(0)
        if isinstance(r, Exception):
            raise r
        return r


def _doc(tasks=None):
    tasks = tasks or [{"_tid": "C", "competency_blocks": [{}], "details": {}}]
    return {"ocs_profile": {"ocs_code": "ISD2519-002v2"},
            "ocs_content": {"ocu_units": [{"_uid": "U1", "tasks": tasks}]},
            "ocs_attitude": {"attitudes": []},
            "version_info": {"versions": []}}


TASK = "ocs_content.ocu_units.U1.tasks.C"


@pytest.mark.asyncio
async def test_build_pool_inputs_from_knowledge():
    k = FakeKnowledge()
    pools, items = await build_pool_inputs(k, _doc())
    assert k.calls == ["ISD2519-002v2"]
    assert pools == {"knowledge": ["K01"], "skills": ["S01"],
                     "outputs": ["O01"], "attitudes": ["A01"]}
    assert items["K01"] == "測試設計技術"


@pytest.mark.asyncio
async def test_scribe_pass_applies_pool_record():
    llm = FakeLlm([{"records": [
        {"type": "record_task_pool", "kind": "knowledge", "task": TASK,
         "pool_id": "K01", "quote": "先讀懂需求規格"}]}])
    res = await scribe_pass(llm, FakeKnowledge(), doc=_doc(),
                            employee_texts=["我先讀懂需求規格再動手"], human_touched=[])
    block = res.new_doc["ocs_content"]["ocu_units"][0]["tasks"][0]["competency_blocks"][0]
    assert block["knowledge"] == [{"code": "K01", "name": "測試設計技術"}]


@pytest.mark.asyncio
async def test_scribe_pass_multi_task_routing():
    doc = _doc(tasks=[{"_tid": "C1", "competency_blocks": [{}], "details": {}},
                      {"_tid": "C2", "competency_blocks": [{}], "details": {}}])
    t1 = "ocs_content.ocu_units.U1.tasks.C1"
    t2 = "ocs_content.ocu_units.U1.tasks.C2"
    llm = FakeLlm([{"records": [
        {"type": "record_task_pool", "kind": "knowledge", "task": t1,
         "pool_id": "K01", "quote": "讀需求"},
        {"type": "record_task_pool", "kind": "skills", "task": t2,
         "pool_id": "S01", "quote": "跑工具"}]}])
    res = await scribe_pass(llm, FakeKnowledge(), doc=doc,
                            employee_texts=["讀需求，然後跑工具"], human_touched=[])
    tasks = res.new_doc["ocs_content"]["ocu_units"][0]["tasks"]
    assert tasks[0]["competency_blocks"][0]["knowledge"][0]["code"] == "K01"
    assert tasks[1]["competency_blocks"][0]["skills"][0]["code"] == "S01"


@pytest.mark.asyncio
async def test_scribe_pass_retries_on_invalid_then_succeeds():
    llm = FakeLlm([
        {"records": [{"type": "record_task_pool", "kind": "knowledge"}]},   # 缺欄→pydantic 拒
        {"records": [{"type": "record_task_pool", "kind": "knowledge", "task": TASK,
                      "pool_id": "K01", "quote": "先讀懂需求規格"}]}])
    res = await scribe_pass(llm, FakeKnowledge(), doc=_doc(),
                            employee_texts=["我先讀懂需求規格"], human_touched=[])
    assert len(llm.prompts) == 2                                  # 重試了一次
    assert "重出" in llm.prompts[1] or "不合法" in llm.prompts[1]  # 精簡錯誤回饋
    assert res.new_doc is not None                               # 第二次成功套用


@pytest.mark.asyncio
async def test_scribe_pass_gives_up_after_retry_without_crashing():
    bad = {"records": [{"type": "record_task_pool"}]}            # 一直不合法
    res = await scribe_pass(FakeLlm([bad, bad]), FakeKnowledge(), doc=_doc(),
                            employee_texts=["隨便說說"], human_touched=[])
    assert res.new_doc is None and res.records_failed is True    # 不擋回合、標記交 backstop
