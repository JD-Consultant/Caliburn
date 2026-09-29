"""A grouped editor must never combine membership from different formal revisions."""

import asyncio
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from caliburn.features.job_description import area_persistence
from caliburn.features.job_description.areas import ResponsibilityArea

pytestmark = pytest.mark.postgres


def test_work_view_pins_revision_even_when_head_changes_between_reads(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    created = client.post(
        "/api/job-files",
        json={"command_id": str(uuid4()), "display_name": "合成工作", "employee_name": "合成人"},
    ).json()
    url = f"/api/job-files/{created['job_file_id']}/jd"
    empty = client.get(f"{url}/work")
    assert empty.status_code == 200
    assert empty.json()["areas"] == empty.json()["tasks"] == []
    assert empty.json()["capabilities"] == empty.json()["task_links"] == []
    assert empty.json()["collaborators"] == empty.json()["conditions"] == []
    area = client.post(
        f"{url}/areas",
        json={
            "command_id": str(uuid4()),
            "expected_revision_id": empty.json()["revision_id"],
            "change": {"action": "create_area", "title": "網站交付", "scope_text": None},
        },
    ).json()
    area_id = area["areas"][0]["area_id"]
    task = client.post(
        f"{url}/tasks",
        json={
            "command_id": str(uuid4()),
            "expected_revision_id": area["revision_id"],
            "change": {
                "action": "create_task",
                "area_id": area_id,
                "title": "交付網頁",
                "description": None,
                "outcomes": ["可操作頁面"],
                "requirements": [],
            },
        },
    ).json()
    capability = client.post(
        f"{url}/capabilities",
        json={
            "command_id": str(uuid4()),
            "expected_revision_id": task["revision_id"],
            "change": {
                "action": "create_capability",
                "kind": "knowledge",
                "name": "資料介面",
                "description": None,
            },
        },
    ).json()
    capability_id = capability["capabilities"][0]["capability_id"]
    linked = client.post(
        f"{url}/capabilities",
        json={
            "command_id": str(uuid4()),
            "expected_revision_id": capability["revision_id"],
            "change": {
                "action": "set_task_capability",
                "task_id": task["tasks"][0]["task_id"],
                "capability_id": capability_id,
                "linked": True,
            },
        },
    ).json()
    read_areas = area_persistence.read_areas
    collaborator = client.post(
        f"{url}/collaborators",
        json={
            "command_id": str(uuid4()),
            "expected_revision_id": linked["revision_id"],
            "change": {"action": "create_collaborator", "name": "設計同事", "scope_text": None},
        },
    ).json()
    condition = client.post(
        f"{url}/conditions",
        json={
            "command_id": str(uuid4()),
            "expected_revision_id": collaborator["revision_id"],
            "change": {
                "action": "create_condition",
                "kind": "schedule_travel",
                "text": "依約支援上線。",
            },
        },
    ).json()
    changed = False

    async def change_after_areas(
        session: AsyncSession, file_id: UUID, revision_id: UUID
    ) -> tuple[ResponsibilityArea, ...]:
        nonlocal changed
        result = await read_areas(session, file_id, revision_id)
        if not changed:
            changed = True
            # A different request commits while the combined projection is being read.
            deleted = await asyncio.to_thread(
                client.post,
                f"{url}/areas",
                json={
                    "command_id": str(uuid4()),
                    "expected_revision_id": condition["revision_id"],
                    "change": {"action": "delete_area", "area_id": area_id},
                },
            )
            assert deleted.status_code == 200
            renamed = await asyncio.to_thread(
                client.post,
                f"{url}/capabilities",
                json={
                    "command_id": str(uuid4()),
                    "expected_revision_id": deleted.json()["revision_id"],
                    "change": {
                        "action": "revise_capability",
                        "capability_id": capability_id,
                        "changes": [{"field": "name", "value": "新版介面知識"}],
                    },
                },
            )
            assert renamed.status_code == 200
            unlinked = await asyncio.to_thread(
                client.post,
                f"{url}/capabilities",
                json={
                    "command_id": str(uuid4()),
                    "expected_revision_id": renamed.json()["revision_id"],
                    "change": {
                        "action": "set_task_capability",
                        "task_id": task["tasks"][0]["task_id"],
                        "capability_id": capability_id,
                        "linked": False,
                    },
                },
            )
            assert unlinked.status_code == 200
            deleted_collaborator = await asyncio.to_thread(
                client.post,
                f"{url}/collaborators",
                json={
                    "command_id": str(uuid4()),
                    "expected_revision_id": unlinked.json()["revision_id"],
                    "change": {
                        "action": "delete_collaborator",
                        "collaborator_id": collaborator["collaborators"][0]["collaborator_id"],
                    },
                },
            )
            assert deleted_collaborator.status_code == 200
            reclassified = await asyncio.to_thread(
                client.post,
                f"{url}/conditions",
                json={
                    "command_id": str(uuid4()),
                    "expected_revision_id": deleted_collaborator.json()["revision_id"],
                    "change": {
                        "action": "revise_condition",
                        "condition_id": condition["conditions"][0]["condition_id"],
                        "changes": [{"field": "kind", "value": "shared_collaboration"}],
                    },
                },
            )
            assert reclassified.status_code == 200
        return result

    monkeypatch.setattr(area_persistence, "read_areas", change_after_areas)
    combined = client.get(f"{url}/work")
    assert combined.status_code == 200
    assert combined.json() == {
        "revision_id": condition["revision_id"],
        "areas": area["areas"],
        "tasks": task["tasks"],
        "capabilities": capability["capabilities"],
        "task_links": linked["task_links"],
        "collaborators": collaborator["collaborators"],
        "conditions": condition["conditions"],
    }
    current = client.get(f"{url}/work").json()
    assert current["revision_id"] != task["revision_id"]
    assert current["areas"] == []
    assert current["tasks"][0]["area_id"] is None
    assert current["capabilities"][0]["name"] == "新版介面知識"
    assert current["task_links"] == []
    assert current["collaborators"] == []
    assert current["conditions"][0]["kind"] == "shared_collaboration"


def test_work_view_missing_file_is_not_an_empty_document(client: TestClient) -> None:
    assert client.get(f"/api/job-files/{uuid4()}/jd/work").status_code == 404
