"""Populate DataGrip diagnostic views from saved native checkpoints; no model requests."""

import argparse
import json
import os
import sys
from uuid import UUID

import psycopg

from caliburn.adapters.database_settings import DatabaseSettings
from caliburn.diagnostics.inspection import read_diagnostics
from caliburn.diagnostics.refresh import refresh_diagnostics


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    scope = parser.add_mutually_exclusive_group(required=True)
    scope.add_argument("--job-file-id", type=UUID)
    scope.add_argument("--execution-id", type=UUID)
    parser.add_argument(
        "--show",
        action="store_true",
        help="Read the existing diagnostic copy as JSON, including controlled content; no refresh.",
    )
    args = parser.parse_args()
    url = os.environ.get("CALIBURN_DATABASE_URL")
    if not url:
        parser.error("Set CALIBURN_DATABASE_URL (same database as the real app)")
    try:
        settings = DatabaseSettings(
            url=url, schema=os.environ.get("CALIBURN_DATABASE_SCHEMA", "caliburn")
        )
        if args.show:
            documents = read_diagnostics(
                settings, job_file_id=args.job_file_id, execution_id=args.execution_id
            )
            print(json.dumps(documents, ensure_ascii=True, indent=2))
            return 0
        count = refresh_diagnostics(
            settings,
            job_file_id=args.job_file_id,
            execution_id=args.execution_id,
        )
    except (psycopg.Error, ValueError, TypeError) as error:
        # DB／serializer 例外可能含正文或憑證，只回報安全類別。
        print(
            f"Diagnostic {'read' if args.show else 'refresh'} failed "
            f"({type(error).__name__}); no partial copy saved.",
            file=sys.stderr,
        )
        return 1
    print(
        f"Refreshed {count} execution(s). Open diagnostic_execution_history / "
        "diagnostic_model_steps / diagnostic_tool_calls."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
