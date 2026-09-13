"""Real chat HTTP and owner/native graph, synthetic SQL material only."""
from uuid import uuid4

from jsonschema import Draft202012Validator

from jd_relational.generated.chat_http import ChatProblem, ChatRunChangePage
from jd_relational.references import ReferenceCodec, ReferenceValidationError
from jd_relational.storage.history import RunChangeMaterial
from test_ai_runtime import make_runtime
from test_chat_api import assert_result, chat_app


def test_saved_interview_without_edits_has_readonly_empty_capture(chat_app, monkeypatch):
    with chat_app() as value:
        calls = []
        def material(document, run, ids):
            calls.append((document, run, ids))
            return RunChangeMaterial("none", (), None, None)
        monkeypatch.setattr(value.runtime.history, "read_run_change", material)
        response = value.client.post(value.path, json=value.payload, headers=value.headers)
        assert response.status_code in {200, 202}
        assert value.runtime.lookup(value.document, value.run).wait(5).status == "completed"
        before = list(value.model_calls)
        response = value.client.get(value.run_path + "/changes")
        page = assert_result(response, ChatRunChangePage)
        assert page["effects_state"] == "settled" and page["continuity"] == "none"
        assert page["records"] == [] and page["captured_operation_count"] == 0
        assert calls == [(value.document, value.run, ())]
        assert value.model_calls == before
        assert page["dataset_id"] == value.dataset and page["run_id"] == value.run
        spec = value.app.openapi()
        shape = Draft202012Validator({"components": spec["components"],
            "$ref": "#/components/schemas/ChatRunChangePage"})
        assert shape.is_valid(page)
        assert not shape.is_valid(page | {"captured_operation_count": 1})


def test_unknown_run_or_invalid_cursor_never_becomes_no_changes(chat_app, monkeypatch):
    with chat_app() as value:
        def never(*args):
            raise AssertionError("bad request must not reach material reader")
        monkeypatch.setattr(value.runtime.history, "read_run_change", never)
        for suffix in ("", "?cursor=bad", "?cursor=" + "x" * 4097):
            response = value.client.get(value.run_path + "/changes" + suffix)
            assert_result(response, ChatProblem, 422)
        assert value.model_calls == []


def test_get_contract_is_published_on_existing_boundary(chat_app):
    with chat_app() as value:
        route = "/api/documents/{document_id}/chat/runs/{run_id}/changes"
        entry = value.app.openapi()["paths"][route]["get"]
        assert entry["responses"]["200"]["content"]["application/json"]["schema"]["$ref"].endswith("/ChatRunChangePage")
        assert "application/problem+json" in entry["responses"]["422"]["content"]
        assert any(field["name"] == "cursor" and field["schema"]["anyOf"][0]["maxLength"] == 4096
                   for field in entry["parameters"])


def test_app_issuer_failure_returns_service_problem_not_caller_error(chat_app, monkeypatch):
    with chat_app() as value:
        response = value.client.post(value.path, json=value.payload, headers=value.headers)
        assert response.status_code in {200, 202}
        assert value.runtime.lookup(value.document, value.run).wait(5).status == "completed"
        def fail(*args, **kwargs):
            raise ReferenceValidationError()
        monkeypatch.setattr(ReferenceCodec, "issue_run_cursor", fail)
        response = value.client.get(value.run_path + "/changes")
        problem = assert_result(response, ChatProblem, 503)
        assert problem["code"] == "service_unavailable"
        assert problem["next_action"] == "lookup_run"
