"""Task 複合 PATCH 經正式 HTTP 與真 PostgreSQL 驗證一次保存。"""

from collections.abc import Iterator
from typing import Any
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, event, text

from caliburn.host.app import build_app
from tests.reference_configuration import HOST_REFERENCE_CONFIGURATION


@pytest.fixture
def task_client(pg_engine: Engine) -> Iterator[TestClient]:
    app = build_app(
        reference_configuration=HOST_REFERENCE_CONFIGURATION,
        database_url=pg_engine.url.render_as_string(hide_password=False),
    )
    with TestClient(app) as client:
        yield client


class TaskJourney:
    """只持有 HTTP 地址與最後一筆完整結果。"""

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

    def write(self, method: str, suffix: str, **body: Any) -> dict[str, Any]:
        response = self.client.request(
            method,
            self.url + suffix,
            json={"expected_version": self.current["version"], **body},
        )
        assert response.status_code == (201 if method == "POST" else 200), response.text
        self.current = response.json()
        assert self.client.get(self.url).json() == self.current
        return self.current


@pytest.fixture
def task_journey(task_client: TestClient) -> TaskJourney:
    workspace = task_client.post(
        "/workspaces", json={"interviewee_name": "JD 任務 PATCH 旅程"}
    )
    assert workspace.status_code == 201, workspace.text
    return TaskJourney(task_client, UUID(workspace.json()["workspace_id"]))


def test_compound_patch_creates_and_links_content_in_one_snapshot(
    task_journey: TaskJourney,
) -> None:
    journey = task_journey
    journey.write("POST", "/duties", name="目的職責")
    duty_id = journey.current["duties"][0]["id"]
    journey.write("POST", "/knowledge", name="既有知識")
    knowledge_id = journey.current["knowledge"][0]["id"]
    journey.write("POST", "/skills", name="既有技能")
    skill_id = journey.current["skills"][0]["id"]
    journey.write("POST", "/tasks", name="原任務", description="原描述")
    task_id = journey.current["tasks"][0]["id"]
    version = journey.current["version"]
    history = journey.client.get(journey.url + "/history").json()["items"]

    result = journey.write(
        "PATCH",
        f"/tasks/{task_id}",
        name="修改任務",
        description=None,
        competency_level=4,
        placement={"destination_duty_id": duty_id},
        changes=[
            {"action": "add_outcome", "text": "共同成果"},
            {"action": "add_outcome", "text": "共同成果"},
            {"action": "add_requirement", "text": "可核對要求"},
            {"action": "link_knowledge", "id": knowledge_id},
            {"action": "link_skill", "id": skill_id},
            {"action": "create_and_link_knowledge", "name": "新知識"},
            {
                "action": "create_and_link_skill",
                "name": "新技能",
                "description": "細節",
            },
        ],
    )

    task = result["tasks"][0]
    assert result["version"] == version + 1
    assert task["name"] == "修改任務"
    assert task["description"] is None
    assert task["competency_level"] == 4
    assert task["duty_id"] == duty_id
    assert [item["text"] for item in task["outcomes"]] == ["共同成果", "共同成果"]
    assert len({item["id"] for item in task["outcomes"]}) == 2
    assert [item["text"] for item in task["requirements"]] == ["可核對要求"]
    assert task["knowledge_ids"] == [knowledge_id, result["knowledge"][1]["id"]]
    assert task["skill_ids"] == [skill_id, result["skills"][1]["id"]]
    assert result["skills"][1]["description"] == "細節"
    after = journey.client.get(journey.url + "/history").json()["items"]
    assert len(after) == len(history) + 1
    assert after[1:] == history
    snapshot = journey.client.get(journey.url + f"/history/{version + 1}").json()
    assert snapshot["content"] == {
        key: value for key, value in result.items() if key != "version"
    }


def test_last_invalid_reference_rolls_back_task_new_definitions_and_history(
    task_journey: TaskJourney,
) -> None:
    journey = task_journey
    journey.write("POST", "/tasks", name="原任務")
    task_id = journey.current["tasks"][0]["id"]
    before = journey.current
    history = journey.client.get(journey.url + "/history").json()
    response = journey.client.patch(
        journey.url + f"/tasks/{task_id}",
        json={
            "expected_version": before["version"],
            "name": "不得保存",
            "changes": [
                {"action": "add_outcome", "text": "不得殘留"},
                {"action": "create_and_link_knowledge", "name": "不得殘留知識"},
                {"action": "create_and_link_skill", "name": "不得殘留技能"},
                {"action": "link_knowledge", "id": str(uuid4())},
            ],
        },
    )
    assert response.status_code == 422, response.text
    assert response.json()["detail"]["code"] == "invalid_task_reference"
    assert response.json()["detail"]["commit_status"] == "not_committed"
    assert journey.client.get(journey.url).json() == before
    assert journey.client.get(journey.url + "/history").json() == history


def test_changes_edit_delete_and_order_task_content_without_replacing_identities(
    task_journey: TaskJourney,
) -> None:
    journey = task_journey
    journey.write(
        "POST",
        "/tasks",
        name="任務",
        outcomes=["成果一", "成果二", "成果三"],
        requirements=["要求一", "要求二", "要求三"],
        knowledge=[{"kind": "new", "name": "知識一"}],
        skills=[{"kind": "new", "name": "技能一"}, {"kind": "new", "name": "技能二"}],
    )
    task = journey.current["tasks"][0]
    task_id = task["id"]
    o1, o2, o3 = [item["id"] for item in task["outcomes"]]
    r1, r2, r3 = [item["id"] for item in task["requirements"]]
    k1 = task["knowledge_ids"][0]
    s1, s2 = task["skill_ids"]
    journey.write("POST", "/knowledge", name="知識二")
    k2 = journey.current["knowledge"][1]["id"]
    version = journey.current["version"]
    result = journey.write(
        "PATCH",
        f"/tasks/{task_id}",
        changes=[
            {"action": "update_outcome", "id": o1, "text": "改寫成果一"},
            {"action": "move_outcome", "id": o1},
            {"action": "delete_outcome", "id": o2},
            {"action": "update_requirement", "id": r2, "text": "改寫要求二"},
            {"action": "move_requirement", "id": r2, "before_id": r1},
            {"action": "delete_requirement", "id": r3},
            {"action": "link_knowledge", "id": k2},
            {"action": "move_knowledge_reference", "id": k2, "before_id": k1},
            {"action": "unlink_skill", "id": s1},
            {"action": "move_skill_reference", "id": s2},
        ],
    )
    task = result["tasks"][0]
    assert result["version"] == version + 1
    assert task["outcomes"] == [
        {"id": o3, "text": "成果三"},
        {"id": o1, "text": "改寫成果一"},
    ]
    assert task["requirements"] == [
        {"id": r2, "text": "改寫要求二"},
        {"id": r1, "text": "要求一"},
    ]
    assert task["knowledge_ids"] == [k2, k1]
    assert task["skill_ids"] == [s2]
    assert [item["id"] for item in result["knowledge"]] == [k1, k2]
    assert [item["id"] for item in result["skills"]] == [s1, s2]
    result = journey.write(
        "PATCH",
        f"/tasks/{task_id}",
        changes=[{"action": "unlink_knowledge", "id": k1}],
    )
    assert result["tasks"][0]["knowledge_ids"] == [k2]
    assert [item["id"] for item in result["knowledge"]] == [k1, k2]


@pytest.mark.parametrize(
    ("target", "actions"),
    [
        ("outcomes", ("update_outcome", "update_outcome")),
        ("outcomes", ("move_outcome", "move_outcome")),
        ("outcomes", ("update_outcome", "delete_outcome")),
        ("outcomes", ("delete_outcome", "move_outcome")),
        ("requirements", ("update_requirement", "update_requirement")),
        ("requirements", ("move_requirement", "move_requirement")),
        ("requirements", ("delete_requirement", "update_requirement")),
        ("requirements", ("move_requirement", "delete_requirement")),
        ("knowledge_ids", ("link_knowledge", "link_knowledge")),
        ("knowledge_ids", ("link_knowledge", "unlink_knowledge")),
        ("knowledge_ids", ("unlink_knowledge", "move_knowledge_reference")),
        ("knowledge_ids", ("move_knowledge_reference", "move_knowledge_reference")),
        ("skill_ids", ("unlink_skill", "unlink_skill")),
        ("skill_ids", ("unlink_skill", "link_skill")),
        ("skill_ids", ("move_skill_reference", "unlink_skill")),
        ("skill_ids", ("move_skill_reference", "move_skill_reference")),
    ],
)
def test_contradictory_changes_reject_the_entire_patch(
    task_journey: TaskJourney, target: str, actions: tuple[str, str]
) -> None:
    journey = task_journey
    journey.write(
        "POST",
        "/tasks",
        name="任務",
        outcomes=["成果"],
        requirements=["要求"],
        knowledge=[{"kind": "new", "name": "知識"}],
        skills=[{"kind": "new", "name": "技能"}],
    )
    before = journey.current
    task = before["tasks"][0]
    identity = task[target][0]
    if isinstance(identity, dict):
        identity = identity["id"]
    changes = [
        {
            "action": action,
            "id": identity,
            **({"text": "改字"} if action.startswith("update_") else {}),
        }
        for action in actions
    ]
    history = journey.client.get(journey.url + "/history").json()
    response = journey.client.patch(
        journey.url + f"/tasks/{task['id']}",
        json={
            "expected_version": before["version"],
            "name": "不得保存",
            "changes": changes,
        },
    )
    assert response.status_code == 422, response.text
    assert response.json()["detail"]["code"] == "invalid_jd_input"
    assert journey.client.get(journey.url).json() == before
    assert journey.client.get(journey.url + "/history").json() == history


@pytest.mark.parametrize(
    ("collection", "action"),
    [("knowledge", "move_knowledge_reference"), ("skills", "move_skill_reference")],
)
def test_moving_an_unlinked_definition_is_an_invalid_task_reference(
    task_journey: TaskJourney, collection: str, action: str
) -> None:
    journey = task_journey
    journey.write("POST", f"/{collection}", name="尚未連結定義")
    definition_id = journey.current[collection][0]["id"]
    journey.write("POST", "/tasks", name="任務")
    before = journey.current
    task_id = before["tasks"][0]["id"]
    response = journey.client.patch(
        journey.url + f"/tasks/{task_id}",
        json={
            "expected_version": before["version"],
            "changes": [{"action": action, "id": definition_id}],
        },
    )
    assert response.status_code == 422, response.text
    assert response.json()["detail"]["code"] == "invalid_task_reference"
    assert journey.client.get(journey.url).json() == before


def test_task_patch_requires_intent_in_http_and_openapi(
    task_journey: TaskJourney,
) -> None:
    journey = task_journey
    journey.write("POST", "/tasks", name="任務")
    before = journey.current
    task_id = before["tasks"][0]["id"]
    invalid_bodies: tuple[dict[str, Any], ...] = (
        {},
        {"changes": []},
        {"changes": None},
        {"placement": None},
        {"placement": {}},
        {"name": None},
        {"changes": [{"action": "unknown"}]},
        {"changes": [{"action": "add_outcome", "text": "成果", "private": "秘密"}]},
        {"changes": [{"action": "link_knowledge", "id": uuid4().hex}]},
        {
            "changes": [
                {"action": "move_requirement", "id": str(uuid4()), "before_id": True}
            ]
        },
        {
            "changes": [
                {"action": "create_and_link_skill", "name": "知識", "changes": []}
            ]
        },
    )
    for body in invalid_bodies:
        response = journey.client.patch(
            journey.url + f"/tasks/{task_id}",
            json={"expected_version": before["version"], **body},
        )
        assert response.status_code == 422, response.text
        assert response.json()["detail"]["code"] == "invalid_request"
        assert "private" not in response.text
    assert journey.client.get(journey.url).json() == before
    schema = journey.client.get("/openapi.json").json()["components"]["schemas"][
        "UpdateTaskRequest"
    ]
    assert {
        "required": ["changes"],
        "properties": {"changes": {"type": "array", "minItems": 1}},
    } in schema["anyOf"]
    unchanged = journey.write("PATCH", f"/tasks/{task_id}", name="任務", changes=[])
    assert unchanged == before


def test_noop_and_stale_version_do_not_write_another_snapshot(
    task_journey: TaskJourney,
) -> None:
    journey = task_journey
    journey.write("POST", "/knowledge", name="未連結知識")
    unlinked = journey.current["knowledge"][0]["id"]
    journey.write(
        "POST",
        "/tasks",
        name="任務",
        description="描述",
        competency_level=3,
        knowledge=[{"kind": "new", "name": "已連結知識"}],
        outcomes=["成果一", "成果二"],
    )
    before = journey.current
    task = before["tasks"][0]
    history = journey.client.get(journey.url + "/history").json()
    body = {
        "name": "任務",
        "placement": {"destination_duty_id": None},
        "changes": [
            {"action": "link_knowledge", "id": task["knowledge_ids"][0]},
            {"action": "unlink_knowledge", "id": unlinked},
            {"action": "move_outcome", "id": task["outcomes"][1]["id"]},
        ],
    }
    assert journey.write("PATCH", f"/tasks/{task['id']}", **body) == before
    for changes in (body, {"changes": [{"action": "link_skill", "id": str(uuid4())}]}):
        stale = journey.client.patch(
            journey.url + f"/tasks/{task['id']}",
            json={"expected_version": before["version"] - 1, **changes},
        )
        assert stale.status_code == 409, stale.text
        assert stale.json()["detail"]["code"] == "jd_concurrency_conflict"
    assert journey.client.get(journey.url).json() == before
    assert journey.client.get(journey.url + "/history").json() == history
    cleared = journey.write(
        "PATCH", f"/tasks/{task['id']}", description=None, competency_level=None
    )
    assert cleared["tasks"][0]["description"] is None
    assert cleared["tasks"][0]["competency_level"] is None
    assert cleared["tasks"][0]["outcomes"] == task["outcomes"]


def test_same_batch_and_existing_definition_names_conflict_atomically(
    task_journey: TaskJourney,
) -> None:
    journey = task_journey
    journey.write("POST", "/knowledge", name="既有名稱")
    journey.write("POST", "/tasks", name="任務")
    before = journey.current
    task_id = before["tasks"][0]["id"]
    history = journey.client.get(journey.url + "/history").json()
    for changes in (
        [{"action": "create_and_link_knowledge", "name": "既有名稱"}],
        [
            {"action": "create_and_link_knowledge", "name": " 同名 "},
            {"action": "create_and_link_knowledge", "name": "同名"},
        ],
        [
            {"action": "create_and_link_skill", "name": "同名"},
            {"action": "create_and_link_skill", "name": "同名"},
        ],
    ):
        response = journey.client.patch(
            journey.url + f"/tasks/{task_id}",
            json={
                "expected_version": before["version"],
                "name": "不保存",
                "changes": [{"action": "add_requirement", "text": "不保存"}, *changes],
            },
        )
        assert response.status_code == 409, response.text
        assert response.json()["detail"]["code"] == "jd_name_conflict"
        assert journey.client.get(journey.url).json() == before
        assert journey.client.get(journey.url + "/history").json() == history
    result = journey.write(
        "PATCH",
        f"/tasks/{task_id}",
        changes=[
            {"action": "create_and_link_knowledge", "name": "同名"},
            {"action": "create_and_link_skill", "name": "同名"},
        ],
    )
    assert result["knowledge"][-1]["name"] == result["skills"][-1]["name"] == "同名"


def test_patch_targets_and_anchors_stay_in_their_workspace_jd_and_task(
    task_journey: TaskJourney,
) -> None:
    journey = task_journey
    journey.write("POST", "/tasks", name="本任務", outcomes=["本成果"])
    task_id = journey.current["tasks"][0]["id"]
    journey.write("POST", "/tasks", name="其他任務", outcomes=["其他成果"])
    other_outcome = journey.current["tasks"][1]["outcomes"][0]["id"]
    workspace = journey.client.post(
        "/workspaces", json={"interviewee_name": "另一空間"}
    ).json()
    foreign = TaskJourney(journey.client, UUID(workspace["workspace_id"]))
    foreign.write("POST", "/knowledge", name="外部知識")
    foreign.write("POST", "/skills", name="外部技能")
    foreign.write("POST", "/duties", name="外部職責")
    foreign_before = foreign.current
    before = journey.current
    outcome_id = before["tasks"][0]["outcomes"][0]["id"]
    history = journey.client.get(journey.url + "/history").json()
    invalid_changes = [
        (
            {"action": "update_outcome", "id": other_outcome, "text": "不保存"},
            404,
            "outcome_not_found",
        ),
        (
            {"action": "move_outcome", "id": outcome_id, "before_id": other_outcome},
            422,
            "invalid_order",
        ),
        (
            {"action": "move_outcome", "id": outcome_id, "before_id": outcome_id},
            422,
            "invalid_order",
        ),
        (
            {"action": "link_knowledge", "id": foreign_before["knowledge"][0]["id"]},
            422,
            "invalid_task_reference",
        ),
        (
            {"action": "unlink_skill", "id": foreign_before["skills"][0]["id"]},
            422,
            "invalid_task_reference",
        ),
    ]
    for change, status, code in invalid_changes:
        response = journey.client.patch(
            journey.url + f"/tasks/{task_id}",
            json={
                "expected_version": before["version"],
                "name": "不保存",
                "changes": [change],
            },
        )
        assert response.status_code == status, response.text
        assert response.json()["detail"]["code"] == code
    for placement in (
        {"destination_duty_id": foreign_before["duties"][0]["id"]},
        {"destination_duty_id": None, "before_id": task_id},
    ):
        response = journey.client.patch(
            journey.url + f"/tasks/{task_id}",
            json={"expected_version": before["version"], "placement": placement},
        )
        assert response.status_code == 422, response.text
    wrong_scope = journey.url.replace(
        str(before["workspace_id"]), workspace["workspace_id"]
    )
    response = journey.client.patch(
        wrong_scope + f"/tasks/{task_id}",
        json={"expected_version": before["version"], "name": "不保存"},
    )
    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "jd_not_found"
    assert journey.client.get(journey.url).json() == before
    assert journey.client.get(journey.url + "/history").json() == history
    assert journey.client.get(foreign.url).json() == foreign_before


def test_snapshot_storage_failure_rolls_back_all_task_patch_effects(
    task_journey: TaskJourney, pg_engine: Engine
) -> None:
    journey = task_journey
    journey.write("POST", "/tasks", name="原任務")
    before = journey.current
    task_id = before["tasks"][0]["id"]
    history = journey.client.get(journey.url + "/history").json()
    with pg_engine.begin() as connection:
        connection.execute(
            text(
                "CREATE FUNCTION reject_task_snapshot() RETURNS trigger "
                "LANGUAGE plpgsql "
                "AS $$ BEGIN RAISE EXCEPTION 'synthetic snapshot rejection'; END $$"
            )
        )
        connection.execute(
            text(
                "CREATE TRIGGER reject_task_snapshot BEFORE INSERT ON "
                "job_description_snapshots "
                "FOR EACH ROW EXECUTE FUNCTION reject_task_snapshot()"
            )
        )
    response = journey.client.patch(
        journey.url + f"/tasks/{task_id}",
        json={
            "expected_version": before["version"],
            "name": "不保存",
            "changes": [
                {"action": "add_outcome", "text": "不保存"},
                {"action": "create_and_link_knowledge", "name": "不保存知識"},
                {"action": "create_and_link_skill", "name": "不保存技能"},
            ],
        },
    )
    assert response.status_code == 500, response.text
    assert response.json()["detail"]["commit_status"] == "not_committed"
    assert "synthetic" not in response.text
    assert journey.client.get(journey.url).json() == before
    assert journey.client.get(journey.url + "/history").json() == history


def test_placement_and_sequential_changes_use_the_current_collection(
    task_journey: TaskJourney,
) -> None:
    journey = task_journey
    journey.write("POST", "/duties", name="目的職責")
    duty_id = journey.current["duties"][0]["id"]
    journey.write("POST", "/tasks", name="任務A", outcomes=["一", "二", "三"])
    task_a = journey.current["tasks"][0]
    journey.write("POST", "/tasks", name="任務B", duty_id=duty_id)
    task_b = journey.current["tasks"][1]["id"]
    journey.write("POST", "/tasks", name="任務C", duty_id=duty_id)
    task_c = journey.current["tasks"][2]["id"]
    first, second, third = [item["id"] for item in task_a["outcomes"]]
    moved = journey.write(
        "PATCH",
        f"/tasks/{task_a['id']}",
        name="任務A編修",
        placement={"destination_duty_id": duty_id, "before_id": task_c},
        changes=[
            {"action": "move_outcome", "id": third, "before_id": first},
            {"action": "move_outcome", "id": second, "before_id": third},
        ],
    )
    assert [item["id"] for item in moved["tasks"]] == [task_b, task_a["id"], task_c]
    assert [item["id"] for item in moved["tasks"][1]["outcomes"]] == [
        second,
        third,
        first,
    ]
    unchanged_order = journey.write(
        "PATCH", f"/tasks/{task_a['id']}", description="只有文字"
    )
    assert [item["id"] for item in unchanged_order["tasks"]] == [
        task_b,
        task_a["id"],
        task_c,
    ]
    before = journey.current
    history = journey.client.get(journey.url + "/history").json()
    # 對不同目標依序移動後回到原排列，最終內容仍是 no-op。
    restored_order = journey.write(
        "PATCH",
        f"/tasks/{task_a['id']}",
        changes=[
            {"action": "move_outcome", "id": second},
            {"action": "move_outcome", "id": third},
            {"action": "move_outcome", "id": first},
        ],
    )
    assert restored_order == before
    assert journey.client.get(journey.url + "/history").json() == history
    end = journey.write(
        "PATCH", f"/tasks/{task_b}", placement={"destination_duty_id": duty_id}
    )
    assert [item["id"] for item in end["tasks"]] == [task_a["id"], task_c, task_b]
    unclassified = journey.write(
        "PATCH", f"/tasks/{task_a['id']}", placement={"destination_duty_id": None}
    )
    assert unclassified["tasks"][0]["id"] == task_a["id"]
    assert unclassified["tasks"][0]["duty_id"] is None


def test_compound_patch_saves_only_changed_content_rows(
    task_journey: TaskJourney,
) -> None:
    journey = task_journey
    journey.write(
        "POST",
        "/tasks",
        name="任務",
        outcomes=["保留成果"],
        requirements=["原要求"],
        knowledge=[{"kind": "new", "name": "保留知識"}],
        skills=[{"kind": "new", "name": "保留技能"}],
    )
    task = journey.current["tasks"][0]
    statements: list[str] = []

    def capture(
        _connection: Any,
        _cursor: Any,
        statement: str,
        _parameters: Any,
        _context: Any,
        _executemany: bool,
    ) -> None:
        if statement.startswith(("INSERT ", "UPDATE ", "DELETE ")):
            statements.append(statement)

    event.listen(Engine, "before_cursor_execute", capture)
    try:
        result = journey.write(
            "PATCH",
            f"/tasks/{task['id']}",
            changes=[
                {"action": "add_outcome", "text": "新增成果"},
                {
                    "action": "update_requirement",
                    "id": task["requirements"][0]["id"],
                    "text": "修改要求",
                },
                {"action": "create_and_link_knowledge", "name": "新知識"},
            ],
        )
    finally:
        event.remove(Engine, "before_cursor_execute", capture)
    assert result["tasks"][0]["outcomes"][0] == task["outcomes"][0]
    assert any(sql.startswith("INSERT INTO task_outcomes ") for sql in statements)
    assert any(sql.startswith("UPDATE task_requirements SET ") for sql in statements)
    assert not any(
        sql.startswith(
            (
                "DELETE ",
                "UPDATE job_tasks SET ",
                "UPDATE knowledge SET ",
                "UPDATE skills SET ",
            )
        )
        for sql in statements
    )
