"""The operator diagnostic names what is configured and never prints a secret."""

from pathlib import Path

from caliburn.adapters.database_settings import DatabaseSettings
from caliburn.settings import ModelSettings, PdfSettings, Settings
from caliburn.status import describe_settings

SECRET_KEY = "sk-status-test-0123456789abcdef"
PASSWORD = "p4ssw0rd-hidden"


async def test_an_empty_configuration_is_reported_not_failed() -> None:
    lines, healthy = await describe_settings(Settings())

    assert healthy
    assert [line.split(":")[0].strip() for line in lines] == ["database", "model", "pdf", "web"]
    assert all("not configured" in line for line in lines)


async def test_an_unreachable_database_is_unhealthy_and_hides_the_password() -> None:
    settings = Settings(
        database=DatabaseSettings(url=f"postgresql://operator:{PASSWORD}@127.0.0.1:1/caliburn")
    )

    lines, healthy = await describe_settings(settings)

    assert not healthy
    assert "NOT usable" in lines[0] and "127.0.0.1:1/caliburn" in lines[0]
    assert PASSWORD not in "\n".join(lines)


async def test_a_configured_model_shows_its_name_but_never_the_key() -> None:
    lines, healthy = await describe_settings(Settings(model=ModelSettings(api_key=SECRET_KEY)))

    text = "\n".join(lines)
    assert healthy
    assert "gpt-6-luna" in text and "reasoning high" in text and "(hidden)" in text
    assert SECRET_KEY not in text


async def test_pdf_and_web_paths_must_exist_to_be_healthy(tmp_path: Path) -> None:
    missing = Settings(
        pdf=PdfSettings(font_path=tmp_path / "missing.ttf"), web_build_directory=tmp_path / "dist"
    )
    lines, healthy = await describe_settings(missing)
    assert not healthy
    assert "MISSING" in lines[2] and "MISSING" in lines[3]

    (tmp_path / "dist").mkdir()
    (tmp_path / "dist" / "index.html").write_text("<html></html>", encoding="utf-8")
    font = tmp_path / "font.ttf"
    font.write_bytes(b"synthetic")
    lines, healthy = await describe_settings(
        Settings(pdf=PdfSettings(font_path=font), web_build_directory=tmp_path / "dist")
    )
    assert healthy
    assert "font ok" in lines[2] and "build found" in lines[3]
