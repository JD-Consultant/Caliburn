"""HTTP 文件與實際邊界共用型別，錯誤不回顯私人輸入。"""

import json
from types import SimpleNamespace

from fastapi.testclient import TestClient

from caliburn.bootstrap import create_app
from caliburn.settings import Settings
from caliburn.transport.http.job_files import get_job_file_workflow


def test_invalid_path_does_not_echo_private_input() -> None:
    app = create_app(Settings())
    app.dependency_overrides[get_job_file_workflow] = lambda: SimpleNamespace()
    with TestClient(app, base_url="http://127.0.0.1:8100") as client:
        response = client.get("/api/job-files/private-employee-value")
    assert response.status_code == 422
    assert "private-employee-value" not in response.text
    assert response.headers["X-Request-ID"]


def test_openapi_validation_errors_do_not_advertise_raw_input() -> None:
    document = create_app(Settings()).openapi()
    schemas = document["components"]["schemas"]
    assert "HTTPValidationError" not in schemas
    response = document["paths"]["/api/job-files"]["post"]["responses"]["422"]
    assert "application/json" in response["content"]


def test_openapi_documents_stream_payloads_and_binary_download() -> None:
    document = create_app(Settings()).openapi()
    assert "CommentaryUpdate" in document["components"]["schemas"]
    stream = document["paths"][
        "/api/job-files/{job_file_id}/consultant-turns/{execution_id}/activity-stream"
    ]["get"]["responses"]
    assert "text/event-stream" in stream["200"]["content"]
    assert "204" in stream
    download = document["paths"]["/api/job-files/{job_file_id}/jd/export.pdf"]["get"]
    assert download["responses"]["200"]["content"]["application/pdf"]["schema"] == {
        "type": "string",
        "format": "binary",
    }
    # 文件生成只需路由型別，不讀環境或啟動資料庫／模型。
    assert json.dumps(document)
