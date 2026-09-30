"""Run the loopback development backend with optional explicit OpenAI credentials.

Database and PDF configuration use target environment variables documented in README.
This does not migrate, erase, seed or start PostgreSQL, and does not switch production.
"""

import argparse
import os
from dataclasses import replace
from decimal import Decimal
from pathlib import Path

import uvicorn

from caliburn.adapters.openai_credentials import read_openai_api_key
from caliburn.bootstrap import create_app
from caliburn.settings import ModelSettings, Settings


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--key-file", type=Path)
    arguments = parser.parse_args()
    configured = Settings.from_environment()
    if arguments.key_file is not None:
        try:
            key = read_openai_api_key(arguments.key_file)
        except OSError, ValueError:
            parser.error("The selected file must contain exactly one plain OPENAI_API_KEY.")
        configured = replace(
            configured,
            model=ModelSettings(
                api_key=key,
                max_cost_usd=Decimal(os.environ.get("CALIBURN_TURN_MAX_COST_USD", "1.00")),
            ),
        )
    if configured.database is None:
        parser.error("Configure CALIBURN_DATABASE_URL for the isolated target database.")
    uvicorn.run(
        create_app(configured), host="127.0.0.1", port=8100, loop="asyncio:SelectorEventLoop"
    )


if __name__ == "__main__":
    main()
