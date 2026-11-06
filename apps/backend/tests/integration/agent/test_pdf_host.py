"""正式 Host 的 PDF 配置、不可用回覆及唯讀下載。"""

import asyncio
import os
import threading
import unicodedata
from io import BytesIO
from pathlib import Path

import httpx2
import pdfplumber
import pytest
from sqlalchemy import Engine

from caliburn.host.app import build_app
from caliburn.host.entrypoint import create_app
from tests.reference_configuration import (
    HOST_REFERENCE_CONFIGURATION,
    write_reference_configuration,
)


def test_pdf_route_is_explicitly_unavailable_without_configuration(
    pg_engine: Engine,
) -> None:
    async def run() -> None:
        app = build_app(
            reference_configuration=HOST_REFERENCE_CONFIGURATION,
            database_url=pg_engine.url.render_as_string(hide_password=False),
        )
        async with (
            app.router.lifespan_context(app),
            httpx2.AsyncClient(
                transport=httpx2.ASGITransport(app=app), base_url="http://testserver"
            ) as client,
        ):
            workspace = await client.post(
                "/workspaces", json={"interviewee_name": "Must not be exported"}
            )
            assert workspace.status_code == 201, workspace.text
            path = workspace.headers["Location"]
            jd = (await client.get(path + "/job-description")).json()
            exported = await client.get(
                f"{path}/job-descriptions/{jd['job_description_id']}/export.pdf"
            )
            assert exported.status_code == 503, exported.text
            assert exported.json() == {"detail": {"code": "pdf_export_unavailable"}}
            assert not exported.content.startswith(b"%PDF-")
            assert (await client.get(path + "/job-description")).json() == jd

    asyncio.run(run(), loop_factory=asyncio.SelectorEventLoop)


def test_configured_host_exports_readonly_pdf_without_employee_name(
    pg_engine: Engine, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    font = os.environ.get("CALIBURN_TEST_PDF_FONT")
    if font is None:
        pytest.skip("Set CALIBURN_TEST_PDF_FONT for actual Host PDF rendering")
    monkeypatch.setenv(
        "CALIBURN_REBUILD_DATABASE_URL",
        pg_engine.url.render_as_string(hide_password=False),
    )
    monkeypatch.setenv("CALIBURN_REBUILD_PDF_FONT_PATH", font)
    for variable in (
        "CALIBURN_REBUILD_AGENT_CONFIG",
        "CALIBURN_REBUILD_AGENT_CHECKPOINT_CONNINFO",
        "CALIBURN_REBUILD_PDF_CHROMIUM_PATH",
    ):
        monkeypatch.delenv(variable, raising=False)
    if executable := os.environ.get("CALIBURN_TEST_PDF_CHROMIUM"):
        monkeypatch.setenv("CALIBURN_REBUILD_PDF_CHROMIUM_PATH", executable)
    monkeypatch.setenv(
        "CALIBURN_REBUILD_REFERENCE_CONFIG",
        str(write_reference_configuration(tmp_path)),
    )

    async def run() -> bytes:
        app = create_app()
        async with (
            app.router.lifespan_context(app),
            httpx2.AsyncClient(
                transport=httpx2.ASGITransport(app=app), base_url="http://testserver"
            ) as client,
        ):
            workspace = await client.post(
                "/workspaces", json={"interviewee_name": "PRIVATE_EMPLOYEE_NAME"}
            )
            assert workspace.status_code == 201, workspace.text
            path = workspace.headers["Location"]
            jd = (await client.get(path + "/job-description")).json()
            jd_path = f"{path}/job-descriptions/{jd['job_description_id']}"
            saved = await client.patch(
                jd_path,
                json={
                    "expected_version": 1,
                    "job_title": "設備維護員",
                    "purpose": "只輸出職務資訊",
                },
            )
            assert saved.status_code == 200, saved.text
            exported = await client.get(jd_path + "/export.pdf")
            assert exported.status_code == 200, exported.text
            assert exported.headers["Content-Type"] == "application/pdf"
            assert exported.headers["Cache-Control"] == "no-store"
            assert exported.headers["Content-Disposition"].startswith("attachment;")
            assert (await client.get(jd_path)).json() == saved.json()
            return exported.content

    original_threads = set(threading.enumerate())
    pdf = asyncio.run(run(), loop_factory=asyncio.SelectorEventLoop)
    # Host 關閉必須等待列印 worker；以實際程序資源觀察，不讀 renderer 私有狀態。
    assert not [
        thread
        for thread in threading.enumerate()
        if thread not in original_threads and not thread.daemon
    ]
    assert pdf.startswith(b"%PDF-")
    with pdfplumber.open(BytesIO(pdf)) as parsed:
        text = unicodedata.normalize(
            "NFKC", "\n".join(page.extract_text() or "" for page in parsed.pages)
        )
    assert "設備維護員" in text
    assert "只輸出職務資訊" in text
    assert "PRIVATE_EMPLOYEE_NAME" not in text
    if output := os.environ.get("CALIBURN_TEST_PDF_OUTPUT"):
        directory = Path(output)
        directory.mkdir(parents=True, exist_ok=True)
        (directory / "jd-host.pdf").write_bytes(pdf)


def test_explicit_pdf_configuration_reports_missing_font_without_empty_pdf(
    pg_engine: Engine, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv(
        "CALIBURN_REBUILD_DATABASE_URL",
        pg_engine.url.render_as_string(hide_password=False),
    )
    monkeypatch.setenv("CALIBURN_REBUILD_PDF_FONT_PATH", str(tmp_path / "absent.ttf"))
    for variable in (
        "CALIBURN_REBUILD_AGENT_CONFIG",
        "CALIBURN_REBUILD_AGENT_CHECKPOINT_CONNINFO",
        "CALIBURN_REBUILD_PDF_CHROMIUM_PATH",
    ):
        monkeypatch.delenv(variable, raising=False)
    monkeypatch.setenv(
        "CALIBURN_REBUILD_REFERENCE_CONFIG",
        str(write_reference_configuration(tmp_path)),
    )

    async def run() -> None:
        app = create_app()
        async with (
            app.router.lifespan_context(app),
            httpx2.AsyncClient(
                transport=httpx2.ASGITransport(app=app), base_url="http://testserver"
            ) as client,
        ):
            workspace = await client.post(
                "/workspaces", json={"interviewee_name": "Must not be exported"}
            )
            assert workspace.status_code == 201, workspace.text
            path = workspace.headers["Location"]
            jd = (await client.get(path + "/job-description")).json()
            exported = await client.get(
                f"{path}/job-descriptions/{jd['job_description_id']}/export.pdf"
            )
            assert exported.status_code == 503, exported.text
            assert exported.json() == {"detail": {"code": "pdf_font_unavailable"}}
            assert not exported.content.startswith(b"%PDF-")
            assert (await client.get(path + "/job-description")).json() == jd

    asyncio.run(run(), loop_factory=asyncio.SelectorEventLoop)
