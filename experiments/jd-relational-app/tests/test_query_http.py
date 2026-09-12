"""Read failures cannot become write receipts or echo private request material."""

from uuid import uuid4
import pytest
from jd_relational.query_http import query_problem
from jd_relational.generated.query_http import QueryProblem


@pytest.mark.parametrize(
    "code,status",
    [
        ("invalid_input", 422),
        ("invalid_ref", 422),
        ("stale_view", 409),
        ("target_missing", 404),
        ("read_failed", 500),
        ("private body", 500),
    ],
)
def test_fixed_query_problem(code, status):
    request_id = uuid4()
    result = query_problem(code, request_id=request_id)
    assert result.status_code == status
    assert result.media_type == "application/problem+json"
    assert result.headers["Cache-Control"] == "no-store"
    assert result.headers["X-Request-ID"] == str(request_id)
    body = QueryProblem.model_validate(result.body, strict=True).model_dump(mode="json")
    assert body["status"] == status and body["instance"] == f"urn:uuid:{request_id}"
    assert "jd_result" not in body and "private body" not in str(body)
    assert body["jd_read_error"]["next_action"] == (
        "stop"
        if status == 500
        else "correct_arguments" if code == "invalid_input" else "reread_current"
    )


def test_request_identity_must_be_server_uuid():
    with pytest.raises(ValueError, match="invalid_http_context"):
        query_problem("invalid_input", request_id="untrusted-request-id")


def test_malformed_internal_error_cannot_break_the_safe_error_projection():
    result = query_problem({"private": "raw-interview-SENTINEL"}, request_id=uuid4())
    assert result.status_code == 500
    assert "SENTINEL" not in str(result.body)
