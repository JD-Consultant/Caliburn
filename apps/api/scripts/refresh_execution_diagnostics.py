"""Populate DataGrip diagnostic views from saved native checkpoints; no model requests."""

import argparse
import os
import sys
from uuid import UUID

import psycopg

from caliburn.adapters.database_settings import DatabaseSettings
from caliburn.diagnostics.refresh import refresh_diagnostics


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    scope = parser.add_mutually_exclusive_group(required=True)
    scope.add_argument("--job-file-id", type=UUID)
    scope.add_argument("--execution-id", type=UUID)
    args = parser.parse_args()
    url = os.environ.get("CALIBURN_DATABASE_URL")
    if not url:
        parser.error("Set CALIBURN_DATABASE_URL (same database as the real app)")
    try:
        count = refresh_diagnostics(
            DatabaseSettings(
                url=url, schema=os.environ.get("CALIBURN_DATABASE_SCHEMA", "caliburn")
            ),
            job_file_id=args.job_file_id,
            execution_id=args.execution_id,
        )
    except (psycopg.Error, ValueError, TypeError) as error:
        # DB errors and serializer errors can include private data or connection credentials.
        print(
            f"Diagnostic refresh failed ({type(error).__name__}); no partial copy saved.",
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
