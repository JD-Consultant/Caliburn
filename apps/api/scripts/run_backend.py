"""Run the local backend with optional explicit OpenAI credentials.

Database and PDF configuration use target environment variables documented in README.
This does not migrate, erase, seed or start PostgreSQL, and does not switch production.
"""

import argparse
from dataclasses import replace
from pathlib import Path

import uvicorn

from caliburn.adapters.openai_credentials import read_openai_api_key
from caliburn.bootstrap import create_app
from caliburn.settings import ModelSettings, Settings


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--key-file", type=Path)
    parser.add_argument(
        "--host",
        choices=("127.0.0.1", "0.0.0.0"),
        default="127.0.0.1",
        help="Use 0.0.0.0 only inside a container published to host loopback.",
    )
    # The default is the Demo port; isolated evaluation backends choose another one.
    parser.add_argument("--port", type=int, default=8100)
    arguments = parser.parse_args()
    configured = Settings.from_environment()
    if arguments.key_file is not None:
        try:
            key = read_openai_api_key(arguments.key_file)
        except OSError, ValueError:
            parser.error("The selected file must contain exactly one plain OPENAI_API_KEY.")
        configured = replace(
            configured,
            model=ModelSettings(api_key=key),
        )
    if configured.database is None:
        parser.error("Configure CALIBURN_DATABASE_URL for the isolated target database.")
    uvicorn.run(
        create_app(configured),
        host=arguments.host,
        port=arguments.port,
        loop="asyncio:SelectorEventLoop",
        proxy_headers=False,
    )


if __name__ == "__main__":
    main()
