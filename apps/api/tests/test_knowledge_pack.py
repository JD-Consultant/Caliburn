"""knowledge_pack 組裝器單測(純函式,無 DB)。spec §5:池 key 表、append 序、聯集、A5。"""
from app.core.domain import knowledge_pack as kp
from app.core.knowledge_dto import (
    CitableItem,
    CodeName,
    CompetencyPool,
    OccupationDetail,
    OccupationTasks,
    OcsName,
    SourceRef,
    TaskRef,
    UnitTasks,
)


def _detail(code, occ_name, attitudes=(), cats=(), prereqs=()):
    return OccupationDetail(
        ocs_code=code, ocs_name=OcsName(occupation_name=occ_name),
        job_categories=[CodeName(code=c, name=n) for c, n in cats],
        attitudes=[CodeName(code=c, name=n) for c, n in attitudes],
        prerequisites=list(prereqs), job_description=f"{occ_name}描述", ocs_level=4)


def _tasks(code, occ_name, units):  # units = [(ocu_code, ocu_name, [(t_code, t_name)])]
    return OccupationTasks(ocs_code=code, ocs_name=occ_name, units=[
        UnitTasks(ocu_code=uc, ocu_name=un,
                  tasks=[TaskRef(task_code=tc, task_name=tn) for tc, tn in ts])
        for uc, un, ts in units])


def _pool(code, occ_name, knowledge=(), skills=(), outputs=(), indicators=()):
    def items(spec, textual=False):
        out = []
        for item_code, val, srcs in spec:  # srcs = [(task_code, level)]
            out.append(CitableItem(
                code=item_code, name=None if textual else val, text=val if textual else None,
                ocs_code=code, ocs_name=occ_name,
                sources=[SourceRef(task_code=tc, competency_level=lv) for tc, lv in srcs]))
        return out
    return CompetencyPool(ocs_code=code,
        knowledge=items(knowledge), skills=items(skills),
        outputs=items(outputs), indicators=items(indicators, textual=True))


def _two_code_pack():
    """A=OC1(順序1)、B=OC2:同名職責「維護」、同名任務「保養」、同名 K「統計」;
    B 另有 A01 撞碼態度(名字不同,A5)。"""
    details = {
        "OC1": _detail("OC1", "甲職業", attitudes=[("A01", "主動積極")],
                       cats=[("J", "資訊服務")], prereqs=["大學以上"]),
        "OC2": _detail("OC2", "乙職業", attitudes=[("A01", "誠信正直")],
                       cats=[("J", "資訊服務")], prereqs=["大學以上"]),
    }
    tasks = {
        "OC1": _tasks("OC1", "甲職業", [("T1", "維護", [("T1.1", "保養"), ("T1.2", "巡檢")])]),
        "OC2": _tasks("OC2", "乙職業", [("T2", "維護", [("T2.3", "保養")])]),
    }
    pools = {
        "OC1": _pool("OC1", "甲職業",
                     knowledge=[("K03", "統計", [("T1.1", 3)]), ("K05", "電學", [("T1.2", 3)])],
                     outputs=[("O1", "紀錄表", [("T1.1", None)])],
                     indicators=[("P1", "完成保養並記錄", [("T1.1", None)])]),
        "OC2": _pool("OC2", "乙職業", knowledge=[("K07", "統計", [("T2.3", 4)])]),
    }
    return kp.build_pack(["OC1", "OC2"], details, tasks, pools)


def test_pools_merge_by_key_and_accumulate_srcs():
    p = _two_code_pack()
    stats = p["pools"]["knowledge"]["統計"]
    assert [s["ocs_code"] for s in stats["srcs"]] == ["OC1", "OC2"]   # append 序:A 先
    assert stats["srcs"][0]["code"] == "K03" and stats["srcs"][1]["code"] == "K07"
    assert list(p["pools"]["knowledge"]) == ["統計", "電學"]           # 合併列停在首現位置


def test_attitudes_dedup_by_name_not_code():  # A5:A01 撞碼不得合併
    p = _two_code_pack()
    assert set(p["pools"]["attitudes"]) == {"主動積極", "誠信正直"}


def test_categories_dedup_by_code_and_notes_by_text():
    p = _two_code_pack()
    assert list(p["pools"]["job_categories"]) == ["J"]
    assert [s["ocs_code"] for s in p["pools"]["job_categories"]["J"]["srcs"]] == ["OC1", "OC2"]
    assert [s["ocs_code"] for s in p["pools"]["prerequisites"]["大學以上"]["srcs"]] == ["OC1", "OC2"]


def test_notes_srcs_carry_positional_n_codes():
    """spec 2026-07-04 §3:notes 來源位置碼 n{i}(1-based、不補零、per-source 清單順序)。"""
    details = {
        "OC1": _detail("OC1", "甲職業", prereqs=["大學以上", "二年經驗"]),
        "OC2": _detail("OC2", "乙職業", prereqs=["大學以上"]),
    }
    p = kp.build_pack(["OC1", "OC2"], details, {}, {})
    srcs = p["pools"]["prerequisites"]["大學以上"]["srcs"]
    assert [(s["ocs_code"], s["code"]) for s in srcs] == [("OC1", "n1"), ("OC2", "n1")]
    srcs2 = p["pools"]["prerequisites"]["二年經驗"]["srcs"]
    assert [(s["ocs_code"], s["code"]) for s in srcs2] == [("OC1", "n2")]


def test_units_and_tasks_merge_by_name_with_urn_srcs():
    p = _two_code_pack()
    assert [s["ocs_code"] for s in p["pools"]["units"]["維護"]["srcs"]] == ["OC1", "OC2"]
    assert p["pools"]["tasks"]["保養"]["srcs"] == ["ocs:OC1:T:T1.1", "ocs:OC2:T:T2.3"]


def test_source_tasks_carry_refs_and_level():
    p = _two_code_pack()
    t11 = p["source_tasks"]["ocs:OC1:T:T1.1"]
    assert t11["k_refs"] == ["統計"] and t11["o_refs"] == ["紀錄表"]
    assert t11["p_refs"] == ["完成保養並記錄"] and t11["competency_level"] == 3
    assert p["source_tasks"]["ocs:OC2:T:T2.3"]["competency_level"] == 4


def test_occupation_details_keep_selection_order():
    p = _two_code_pack()
    assert [d["ocs_code"] for d in p["occupation_details"]] == ["OC1", "OC2"]


def test_empty_input_gives_empty_shape():
    p = kp.build_pack([], {}, {}, {})
    assert p["occupation_details"] == [] and p["source_tasks"] == {}
    assert set(p["pools"]) == {"units", "tasks", "knowledge", "skills", "outputs",
        "indicators", "attitudes", "job_categories", "occupations", "industries",
        "prerequisites", "supplements"}
    assert all(v == {} for v in p["pools"].values())
