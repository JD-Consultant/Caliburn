"""A zero net text diff never hides a new fixed source revision."""

from dataclasses import replace
from uuid import uuid4

from caliburn.features.job_description.models import ProfileField
from caliburn.features.job_description.sources import (
    JdSourceReference,
    JdSourceTarget,
    MemorySource,
    MemorySourceLayer,
    SourceTargetKind,
)
from caliburn.features.work_memory.models import MemoryContent
from caliburn.features.work_memory.revisions import MemoryLayer, MemoryObjectRevision
from caliburn.transport.jd_source_markdown import project_jd_source_changes
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
