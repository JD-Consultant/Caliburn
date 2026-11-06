"""資源 PATCH 經正式 HTTP 與真 PostgreSQL 驗證共同保存及回滾。"""

from collections.abc import Iterator
from typing import Any
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine

from caliburn.host.app import build_app
from tests.reference_configuration import HOST_REFERENCE_CONFIGURATION


class ResourceJourney:
    """使用公開 HTTP 建立合成前置，保留每次已提交結果供斷言。"""

    def __init__(self, client: TestClient, workspace_id: UUID) -> None:
        self.client = client
        initialized = client.get(f"/workspaces/{workspace_id}/job-description")
        assert initialized.status_code == 200, initialized.text
        self.current: dict[str, Any] = initialized.json()
        assert self.current["version"] == 1
        assert self.current["citations"] == []
        self.url = (
            f"http://testserver/workspaces/{workspace_id}/job-descriptions/"
            f"{self.current['job_description_id']}"
        )

    def add(self, collection: str, body: dict[str, Any]) -> str:
        response = self.client.post(
            f"{self.url}/{collection}",
            json={"expected_version": self.current["version"], **body},
        )
        assert response.status_code == 201, response.text
        previous_ids = {item["id"] for item in self.current[collection]}
        self.current = response.json()
        return str(
            next(
                item["id"]
                for item in self.current[collection]
                if item["id"] not in previous_ids
            )
        )

    def patch(self, suffix: str, body: dict[str, Any]) -> dict[str, Any]:
        response = self.client.patch(
            self.url + suffix,
            json={"expected_version": self.current["version"], **body},
        )
        assert response.status_code == 200, response.text
        self.current = response.json()
        assert self.client.get(self.url).json() == self.current
        return self.current

    def history(self) -> list[dict[str, Any]]:
        response = self.client.get(self.url + "/history")
        assert response.status_code == 200, response.text
        result: list[dict[str, Any]] = response.json()["items"]
        return result


@pytest.fixture
def resources(pg_engine: Engine) -> Iterator[ResourceJourney]:
    app = build_app(
        reference_configuration=HOST_REFERENCE_CONFIGURATION,
        database_url=pg_engine.url.render_as_string(hide_password=False),
    )
    with TestClient(app) as client:
        workspace = client.post(
            "/workspaces", json={"interviewee_name": "JD 資源 PATCH 旅程"}
        )
        assert workspace.status_code == 201, workspace.text
        yield ResourceJourney(client, UUID(workspace.json()["workspace_id"]))


@pytest.mark.parametrize(
    ("collection", "name_field", "detail_field"),
    [
        ("duties", "name", "scope"),
        ("knowledge", "name", "description"),
        ("skills", "name", "description"),
        ("collaborations", "collaborator_name", "scope"),
    ],
)
def test_named_resource_patch_saves_fields_and_placement_in_one_version(
    resources: ResourceJourney, collection: str, name_field: str, detail_field: str
) -> None:
    first_id = resources.add(collection, {name_field: "第一筆"})
    second_id = resources.add(collection, {name_field: "第二筆"})
    third_id = resources.add(collection, {name_field: "第三筆", detail_field: "舊內容"})
    previous_version = resources.current["version"]
    previous_history = resources.history()

    result = resources.patch(
        f"/{collection}/{third_id}",
        {
            name_field: "已修改",
            detail_field: "新內容",
            "placement": {"before_id": first_id},
            "correlation_id": "resource-patch",
        },
    )

    assert [item["id"] for item in result[collection]] == [
        third_id,
        first_id,
        second_id,
    ]
    assert result[collection][0][name_field] == "已修改"
    assert result[collection][0][detail_field] == "新內容"
    assert result["version"] == previous_version + 1
    history = resources.history()
    assert len(history) == len(previous_history) + 1
    assert history[0]["correlation_id"] == "resource-patch"
    snapshot = resources.client.get(
        f"{resources.url}/history/{result['version']}"
    ).json()
    assert snapshot["content"][collection] == result[collection]


def test_condition_patch_saves_text_kind_and_placement_in_one_version(
    resources: ResourceJourney,
) -> None:
    moved_id = resources.add(
        "conditions", {"kind": "work_environment", "text": "待更正條件"}
    )
    unchanged_id = resources.add(
        "conditions", {"kind": "work_environment", "text": "保留環境"}
    )
    first_id = resources.add(
        "conditions", {"kind": "qualification", "text": "第一資格"}
    )
    second_id = resources.add(
        "conditions", {"kind": "qualification", "text": "第二資格"}
    )
    previous_version = resources.current["version"]
    previous_history = resources.history()

    result = resources.patch(
        f"/conditions/{moved_id}",
        {
            "text": "更正後資格",
            "kind": "qualification",
            "placement": {"before_id": second_id},
        },
    )

    assert result["conditions"] == [
        {"id": unchanged_id, "kind": "work_environment", "text": "保留環境"},
        {"id": first_id, "kind": "qualification", "text": "第一資格"},
        {"id": moved_id, "kind": "qualification", "text": "更正後資格"},
        {"id": second_id, "kind": "qualification", "text": "第二資格"},
    ]
    assert result["version"] == previous_version + 1
    assert len(resources.history()) == len(previous_history) + 1
    snapshot = resources.client.get(
        f"{resources.url}/history/{result['version']}"
    ).json()
    assert snapshot["content"]["conditions"] == result["conditions"]


def test_resource_action_routes_are_removed(resources: ResourceJourney) -> None:
    cases = [
        ("duties", {"name": "職責"}),
        ("knowledge", {"name": "知識"}),
        ("skills", {"name": "技能"}),
        ("collaborations", {"collaborator_name": "協作"}),
        ("conditions", {"kind": "qualification", "text": "資格"}),
    ]
    for collection, body in cases:
        item_id = resources.add(collection, body)
        response = resources.client.post(
            f"{resources.url}/{collection}/{item_id}:move",
            json={"expected_version": resources.current["version"]},
        )
        assert response.status_code in {404, 405}, response.text
    condition_id = resources.current["conditions"][0]["id"]
    response = resources.client.post(
        f"{resources.url}/conditions/{condition_id}:reclassify",
        json={
            "expected_version": resources.current["version"],
            "kind": "qualification",
        },
    )
    assert response.status_code in {404, 405}, response.text
    operation_ids = {
        operation["operationId"]
        for path in resources.client.get("/openapi.json").json()["paths"].values()
        for operation in path.values()
    }
    assert operation_ids.isdisjoint(
        {
            "jd_move_duty",
            "jd_move_knowledge",
            "jd_move_skill",
            "jd_move_collaboration",
            "jd_move_condition",
            "jd_reclassify_condition",
        }
    )


@pytest.mark.parametrize(
    ("collection", "name_field"),
    [
        ("duties", "name"),
        ("knowledge", "name"),
        ("skills", "name"),
        ("collaborations", "collaborator_name"),
    ],
)
def test_named_resource_keeps_position_until_placement_is_explicit(
    resources: ResourceJourney, collection: str, name_field: str
) -> None:
    first_id = resources.add(collection, {name_field: "第一筆"})
    second_id = resources.add(collection, {name_field: "第二筆"})
    third_id = resources.add(collection, {name_field: "第三筆"})

    result = resources.patch(f"/{collection}/{first_id}", {name_field: "第一筆已修改"})
    assert [item["id"] for item in result[collection]] == [
        first_id,
        second_id,
        third_id,
    ]

    result = resources.patch(f"/{collection}/{first_id}", {"placement": {}})
    assert [item["id"] for item in result[collection]] == [
        second_id,
        third_id,
        first_id,
    ]

    result = resources.patch(
        f"/{collection}/{second_id}", {"placement": {"before_id": None}}
    )
    assert [item["id"] for item in result[collection]] == [
        third_id,
        first_id,
        second_id,
    ]


def test_condition_kind_only_appends_to_new_group_and_same_kind_keeps_order(
    resources: ResourceJourney,
) -> None:
    first_id = resources.add(
        "conditions", {"kind": "work_environment", "text": "第一環境"}
    )
    second_id = resources.add(
        "conditions", {"kind": "work_environment", "text": "第二環境"}
    )
    qualification_id = resources.add(
        "conditions", {"kind": "qualification", "text": "既有資格"}
    )
    previous = resources.current
    previous_history = resources.history()

    result = resources.patch(f"/conditions/{first_id}", {"kind": "work_environment"})
    assert result == previous
    assert resources.history() == previous_history

    result = resources.patch(f"/conditions/{first_id}", {"text": "修改環境"})
    assert [item["id"] for item in result["conditions"]] == [
        first_id,
        second_id,
        qualification_id,
    ]

    result = resources.patch(f"/conditions/{first_id}", {"kind": "qualification"})
    assert result["conditions"] == [
        {"id": second_id, "kind": "work_environment", "text": "第二環境"},
        {"id": qualification_id, "kind": "qualification", "text": "既有資格"},
        {"id": first_id, "kind": "qualification", "text": "修改環境"},
    ]
    result = resources.patch(
        f"/conditions/{first_id}", {"placement": {"before_id": qualification_id}}
    )
    assert [item["id"] for item in result["conditions"]] == [
        second_id,
        first_id,
        qualification_id,
    ]
    result = resources.patch(f"/conditions/{first_id}", {"placement": {}})
    assert [item["id"] for item in result["conditions"]] == [
        second_id,
        qualification_id,
        first_id,
    ]


RESOURCE_CASES = [
    ("duties", {"name": "原始職責", "scope": "原始範圍"}, {"name": "修改職責"}),
    (
        "knowledge",
        {"name": "原始知識", "description": "原始描述"},
        {"name": "修改知識"},
    ),
    ("skills", {"name": "原始技能", "description": "原始描述"}, {"name": "修改技能"}),
    (
        "collaborations",
        {"collaborator_name": "原始協作", "scope": "原始範圍"},
        {"collaborator_name": "修改協作"},
    ),
    (
        "conditions",
        {"text": "原始環境", "kind": "work_environment"},
        {"text": "修改資格", "kind": "qualification"},
    ),
]


@pytest.mark.parametrize(("collection", "original", "updates"), RESOURCE_CASES)
def test_invalid_anchor_rolls_back_fields_classification_and_history(
    resources: ResourceJourney,
    collection: str,
    original: dict[str, Any],
    updates: dict[str, Any],
) -> None:
    item_id = resources.add(collection, original)
    # Condition 的舊分類錨點不能用於修改後的新分類。
    wrong_group_id = resources.add(
        "conditions", {"kind": "work_environment", "text": "另一組錨點"}
    )
    previous = resources.current
    previous_history = resources.history()

    for anchor in (str(uuid4()), item_id, wrong_group_id):
        response = resources.client.patch(
            f"{resources.url}/{collection}/{item_id}",
            json={
                "expected_version": previous["version"],
                **updates,
                "placement": {"before_id": anchor},
            },
        )
        assert response.status_code == 422, response.text
        assert response.json()["detail"]["code"] == "invalid_order"
        assert response.json()["detail"]["commit_status"] == "not_committed"
        assert resources.client.get(resources.url).json() == previous
        assert resources.history() == previous_history


@pytest.mark.parametrize(("collection", "original", "updates"), RESOURCE_CASES)
def test_resource_patch_noop_keeps_version_but_stale_noop_is_rejected(
    resources: ResourceJourney,
    collection: str,
    original: dict[str, Any],
    updates: dict[str, Any],
) -> None:
    item_id = resources.add(collection, original)
    previous = resources.current
    previous_history = resources.history()
    payload = {**original, "placement": {"before_id": None}}

    assert resources.patch(f"/{collection}/{item_id}", payload) == previous
    assert resources.history() == previous_history

    response = resources.client.patch(
        f"{resources.url}/{collection}/{item_id}",
        json={"expected_version": previous["version"] - 1, **payload},
    )
    assert response.status_code == 409, response.text
    assert response.json()["detail"]["code"] == "jd_concurrency_conflict"
    assert response.json()["detail"]["reason"] == "version"
    assert resources.client.get(resources.url).json() == previous
    assert resources.history() == previous_history


@pytest.mark.parametrize(("collection", "original", "updates"), RESOURCE_CASES)
def test_resource_patch_rejects_absent_intent_null_placement_and_unknown_fields(
    resources: ResourceJourney,
    collection: str,
    original: dict[str, Any],
    updates: dict[str, Any],
) -> None:
    item_id = resources.add(collection, original)
    previous = resources.current
    previous_history = resources.history()
    for body in (
        {},
        {"placement": None},
        {**updates, "placement": None},
        {"placement": {"after_id": item_id}},
        {"placement": {"before_id": "invalid"}},
        {**updates, "readonly": "rejected"},
    ):
        response = resources.client.patch(
            f"{resources.url}/{collection}/{item_id}",
            json={"expected_version": previous["version"], **body},
        )
        assert response.status_code == 422, response.text
        assert response.json()["detail"]["code"] == "invalid_request"
        assert response.json()["detail"]["commit_status"] == "not_committed"
        assert resources.client.get(resources.url).json() == previous
        assert resources.history() == previous_history


@pytest.mark.parametrize("field", ["text", "kind"])
def test_condition_patch_rejects_null_required_fields(
    resources: ResourceJourney, field: str
) -> None:
    item_id = resources.add("conditions", {"kind": "qualification", "text": "資格"})
    previous = resources.current
    response = resources.client.patch(
        f"{resources.url}/conditions/{item_id}",
        json={"expected_version": previous["version"], field: None},
    )
    assert response.status_code == 422, response.text
    assert resources.client.get(resources.url).json() == previous


@pytest.mark.parametrize(
    ("collection", "references_field"),
    [("knowledge", "knowledge_ids"), ("skills", "skill_ids")],
)
def test_definition_placement_does_not_reorder_task_references(
    resources: ResourceJourney, collection: str, references_field: str
) -> None:
    first_id = resources.add(collection, {"name": "第一定義"})
    second_id = resources.add(collection, {"name": "第二定義"})
    resources.add(
        "tasks",
        {
            "name": "使用兩筆定義的任務",
            collection: [
                {"kind": "existing", "id": first_id},
                {"kind": "existing", "id": second_id},
            ],
        },
    )

    result = resources.patch(
        f"/{collection}/{second_id}",
        {"name": "已改名的第二定義", "placement": {"before_id": first_id}},
    )

    assert [item["id"] for item in result[collection]] == [second_id, first_id]
    assert result["tasks"][0][references_field] == [first_id, second_id]
