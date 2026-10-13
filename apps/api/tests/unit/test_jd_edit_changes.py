"""刪任務移除其連結及引用，保留共享能力和其他任務的原件。"""

from uuid import uuid4

from caliburn.features.job_description.capabilities import (
    Capability,
    CapabilityKind,
    TaskCapabilityLink,
)
from caliburn.features.job_description.edit_changes import apply_content_changes
from caliburn.features.job_description.models import JdProfile
from caliburn.features.job_description.sources import (
    InterviewSource,
    JdSourceReference,
    JdSourceTarget,
    SourceTargetKind,
)
from caliburn.features.job_description.tasks import DeleteTask, EditJdTasks, WorkTask
from caliburn.features.job_description.work_models import JdWorkRevision


def test_deleting_task_drops_only_its_links_and_evidence() -> None:
    removed = WorkTask(uuid4(), uuid4(), None, "移除任務", None, ())
    retained = WorkTask(uuid4(), uuid4(), None, "保留任務", None, ())
    capability = Capability(uuid4(), uuid4(), CapabilityKind.SKILL, "共享技能", None)
    revision_id = uuid4()
    links = tuple(
        TaskCapabilityLink(task.task_id, capability.capability_id) for task in (removed, retained)
    )
    work = JdWorkRevision(revision_id, (), (removed, retained), (capability,), links, (), ())
    references = tuple(
        JdSourceReference(
            uuid4(),
            JdSourceTarget(SourceTargetKind.TASK, task.task_id),
            InterviewSource(uuid4()),
            reviewed_revision_id=revision_id,
        )
        for task in (removed, retained)
    )

    changed = apply_content_changes(
        JdProfile(),
        work,
        references,
        EditJdTasks(uuid4(), revision_id, DeleteTask(removed.task_id)),
    )

    assert changed.work.tasks == (retained,)
    assert changed.work.capabilities == (capability,)
    assert changed.work.task_links == (links[1],)
    assert changed.references == (references[1],)
    assert changed.changed_content is None
    assert work.tasks == (removed, retained)
    assert work.task_links == links
