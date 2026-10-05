"""Offline prompt assembly checks; these do not establish model adherence or JD quality."""

from pathlib import Path

import pytest
from study_prompt import instructions_for

PROMPTS = Path(__file__).resolve().with_name("prompts")


@pytest.mark.parametrize(
    ("arm", "entry_file", "expected"),
    [
        ("raw", "raw.md", "共同專業規則\n\n原話入口\n"),
        ("summary", "summary.md", "共同專業規則\n\n摘要入口\n"),
        ("memory", "memory.md", "共同專業規則\n\n記憶入口\n"),
    ],
)
def test_loads_only_common_and_selected_entry(
    arm: str, entry_file: str, expected: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    # A wrong arm, globbed directory, or read of live prompts/data must fail here.
    files = {
        "common.md": "共同專業規則\n",
        "raw.md": "原話入口\n",
        "summary.md": "摘要入口\n",
        "memory.md": "記憶入口\n",
    }
    reads: list[str] = []

    def read_text(path: Path, *, encoding: str) -> str:
        assert path.parent == PROMPTS
        assert path.name in {"common.md", entry_file}
        assert encoding == "utf-8"
        reads.append(path.name)
        return files[path.name]

    monkeypatch.setattr(Path, "read_text", read_text)

    assert instructions_for(arm) == expected
    assert reads == ["common.md", entry_file]


@pytest.mark.parametrize("arm", ["", "RAW", " summary", "other", "../common"])
def test_rejects_unknown_arm_before_reading_files(
    arm: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    def unexpected_read(path: Path, *, encoding: str) -> str:
        pytest.fail("An unknown arm must not select a file or silently become a control arm")

    monkeypatch.setattr(Path, "read_text", unexpected_read)

    with pytest.raises(ValueError, match="Unsupported study arm"):
        instructions_for(arm)


@pytest.mark.parametrize("empty_file", ["common.md", "summary.md"])
def test_rejects_empty_guidance_instead_of_running_a_weakened_arm(
    empty_file: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    def read_text(path: Path, *, encoding: str) -> str:
        return " \n\t" if path.name == empty_file else "有效指引"

    monkeypatch.setattr(Path, "read_text", read_text)

    with pytest.raises(ValueError, match="Empty study prompt"):
        instructions_for("summary")


def test_missing_guidance_does_not_fall_back_to_production(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def missing_read(path: Path, *, encoding: str) -> str:
        raise FileNotFoundError("missing frozen prompt")

    monkeypatch.setattr(Path, "read_text", missing_read)

    with pytest.raises(FileNotFoundError, match="missing frozen prompt"):
        instructions_for("raw")


@pytest.mark.parametrize(
    ("arm", "entry_file"),
    [("raw", "raw.md"), ("summary", "summary.md"), ("memory", "memory.md")],
)
def test_shipped_assets_reach_instructions_unchanged_from_another_working_directory(
    arm: str, entry_file: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    common = (PROMPTS / "common.md").read_text(encoding="utf-8").strip()
    entry = (PROMPTS / entry_file).read_text(encoding="utf-8").strip()
    assert common and entry
    monkeypatch.chdir(PROMPTS.parent)

    # This checks asset selection and transport, not whether a model obeys the prose.
    assert instructions_for(arm) == common + "\n\n" + entry + "\n"
