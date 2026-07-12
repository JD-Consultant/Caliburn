"""backstop v3(ADR 0030 T5)= 確定性撿漏 sweep。零 LLM(§6.4 禁令)。

命中規則:員工提過(正規化子串)、且文件(含待審)沒有 → 產 held 追問。
"""
from app.interview.backstop import SWEEP_EVERY, backstop_sweep

POOL_ITEMS = {"K01": "測試設計技術", "S01": "測試工具使用"}
UNASKED = [{"key": "X:T1", "name": "測試環境建置", "unit": "測試", "ocs_code": "X",
            "task_code": "T1"}]


def _doc(with_env_task=False):
    tasks = [{"_tid": "C", "task_codes": [{"code": None, "name": "設計測試案例"}],
              "competency_blocks": [{}], "details": {}}]
    if with_env_task:
        tasks.append({"_tid": "E",
                      "task_codes": [{"code": None, "name": "測試環境建置"}],
                      "competency_blocks": [], "details": None})
    return {"ocs_content": {"ocu_units": [{"_uid": "U1", "tasks": tasks}]},
            "ocs_attitude": {"attitudes": []}}


def test_unasked_task_mentioned_becomes_held_question():
    held = backstop_sweep(doc=_doc(),
                          texts_since=["我上週還在弄測試環境建置,搞了三天"],
                          unasked_tasks=UNASKED, pool_items={})
    assert len(held) == 1 and "測試環境建置" in held[0]


def test_already_in_doc_not_re_asked():
    held = backstop_sweep(doc=_doc(with_env_task=True),
                          texts_since=["測試環境建置那些"],
                          unasked_tasks=UNASKED, pool_items={})
    assert held == []


def test_pool_item_mentioned_becomes_held():
    held = backstop_sweep(doc=_doc(), texts_since=["其實測試工具使用我很熟"],
                          unasked_tasks=[], pool_items=POOL_ITEMS)
    assert len(held) == 1 and "測試工具使用" in held[0]


def test_no_mention_no_noise():
    held = backstop_sweep(doc=_doc(), texts_since=["今天天氣不錯"],
                          unasked_tasks=UNASKED, pool_items=POOL_ITEMS)
    assert held == []


def test_normalization_tolerates_spacing():
    held = backstop_sweep(doc=_doc(), texts_since=["測試 環境 建置也歸我管"],
                          unasked_tasks=UNASKED, pool_items={})
    assert len(held) == 1


def test_no_llm_in_module():
    """§6.4 禁令斷言:backstop 模組零 LLM 依賴(select_schema/async 不得出現)。"""
    import inspect
    import app.interview.backstop as B
    src = inspect.getsource(B)
    assert "select_schema" not in src
    assert "async def" not in src            # 純同步純函式
    assert isinstance(SWEEP_EVERY, int) and SWEEP_EVERY >= 1
