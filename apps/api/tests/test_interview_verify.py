"""verify 六查(ADR 0030 T3):純函式 output guardrail。

每查至少一過一擋;錯誤必須可行動(含修正提示)。
"""
from app.interview.verify import verify_ops

DOC = {
    "ocs_profile": {"ocs_code": "ABC1234", "job_description": "負責…"},
    "ocs_content": {"ocu_units": [
        {"_uid": "u1", "ocu_code": "T1", "ocu_name": "生產排程",
         "tasks": [
             {"_tid": "t1",
              "task_codes": [{"code": "T1.1", "name": "排定週生產計畫"}],
              "competency_blocks": [
                  {"competency_level": 3,
                   "indicators": [{"code": "P1", "text": "能於期限內完成排程"}],
                   "outputs": [{"code": None, "name": "週生產計畫表"}],
                   "knowledge": [], "skills": []}],
              "details": {"frequency": "每週"}},
         ]},
    ]},
    "ocs_attitude": {"attitudes": [{"code": "A01", "name": "謹慎"}]},
}
TURNS = {3: "我們每週一要排定整條線的生產計畫,還要跟業務對需求",
         5: "報表都是用 ERP 拉出來再人工調"}
REFS = {"ocs:unit:ABC1234:t2", "K01"}
HEADERS = {"ABC1234", "XYZ9999"}
TASKS_PATH = "ocs_content.ocu_units.u1.tasks.t1.task_codes"
SLOT_PATH = "ocs_content.ocu_units.u1.tasks.t1.details.tools"


def run(ops):
    return verify_ops(ops, doc=DOC, turns=TURNS, ref_codes=REFS, header_codes=HEADERS)


def _q(tid=3, text="每週一要排定整條線的生產計畫"):
    return {"turn_id": tid, "text": text}


def test_add_with_quote_passes():
    r = run([{"target_path": TASKS_PATH, "op": "add", "value": "跨部門需求對齊",
              "src": {"quote": _q()}}])
    assert r.ok, r.errors


def test_ref_and_quote_coexist_passes():
    r = run([{"target_path": TASKS_PATH, "op": "add", "value": "產線異常處理",
              "src": {"ref_urn": "ocs:unit:ABC1234:t2", "quote": _q()}}])
    assert r.ok, r.errors


def test_add_without_any_src_rejected():
    r = run([{"target_path": TASKS_PATH, "op": "add", "value": "腦補任務", "src": {}}])
    assert not r.ok and r.errors[0].check == "src"


def test_hallucinated_quote_rejected_with_hint():
    r = run([{"target_path": TASKS_PATH, "op": "add", "value": "X",
              "src": {"quote": {"turn_id": 3, "text": "這句話從沒說過"}}}])
    assert not r.ok and r.errors[0].check == "quote"
    assert "找不到" in r.errors[0].message and r.errors[0].hint


def test_quote_in_wrong_turn_hints_correct_turn():
    r = run([{"target_path": TASKS_PATH, "op": "add", "value": "X",
              "src": {"quote": {"turn_id": 3, "text": "用 ERP 拉出來"}}}])
    assert not r.ok and r.errors[0].check == "quote"
    assert "第 5 輪" in (r.errors[0].hint or "")


def test_quote_normalization_tolerates_whitespace_fullwidth():
    r = run([{"target_path": TASKS_PATH, "op": "add", "value": "X",
              "src": {"quote": {"turn_id": 5, "text": "用ERP 拉出來 再人工調"}}}])
    assert r.ok, r.errors


def test_ref_outside_reference_set_rejected():
    r = run([{"target_path": TASKS_PATH, "op": "add", "value": "X",
              "src": {"ref_urn": "ocs:unit:OTHER:t9"}}])
    assert not r.ok and r.errors[0].check == "src"


def test_add_duplicate_rejected():
    r = run([{"target_path": TASKS_PATH, "op": "add", "value": "排定週生產計畫",
              "src": {"quote": _q()}}])
    assert not r.ok and r.errors[0].check == "invariant"
    assert "已存在" in r.errors[0].message


def test_add_to_missing_container_rejected():
    r = run([{"target_path": "ocs_content.ocu_units.u9.tasks.t1.task_codes",
              "op": "add", "value": "X", "src": {"quote": _q()}}])
    assert not r.ok and r.errors[0].check == "permission"


def test_mod_missing_target_rejected():
    r = run([{"target_path": f"{SLOT_PATH.rsplit('.', 1)[0]}.ghost_slot",
              "op": "mod", "value": "X", "src": {"quote": _q()}}])
    assert not r.ok


def test_mod_slot_passes_and_level_normalizes():
    ok = run([{"target_path": SLOT_PATH, "op": "mod", "value": "ERP、排程軟體",
               "src": {"quote": {"turn_id": 5, "text": "用 ERP 拉出來"}}}])
    assert ok.ok, ok.errors
    lvl_path = "ocs_content.ocu_units.u1.tasks.t1.competency_blocks.0.competency_level"
    ok2 = run([{"target_path": lvl_path, "op": "mod", "value": "4級",
                "src": {"ref_urn": "K01"}}])
    assert ok2.ok, ok2.errors
    bad = run([{"target_path": lvl_path, "op": "mod", "value": "6",
                "src": {"ref_urn": "K01"}}])
    assert not bad.ok and bad.errors[0].check == "contract"


def test_position_code_rejected_for_anyone():
    r = run([{"target_path": f"{TASKS_PATH}.0.code", "op": "mod", "value": "T9.9",
              "src": {"quote": _q()}}])
    assert not r.ok and r.errors[0].check == "invariant"
    assert "renumber" in r.errors[0].message


def test_header_basis_mod_gated_by_reference_set():
    ok = run([{"target_path": "ocs_profile.ocs_code", "op": "mod", "value": "XYZ9999",
               "src": {"ref_urn": "K01"}}])
    assert ok.ok, ok.errors
    bad = run([{"target_path": "ocs_profile.ocs_code", "op": "mod", "value": "NOPE001",
                "src": {"ref_urn": "K01"}}])
    assert not bad.ok and bad.errors[0].check == "invariant"


def test_attitude_only_at_document_level():
    r = run([{"target_path": "ocs_content.ocu_units.u1.tasks.t1.attitudes",
              "op": "add", "value": "積極", "src": {"quote": _q()}}])
    assert not r.ok and r.errors[0].check == "invariant"
    ok = run([{"target_path": "ocs_attitude.attitudes", "op": "add", "value": "耐心",
               "src": {"quote": _q()}}])
    assert ok.ok, ok.errors


def test_hygiene_length_and_control_chars():
    long_val = "x" * 501
    r = run([{"target_path": TASKS_PATH, "op": "add", "value": long_val,
              "src": {"quote": _q()}}])
    assert not r.ok and r.errors[0].check == "hygiene"
    r2 = run([{"target_path": SLOT_PATH, "op": "mod", "value": "第一行\n第二行",
               "src": {"quote": {"turn_id": 5, "text": "用 ERP 拉出來"}}}])
    assert not r2.ok and r2.errors[0].check == "hygiene"


def test_del_needs_existing_target_but_no_src():
    ok = run([{"target_path": f"{TASKS_PATH}.0", "op": "del", "src": {}}])
    assert ok.ok, ok.errors
    bad = run([{"target_path": f"{TASKS_PATH}.9", "op": "del", "src": {}}])
    assert not bad.ok and bad.errors[0].check == "permission"


def test_errors_carry_op_index_for_retry():
    r = run([
        {"target_path": TASKS_PATH, "op": "add", "value": "合法任務",
         "src": {"quote": _q()}},
        {"target_path": TASKS_PATH, "op": "add", "value": "壞任務", "src": {}},
    ])
    assert not r.ok and len(r.errors) == 1 and r.errors[0].op_index == 1
