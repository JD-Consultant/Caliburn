"""管理命令可由安裝套件執行，不依賴 checkout 或外送模型。"""

import json
import os
import subprocess
import sys
from dataclasses import asdict
from importlib.resources import files
from pathlib import Path
from typing import NoReturn

import pytest
from alembic.config import Config
from alembic.script import ScriptDirectory
from qdrant_client import QdrantClient, models
from sqlalchemy import Engine, event

from caliburn.modules.occupation_reference.configuration import ReferenceConfiguration
from caliburn.modules.occupation_reference.domain.source import PREPROCESSING
from caliburn.modules.occupation_reference.infrastructure.models.local import (
    embedding_signature,
)
from caliburn.modules.occupation_reference.infrastructure.qdrant.store import (
    MANIFEST_ID,
    IndexManifest,
)
from caliburn.status import database_status, reference_status


def test_migration_command_exposes_explicit_checkpoint_setup(tmp_path: Path) -> None:
    result = subprocess.run(
        [sys.executable, "-X", "utf8", "-m", "caliburn.migrate", "--help"],
        cwd=tmp_path,
        capture_output=True,
        encoding="utf-8",
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert "--with-checkpoints" in result.stdout


def test_migrations_are_resolved_from_the_installed_package() -> None:
    assert files("caliburn").joinpath("migrations", "env.py").is_file()
    config = Config()
    config.set_main_option("script_location", "caliburn:migrations")
    scripts = ScriptDirectory.from_config(config)
    assert scripts.get_heads() == ["0009_jd_citations"]
    assert len(list(scripts.walk_revisions())) == 9


def test_status_without_settings_returns_safe_failure_json(tmp_path: Path) -> None:
    environment = {
        name: value
        for name, value in os.environ.items()
        if not name.startswith("CALIBURN_REBUILD_")
    }
    result = subprocess.run(
        [sys.executable, "-X", "utf8", "-m", "caliburn.status"],
        cwd=tmp_path,
        env=environment,
        capture_output=True,
        encoding="utf-8",
        check=False,
    )
    assert result.returncode == 1
    assert '"not_configured"' in result.stdout
    assert result.stderr == ""


@pytest.mark.parametrize("module", ["caliburn.migrate", "caliburn.status"])
def test_cli_does_not_expose_invalid_connection_settings(
    tmp_path: Path, module: str
) -> None:
    environment = {
        name: value
        for name, value in os.environ.items()
        if not name.startswith("CALIBURN_REBUILD_")
    }
    environment["CALIBURN_REBUILD_DATABASE_URL"] = "invalid://secret-credential"
    args = [sys.executable, "-X", "utf8", "-m", module]
    if module == "caliburn.migrate":
        args.extend(["upgrade", "head"])
    result = subprocess.run(
        args,
        cwd=tmp_path,
        env=environment,
        capture_output=True,
        encoding="utf-8",
        check=False,
    )
    assert result.returncode == 1
    assert "secret-credential" not in result.stdout + result.stderr
    assert json.loads(result.stdout)["status"] in {"failed", "not_ready"}
    assert result.stderr == ""


def test_reference_status_rejects_invalid_configuration_without_loading_models(
    tmp_path: Path,
) -> None:
    configuration = tmp_path / "reference.json"
    configuration.write_text('{"collection": "test", "invalid": "secret"}')
    assert reference_status(str(configuration)) == {"status": "invalid_configuration"}


def test_reference_status_validates_existing_index_without_model_sdks(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    client = QdrantClient(location=":memory:")
    client.create_collection("status_test", vectors_config={})
    client.upsert(
        "status_test",
        points=[
            models.PointStruct(
                id=MANIFEST_ID,
                vector={},
                payload=IndexManifest(
                    preprocessing=PREPROCESSING,
                    **asdict(embedding_signature()),
                    document_count=1,
                    point_count=1,
                ).model_dump(),
            )
        ],
    )
    monkeypatch.setattr(
        "caliburn.modules.occupation_reference.bootstrap.QdrantClient",
        lambda **kwargs: client,
    )
    monkeypatch.setitem(sys.modules, "torch", None)
    monkeypatch.setitem(sys.modules, "transformers", None)
    configuration = tmp_path / "reference.json"
    configuration.write_text(
        ReferenceConfiguration(collection="status_test").model_dump_json(),
        encoding="utf-8",
    )

    assert reference_status(str(configuration)) == {"status": "ready"}


def test_database_status_bounds_the_driver_connection_timeout() -> None:
    parameters: dict[str, object] = {}

    def stop_before_connect(
        dialect: object,
        connection_record: object,
        args: list[object],
        kwargs: dict[str, object],
    ) -> NoReturn:
        parameters.update(kwargs)
        raise RuntimeError("No network access in this driver configuration test")

    event.listen(Engine, "do_connect", stop_before_connect)
    try:
        assert database_status(
            "postgresql+psycopg://localhost/status_test?connect_timeout=120"
        ) == {"status": "unavailable"}
    finally:
        event.remove(Engine, "do_connect", stop_before_connect)
    assert parameters["connect_timeout"] == "5"
