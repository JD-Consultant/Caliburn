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
