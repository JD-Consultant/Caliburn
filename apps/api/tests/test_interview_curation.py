"""T3(0028 D1/D4/D6):裁剪 pass——AI 依故事對官方任務池預勾/排除。
strict schema(enum 鎖池)+確定性守衛(quote 逐字、衝突雙棄);保守=不確定不出記錄。
純函式 + fake LLM,無 DB 無網路。"""
import pytest

from app.interview.curation import (
    CurationOutput, apply_curation, curation_pass, curation_schema,
)

POOL = [
    {"key": "ISD:T1", "name": "需求訪談", "unit": "規劃", "ocs_code": "ISD", "task_code": "T1"},
    {"key": "ISD:T2", "name": "介面設計", "unit": "規劃", "ocs_code": "ISD", "task_code": "T2"},
]
SAID = ["我平常主要跟客戶開需求訪談", "介面設計那種我沒有做"]


def _tags(schema):
    return {v["properties"]["type"]["enum"][0]
            for v in schema["properties"]["records"]["items"]["anyOf"]}


def test_schema_locked_to_pool_keys_and_none_escape():
    s = curation_schema([p["key"] for p in POOL])
    assert _tags(s) == {"precheck", "decline", "none"}
    pre = next(v for v in s["properties"]["records"]["items"]["anyOf"]
               if v["properties"]["type"]["enum"] == ["precheck"])
    assert pre["properties"]["key"]["enum"] == ["ISD:T1", "ISD:T2"]


def test_schema_empty_pool_fail_closed():
    assert _tags(curation_schema([])) == {"none"}          # 只剩逃生口


def test_apply_precheck_and_decline_with_guards():
    records = [
        {"type": "precheck", "key": "ISD:T1", "quote": "跟客戶開需求訪談"},
        {"type": "decline", "key": "ISD:T2", "quote": "介面設計那種我沒有做"},
        {"type": "precheck", "key": "ISD:T9", "quote": "跟客戶開需求訪談"},   # 池外
        {"type": "none"},
    ]
    res = apply_curation(records, pool_tasks=POOL, employee_texts=SAID)
    assert [p["key"] for p in res.precheck] == ["ISD:T1"]
    assert res.precheck[0]["name"] == "需求訪談"            # 池 metadata 回填(給 UI 顯示)
    assert [d["key"] for d in res.declined] == ["ISD:T2"]
    assert any("ISD:T9" in g for g in res.guard_log)


def test_apply_unverified_quote_dropped():
    records = [{"type": "precheck", "key": "ISD:T1", "quote": "他沒說過這句"}]
    res = apply_curation(records, pool_tasks=POOL, employee_texts=SAID)
    assert res.precheck == [] and any("quote" in g for g in res.guard_log)


def test_apply_conflict_same_key_drops_both():
    """同 key 又預勾又排除=LLM 自相矛盾 → 雙棄留痕(寧可少不硬猜)。"""
    records = [
        {"type": "precheck", "key": "ISD:T1", "quote": "跟客戶開需求訪談"},
        {"type": "decline", "key": "ISD:T1", "quote": "跟客戶開需求訪談"},
    ]
    res = apply_curation(records, pool_tasks=POOL, employee_texts=SAID)
    assert res.precheck == [] and res.declined == []
    assert any("衝突" in g for g in res.guard_log)


class FakeLlm:
    def __init__(self, responses):
        self.responses = list(responses)
        self.prompts = []

    async def select_schema(self, prompt, schema, *, role="select", schema_name="output"):
        self.prompts.append(prompt)
        r = self.responses.pop(0)
        if isinstance(r, Exception):
            raise r
        return r


@pytest.mark.asyncio
async def test_curation_pass_happy():
    llm = FakeLlm([{"records": [
        {"type": "precheck", "key": "ISD:T1", "quote": "跟客戶開需求訪談"}]}])
    res = await curation_pass(llm, pool_tasks=POOL, employee_texts=SAID)
    assert [p["key"] for p in res.precheck] == ["ISD:T1"]
    assert res.failed is False
    assert "需求訪談" in llm.prompts[0]                     # 池選單有進 prompt


@pytest.mark.asyncio
async def test_curation_pass_retry_then_fail_closed():
    bad = {"records": [{"type": "precheck"}]}               # 缺欄 → pydantic 拒
    llm = FakeLlm([bad, bad])
    res = await curation_pass(llm, pool_tasks=POOL, employee_texts=SAID)
    assert len(llm.prompts) == 2                            # 重試一次
    assert res.failed is True and res.precheck == [] and res.declined == []


def test_pydantic_rejects_unknown_type():
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        CurationOutput.model_validate({"records": [{"type": "delete_all"}]})


def test_curation_ops_two_phase_lands_on_virgin_doc():
    """0033 T1【接縫,BUG-1】:**空文件**+quote-backed precheck → 官方殼+任務
    兩相直落成功(= session 330a0bed 第 3 輪 14 筆全滅的場景轉綠)。
    復刻 service ②½ 的兩相迴圈:u_ops 先落、t_ops 對含殼文件再驗。"""
    from app.interview.curation import curation_ops
    from app.interview.scribe import land_ops

    pool_by_key = {"ISD:T1": {"key": "ISD:T1", "name": "需求訪談", "unit": "規劃",
                              "ocs_code": "ISD", "task_code": "T1",
                              "task_urn": "ocs:ISD:T:T1", "unit_urn": "ocs:ISD:U:U1"}}
    turns = {3: "我平常主要跟客戶開需求訪談"}
    precheck = [{"key": "ISD:T1", "name": "需求訪談", "unit": "規劃",
                 "quote": "跟客戶開需求訪談"}]
    u_ops, t_ops, guard = curation_ops(precheck, doc={}, turns=turns,
                                       pool_by_key=pool_by_key)
    assert u_ops and t_ops, guard
    doc: dict = {}
    for phase_ops in (u_ops, t_ops):
        nd, g, landed = land_ops(phase_ops, doc=doc, turns=turns,
                                 ref_codes={"ocs:ISD:T:T1", "ocs:ISD:U:U1"},
                                 header_codes=set(), pool_items={})
        assert nd is not None and landed, g
        doc = nd
    unit = doc["ocs_content"]["ocu_units"][0]
    assert unit["ocu_name"] == "規劃" and unit["_pending"]["op"] == "add"
    task = unit["tasks"][0]
    assert task["task_codes"][0]["name"] == "需求訪談"
    assert task["provenance"] == {"ocs_code": "ISD", "task_code": "T1"}
    assert task["_pending"]["op"] == "add"
