"""0031 引擎盲區回歸:0029 後參考集合住 profile——引擎必須 profile∪doc 一起看。
釘死 session 6f807f1e 事故:profile 有碼+文件空 → 不得再停在 onboarding。"""
import asyncio

from app.core.knowledge_dto import CitableItem, CompetencyPool
from app.interview import consultant as C
from app.interview import ledger as L
from app.interview.scribe import build_pool_inputs
from app.interview.service import _ref_codes_ordered

EMPTY_DOC = {"ocs_profile": {}, "ocs_content": {"ocu_units": []},
             "ocs_attitude": {"attitudes": []}}
REF = frozenset({"INM3514-001v4"})


def test_next_gap_moves_past_onboarding_with_profile_codes():
    assert L.next_gap(EMPTY_DOC, {}, {}) == L.ONBOARD_OCCUPATION      # 舊行為保留
    assert L.next_gap(EMPTY_DOC, {}, {}, None, REF) == L.CURATION_TASKS   # 事故修復


def test_derive_phase_with_ref_codes():
    assert L.derive_phase(EMPTY_DOC, {}) == "onboarding_occupation"
    assert L.derive_phase(EMPTY_DOC, {}, REF) == "task_curation"


def test_ref_codes_ordered_doc_first_dedup():
    doc = {"ocs_profile": {"ocs_code": "A1"},
           "version_info": {"versions": [{"ocs_code": "B2"}]}}
    assert _ref_codes_ordered(doc, ["B2", "C3"]) == ["A1", "B2", "C3"]
    assert _ref_codes_ordered(EMPTY_DOC, ["C3"]) == ["C3"]


def test_reference_block_shows_reference_set():
    block = C._reference_block(EMPTY_DOC, None, REF)
    assert "INM3514-001v4" in block and "參考集合" in block
    empty = C._reference_block(EMPTY_DOC, None)
    assert "空" in empty


def test_consultant_ctx_occ_dismissed_line():
    msgs = C.build_consultant_messages(
        doc=EMPTY_DOC, ledger_state={}, recent_turns=[("employee", "hi")],
        employee_text="我做網站", occ_dismissed=True)
    joined = "\n".join(m["content"] for m in msgs)
    assert "關掉了職類建議卡" in joined and "不要複讀" in joined
    # 已有參考集合 → 話術不再出現(卡片已無意義)
    msgs2 = C.build_consultant_messages(
        doc=EMPTY_DOC, ledger_state={}, recent_turns=[("employee", "hi")],
        employee_text="我做網站", occ_dismissed=True, ref_codes=REF)
    assert "關掉了職類建議卡" not in "\n".join(m["content"] for m in msgs2)


def test_build_pool_inputs_unions_extra_codes():
    class _K:
        async def competencies(self, code):
            return CompetencyPool(
                ocs_code=code,
                knowledge=[CitableItem(id=f"{code}-k", type="K",
                                       code=f"K-{code}", name=f"知識{code}")],
                skills=[], outputs=[], attitudes=[])

    pools, items = asyncio.run(build_pool_inputs(_K(), EMPTY_DOC, ("X1", "Y2")))
    assert set(pools["knowledge"]) == {"K-X1", "K-Y2"}
    assert items["K-X1"] == "知識X1"
