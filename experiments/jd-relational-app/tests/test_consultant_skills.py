"""The three analysis methods must be reachable, bounded, and read-only.

Counter-examples are fixed in docs/specs/2026-09-14-jd-consultant-guidance-and-skills-slice.md.
No provider, no document, no connection.
"""

from pathlib import Path

import pytest

from caliburn_memory.skills import SkillAssets, analysis_files, analysis_skills
from jd_relational.consultant_app import analysis_skills_middleware

ANALYSIS = ("work-scope-interview", "compare-work-patterns", "outcomes-and-expertise")
BODIES = ("## 訪談方法", "## 比較方法", "## 深入方法")


@pytest.fixture(scope="module")
def assets():
    return SkillAssets()


def _names(listed):
    return {entry["path"].strip("/").rsplit("/", 1)[-1] for entry in listed.entries}


def test_exactly_the_three_analysis_methods_are_mounted(assets):
    names = _names(assets.ls("/"))
    assert "write-customized-jd" not in names, "the later JD skill is not adopted"
    assert names == set(ANALYSIS), names


def test_each_method_reads_through_the_same_route_the_model_uses(assets):
    files = analysis_files(assets)
    for name in ANALYSIS:
        result = files.read(f"/skills/{name}/SKILL.md", limit=1000)
        assert result.error is None, result.error
        assert f"name: {name}" in result.file_data["content"], name


def test_the_methods_the_model_is_offered_are_names_and_purposes_only():
    middleware = analysis_skills_middleware()
    loaded = middleware.before_agent({}, None, None)
    metadata = loaded["skills_metadata"]
    assert {skill["name"] for skill in metadata} == set(ANALYSIS)
    listing = middleware._format_skills_list(metadata)
    for name in ANALYSIS:
        assert name in listing, name
    for body in BODIES:
        assert body not in listing, body


def test_the_prompt_tells_the_model_to_load_only_what_it_needs():
    template = analysis_skills_middleware().system_prompt_template
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
    assert {item.name for item in root.iterdir() if item.is_dir()} == set(ANALYSIS)
    for name in ANALYSIS:
        assert (root / name / "SKILL.md").is_file(), name
