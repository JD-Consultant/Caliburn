"""JD HTTP 契約透過正式組裝與真 PostgreSQL 保存及讀回。"""

from collections.abc import Iterator
from typing import Any
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, event
from sqlalchemy.orm import Session

from caliburn.host.app import build_app
from tests.reference_configuration import HOST_REFERENCE_CONFIGURATION

CONTENT_FIELDS = {
    "job_description_id",
    "workspace_id",
    "job_title",
    "organization_unit",
    "reports_to",
    "purpose",
    "baseline_competency_level",
    "duties",
    "tasks",
    "knowledge",
    "skills",
    "collaborations",
    "conditions",
    "citations",
}


@pytest.fixture
def jd_api_client(pg_engine: Engine) -> Iterator[TestClient]:
    app = build_app(
        reference_configuration=HOST_REFERENCE_CONFIGURATION,
        database_url=pg_engine.url.render_as_string(hide_password=False),
    )
    with TestClient(app) as client:
        yield client


def test_create_and_read_jd_through_workspace_lookup(
    jd_api_client: TestClient, jd_workspace_id: UUID
) -> None:
    lookup = f"/workspaces/{jd_workspace_id}/job-description"
    assert jd_api_client.get(lookup).status_code == 404

    response = jd_api_client.post(lookup, json={})
    assert response.status_code == 201, response.text
    result = response.json()
    saved = result
    assert saved["workspace_id"] == str(jd_workspace_id)
    assert saved["version"] == 1
    assert set(saved) == CONTENT_FIELDS | {"version"}
    assert (
        response.headers["Location"]
        == f"http://testserver/workspaces/{jd_workspace_id}/job-descriptions/{saved['job_description_id']}"
    )
    assert jd_api_client.get(response.headers["Location"]).json() == saved
    assert jd_api_client.get(lookup).json() == saved
    duplicate = jd_api_client.post(lookup, json={})
    assert duplicate.status_code == 409
    assert duplicate.json()["detail"]["code"] == "jd_already_exists"
    assert jd_api_client.get(lookup).json() == saved
    missing = jd_api_client.post(f"/workspaces/{uuid4()}/job-description", json={})
    assert missing.status_code == 404


class JdHttpJourney:
    """只代管 HTTP 前置與完整回覆檢查；業務結果由各測例明列。"""

    def __init__(self, client: TestClient, workspace_id: UUID) -> None:
        self.client = client
        response = client.get(f"/workspaces/{workspace_id}/job-description")
        assert response.status_code == 200, response.text
        self.current: dict[str, Any] = response.json()
        assert self.current["version"] == 1
        assert self.current["citations"] == []
        self.url = (
            f"http://testserver/workspaces/{workspace_id}/job-descriptions/"
            f"{self.current['job_description_id']}"
        )

    def write(
        self,
        method: str,
        suffix: str,
        body: dict[str, Any] | None = None,
        *,
        status: int = 200,
    ) -> dict[str, Any]:
        """每個寫入口先以舊版確認拒絕，再核成功的完整已保存結果。"""
        payload = dict(body or {})
        previous = self.current
        version = previous["version"]
        if version > 1:
            stale = self._request(method, suffix, payload, version - 1)
            assert stale.status_code == 409, stale.text
            assert stale.json()["detail"]["code"] == "jd_concurrency_conflict"
            assert self.client.get(self.url).json() == previous
        response = self._request(method, suffix, payload, version)
        assert response.status_code == status, response.text
        result: dict[str, Any] = response.json()
        assert set(result) == CONTENT_FIELDS | {"version"}
        changed = {key: result[key] for key in CONTENT_FIELDS} != {
            key: previous[key] for key in CONTENT_FIELDS
        }
        self.current = result
        assert self.current["version"] == version + int(changed or suffix == ":restore")
        assert self.client.get(self.url).json() == self.current
        if status == 201:
            assert response.headers["Location"] == self.url
        return result

    def _request(
        self, method: str, suffix: str, body: dict[str, Any], version: int
    ) -> Any:
        payload = {**body, "expected_version": version}
        if method == "DELETE":
            return self.client.delete(self.url + suffix, params=payload)
        return self.client.request(method, self.url + suffix, json=payload)


@pytest.fixture
def jd_journey(jd_api_client: TestClient) -> JdHttpJourney:
    workspace = jd_api_client.post(
        "/workspaces", json={"interviewee_name": "JD HTTP 契約旅程"}
    )
    assert workspace.status_code == 201, workspace.text
    journey = JdHttpJourney(jd_api_client, UUID(workspace.json()["workspace_id"]))
    journey.write("PATCH", "", {"purpose": "合成 HTTP 接線測試"})
    return journey


@pytest.mark.parametrize(
    ("collection", "kind", "name_field", "detail_field"),
    [
        ("duties", "duty", "name", "scope"),
        ("knowledge", "knowledge", "name", "description"),
        ("skills", "skill", "name", "description"),
        ("collaborations", "collaboration", "collaborator_name", "scope"),
    ],
)
def test_named_collection_crud_move_and_partial_update(
    jd_journey: JdHttpJourney,
    collection: str,
    kind: str,
    name_field: str,
    detail_field: str,
) -> None:
    """各集合正確映射名稱／描述、目標與排序；null 清空而省略保留。"""
    journey = jd_journey
    first = journey.write(
        "POST",
        f"/{collection}",
        {name_field: " 第一筆 ", detail_field: "保留的描述"},
        status=201,
    )
    first_id = first[collection][-1]["id"]
    second = journey.write("POST", f"/{collection}", {name_field: "第二筆"}, status=201)
    second_id = second[collection][-1]["id"]

    journey.write("PATCH", f"/{collection}/{first_id}", {name_field: "已改名"})
    assert journey.current[collection][0][detail_field] == "保留的描述"
    journey.write("PATCH", f"/{collection}/{first_id}", {detail_field: None})
    assert journey.current[collection][0][name_field] == "已改名"
    assert journey.current[collection][0][detail_field] is None
    journey.write(
        "PATCH", f"/{collection}/{second_id}", {"placement": {"before_id": first_id}}
    )
    assert [item["id"] for item in journey.current[collection]] == [second_id, first_id]
    journey.write("PATCH", f"/{collection}/{second_id}", {"placement": {}})
    assert [item["id"] for item in journey.current[collection]] == [first_id, second_id]
    journey.write("DELETE", f"/{collection}/{first_id}")
    assert [item["id"] for item in journey.current[collection]] == [second_id]


def test_composite_task_creation_patch_move_and_delete(
    jd_journey: JdHttpJourney,
) -> None:
    """多 O/P 與既有／新 K/S 在一次 Task 新增保存；移組與刪除回完整根。"""
    journey = jd_journey
    duty = journey.write("POST", "/duties", {"name": "職責"}, status=201)
    duty_id = duty["duties"][-1]["id"]
    knowledge = journey.write("POST", "/knowledge", {"name": "既有知識"}, status=201)
    knowledge_id = knowledge["knowledge"][-1]["id"]
    skill = journey.write("POST", "/skills", {"name": "既有技能"}, status=201)
    skill_id = skill["skills"][-1]["id"]
    created = journey.write(
        "POST",
        "/tasks",
        {
            "name": "處理客戶問題",
            "description": " 原始描述 ",
            "duty_id": duty_id,
            "competency_level": 3,
            "outcomes": ["完成問題分類", "完成可追蹤回覆"],
            "requirements": ["核對背景", "保留處理依據"],
            "knowledge": [
                {"kind": "existing", "id": knowledge_id},
                {"kind": "new", "name": "新知識", "description": "新知識描述"},
            ],
            "skills": [
                {"kind": "new", "name": "新技能"},
                {"kind": "existing", "id": skill_id},
            ],
        },
        status=201,
    )
    task = journey.current["tasks"][0]
    task_id = task["id"]
    assert task["duty_id"] == duty_id
    assert [item["text"] for item in task["outcomes"]] == [
        "完成問題分類",
        "完成可追蹤回覆",
    ]
    assert [item["text"] for item in task["requirements"]] == [
        "核對背景",
        "保留處理依據",
    ]
    assert task["knowledge_ids"] == [
        knowledge_id,
        journey.current["knowledge"][1]["id"],
    ]
    assert task["skill_ids"] == [journey.current["skills"][1]["id"], skill_id]
    assert created == journey.current
    assert (
        len(
            {
                task_id,
                *(item["id"] for item in task["outcomes"]),
                *(item["id"] for item in task["requirements"]),
                created["knowledge"][-1]["id"],
                created["skills"][-1]["id"],
            }
        )
        == 7
    )

    journey.write("PATCH", f"/tasks/{task_id}", {"name": "完成問題處理"})
    assert journey.current["tasks"][0]["description"] == " 原始描述 "
    journey.write(
        "PATCH",
        f"/tasks/{task_id}",
        {"description": None, "competency_level": None},
    )
    assert journey.current["tasks"][0]["description"] is None
    assert journey.current["tasks"][0]["competency_level"] is None
    anchor = journey.write("POST", "/tasks", {"name": "未分類任務"}, status=201)
    anchor_id = anchor["tasks"][0]["id"]
    journey.write(
        "PATCH",
        f"/tasks/{task_id}",
        {"placement": {"destination_duty_id": None, "before_id": anchor_id}},
    )
    assert journey.current["tasks"][0]["duty_id"] is None
    assert [item["id"] for item in journey.current["tasks"]] == [task_id, anchor_id]
    journey.write("DELETE", f"/tasks/{task_id}")
    assert [item["id"] for item in journey.current["tasks"]] == [anchor_id]
    journey.write("DELETE", f"/tasks/{anchor_id}")
    assert journey.current["tasks"] == []
    assert len(journey.current["knowledge"]) == len(journey.current["skills"]) == 2


@pytest.mark.parametrize(
    "collection, kind", [("outcomes", "outcome"), ("requirements", "requirement")]
)
def test_task_patch_preserves_text_parent_and_order(
    jd_journey: JdHttpJourney, collection: str, kind: str
) -> None:
    journey = jd_journey
    task = journey.write("POST", "/tasks", {"name": "測試任務"}, status=201)
    task_id = task["tasks"][0]["id"]
    path = f"/tasks/{task_id}"
    first = journey.write(
        "PATCH", path, {"changes": [{"action": f"add_{kind}", "text": "第一項"}]}
    )
    first_id = first["tasks"][0][collection][-1]["id"]
    second = journey.write(
        "PATCH", path, {"changes": [{"action": f"add_{kind}", "text": "第二項"}]}
    )
    second_id = second["tasks"][0][collection][-1]["id"]
    journey.write(
        "PATCH",
        path,
        {"changes": [{"action": f"update_{kind}", "id": first_id, "text": "編修後"}]},
    )
    assert journey.current["tasks"][0][collection][0]["text"] == "編修後"
    journey.write(
        "PATCH",
        path,
        {
            "changes": [
                {"action": f"move_{kind}", "id": second_id, "before_id": first_id}
            ]
        },
    )
    assert [item["id"] for item in journey.current["tasks"][0][collection]] == [
        second_id,
        first_id,
    ]
    journey.write(
        "PATCH", path, {"changes": [{"action": f"delete_{kind}", "id": first_id}]}
    )
    assert journey.current["tasks"][0][collection] == [
        {"id": second_id, "text": "第二項"}
    ]


@pytest.mark.parametrize(
    "collection, kind, ids_field",
    [
        ("knowledge", "knowledge", "knowledge_ids"),
        ("skills", "skill", "skill_ids"),
    ],
)
def test_task_patch_uses_definition_identity_and_noop_link(
    jd_journey: JdHttpJourney, collection: str, kind: str, ids_field: str
) -> None:
    journey = jd_journey
    task = journey.write("POST", "/tasks", {"name": "測試任務"}, status=201)
    task_id = task["tasks"][0]["id"]
    first = journey.write("POST", f"/{collection}", {"name": "第一項"}, status=201)
    first_id = first[collection][-1]["id"]
    second = journey.write("POST", f"/{collection}", {"name": "第二項"}, status=201)
    second_id = second[collection][-1]["id"]
    path = f"/tasks/{task_id}"
    link_first = {"changes": [{"action": f"link_{kind}", "id": first_id}]}
    journey.write("PATCH", path, link_first)
    previous = journey.current
    unchanged = journey.write("PATCH", path, link_first)
    assert unchanged == previous
    journey.write(
        "PATCH", path, {"changes": [{"action": f"link_{kind}", "id": second_id}]}
    )
    journey.write(
        "PATCH",
        path,
        {
            "changes": [
                {
                    "action": f"move_{kind}_reference",
                    "id": second_id,
                    "before_id": first_id,
                }
            ]
        },
    )
    assert journey.current["tasks"][0][ids_field] == [second_id, first_id]
    journey.write(
        "PATCH", path, {"changes": [{"action": f"unlink_{kind}", "id": first_id}]}
    )
    assert journey.current["tasks"][0][ids_field] == [second_id]
    assert len(journey.current[collection]) == 2


def test_condition_routes_keep_text_classification_and_order_distinct(
    jd_journey: JdHttpJourney,
) -> None:
    journey = jd_journey
    first = journey.write(
        "POST",
        "/conditions",
        {"kind": "work_environment", "text": "現場工作"},
        status=201,
    )
    first_id = first["conditions"][-1]["id"]
    second = journey.write(
        "POST",
        "/conditions",
        {"kind": "schedule_travel", "text": "每月出差"},
        status=201,
    )
    second_id = second["conditions"][-1]["id"]
    journey.write("PATCH", f"/conditions/{first_id}", {"text": "操作設備"})
    assert journey.current["conditions"][0]["kind"] == "work_environment"
    journey.write("PATCH", f"/conditions/{first_id}", {"kind": "schedule_travel"})
    journey.write(
        "PATCH", f"/conditions/{second_id}", {"placement": {"before_id": first_id}}
    )
    assert journey.current["conditions"] == [
        {"id": second_id, "kind": "schedule_travel", "text": "每月出差"},
        {"id": first_id, "kind": "schedule_travel", "text": "操作設備"},
    ]
    journey.write("DELETE", f"/conditions/{first_id}")
    assert [item["id"] for item in journey.current["conditions"]] == [second_id]


def test_root_patch_preserves_omission_and_explicit_null(
    jd_journey: JdHttpJourney,
) -> None:
    journey = jd_journey
    journey.write(
        "PATCH",
        "",
        {
            "job_title": " 工程師 ",
            "organization_unit": "技術部",
            "reports_to": "主管",
            "baseline_competency_level": 3.0,
        },
    )
    journey.write("PATCH", "", {"organization_unit": None})
    assert journey.current["job_title"] == " 工程師 "
    assert journey.current["organization_unit"] is None
    assert journey.current["reports_to"] == "主管"
    assert journey.current["baseline_competency_level"] == 3


def test_history_reads_compare_and_restore_require_current_version(
    jd_journey: JdHttpJourney,
) -> None:
    journey = jd_journey
    initial = journey.current
    journey.write("PATCH", "", {"purpose": "新目的", "correlation_id": "edit-1"})
    edited = journey.current
    history_url = journey.url + "/history"
    history = journey.client.get(history_url).json()
    assert len(history["items"]) == 3
    latest = history["items"][0]
    assert latest["job_description_id"] == edited["job_description_id"]
    assert latest["version"] == edited["version"]
    assert latest["correlation_id"] == "edit-1"
    assert set(latest) == {
        "job_description_id",
        "version",
        "kind",
        "recorded_at",
        "correlation_id",
        "reverts_correlation_id",
        "restored_from_version",
    }
    assert journey.client.get(history_url, params={"page_size": 0}).json() == history
    assert journey.client.get(history_url, params={"page_size": 101}).json() == history
    first_page = journey.client.get(history_url, params={"page_size": 1}).json()
    assert first_page["items"] == [latest]
    rest = journey.client.get(
        history_url,
        params={"page_size": 2, "page_token": first_page["next_page_token"]},
    ).json()
    assert len(rest["items"]) == 2
    assert rest["next_page_token"] is None
    old = journey.client.get(history_url + "/" + str(initial["version"]))
    assert old.status_code == 200, old.text
    assert set(old.json()["content"]) == CONTENT_FIELDS
    assert old.json()["content"]["purpose"] == "合成 HTTP 接線測試"
    assert old.json()["entry"]["version"] == initial["version"]
    difference = journey.client.get(
        journey.url + "/history:compare",
        params={
            "before_version": initial["version"],
            "after_version": edited["version"],
        },
    )
    assert difference.status_code == 200, difference.text
    assert set(difference.json()) == {
        "job_description_id",
        "before_version",
        "after_version",
        "items",
        "collections",
    }
    assert difference.json()["job_description_id"] == edited["job_description_id"]
    assert difference.json()["before_version"] == initial["version"]
    assert difference.json()["after_version"] == edited["version"]
    assert difference.json()["items"][0]["fields"] == [
        {"field": "purpose", "before": "合成 HTTP 接線測試", "after": "新目的"}
    ]
    rejected = journey.client.post(
        journey.url + ":restore",
        json={
            "target_version": initial["version"],
            "expected_version": initial["version"],
        },
    )
    assert rejected.status_code == 409, rejected.text
    assert journey.client.get(journey.url).json() == edited
    assert journey.client.get(history_url).json() == history
    restored = journey.write(
        "POST",
        ":restore",
        {
            "target_version": initial["version"],
            "correlation_id": "restore-1",
            "reverts_correlation_id": "edit-1",
        },
    )
    assert restored["purpose"] == initial["purpose"]
    assert restored["version"] == edited["version"] + 1
    repeated = journey.write(
        "POST",
        ":restore",
        {
            "target_version": initial["version"],
            "correlation_id": "restore-2",
            "reverts_correlation_id": "edit-1",
        },
    )
    assert {key: repeated[key] for key in CONTENT_FIELDS} == {
        key: restored[key] for key in CONTENT_FIELDS
    }
    assert repeated["version"] == restored["version"] + 1
    filtered = journey.client.get(
        history_url,
        params={"correlation_id": "restore-2", "reverts_correlation_id": "edit-1"},
    ).json()
    assert len(filtered["items"]) == 1
    marker = filtered["items"][0]
    assert marker["kind"] == "restored"
    assert marker["version"] == repeated["version"]
    assert marker["restored_from_version"] == initial["version"]
    mismatched_filter = journey.client.get(
        history_url,
        params={"correlation_id": "nonmatching", "reverts_correlation_id": "edit-1"},
    ).json()
    assert mismatched_filter["items"] == []


@pytest.mark.parametrize(
    "operation",
    [
        "current",
        "history_list",
        "history_get",
        "compare",
        "restore",
        "root_write",
        "child_write",
    ],
)
def test_workspace_scope_rejects_a_foreign_jd_without_writing(
    jd_journey: JdHttpJourney, operation: str
) -> None:
    journey = jd_journey
    before = journey.current
    history = journey.client.get(journey.url + "/history").json()
    workspace = journey.client.post(
        "/workspaces", json={"interviewee_name": "其他範圍"}
    )
    foreign_workspace = workspace.json()["workspace_id"]
    scoped_url = journey.url.replace(before["workspace_id"], foreign_workspace)
    if operation == "current":
        response = journey.client.get(scoped_url)
    elif operation == "history_list":
        response = journey.client.get(scoped_url + "/history")
    elif operation == "history_get":
        response = journey.client.get(scoped_url + "/history/1")
    elif operation == "compare":
        response = journey.client.get(
            scoped_url + "/history:compare",
            params={"before_version": 1, "after_version": before["version"]},
        )
    elif operation == "restore":
        response = journey.client.post(
            scoped_url + ":restore",
            json={"target_version": 1, "expected_version": before["version"]},
        )
    elif operation == "root_write":
        response = journey.client.patch(
            scoped_url,
            json={"purpose": "不可跨範圍", "expected_version": before["version"]},
        )
    else:
        response = journey.client.post(
            scoped_url + "/tasks",
            json={"name": "不可跨範圍", "expected_version": before["version"]},
        )
    assert response.status_code == 404, response.text
    assert response.json()["detail"]["code"] == "jd_not_found"
    assert journey.client.get(journey.url).json() == before
    assert journey.client.get(journey.url + "/history").json() == history


def test_restore_only_resolves_versions_inside_the_requested_jd(
    jd_journey: JdHttpJourney,
) -> None:
    journey = jd_journey
    workspace = journey.client.post("/workspaces", json={"interviewee_name": "其他 JD"})
    other = JdHttpJourney(journey.client, UUID(workspace.json()["workspace_id"]))
    for text in ("其他一", "其他二", "其他三"):
        other.write("PATCH", "", {"purpose": text})
    before = journey.current
    history = journey.client.get(journey.url + "/history").json()
    assert other.current["version"] > before["version"]
    response = journey.client.post(
        journey.url + ":restore",
        json={
            "target_version": other.current["version"],
            "expected_version": before["version"],
        },
    )
    assert response.status_code == 404, response.text
    assert journey.client.get(journey.url).json() == before
    assert journey.client.get(journey.url + "/history").json() == history


def test_invalid_http_inputs_and_composite_failure_leave_content_and_history_unchanged(
    jd_journey: JdHttpJourney,
) -> None:
    journey = jd_journey
    task_result = journey.write("POST", "/tasks", {"name": "測試任務"}, status=201)
    task_id = task_result["tasks"][0]["id"]
    current = journey.current
    version = current["version"]
    history = journey.client.get(journey.url + "/history").json()
    invalid_requests: list[tuple[str, dict[str, Any]]] = [
        ("", {"expected_version": version}),
        ("", {"job_title": "缺少前置"}),
        ("", {"expected_version": True, "job_title": "不可當整數"}),
        ("", {"expected_version": str(version), "job_title": "不可轉型"}),
        ("", {"expected_version": 9007199254740992, "job_title": "超界"}),
        ("", {"expected_version": version, "purpose": "private-secret\u0000"}),
        ("", {"expected_version": version, "private-secret-field": "private-value"}),
        (f"/tasks/{task_id}", {"expected_version": version, "name": None}),
    ]
    for suffix, body in invalid_requests:
        rejected = journey.client.patch(journey.url + suffix, json=body)
        assert rejected.status_code == 422, rejected.text
        assert "private" not in rejected.text
        assert "input" not in rejected.text
        assert "Value error" not in rejected.text
    missing_destination = journey.client.patch(
        journey.url + f"/tasks/{task_id}",
        json={"expected_version": version, "placement": {}},
    )
    assert missing_destination.status_code == 422
    missing_delete_version = journey.client.delete(journey.url + f"/tasks/{task_id}")
    assert missing_delete_version.status_code == 422
    composite = journey.client.post(
        journey.url + "/tasks",
        json={
            "expected_version": version,
            "name": "不應保存的任務",
            "knowledge": [
                {"kind": "new", "name": "不應殘留的知識"},
                {"kind": "existing", "id": str(uuid4())},
            ],
            "outcomes": ["不應殘留的成果"],
        },
    )
    assert composite.status_code == 422, composite.text
    assert journey.client.get(journey.url).json() == current
    assert journey.client.get(journey.url + "/history").json() == history


@pytest.mark.parametrize(
    "version", ["0", "01", "+1", "-1", "1.0", "1e3", "9007199254740992"]
)
def test_history_version_rejects_noncanonical_or_unsafe_decimal(
    jd_journey: JdHttpJourney, version: str
) -> None:
    journey = jd_journey
    response = journey.client.get(journey.url + "/history/" + version)
    assert response.status_code == 422, response.text


@pytest.mark.parametrize(
    "stage, commit_status, changed",
    [
        ("before_commit", "not_committed", False),
        ("after_commit", "unknown", True),
    ],
)
def test_commit_boundary_failures_report_facts_without_retry(
    jd_journey: JdHttpJourney, stage: str, commit_status: str, changed: bool
) -> None:
    """真交易故障注入；class after_commit 早於 UoW 確認，故仍為 unknown。"""
    journey = jd_journey
    previous = journey.current
    history_before = journey.client.get(journey.url + "/history").json()
    attempts = 0

    def fail(session: Session) -> None:
        nonlocal attempts
        attempts += 1
        raise RuntimeError("private SQL input and connection details")

    event.listen(Session, stage, fail)
    try:
        response = journey.client.patch(
            journey.url,
            json={"expected_version": previous["version"], "purpose": "故障邊界寫入"},
        )
    finally:
        event.remove(Session, stage, fail)
    assert response.status_code == 500, response.text
    assert response.json()["detail"]["commit_status"] == commit_status
    assert "private" not in response.text
    assert attempts == 1
    saved = journey.client.get(journey.url).json()
    history_after = journey.client.get(journey.url + "/history").json()
    if changed:
        assert saved["purpose"] == "故障邊界寫入"
        assert saved["version"] == previous["version"] + 1
        assert len(history_after["items"]) == len(history_before["items"]) + 1
    else:
        assert saved == previous
        assert history_after == history_before


def test_confirmed_commit_cleanup_failure_returns_committed(
    jd_journey: JdHttpJourney, monkeypatch: pytest.MonkeyPatch
) -> None:
    """已確認提交後 close 失敗，HTTP 保留 committed 且不重送寫入。"""
    journey = jd_journey
    previous = journey.current
    original_close = Session.close
    attempts = 0

    def close_then_fail(session: Session) -> None:
        nonlocal attempts
        original_close(session)
        attempts += 1
        raise RuntimeError("private cleanup failure")

    with monkeypatch.context() as injection:
        injection.setattr(Session, "close", close_then_fail)
        response = journey.client.patch(
            journey.url,
            json={
                "expected_version": previous["version"],
                "purpose": "提交確認後清理失敗",
            },
        )
    assert response.status_code == 500, response.text
    assert response.json()["detail"]["commit_status"] == "committed"
    assert "private" not in response.text
    assert attempts == 1
    saved = journey.client.get(journey.url).json()
    assert saved["purpose"] == "提交確認後清理失敗"
    assert saved["version"] == previous["version"] + 1


def test_history_version_safe_integer_boundary_is_accepted_without_rounding(
    jd_journey: JdHttpJourney,
) -> None:
    journey = jd_journey
    maximum = 9007199254740991
    missing = journey.client.get(journey.url + "/history/" + str(maximum))
    assert missing.status_code == 404, missing.text
    comparison = journey.client.get(
        journey.url + "/history:compare",
        params={"before_version": 1, "after_version": maximum},
    )
    assert comparison.status_code == 404, comparison.text
    restore = journey.client.post(
        journey.url + ":restore",
        json={
            "target_version": maximum,
            "expected_version": journey.current["version"],
        },
    )
    assert restore.status_code == 404, restore.text
    stale = journey.client.patch(
        journey.url, json={"purpose": "過期", "expected_version": maximum}
    )
    assert stale.status_code == 409, stale.text
    for invalid in (0, -1, True, "1", maximum + 1):
        rejected = journey.client.post(
            journey.url + ":restore",
            json={
                "target_version": invalid,
                "expected_version": journey.current["version"],
            },
        )
        assert rejected.status_code == 422, rejected.text
    assert journey.client.get(journey.url).json() == journey.current
