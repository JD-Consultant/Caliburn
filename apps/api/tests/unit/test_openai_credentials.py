"""An explicit key file must never import unrelated legacy application settings."""

from pathlib import Path

import pytest

from caliburn.adapters.openai_credentials import read_openai_api_key


def test_reads_only_the_requested_key_without_applying_other_settings(tmp_path, monkeypatch):
    monkeypatch.delenv("LEGACY_DATABASE_URL", raising=False)
    path: Path = tmp_path / "credentials.env"
    path.write_text(
        '# synthetic fixture\nLEGACY_DATABASE_URL=do-not-load\nOPENAI_API_KEY="synthetic-key"\n',
        encoding="utf-8-sig",
    )
    assert read_openai_api_key(path) == "synthetic-key"
    import os

    assert "LEGACY_DATABASE_URL" not in os.environ


@pytest.mark.parametrize(
    "content",
    ["", "OPENAI_API_KEY=", "OPENAI_API_KEY=a\nOPENAI_API_KEY=b", "OPENAI_API_KEY=$(command)"],
)
def test_missing_ambiguous_or_executable_values_are_rejected_without_echo(tmp_path, content):
    path = tmp_path / "credentials.env"
    path.write_text(content, encoding="utf-8")
    with pytest.raises(ValueError, match="Exactly one plain OPENAI_API_KEY"):
        read_openai_api_key(path)
