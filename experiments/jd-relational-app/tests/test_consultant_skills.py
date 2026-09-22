"""The on-demand consultant methods must be reachable, bounded, and read-only.

Counter-examples are fixed in docs/specs/2026-09-14-jd-consultant-guidance-and-skills-slice.md.
No provider, no document, no connection.
"""

from pathlib import Path

import pytest

from caliburn_memory.skills import SkillAssets, analysis_files, analysis_skills
from jd_relational.consultant_app import analysis_skills_middleware

SKILLS = (
    "work-scope-interview",
    "compare-work-patterns",
    "outcomes-and-expertise",
    "write-customized-jd",
)
BODIES = ("## 訪談方法", "## 比較方法", "## 深入方法", "# 客製化職務說明書撰寫與修訂")


@pytest.fixture(scope="module")
def assets():
    return SkillAssets()


def _names(listed):
    return {entry["path"].strip("/").rsplit("/", 1)[-1] for entry in listed.entries}


def test_the_three_analysis_methods_and_on_demand_jd_method_are_mounted(assets):
    names = _names(assets.ls("/"))
    assert names == set(SKILLS), names


def test_each_method_reads_through_the_same_route_the_model_uses(assets):
    files = analysis_files(assets)
    for name in SKILLS:
        result = files.read(f"/skills/{name}/SKILL.md", limit=1000)
        assert result.error is None, result.error
        assert f"name: {name}" in result.file_data["content"], name


def test_the_methods_the_model_is_offered_are_names_and_purposes_only():
    middleware = analysis_skills_middleware()
    loaded = middleware.before_agent({}, None, None)
    metadata = loaded["skills_metadata"]
    assert {skill["name"] for skill in metadata} == set(SKILLS)
    listing = middleware._format_skills_list(metadata)
    for name in SKILLS:
        assert name in listing, name
    for body in BODIES:
        assert body not in listing, body


def test_the_prompt_tells_the_model_to_load_only_what_it_needs():
    template = analysis_skills_middleware().system_prompt_template
    assert "按需工作方法" in template
    assert "按需分析方法" not in template
    assert "不要每回合載入全部" in template
    assert "/skills/" in analysis_skills_middleware()._format_skills_locations()
    for body in BODIES:
        assert body not in template, body


def test_assets_grant_no_write_execute_or_upload(assets):
    for absent in ("write_file", "edit_file", "delete_file", "execute", "run_command"):
        assert not hasattr(assets, absent), absent
    # upload_files exists on the backend protocol itself; what matters is that
    # this asset store never implements it, so a call cannot put a file here.
    assert "upload_files" not in vars(type(assets))
    with pytest.raises(NotImplementedError):
        assets.upload_files(["/work-scope-interview/SKILL.md"])


@pytest.mark.parametrize("path", ["/etc/passwd", "C:/Windows/win.ini", "/skills/../../secret",
                                  "S:/caliburn/AGENTS.md"])
def test_a_path_outside_the_assets_is_a_correctable_input_error(assets, path):
    result = assets.read(path)
    assert result.error is not None
    assert result.file_data is None


def test_the_adopted_assets_live_in_the_package_not_the_app():
    import caliburn_memory
    root = Path(caliburn_memory.__file__).resolve().parent / "skills"
    assert {item.name for item in root.iterdir() if item.is_dir()} == set(SKILLS)
    for name in SKILLS:
        assert (root / name / "SKILL.md").is_file(), name


def test_jd_method_is_on_demand_and_carries_the_current_writing_contract(assets):
    files = analysis_files(assets)
    result = files.read("/skills/write-customized-jd/SKILL.md", limit=1000)
    assert result.error is None, result.error
    body = result.file_data["content"]
    assert "日常訪談" in body and "不必載入" in body
    assert "工作理解" in body and "相關案例" in body and "原始訪談" in body
    assert "最新已保存" in body and "尚未" in body and "Memory" in body
    writing_path = "/skills/write-customized-jd/references/writing-and-correction.md"
    complete_path = "/skills/write-customized-jd/references/complete-work-guide.md"
    assert writing_path in body and complete_path in body

    writing = files.read(writing_path, limit=1000)
    complete = files.read(complete_path, limit=1000)
    assert writing.error is None, writing.error
    assert complete.error is None, complete.error
    writing_body = writing.file_data["content"]
    complete_body = complete.file_data["content"]
    assert "職務目的" in writing_body and "職責" in writing_body and "任務" in writing_body
    assert "成果／產出" in writing_body and "工作執行要求" in writing_body
    assert "知識" in writing_body and "技能" in writing_body
    assert "KPI" in writing_body and "資格" in writing_body
    assert "工作→JD" in complete_body and "JD→工作" in complete_body
    assert "低頻" in complete_body and "案例" in complete_body


def test_every_named_skill_path_in_skill_bodies_resolves(assets):
    import re

    files = analysis_files(assets)
    for name in SKILLS:
        body = files.read(f"/skills/{name}/SKILL.md", limit=1000).file_data["content"]
        for path in re.findall(r"/skills/[a-z0-9-]+/SKILL\.md", body):
            assert files.read(path, limit=1).error is None, f"{name} names missing {path}"
