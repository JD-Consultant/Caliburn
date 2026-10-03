"""A zero net text diff never hides a new fixed source revision."""

from dataclasses import replace
from uuid import uuid4

import pytest

from caliburn.features.job_description.models import ProfileField
from caliburn.features.job_description.sources import (
    InterviewSource,
    JdSourceReference,
    JdSourceTarget,
    MemorySource,
    MemorySourceLayer,
    SourceTargetKind,
)
from caliburn.features.work_memory.models import MemoryContent
from caliburn.features.work_memory.revisions import MemoryLayer, MemoryObjectRevision
from caliburn.transport import jd_source_markdown
from caliburn.transport.jd_source_markdown import project_jd_source_changes
from caliburn.workflows.jd_evidence import JdEvidenceChanges
from caliburn.workflows.jd_source_queries import JdSourceChanges, MemorySourceChange


def test_equal_text_new_revision_remains_visible_without_claiming_alignment() -> None:
    original = MemoryObjectRevision(
        uuid4(),
        uuid4(),
        uuid4(),
        MemoryLayer.WORK_SITUATION,
        MemoryContent("盤點", "庫存核對", "每月核對庫存。"),
    )
    reference = JdSourceReference(
        uuid4(),
        JdSourceTarget(SourceTargetKind.PROFILE_FIELD, field=ProfileField.PURPOSE),
        MemorySource(
            MemorySourceLayer.WORK_SITUATION,
            uuid4(),
            original.object_id,
            original.revision_id,
        ),
    )
    result = JdSourceChanges(
        reference,
        (MemorySourceChange(original, replace(original, revision_id=uuid4()), (), ()),),
    )
    rendered = project_jd_source_changes(result)
    assert "來源修訂已更新" in rendered
    assert "沒有淨文字差異" in rendered
    assert "未解除待核對" in rendered
    assert "相關來源鏈亦無變化" not in rendered
    unchanged = replace(result, changes=(MemorySourceChange(original, original, (), ()),))
    assert "來源修訂已更新" not in project_jd_source_changes(unchanged)


def test_jd_diff_preserves_embedded_fences_and_field_boundaries() -> None:
    reference = JdSourceReference(
        uuid4(),
        JdSourceTarget(SourceTargetKind.TASK, uuid4()),
        InterviewSource(uuid4()),
        needs_review=True,
        reviewed_revision_id=uuid4(),
    )
    change = JdEvidenceChanges(
        reference,
        ("任務原名", "第一行\n````\n<script>原文</script>"),
        ("任務新名", "替換內容"),
        None,
    )
    rendered = jd_source_markdown.project_jd_target_changes(change)
    assert "-任務原名" in rendered and "+任務新名" in rendered
    assert "`````diff\n" in rendered
    assert "-````" in rendered and "-<script>原文</script>" in rendered
    assert rendered.endswith("`````")
    assert "未解除待核對" in rendered


@pytest.mark.parametrize("needs_review", [False, True])
def test_equal_jd_text_distinguishes_unchanged_from_edited_and_reverted(needs_review) -> None:
    reference = JdSourceReference(
        uuid4(),
        JdSourceTarget(SourceTargetKind.PROFILE_FIELD, field=ProfileField.PURPOSE),
        InterviewSource(uuid4()),
        needs_review=needs_review,
        reviewed_revision_id=uuid4(),
    )
    rendered = jd_source_markdown.project_jd_target_changes(
        JdEvidenceChanges(reference, (None,), (None,), None)
    )
    assert "沒有淨差異" in rendered
    assert ("曾修改" in rendered) is needs_review
    assert "diff\n" not in rendered
