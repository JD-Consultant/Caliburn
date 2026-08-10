"""OPKS prompt 只承載模型必須知道、程式無法代判的規則。"""

from app.opks.llm import OPKS_INSTRUCTIONS


def test_prompt_is_behavior_first_grounded_and_allows_abstention():
    for phrase in (
        "只根據本次 packet 的員工依據",
        "完成這項工作不可缺少",
        "工作產出",
        "行為指標",
        "知識",
        "技能",
        "uncertain",
        "不得自行補數字",
        "不得自行補『依公司規定』",
        "優先 reuse_existing",
        "待決提案不是已成立事實",
        "已拒絕",
    ):
        assert phrase in OPKS_INSTRUCTIONS


def test_prompt_exposes_every_wire_coupling_rule():
    for phrase in (
        "add_new：target_ordinal=0",
        "reuse_existing：只限 knowledge／skill",
        "revise_existing：target_ordinal>0",
        "remove_existing：target_ordinal>0",
        "uncertain：target_ordinal=0",
    ):
        assert phrase in OPKS_INSTRUCTIONS


def test_prompt_does_not_expand_the_first_slice_scope():
    lowered = OPKS_INSTRUCTIONS.lower()
    for forbidden in (
        "attitude",
        "taxonomy",
        "proficiency",
        "external code",
        "匯出編碼",
        "職能基準代碼",
    ):
        assert forbidden not in lowered

