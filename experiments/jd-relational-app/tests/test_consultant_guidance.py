"""The consultant's method must arrive intact, and name only what exists.

Counter-examples are fixed in docs/specs/2026-09-14-jd-consultant-guidance-and-skills-slice.md.
No provider, no document, no connection.
"""

import ast
import re
import subprocess
from pathlib import Path

import pytest

from caliburn_memory.guidance import MEMORY_ACTION_GUIDANCE
from jd_relational.consultant_guidance import (
    ADVISOR_INSTRUCTIONS, GENERAL_CONDUCT, JD_CAPABILITY, build_consultant_guidance,
)
from jd_relational.memory_context import build_consultant_tools

REPO = Path(__file__).resolve().parents[3]
SOURCE_COMMIT = "033540ce"


def _adopted_constant(path, name):
    """Read a constant out of the adoption source without importing that host."""
    raw = subprocess.run(["git", "show", f"{SOURCE_COMMIT}:{path}"], cwd=REPO,
                         capture_output=True, check=True).stdout.decode("utf-8")
    for node in ast.parse(raw).body:
        if isinstance(node, ast.Assign) and getattr(node.targets[0], "id", None) == name:
            return ast.literal_eval(node.value)
    raise AssertionError(f"{name} is not in {path}")


@pytest.fixture(scope="module")
def verified():
    return _adopted_constant("experiments/analysis-agent/src/analysis_agent/api.py",
                             "ADVISOR_INSTRUCTIONS")


UNADOPTED_TAIL = (
    "需要撰寫或實質修正JD時，按需讀write-customized-jd方法與目前稿，使用已提供的JD工具，依實際保存結果說明。",
    "資料不足繼續訪談，已有足夠理解可先寫支持的部分，不必每輪修改JD。",
)


def test_every_verified_interview_sentence_survives_verbatim(verified):
    # Exactly two sentences are deliberately dropped. Every other sentence of
    # the verified guidance must appear exactly as written, and in order.
    sentences = [part + "。" for part in verified.split("。") if part]
    assert set(UNADOPTED_TAIL) < set(sentences), "the tail moved; recheck the adoption diff"
    interview = [sentence for sentence in sentences
                 if sentence not in UNADOPTED_TAIL and sentence != GENERAL_CONDUCT]
    assert len(interview) == 11
    position = -1
    for sentence in interview:
        found = ADVISOR_INSTRUCTIONS.find(sentence)
        assert found > position, sentence
        position = found


def test_the_unadopted_jd_tail_is_gone_but_its_general_rule_is_kept(verified):
    guidance = build_consultant_guidance()
    assert "write-customized-jd" not in guidance
    assert "按需讀write-customized-jd方法與目前稿" not in guidance
    assert "不製作" not in guidance and "不編輯JD" not in guidance
    assert GENERAL_CONDUCT == "不顯示隱藏推理。"
    assert GENERAL_CONDUCT in verified and GENERAL_CONDUCT in guidance


def test_jd_capability_names_only_registered_tools():
    registered = {tool.name for tool in build_consultant_tools()}
    named = set(re.findall(r"jd_[a-z_]+", JD_CAPABILITY))
    assert named, "the JD paragraph must actually name the tools"
    assert named <= registered, named - registered


def test_jd_capability_covers_the_six_chapters_and_refuses_model_authored_identity():
    for chapter in ("基本資料", "職務目的", "職責與任務", "所需知識", "所需技能",
                    "適用條件與責任邊界"):
        assert chapter in JD_CAPABILITY, chapter
    assert "成果" in JD_CAPABILITY and "要求" in JD_CAPABILITY
    for owned in ("UUID", "外鍵", "位置", "版本", "引用token"):
        assert owned in JD_CAPABILITY, owned


def test_memory_actions_are_verbatim_and_only_mention_registered_tools():
    guidance = build_consultant_guidance()
    assert MEMORY_ACTION_GUIDANCE in guidance
    registered = {tool.name for tool in build_consultant_tools()}
    assert "repair_memory" in registered and "request_memory_consolidation" in registered
    for mentioned in re.findall(r"\b(?:repair_memory|request_memory_consolidation)\b",
                                MEMORY_ACTION_GUIDANCE):
        assert mentioned in registered


def test_only_live_repair_changed_and_background_wording_stays_adopted_verbatim():
    adopted = _adopted_constant(
        "experiments/analysis-agent/src/analysis_agent/live_memory.py", "MEMORY_ACTION_GUIDANCE")
    marker = "### Background consolidation\n"
    assert MEMORY_ACTION_GUIDANCE.split(marker, 1)[1] == adopted.split(marker, 1)[1]
    live = MEMORY_ACTION_GUIDANCE.split(marker, 1)[0]
    for required in ("explicit correction", "current turn's Memory version",
                     "every directly affected current work understanding",
                     "revalidate", "Runtime owns", "Do not partially repair"):
        assert required in live
    for obsolete in ("Repair your own", "add a section", "two existing files"):
        assert obsolete not in live


def test_skill_bodies_are_not_pasted_into_the_prompt():
    # Skills are offered by name and path; loading one is the model's choice.
    guidance = build_consultant_guidance()
    for heading in ("## 訪談方法", "## 比較方法", "## 深入方法"):
        assert heading not in guidance, heading
