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
    read_areas = area_persistence.read_areas
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
                    "expected_revision_id": task["revision_id"],
                    "change": {"action": "delete_area", "area_id": area_id},
                },
            )
            assert deleted.status_code == 200
        return result

    monkeypatch.setattr(area_persistence, "read_areas", change_after_areas)
    combined = client.get(f"{url}/work")
    assert combined.status_code == 200
    assert combined.json() == {
        "revision_id": task["revision_id"],
        "areas": area["areas"],
        "tasks": task["tasks"],
    }
    current = client.get(f"{url}/work").json()
    assert current["revision_id"] != task["revision_id"]
    assert current["areas"] == []
    assert current["tasks"][0]["area_id"] is None


def test_work_view_missing_file_is_not_an_empty_document(client: TestClient) -> None:
    assert client.get(f"/api/job-files/{uuid4()}/jd/work").status_code == 404
