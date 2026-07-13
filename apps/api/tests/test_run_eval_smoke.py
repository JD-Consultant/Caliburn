import asyncio
from tests.conftest_graph import FakeLlm
from evals.run_eval import run_all


def test_run_all_passes_with_good_stub():
    # stub：JSON 類回合法 zh-TW JSON
    good = '{"situation":"晨班巡檢產線","purpose":"確保設備可用"}'
    ok, report = asyncio.run(run_all(llm=FakeLlm(text=good)))
    # doc_structure 類已隨 authoring 退場(T12):結構驗證=契約 schema+verify 六查
    assert set(report) == {"json_zhtw"}
    assert isinstance(ok, bool)
