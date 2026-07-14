"""T7(0033):事件收割 pass——BEI 即時編碼;P 的結構性的家。
fake LLM/knowledge;無 DB 無網路。教材注入接縫=BUG-2 型防回歸。"""
import pytest

from app.interview.harvest import HARVEST_SYS, _episode_turns, _locate, harvest_pass


class FakeCitable:
    def __init__(self, code, name):
        self.code, self.name = code, name


class FakePool:
    def __init__(self):
        self.knowledge = [FakeCitable("ocs:X:K:K01", "非同步處理概念")]
        self.skills = [FakeCitable("ocs:X:S:S01", "React 開發")]
        self.outputs = [FakeCitable("ocs:X:O:O01", "測試報告")]
        self.attitudes = []


class FakeKnowledge:
    async def competencies(self, code):
        return FakePool()


class FakeLlm:
    def __init__(self, result):
        self._result = result
        self.prompts = []

    async def select_schema(self, prompt, schema, *, role="select", schema_name="output"):
        self.prompts.append(prompt)
        if isinstance(self._result, Exception):
            raise self._result
        return self._result


def _doc():
    return {"ocs_profile": {"ocs_code": "X"},
            "ocs_content": {"ocu_units": [{"_uid": "u1", "ocu_name": "開發",
                "tasks": [{"_tid": "t1", "task_codes": [{"code": None, "name": "上傳功能"}],
                           "competency_blocks": [], "details": None}]}]},
            "ocs_attitude": {"attitudes": []}}


TP = "ocs_content.ocu_units.u1.tasks.t1"
TURNS = {5: "那次我做拖曳上傳", 7: "怎麼算做好?使用者放開滑鼠後手沒再焦慮亂點就算過關"}


# ---- 教材注入接縫(BUG-2 型:P 教材真的送到寫 P 的角色) ----

def test_harvest_sys_targets_indicators():
    assert "draft_indicator" in HARVEST_SYS and "STAR" in HARVEST_SYS


@pytest.mark.asyncio
async def test_harvest_prompt_injects_indicator_material():
    """【接縫,BUG-2】:收割 prompt 必含 behavior-indicator + ks-distinction 教材全文
    標誌句——這正是驗屍中斷掉沒人發現的那條線(教材沒送到寫 P 的角色)。"""
    llm = FakeLlm({"records": [{"type": "none"}]})
    ep = {"target": TP, "opened_seq": 5}
    await harvest_pass(llm, FakeKnowledge(), doc=_doc(), turns=TURNS, episode=ep,
                       header_codes=set(), ref_ocs_codes=("X",))
    p = llm.prompts[0]
    assert "可觀察" in p                          # behavior-indicator 標誌句
    assert "知識 K" in p or "技能 S" in p or "ks-distinction" in p


# ---- 收割落地(P → _pending) ----

@pytest.mark.asyncio
async def test_harvest_drafts_indicator_as_pending():
    llm = FakeLlm({"records": [{"type": "draft_indicator", "task": TP,
        "text": "使用者放開滑鼠後,畫面即時顯示 Loading 且手不再焦慮亂點",
        "quote": "使用者放開滑鼠後手沒再焦慮亂點就算過關"}]})
    ep = {"target": TP, "opened_seq": 5}
    res = await harvest_pass(llm, FakeKnowledge(), doc=_doc(), turns=TURNS, episode=ep,
                             header_codes=set(), ref_ocs_codes=("X",))
    assert res.progressed is True
    task = res.new_doc["ocs_content"]["ocu_units"][0]["tasks"][0]
    ind = task["competency_blocks"][0]["indicators"][0]
    assert ind["_pending"]["op"] == "add"
    assert "Loading" in ind["text"]
    # quote 跨多輪定位到第 7 輪(非事件開場第 5 輪)
    assert ind["_pending"]["src"]["quote"]["turn_id"] == 7


# ---- 純函式 helpers ----

def test_episode_turns_range():
    assert _episode_turns({3: "a", 5: "b", 7: "c"}, 5) == {5: "b", 7: "c"}


def test_locate_finds_turn():
    assert _locate("手沒再焦慮亂點", TURNS) == 7
    assert _locate("從沒說過", TURNS) == 0


# ---- fail-open(LLM 掛不擋回合) ----

@pytest.mark.asyncio
async def test_harvest_fail_open_on_llm_error():
    llm = FakeLlm(RuntimeError("provider down"))
    ep = {"target": TP, "opened_seq": 5}
    res = await harvest_pass(llm, FakeKnowledge(), doc=_doc(), turns=TURNS, episode=ep,
                             header_codes=set(), ref_ocs_codes=("X",))
    assert res.records_failed is True and res.new_doc is None


@pytest.mark.asyncio
async def test_harvest_empty_when_no_episode_turns():
    llm = FakeLlm({"records": []})
    ep = {"target": TP, "opened_seq": 99}          # 開場輪在逐字稿之後 → 無事件內容
    res = await harvest_pass(llm, FakeKnowledge(), doc=_doc(), turns=TURNS, episode=ep,
                             header_codes=set(), ref_ocs_codes=("X",))
    assert res.new_doc is None and res.progressed is False
