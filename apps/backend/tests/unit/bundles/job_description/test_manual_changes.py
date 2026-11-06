"""固定人工差異保留兩端資料與順序，不泄漏 UUID 或以版號當內容修改。"""

import json

from caliburn.bundles.job_description.manual_changes import project_manual_changes
from tests.unit.bundles.job_description.test_projection import refs, snapshot


def test_version_only_difference_has_no_manual_change() -> None:
    before = snapshot()
    assert (
        project_manual_changes(before, before.model_copy(update={"version": 9}), refs())
        is None
    )


def test_manual_change_shows_before_and_after_with_stable_model_ref() -> None:
    before = snapshot()
    task = before.tasks[0].model_copy(update={"name": "異常驗收"})
    after = before.model_copy(update={"version": 9, "tasks": (task,)})
    result = project_manual_changes(before, after, refs())
    assert result is not None
    assert result["before_version"] == 7 and result["after_version"] == 9
    item = result["items"][0]
    assert item["read_ref"] == "task_104"
    assert item["before"]["name"] == "驗收"
    assert item["after"]["name"] == "異常驗收"
    assert str(before.job_description_id) not in json.dumps(result)


def test_deleted_task_has_historical_body_and_removed_ref_not_a_live_target() -> None:
    before = snapshot()
    after = before.model_copy(update={"version": 8, "tasks": ()})
    result = project_manual_changes(before, after, refs())
    assert result is not None
    task = next(item for item in result["items"] if item["read_ref"] == "task_104")
    assert task["change"] == "removed"
    assert task["before"]["name"] == "驗收" and task["after"] is None
    order = next(
        item for item in result["collections"] if item["collection"] == "tasks"
    )
    assert order["before_refs"] == ["task_104"] and order["after_refs"] == []
