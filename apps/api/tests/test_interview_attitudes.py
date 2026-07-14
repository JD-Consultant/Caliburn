"""T4(0028 D3):態度收尾 pass——讀全逐字稿整體編碼 2–4 條,每條綁最強引文。
strict 池 enum+確定性守衛(quote 逐字、去重、含 existing 的 MAX_A 硬上限);只產建議。
fake LLM,無 DB。"""
import pytest

from app.interview import coverage as L
from app.interview.attitudes import attitudes_pass, attitudes_schema

POOL = ["A01", "A03", "A04", "A05", "A06"]
ITEMS = {"A01": "親和關係", "A03": "謹慎細心", "A04": "彈性", "A05": "應對不明狀況",
         "A06": "自我提升"}
SAID = ["回歸沒跑完我絕不簽核放行,擋版 blocker 當天就通報",
        "環境被佔住我就先去補自動化腳本,順序自己排"]


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


def _att(pid, quote, rationale="故事顯示此態度"):
    return {"pool_id": pid, "quote": quote, "rationale": rationale}


def test_schema_pool_enum_locked():
    s = attitudes_schema(POOL)
    item = s["properties"]["attitudes"]["items"]
    assert item["properties"]["pool_id"]["enum"] == POOL


@pytest.mark.asyncio
async def test_happy_two_proposals_to_suggestions():
    llm = FakeLlm([{"attitudes": [
        _att("A03", "回歸沒跑完我絕不簽核放行"),
        _att("A05", "環境被佔住我就先去補自動化腳本")]}])
    res = await attitudes_pass(llm, pool=POOL, pool_items=ITEMS,
                               employee_texts=SAID, existing=[])
    assert [p["pool_id"] for p in res.proposals] == ["A03", "A05"]
    sugs = res.to_suggestions()
    assert sugs[0]["doc_path"] == "ocs_attitude.attitudes"
    assert sugs[0]["new_value"] == {"code": "A03", "name": "謹慎細心"}
    assert "回歸沒跑完" in sugs[0]["reason"]                 # 引文入 reason(人審看得到)


@pytest.mark.asyncio
async def test_guards_pool_quote_dedup_existing():
    llm = FakeLlm([{"attitudes": [
        _att("A99", "回歸沒跑完我絕不簽核放行"),              # 池外
        _att("A03", "他沒說過這句"),                          # quote 未驗
        _att("A05", "環境被佔住我就先去補自動化腳本"),
        _att("A05", "順序自己排"),                            # 重複 code
        _att("A01", "擋版 blocker 當天就通報")]},])
    res = await attitudes_pass(llm, pool=POOL, pool_items=ITEMS,
                               employee_texts=SAID, existing=["A01"])   # A01 已在文件
    assert [p["pool_id"] for p in res.proposals] == ["A05"]
    assert any("A99" in g for g in res.guard_log)
    assert any("quote" in g for g in res.guard_log)


@pytest.mark.asyncio
async def test_hard_cap_max_a_including_existing():
    llm = FakeLlm([{"attitudes": [
        _att("A03", "回歸沒跑完我絕不簽核放行"),
        _att("A04", "環境被佔住我就先去補自動化腳本"),
        _att("A05", "順序自己排"),
        _att("A06", "擋版 blocker 當天就通報")]}])
    res = await attitudes_pass(llm, pool=POOL, pool_items=ITEMS,
                               employee_texts=SAID, existing=["A01", "A02"])
    assert len(res.proposals) == L.MAX_A - 2                 # 硬上限含 existing
    assert any("上限" in g for g in res.guard_log)


@pytest.mark.asyncio
async def test_existing_full_skips_llm():
    llm = FakeLlm([])
    res = await attitudes_pass(llm, pool=POOL, pool_items=ITEMS, employee_texts=SAID,
                               existing=["A01", "A03", "A04", "A05"])   # 已滿 MAX_A
    assert res.proposals == [] and llm.prompts == []          # 不呼 LLM(省成本)


@pytest.mark.asyncio
async def test_retry_then_fail_closed():
    llm = FakeLlm([ValueError("boom"), ValueError("boom")])
    res = await attitudes_pass(llm, pool=POOL, pool_items=ITEMS,
                               employee_texts=SAID, existing=[])
    assert res.failed is True and res.proposals == []
