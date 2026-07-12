"""count_pending / 匯出剝除(ADR 0030 T2):`_pending` 計數與 _strip_underscore 覆蓋。

計數規則:inline 標記(dict 帶 "op")算 1;集合式(TaskDetails/OcsProfile 的
`_pending: {槽名: mark}`)逐槽算;null/空不算。匯出(assemble_final)後不得殘留。
"""
from app.core.domain.ocs_doc import assemble_final, count_pending

MARK = {"op": "add", "by": "ai", "turn_id": 3,
        "src": {"quote": {"turn_id": 3, "text": "原話"}}}
MARK_MOD = {"op": "mod", "by": "ai", "turn_id": 5, "prev": "舊值",
            "src": {"ref_urn": "ocs:x"}}


def _doc_with_pending() -> dict:
    return {
        "ocs_profile": {
            "ocs_code": "ABC1234",
            "_pending": {"job_description": MARK_MOD, "ocs_level": None},
        },
        "ocs_content": {"ocu_units": [
            {"ocu_code": "T1", "ocu_name": "職責一", "_pending": MARK,
             "tasks": [
                 {"task_codes": [{"code": None, "name": "新任務", "_pending": MARK}],
                  "competency_blocks": [
                      {"indicators": [{"code": "P1", "text": "指標", "_pending": MARK_MOD}],
                       "outputs": [], "knowledge": [], "skills": []}],
                  "details": {"frequency": "每週",
                              "_pending": {"frequency": MARK_MOD}}},
             ]},
        ]},
        "ocs_attitude": {"attitudes": [{"code": "A01", "name": "謹慎", "_pending": MARK}]},
        "notes": {"prerequisites": [], "supplements": []},
    }


def test_count_pending_counts_inline_and_collection():
    # inline:unit + task_code + indicator + attitude = 4;集合式:profile 1 + details 1 = 2
    assert count_pending(_doc_with_pending()) == 6


def test_count_pending_zero_on_clean_doc():
    assert count_pending({"ocs_profile": {"ocs_code": "X"}, "ocs_content": {}}) == 0


def test_assemble_final_strips_all_pending():
    final = assemble_final(_doc_with_pending())
    assert count_pending(final) == 0
    # 深層抽查:不得殘留任何 _pending 鍵
    def no_pending(node):
        if isinstance(node, dict):
            assert "_pending" not in node
            for v in node.values():
                no_pending(v)
        elif isinstance(node, list):
            for v in node:
                no_pending(v)
    no_pending(final)
