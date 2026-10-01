"""Operator diagnostics: what the next start would use, without starting or changing anything.

Reads the same explicit settings as the server. It prints names and states only, never the
database password or the OpenAI key, and never starts a model request, migration or process.
"""

import asyncio
import sys

from sqlalchemy.engine import make_url

from caliburn.adapters.database import Database
from caliburn.settings import Settings


async def describe_settings(settings: Settings) -> tuple[list[str], bool]:
    """One line per capability and whether anything configured is unusable."""
    lines: list[str] = []
    healthy = True

    if settings.database is None:
        lines.append(
            "database : not configured (set CALIBURN_DATABASE_URL); the API serves health only"
        )
    else:
        url = make_url(settings.database.url)
        target = f"{url.host}:{url.port}/{url.database}, schema {settings.database.schema}"
        database = Database(settings.database)
        try:
            await database.verify_schema()
            lines.append(f"database : {target} reachable, migrations at head")
        except Exception as error:  # Diagnostic boundary: report the kind, never the message.
            healthy = False
            lines.append(
                f"database : {target} NOT usable ({type(error).__name__}); "
                "run `pnpm app:migrate` after creating the database"
            )
        finally:
            await database.close()

    if settings.model is None:
        lines.append(
            "model    : not configured (set OPENAI_API_KEY or provide apps/api/.env); "
            "manual JD editing works, AI interviews are disabled"
        )
    else:
        lines.append(
            f"model    : OpenAI key configured (hidden); {settings.model.model}, "
            f"reasoning {settings.model.reasoning_effort}"
        )

    if settings.pdf is None:
        lines.append("pdf      : not configured (set CALIBURN_PDF_FONT_PATH); export returns 503")
    else:
        font = settings.pdf.font_path.is_file()
        browser = settings.pdf.executable_path is None or settings.pdf.executable_path.is_file()
        healthy = healthy and font and browser
        lines.append(
            f"pdf      : font {'ok' if font else 'MISSING'}; "
            + (
                "Playwright's installed browser"
                if settings.pdf.executable_path is None
                else f"browser {'ok' if browser else 'MISSING'}"
            )
        )

    if settings.web_build_directory is None:
        lines.append("web      : not configured; the API does not serve the UI")
    else:
        built = (settings.web_build_directory / "index.html").is_file()
        healthy = healthy and built
        lines.append(f"web      : {'build found' if built else 'build MISSING (run pnpm build)'}")
    return lines, healthy


def main() -> int:
    settings = Settings.from_environment()
    lines, healthy = asyncio.run(
        describe_settings(settings), loop_factory=asyncio.SelectorEventLoop
    )
    print("\n".join(lines))
    return 0 if healthy else 1


if __name__ == "__main__":
    sys.exit(main())
