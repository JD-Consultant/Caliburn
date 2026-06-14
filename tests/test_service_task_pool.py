from jd_ocs_indexer.api import service
from tests.conftest import FakeQdrant, FakePoint


def _task(ocs, unit, tid, title, acts):
    return FakePoint(id=f"{ocs}-{tid}", payload={
        "chunk_level": "task", "ocs_code": ocs, "unit_id": unit, "unit_title": "U-" + unit,
        "task_id": tid, "task_title": title, "activity_examples": acts,
    })


def test_task_pool_groups_task_points_by_unit_with_id_and_jobtitle():
    profiles = [FakePoint(id="pf", payload={"chunk_level": "profile", "ocs_code": "OC1", "job_title": "工程師"})]
    tasks = [
        _task("OC1", "U1", "T1.2", "任務B", ["a", "b"]),
        _task("OC1", "U1", "T1.1", "任務A", ["c"]),
    ]
    # service scrolls profiles first, then tasks → two scroll pages
    fake = FakeQdrant(scroll_pages=[(profiles, None), (tasks, None)])
    out = service.build_task_pool(fake, "ocs_v3", ocs_codes=["OC1"], activity_examples=1)
    g = out["groups"][0]
    assert g["ocs_code"] == "OC1" and g["job_title"] == "工程師"
    u = g["units"][0]
    assert u["unit_id"] == "U1" and u["unit_title"] == "U-U1"
    # tasks sorted by task_id; activity_examples capped at 1; each carries id
    assert [t["task_id"] for t in u["tasks"]] == ["T1.1", "T1.2"]
    assert u["tasks"][0]["id"] == "OC1-T1.1" and u["tasks"][1]["activity_examples"] == ["a"]
