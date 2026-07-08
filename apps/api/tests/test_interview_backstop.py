"""T12:backstop 收尾複查(spec §6;ADR 0027 第4組件)。
只答兩題(漏記/出處違規)、只產建議、確定性後驗(gap∈空縫、path∈已寫、quote 逐字)。
fake llm;無真 LLM。"""
import pytest

from app.interview.backstop import BackstopResult, backstop_pass


class FakeLlm:
    def __init__(self, result):
        self._r = result
        self.calls = []

    async def select_schema(self, prompt, schema, *, role="select", schema_name="output"):
        self.calls.append({"role": role, "prompt": prompt})
        return self._r


EMPLOYEE = ["我每天巡檢設備", "遇到異常就開維修單,通常要等主管簽核才能停機"]
GAPS = [{"gap": "T.details.wait_points", "label": "等待瓶頸"},
        {"gap": "T.details.exceptions", "label": "例外處理"}]
RECORDED = [{"path": "T.details.frequency", "quote": "我每天巡檢設備"}]


@pytest.mark.asyncio
async def test_valid_miss_and_misattribution_kept():
    llm = FakeLlm({
        "misses": [{"gap": "T.details.wait_points", "quote": "要等主管簽核才能停機"}],
        "misattributed": [{"path": "T.details.frequency", "reason": "引文其實在講停機不是頻率"}]})
    res = await backstop_pass(llm, employee_texts=EMPLOYEE, empty_gaps=GAPS, recorded=RECORDED)
    assert isinstance(res, BackstopResult)
    assert res.misses[0]["gap"] == "T.details.wait_points"
    assert res.misattributed[0]["path"] == "T.details.frequency"
    assert llm.calls[0]["role"] == "select"           # 便宜模型


@pytest.mark.asyncio
async def test_miss_with_hallucinated_gap_dropped():
    llm = FakeLlm({"misses": [{"gap": "T.details.NONEXISTENT", "quote": "要等主管簽核才能停機"}],
                   "misattributed": []})
    res = await backstop_pass(llm, employee_texts=EMPLOYEE, empty_gaps=GAPS, recorded=RECORDED)
    assert res.misses == []                            # gap 不在空縫清單 → 丟


@pytest.mark.asyncio
async def test_miss_with_fabricated_quote_dropped():
    llm = FakeLlm({"misses": [{"gap": "T.details.exceptions", "quote": "我每天寫一萬行程式"}],
                   "misattributed": []})
    res = await backstop_pass(llm, employee_texts=EMPLOYEE, empty_gaps=GAPS, recorded=RECORDED)
    assert res.misses == []                            # quote 不在逐字稿 → 丟


@pytest.mark.asyncio
async def test_misattribution_with_unknown_path_dropped():
    llm = FakeLlm({"misses": [],
                   "misattributed": [{"path": "T.details.GHOST", "reason": "x"}]})
    res = await backstop_pass(llm, employee_texts=EMPLOYEE, empty_gaps=GAPS, recorded=RECORDED)
    assert res.misattributed == []                     # path 不在已寫清單 → 丟


@pytest.mark.asyncio
async def test_nothing_to_check_skips_llm():
    llm = FakeLlm({"misses": [], "misattributed": []})
    res = await backstop_pass(llm, employee_texts=EMPLOYEE, empty_gaps=[], recorded=[])
    assert res.misses == [] and res.misattributed == [] and llm.calls == []   # 無縫無寫→不呼


def test_to_suggestions_shape():
    res = BackstopResult(
        misses=[{"gap": "T.details.wait_points", "quote": "要等主管簽核"}],
        misattributed=[{"path": "T.details.frequency", "reason": "引文離題"}])
    sugs = res.to_suggestions()
    assert any(s["doc_path"] == "T.details.wait_points" and "補漏" in s["reason"] for s in sugs)
    assert any(s["doc_path"] == "T.details.frequency" and "出處" in s["reason"] for s in sugs)
