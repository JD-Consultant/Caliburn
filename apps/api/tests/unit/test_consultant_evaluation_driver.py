"""固定案例只送公開輸入，失敗不自動重送，評閱標準不進模型輸入。"""

import json
import os
from uuid import uuid4

import httpx2
import pytest

from caliburn.adapters.database_settings import require_isolated_test_database
from evaluations.consultant_cases import EvaluationCase
from evaluations.consultant_comparison import drive_case


@pytest.mark.parametrize("status", ["completed", "failed", "paused", "active"])
async def test_case_stops_on_noncompletion_and_does_not_submit_evaluator_material(status):
    file_id, execution_id = str(uuid4()), str(uuid4())
    submitted = []

    def respond(request):
        if request.method == "POST":
            payload = json.loads(request.content)
            submitted.append(payload)
            if request.url.path == "/api/job-files":
                return httpx2.Response(201, json={"job_file_id": file_id})
            return httpx2.Response(202, json={"execution_id": execution_id})
        if "consultant-turns" in request.url.path:
            return httpx2.Response(200, json={"status": status})
        return httpx2.Response(200, json={})

    async with httpx2.AsyncClient(
        base_url="http://evaluation.invalid", transport=httpx2.MockTransport(respond)
    ) as client:
        result = await drive_case(
            client,
            EvaluationCase(name="synthetic", inputs=("第一段", "第二段"), criteria=("評閱秘密",)),
            timeout_seconds=0,
        )
    expected = 2 if status == "completed" else 1
    assert len(result["turns"]) == expected
    assert len(submitted) == 1 + expected
    assert "評閱秘密" not in json.dumps(submitted, ensure_ascii=False)
    assert result["all_inputs_completed"] == (status == "completed")
    assert result["turns"][0]["observation_timeout"] == (status == "active")


@pytest.mark.parametrize("redirect", ["url", "PGHOSTADDR", "PGSERVICE", "PGSERVICEFILE"])
def test_isolated_evaluation_rejects_libpq_target_redirection(monkeypatch, redirect):
    url = "postgresql://localhost/synthetic_test"
    if redirect == "url":
        url += "?hostaddr=203.0.113.10"
    else:
        monkeypatch.setenv(redirect, "redirect-not-allowed")
    with pytest.raises(ValueError, match="redirected"):
        require_isolated_test_database(url, environment=os.environ)
