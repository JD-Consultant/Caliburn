"""Use the product's existing credential reader; do not install a dotenv dependency."""

import asyncio
import os

from caliburn.adapters.openai_credentials import read_openai_api_key
from run_reading_probe import OUTPUT, ROOT, execute
from study_manifest import file_hash, save_new


if __name__ == "__main__":
    os.environ["OPENAI_API_KEY"] = os.environ.get("OPENAI_API_KEY") or read_openai_api_key(
        ROOT / "apps/api/.env"
    )
    save_new(OUTPUT / "launch-note.json", {
        "reason": "The original CLI imported unavailable python-dotenv before admission. No started.json, trace or paid requests existed. This launcher uses the existing product credential reader and calls the same frozen execute().",
        "launcher_sha256": file_hash(__import__("pathlib").Path(__file__)),
        "credential_reader_sha256": file_hash(ROOT / "apps/api/src/caliburn/adapters/openai_credentials.py"),
        "changes_to_frozen_materials": False,
    })
    with asyncio.Runner(loop_factory=asyncio.SelectorEventLoop) as loop:
        loop.run(execute())
