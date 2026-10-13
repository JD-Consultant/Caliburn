"""在同一唯讀快照查閱本機 AI 執行原件，不啟動 Agent。"""

import argparse
import asyncio
import io
import json
import os
import sys
from uuid import UUID

from caliburn.adapters.database_settings import DatabaseSettings
from caliburn.diagnostics.inspection import read_diagnostics


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    scope = parser.add_mutually_exclusive_group(required=True)
    scope.add_argument("--job-file-id", type=UUID, help="List this file's rounds.")
    scope.add_argument("--execution-id", type=UUID, help="Inspect one round's saved Steps.")
    parser.add_argument(
        "--request-id", type=UUID, help="Select a logical Step within --execution-id."
    )
    parser.add_argument(
        "--full",
        action="store_true",
        help="Include original content and fixed historical bodies as JSON.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=100,
        help="Maximum overview rounds (default: 100); full exports include all rounds.",
    )
    parser.add_argument(
        "--after", type=UUID, help="Continue the file overview after this execution ID."
    )
    args = parser.parse_args()
    if args.request_id is not None and args.execution_id is None:
        parser.error("--request-id requires --execution-id")
    if args.after is not None and (args.job_file_id is None or args.full):
        parser.error("--after requires a file overview without --full")
    url = os.environ.get("CALIBURN_DATABASE_URL")
    if not url:
        parser.error("Set CALIBURN_DATABASE_URL to the application database")
    try:
        settings = DatabaseSettings(
            url=url, schema=os.environ.get("CALIBURN_DATABASE_SCHEMA", "caliburn")
        )
        with asyncio.Runner(loop_factory=asyncio.SelectorEventLoop) as runner:
            documents = runner.run(
                read_diagnostics(
                    settings,
                    job_file_id=args.job_file_id,
                    execution_id=args.execution_id,
                    request_id=args.request_id,
                    full=args.full,
                    limit=args.limit,
                    after=args.after,
                )
            )
        # Windows 管線可能預設 ANSI；JSON 匯出固定用 UTF-8。
        if isinstance(sys.stdout, io.TextIOWrapper):
            sys.stdout.reconfigure(encoding="utf-8")
        print(json.dumps(documents, ensure_ascii=False, indent=2))
    except Exception as error:
        # Database and serializer exceptions may contain originals or credentials.
        print(
            f"Diagnostic read failed ({type(error).__name__}); no output exported.", file=sys.stderr
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
