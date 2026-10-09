"""Historical change presentation preserves net content and source-only effects."""

from dataclasses import replace
from uuid import UUID

from caliburn.features.job_description.change_queries import JdChangeSnapshot
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
from caliburn.transport.turn_jd_markdown import project_turn_jd_changes


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
