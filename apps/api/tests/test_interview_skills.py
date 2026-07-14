"""T7(ADR 0030 §6.8):skill 八檔+確定性載入+context 三層前綴穩定。純函式。"""
from app.interview import consultant as C
from app.interview import coverage as CO
from app.interview.skill_loader import (
    ALL_SKILLS, load_skill, parse_frontmatter, skills_for, _SKILLS_DIR,
)


# ---- 載入對應表(逐 kind;plan T7 對應表) ----

def test_skills_for_mapping_per_kind():
    P = "consultant-principles"
    assert skills_for("onboarding_occupation", CO.ONBOARD_OCCUPATION) == [P, "duty-task-structure"]
    assert skills_for("task_curation", CO.CURATION_TASKS) == [P, "duty-task-structure"]
    tp = "ocs_content.ocu_units.u1.tasks.t1"
    assert skills_for("opks_deep", f"{tp}.outputs") == [P, "output-writing", "probing"]
    assert skills_for("opks_deep", f"{tp}.indicators") == [P, "behavior-indicator", "probing"]
    assert skills_for("opks_deep", f"{tp}.knowledge") == [P, "ks-distinction", "probing"]
    assert skills_for("opks_deep", f"{tp}.skills") == [P, "ks-distinction", "probing"]
    assert skills_for("opks_deep", "ocs_profile.standard_level") == [P, "level-judgment", "probing"]
    assert skills_for("attitudes_wrapup", "ocs_attitude") == [P, "attitude-writing"]
    # 深聊槽缺口(details.*)→ 預設帶追問術
    assert skills_for("opks_deep", f"{tp}.details.frequency") == [P, "probing"]
    assert skills_for("opks_deep", None) == [P, "probing"]


# ---- 八檔存在、frontmatter 可解析、內文非空 ----

def test_all_eight_skill_files_parse():
    assert len(ALL_SKILLS) == 8
    for name in ALL_SKILLS:
        text = (_SKILLS_DIR / name / "SKILL.md").read_text(encoding="utf-8")
        meta, body = parse_frontmatter(text)
        assert meta["name"] == name
        assert meta["description"]
        assert "一句話判準" in body or "六規則" in body or "追問" in body
        assert body.strip()
        assert load_skill(name) == body


# ---- context 三層:前綴 byte 級穩定(同 doc 兩回合) ----

_DOC = {"ocs_profile": {"ocs_code": "X"},
        "ocs_content": {"ocu_units": [{"_uid": "U1", "ocu_name": "測試", "tasks": [
            {"_tid": "C", "task_codes": [{"code": "T1", "name": "測試案例設計"}],
             "competency_blocks": [{}], "details": {}}]}]},
        "ocs_attitude": {"attitudes": []}}


def test_prefix_stable_across_turns():
    kw = dict(doc=_DOC, ledger_state={})
    m1 = C.build_consultant_messages(recent_turns=[("employee", "hi")],
                                     employee_text="第一回合的話", **kw)
    m2 = C.build_consultant_messages(recent_turns=[("employee", "hi"), ("consultant", "好")],
                                     employee_text="第二回合說了別的", **kw)
    # 前綴 1(system+常駐教材)+前綴 2(參考基準)= 前三則,byte 級相等
    assert [m["content"] for m in m1[:3]] == [m["content"] for m in m2[:3]]
    assert "判準教材:總則" in m1[1]["content"]
    assert "參考基準" in m1[2]["content"] and "X" in m1[2]["content"]


def test_first_turn_keeps_same_prefix():
    m0 = C.build_consultant_messages(doc=_DOC, ledger_state={}, recent_turns=[],
                                     employee_text="")
    m1 = C.build_consultant_messages(doc=_DOC, ledger_state={}, recent_turns=[("employee", "hi")],
                                     employee_text="x")
    assert [m["content"] for m in m0[:3]] == [m["content"] for m in m1[:3]]


def test_gap_skill_injected_in_dynamic_zone():
    # _DOC 有職類+任務有缺口 → phase=opks_deep → 動態區帶追問術教材(probing)
    msgs = C.build_consultant_messages(doc=_DOC, ledger_state={}, recent_turns=[("employee", "hi")],
                                       employee_text="我都用 Python 寫自動化")
    dyn = msgs[3]["content"]
    assert "判準教材(本回合欄位適用)" in dyn
    # 前綴不得混入動態教材(快取分層)
    assert "判準教材(本回合欄位適用)" not in msgs[0]["content"] + msgs[1]["content"] + msgs[2]["content"]
