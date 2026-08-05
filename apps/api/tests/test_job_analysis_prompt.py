"""T3:Static Instructions 的預算與**判準不得誤傷**。

瘦身的風險不是刪太少,是刪到產品本身。所以這裡同時守兩件事:總量有上限,
而六段顧問判準逐段位元組數必須一字不差。
"""

from __future__ import annotations

import re

import pytest

from app.job_analysis.application.verifier import ViolationCode
from app.job_analysis.llm import TASK_ANALYSIS_INSTRUCTIONS


#: 5,934 實測 ＋ 少量修辭餘裕。再往下只能砍判準,那是砍產品。
#: 5,200 → 6,000:ADR 0054 決定 16 要求「K/S 不得問成認領題」只住主顧問 prompt 一處,
#: 那段判準(844 bytes)沒有別的家可去。owner 於 2026-08-05 核准這次放寬。
INSTRUCTIONS_BYTES_BUDGET = 6000

#: 六段顧問判準的逐段位元組數。**這些數字改變就是判準被動到了。**
#: 只有在確實要改判準文字時才更新,而且要在同一個 commit 說明改了什麼、為什麼。
JUDGEMENT_SECTIONS = {
    "顧問訪談方式": 963,
    "Task 成立條件(四項同時滿足)": 658,
    "Enabler 硬規則": 370,
    "Split 與 Merge(任一條成立就檢查,不是自動執行)": 834,
    "不成立的訊號怎麼放": 833,
    "OPKS 缺口的追問": 844,
}


def sections() -> dict[str, int]:
    parts = re.split(r"^(## .*)$", TASK_ANALYSIS_INSTRUCTIONS, flags=re.M)
    return {
        parts[index].removeprefix("## ").strip(): len(
            (parts[index] + parts[index + 1]).encode("utf-8")
        )
        for index in range(1, len(parts), 2)
    }


def test_instructions_stay_inside_the_budget():
    assert len(TASK_ANALYSIS_INSTRUCTIONS.encode("utf-8")) <= INSTRUCTIONS_BYTES_BUDGET


@pytest.mark.parametrize(("heading", "size"), sorted(JUDGEMENT_SECTIONS.items()))
def test_the_consultant_judgement_is_untouched(heading: str, size: int):
    assert sections()[heading] == size


def test_only_the_judgement_and_the_behaviour_sections_remain():
    assert set(sections()) == {*JUDGEMENT_SECTIONS, "行為與禁止事項"}


# ── 已搬到別處的規則不得回流 ───────────────────────────────────────────────


@pytest.mark.parametrize(
    ("phrase", "enforced_by"),
    [
        pytest.param(
            "不要包在程式碼區塊裡", "strict structured output", id="json-only"
        ),
        pytest.param("一輪只問一個問題", "next_question 是單一物件", id="one-question"),
        pytest.param(
            "其餘三個必須是 null", "wire 契約已無 payload 插槽", id="payload-slots"
        ),
        pytest.param(
            "`add` 配 no_match", ViolationCode.RELATION_DOES_NOT_MATCH_MAPPING, id="relation-mapping"
        ),
        pytest.param(
            "每一筆訊號都要有 `anchors`", ViolationCode.ANCHOR_MISSING, id="anchors-present"
        ),
        pytest.param(
            "不得**出現在任何 target",
            ViolationCode.TARGET_ORDINAL_RETIRED,
            id="retired-target",
        ),
        pytest.param(
            "必須出現在同一筆訊號的 `anchors` 裡",
            ViolationCode.SUPERSESSION_MISSING_CURRENT_TURN_ANCHOR,
            id="supersession-anchor",
        ),
        pytest.param(
            "只有兩種情況可填",
            ViolationCode.RESOLUTION_MAPPING_INVALID,
            id="resolution-mapping",
        ),
        pytest.param("`limitations`", "欄位已移除", id="limitations"),
    ],
)
def test_rules_guaranteed_elsewhere_are_not_restated(phrase: str, enforced_by):
    """重複的規則不只多付 token,重疊與衝突的訊息還會消耗模型的推理。"""

    assert phrase not in TASK_ANALYSIS_INSTRUCTIONS, f"already enforced by {enforced_by}"


# ── 只有模型能做的判斷必須留著 ─────────────────────────────────────────────


@pytest.mark.parametrize(
    "rule",
    [
        # 違反要付一次完整呼叫才會發現,值得先講。
        "逐字子字串",
        "矛盾未解至少要引兩句",
        # verifier 只驗形式,驗不了「這條依據是不是真的支持這個 child」。
        "只沿用真正支持它的依據",
        # 語意判斷:packet 的待決提案不是現況事實。
        "不是現況事實",
        "不得自動換 ID 或 merge",
        "不要重問或重送同一份提案",
        "不要自行復活它",
        "不要硬填",
        # 短答只有靠 active_question 才可解讀。
        "短答要能接回 `active_question`",
    ],
)
def test_semantic_judgement_survives_the_slimming(rule: str):
    assert rule in TASK_ANALYSIS_INSTRUCTIONS


# ── ADR 0054 決定 16:K/S 的問法只住這裡一處 ────────────────────────────────


@pytest.mark.parametrize(
    ("phrase", "authority"),
    [
        pytest.param(
            "不得問「你需要什麼知識／技能」",
            "ADR 0048 決定 14（Morgeson 的 ability-to 句式膨脹、OPM 明文禁止）",
            id="no-ks-claim-question",
        ),
        pytest.param(
            "你是否具備⋯⋯的能力",
            "ADR 0048 決定 14",
            id="no-ability-phrasing",
        ),
        pytest.param(
            "還是你目前\n  剛好使用的工具或方法",
            "ADR 0048 決定 17 的對比追問",
            id="contrast-follow-up",
        ),
        pytest.param(
            "`settled_issues`",
            "ADR 0054 決定 20:已問過勿重問",
            id="settled-memory",
        ),
    ],
)
def test_the_gap_questioning_rules_are_visible_to_the_model(phrase: str, authority):
    """gap 本身不帶問句(決定 16),所以問法的權威只有這一份 prompt。

    OPKS specialist 只寫「缺什麼」;問句在提問當下由主顧問生成。這讓 0048 決定 14
    只需要維護一處,但也代表這裡刪掉就沒有第二道防線。
    """

    assert phrase in TASK_ANALYSIS_INSTRUCTIONS, f"required by {authority}"
