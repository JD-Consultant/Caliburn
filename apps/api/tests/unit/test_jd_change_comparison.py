"""人工 net 必須涵蓋結構及引用，且忽略只供保存的修訂號。"""

from dataclasses import replace
from uuid import UUID

from caliburn.features.job_description.areas import ResponsibilityArea
from caliburn.features.job_description.capabilities import (
    Capability,
    CapabilityKind,
    TaskCapabilityLink,
)
from caliburn.features.job_description.change_comparison import (
    JdChangeSnapshot,
    compare_jd_snapshots,
)
from caliburn.features.job_description.models import JdProfile, ProfileField
from caliburn.features.job_description.sources import (
    InterviewSource,
    JdSourceReference,
    JdSourceTarget,
    SourceTargetKind,
)
from caliburn.features.job_description.tasks import DetailKind, TaskDetail, WorkTask
from caliburn.features.job_description.work_models import JdWorkRevision


def snapshot() -> JdChangeSnapshot:
    return JdChangeSnapshot(
        JdProfile(purpose="原目的"),
        JdWorkRevision(
            UUID(int=1),
            (ResponsibilityArea(UUID(int=2), UUID(int=3), "原職責", None),),
            (
                WorkTask(
                    UUID(int=4),
                    UUID(int=5),
                    UUID(int=2),
                    "原任務",
                    None,
                    (TaskDetail(UUID(int=30), DetailKind.OUTCOME, "產出"),),
                ),
            ),
            (Capability(UUID(int=6), UUID(int=7), CapabilityKind.SKILL, "技能", None),),
            (TaskCapabilityLink(UUID(int=4), UUID(int=6)),),
            (),
            (),
        ),
        (
            JdSourceReference(
                UUID(int=8),
                JdSourceTarget(SourceTargetKind.TASK, UUID(int=4)),
                InterviewSource(UUID(int=9)),
                reviewed_revision_id=UUID(int=1),
            ),
        ),
    )


def test_net_compares_structure_links_and_reference_review_metadata() -> None:
    before = snapshot()
    after = replace(
        before,
        profile=JdProfile(purpose="新目的"),
        work=replace(
            before.work, tasks=(replace(before.work.tasks[0], area_id=None),), task_links=()
        ),
        sources=(replace(before.sources[0], needs_review=True, reviewed_revision_id=UUID(int=10)),),
    )
    net = compare_jd_snapshots(before, after)
    assert net.profile_fields == (ProfileField.PURPOSE,)
    assert set(net.item_refs) == {
        f"area_{UUID(int=2).hex}",
        f"task_{UUID(int=4).hex}",
        f"skill_{UUID(int=6).hex}",
    }
    assert net.citation_ids == (UUID(int=8),)
    # 正文和旗標相同，也不能漏掉核對基底或 target 的改動。
    for changed in (
        replace(before.sources[0], reviewed_revision_id=UUID(int=11)),
        replace(
            before.sources[0],
            target=JdSourceTarget(SourceTargetKind.PROFILE_FIELD, field=ProfileField.PURPOSE),
        ),
    ):
        assert compare_jd_snapshots(before, replace(before, sources=(changed,))).citation_ids == (
            UUID(int=8),
        )


def test_net_ignores_intermediate_operations_and_storage_only_revisions() -> None:
    before = snapshot()
    after = replace(
        before,
        work=replace(
            before.work,
            revision_id=UUID(int=20),
            areas=(replace(before.work.areas[0], content_revision_id=UUID(int=21)),),
            tasks=(replace(before.work.tasks[0], content_revision_id=UUID(int=22)),),
            capabilities=(replace(before.work.capabilities[0], content_revision_id=UUID(int=23)),),
        ),
    )
    net = compare_jd_snapshots(before, after)
    assert (net.profile_fields, net.item_refs, net.citation_ids) == ((), (), ())
