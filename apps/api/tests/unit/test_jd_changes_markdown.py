"""Historical change presentation preserves net content and source-only effects."""

from dataclasses import replace
from uuid import UUID

import pytest

from caliburn.features.job_description.change_comparison import (
    JdChangeSnapshot,
    compare_jd_snapshots,
)
from caliburn.features.job_description.models import JdProfile, ProfileField
from caliburn.features.job_description.sources import (
    InterviewSource,
    JdSourceReference,
    JdSourceTarget,
    MemorySource,
    MemorySourceLayer,
    SourceTargetKind,
)
from caliburn.features.job_description.work_models import JdWorkRevision
from caliburn.transport.jd_changes_markdown import (
    project_manual_jd_changes,
    project_manual_source,
    project_turn_jd_changes,
)
from caliburn.workflows.job_description.reads import JdSourceReading
from caliburn.workflows.job_description.source_queries import MemorySourceVersion


def snapshot(*references: JdSourceReference) -> JdChangeSnapshot:
    return JdChangeSnapshot(
        JdProfile(), JdWorkRevision(UUID(int=1), (), (), (), (), (), ()), references
    )


def test_source_revision_and_review_changes_count_without_exposing_raw_source_data() -> None:
    target = JdSourceTarget(SourceTargetKind.PROFILE_FIELD, field=ProfileField.PURPOSE)
    memory = JdSourceReference(
        UUID(int=2),
        target,
        MemorySource(MemorySourceLayer.WORK_UNDERSTANDING, UUID(int=3), UUID(int=4), UUID(int=5)),
    )
    removed = JdSourceReference(UUID(int=6), target, InterviewSource(UUID(int=7)))
    updated = replace(
        memory,
        source=MemorySource(
            MemorySourceLayer.WORK_UNDERSTANDING, UUID(int=8), UUID(int=4), UUID(int=9)
        ),
        reviewed_revision_id=UUID(int=10),
    )
    markdown = project_turn_jd_changes(snapshot(memory, removed), snapshot(updated))
    assert "正文淨差異：無" in markdown
    assert "新增 0 筆、移除 1 筆、調整 1 筆" in markdown
    assert str(memory.citation_id) not in markdown
    assert str(updated.source.revision_id) not in markdown


def test_diff_keeps_embedded_fences_as_literal_content() -> None:
    before = snapshot()
    after = replace(before, profile=JdProfile(purpose="````\n<script>不執行</script>\n````"))
    markdown = project_turn_jd_changes(before, after)
    assert "`````diff\n\n" in markdown
    assert "+````\n+<script>不執行</script>\n+````" in markdown
    assert "\n\n`````\n" in markdown


def test_manual_reference_endpoints_show_sequences_review_and_deleted_locators() -> None:
    before = snapshot(
        JdSourceReference(
            UUID(int=6),
            JdSourceTarget(SourceTargetKind.PROFILE_FIELD, field=ProfileField.PURPOSE),
            InterviewSource(UUID(int=7)),
            reviewed_revision_id=UUID(int=1),
        )
    )
    updated = replace(
        before.sources[0],
        source=InterviewSource(UUID(int=8)),
        needs_review=True,
        reviewed_revision_id=UUID(int=9),
    )
    added = replace(
        updated,
        citation_id=UUID(int=10),
        target=JdSourceTarget(SourceTargetKind.PROFILE_FIELD, field=ProfileField.JOB_TITLE),
    )
    after = replace(before, sources=(updated, added))
    labels = {before.sources[0].source: "訪談序號 2", updated.source: "訪談序號 4"}
    markdown = project_manual_jd_changes(
        compare_jd_snapshots(before, after),
        format_ref=lambda ref: "citation_1" if ref.endswith(UUID(int=6).hex) else "citation_2",
        format_source=lambda ref: labels[ref.source],
    )
    assert "改前：target=profile.purpose；訪談序號 2；JD 核對狀態=已核對" in markdown
    assert "改後：target=profile.purpose；訪談序號 4；JD 核對狀態=待核對" in markdown
    assert "固定來源身分或依據版本已變更" in markdown and "JD 核對基底已變更" in markdown
    assert "citation_2：來源引用新增" in markdown and "profile.job_title" in markdown
    removed = project_manual_jd_changes(
        compare_jd_snapshots(after, snapshot()),
        format_ref=lambda _: "citation_1",
        format_source=lambda ref: labels[ref.source],
    )
    assert "移除（歷史定位，不可編輯）" in removed and "改後：無" in removed
    assert all(
        str(identity) not in markdown
        for identity in (UUID(int=1), UUID(int=6), UUID(int=7), UUID(int=8), UUID(int=9))
    )


def test_manual_memory_endpoints_keep_historical_titles_and_coverage_without_raw_ids() -> None:
    target = JdSourceTarget(SourceTargetKind.PROFILE_FIELD, field=ProfileField.PURPOSE)
    before = snapshot(
        JdSourceReference(
            UUID(int=2),
            target,
            MemorySource(
                MemorySourceLayer.WORK_UNDERSTANDING, UUID(int=3), UUID(int=4), UUID(int=5)
            ),
        )
    )
    after = replace(
        before,
        sources=(
            replace(
                before.sources[0],
                source=MemorySource(
                    MemorySourceLayer.WORK_UNDERSTANDING, UUID(int=6), UUID(int=4), UUID(int=7)
                ),
            ),
        ),
    )
    readings = {
        before.sources[0]: JdSourceReading(
            before.sources[0],
            historical_title="原月盤點理解",
            source_version=MemorySourceVersion(UUID(int=3), UUID(int=5), 2),
        ),
        after.sources[0]: JdSourceReading(
            after.sources[0],
            historical_title="修訂盤點理解",
            source_version=MemorySourceVersion(UUID(int=6), UUID(int=7), 6),
        ),
    }
    markdown = project_manual_jd_changes(
        compare_jd_snapshots(before, after),
        format_ref=lambda _: "citation_1",
        format_source=lambda ref: project_manual_source(readings[ref]),
    )
    assert (
        "改前：target=profile.purpose；Memory work_understanding：原月盤點理解；涵蓋訪談至 2"
        in markdown
    )
    assert (
        "改後：target=profile.purpose；Memory work_understanding：修訂盤點理解；涵蓋訪談至 6"
        in markdown
    )
    assert "固定來源身分或依據版本已變更" in markdown
    assert all(str(UUID(int=identity)) not in markdown for identity in range(2, 8))


@pytest.mark.parametrize(
    ("historical_title", "target_title", "expected"),
    [(None, "月末盤點理解", "月末盤點理解"), ("原月盤點理解", "新版名", "原月盤點理解")],
)
def test_manual_source_uses_original_title_from_owner_metadata(
    historical_title, target_title, expected
) -> None:
    reference = JdSourceReference(
        UUID(int=2),
        JdSourceTarget(SourceTargetKind.PROFILE_FIELD, field=ProfileField.PURPOSE),
        MemorySource(MemorySourceLayer.WORK_UNDERSTANDING, UUID(int=3), UUID(int=4), UUID(int=5)),
    )
    reading = JdSourceReading(
        reference,
        historical_title=historical_title,
        target_title=target_title,
        source_version=MemorySourceVersion(UUID(int=3), UUID(int=5), 2),
    )
    assert project_manual_source(reading) == f"Memory work_understanding：{expected}；涵蓋訪談至 2"


def test_manual_memory_source_without_any_readable_title_is_not_rendered_as_none() -> None:
    reference = JdSourceReference(
        UUID(int=2),
        JdSourceTarget(SourceTargetKind.PROFILE_FIELD, field=ProfileField.PURPOSE),
        MemorySource(MemorySourceLayer.WORK_UNDERSTANDING, UUID(int=3), UUID(int=4), UUID(int=5)),
    )
    with pytest.raises(ValueError, match="title"):
        project_manual_source(
            JdSourceReading(
                reference, source_version=MemorySourceVersion(UUID(int=3), UUID(int=5), 2)
            )
        )
