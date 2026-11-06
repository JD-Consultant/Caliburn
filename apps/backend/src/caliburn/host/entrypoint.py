"""由明示環境設定組裝 API 與正式同源 Web Host。"""

import os
from pathlib import Path

from fastapi import FastAPI

from caliburn.host.agent_settings import load_agent_configuration
from caliburn.host.app import build_app
from caliburn.host.web import build_web_app
from caliburn.modules.job_description.infrastructure.pdf_renderer import (
    PdfConfiguration,
)
from caliburn.modules.occupation_reference.configuration import (
    load_reference_configuration,
)


def create_app() -> FastAPI:
    database_url = os.environ.get("CALIBURN_REBUILD_DATABASE_URL")
    if not database_url:
        raise ValueError("必須設定 CALIBURN_REBUILD_DATABASE_URL")
    agent_configuration = None
    checkpoint_conninfo = os.environ.get("CALIBURN_REBUILD_AGENT_CHECKPOINT_CONNINFO")
    if path := os.environ.get("CALIBURN_REBUILD_AGENT_CONFIG"):
        if not checkpoint_conninfo:
            raise ValueError("必須設定 CALIBURN_REBUILD_AGENT_CHECKPOINT_CONNINFO")
        agent_configuration = load_agent_configuration(
            Path(path), checkpoint_conninfo=checkpoint_conninfo
        )
    reference_path = os.environ.get("CALIBURN_REBUILD_REFERENCE_CONFIG")
    if not reference_path:
        raise ValueError("必須設定 CALIBURN_REBUILD_REFERENCE_CONFIG")
    reference_configuration = load_reference_configuration(Path(reference_path))
    pdf_configuration = None
    if pdf_font := os.environ.get("CALIBURN_REBUILD_PDF_FONT_PATH"):
        pdf_browser = os.environ.get("CALIBURN_REBUILD_PDF_CHROMIUM_PATH")
        pdf_configuration = PdfConfiguration(
            font_path=Path(pdf_font),
            executable_path=Path(pdf_browser) if pdf_browser else None,
        )
    web_path = os.environ.get("CALIBURN_REBUILD_WEB_DIST")
    web_dist = Path(web_path) if web_path else None
    if web_dist is not None and not (web_dist / "index.html").is_file():
        raise ValueError("CALIBURN_REBUILD_WEB_DIST 必須包含已建置的 index.html")
    app = build_app(
        database_url=database_url,
        agent_configuration=agent_configuration,
        reference_configuration=reference_configuration,
        checkpoint_conninfo=checkpoint_conninfo,
        pdf_configuration=pdf_configuration,
    )
    return build_web_app(app, web_dist) if web_dist is not None else app
