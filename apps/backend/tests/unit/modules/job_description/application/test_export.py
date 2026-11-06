"""完整匯出只投影 JD，不含員工資料、來源或控制定位。"""

import asyncio
import importlib
import importlib.util
from uuid import UUID

import pytest

from caliburn.modules.job_description.application.job_description_results import (
    JobDescriptionResult,
)
from caliburn.modules.job_description.domain.models.citation import InterviewReference
from caliburn.modules.job_description.domain.models.condition_kind import ConditionKind
from caliburn.modules.job_description.domain.models.job_description import (
    JobDescription,
)


def document() -> JobDescriptionResult:
    root = JobDescription.create(workspace_id=UUID(int=41))
    root.update_details(
        job_title="<script>設備員</script>",
        organization_unit="製造部",
        reports_to="組長",
        purpose="保持設備穩定",
        baseline_competency_level=3,
    )
    duty = root.add_duty(name="設備維護", scope="設備範圍")
    knowledge = root.add_knowledge(name="機械原理", description="設備結構與運作")
    skill = root.add_skill(name="故障診斷", description="定位異常原因")
    root.add_task(
        name="檢查設備",
        description="依序確認\n登錄結果",
        duty_id=duty,
        competency_level=4,
        outcomes=("點檢紀錄",),
        requirements=("交班前完成",),
        knowledge=(knowledge,),
        skills=(skill,),
    )
    root.add_task(name="突發支援", description="跨組協助")
    root.add_collaboration(collaborator_name="維修組", scope="缺陷交接")
    for kind in ConditionKind:
        root.add_condition(kind=kind, text=f"條件-{kind.value}")
    root.add_citation(
        target_kind="duty",
        target_id=duty,
        source=InterviewReference(
            workspace_id=root.workspace_id, message_id=UUID(int=77)
        ),
    )
    return JobDescriptionResult.from_job_description(root, version=7)


def projection(snapshot: JobDescriptionResult) -> str:
    name = "caliburn.modules.job_description.application.export_projection"
    assert importlib.util.find_spec(name) is not None, "尚未提供完整 JD 匯出投影"
    result = importlib.import_module(name).project_jd_export_html(snapshot)
    assert isinstance(result, str)
    return result


def test_complete_export_preserves_content_level_order_and_escapes_html() -> None:
    snapshot = document()
    html = projection(snapshot)
    for text in (
        "&lt;script&gt;設備員&lt;/script&gt;",
        "製造部",
        "組長",
        "保持設備穩定",
        "基準職能級別",
        "3",
        "設備維護",
        "設備範圍",
        "檢查設備",
        "依序確認\n登錄結果",
        "職能級別",
        "4",
        "點檢紀錄",
        "交班前完成",
        "機械原理",
        "設備結構與運作",
        "故障診斷",
        "定位異常原因",
        "未分類任務",
        "突發支援",
        "跨組協助",
        "維修組",
        "缺陷交接",
    ):
        assert text in html
    for kind in ConditionKind:
        assert f"條件-{kind.value}" in html
    assert html.index("設備維護") < html.index("檢查設備") < html.index("突發支援")
    for value in (
        "<script>",
        "citation",
        "message_",
        "read_ref",
        str(snapshot.job_description_id),
        str(UUID(int=77)),
    ):
        assert value not in html


def test_empty_jd_is_exportable_without_inventing_content() -> None:
    root = JobDescription.create(workspace_id=UUID(int=41))
    html = projection(JobDescriptionResult.from_job_description(root, version=1))
    assert "尚無已保存的職務內容" in html


def test_orphan_task_is_not_silently_omitted_from_export() -> None:
    snapshot = document()
    broken = snapshot.model_copy(update={"duties": ()})
    with pytest.raises(ValueError, match="不完整"):
        projection(broken)


def test_export_uses_scoped_snapshot_before_rendering() -> None:
    name = "caliburn.modules.job_description.application.exporting"
    assert importlib.util.find_spec(name) is not None, "尚未提供 scoped PDF 匯出用例"
    module = importlib.import_module(name)
    snapshot = document()

    class Queries:
        def get_job_description(
            self, *, workspace_id: UUID, job_description_id: UUID
        ) -> JobDescriptionResult | None:
            assert (workspace_id, job_description_id) == (
                snapshot.workspace_id,
                snapshot.job_description_id,
            )
            return snapshot

    class Renderer:
        async def render_html(self, body_html: str) -> bytes:
            assert "檢查設備" in body_html
            return b"%PDF-synthetic-renderer"

    output = asyncio.run(
        module.export_job_description(
            workspace_id=snapshot.workspace_id,
            job_description_id=snapshot.job_description_id,
            queries=Queries(),
            renderer=Renderer(),
        )
    )
    assert output == b"%PDF-synthetic-renderer"
