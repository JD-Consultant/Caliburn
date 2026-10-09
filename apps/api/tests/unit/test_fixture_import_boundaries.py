"""Recovery support imports independently of test modules and their private APIs."""

import subprocess
import sys
from pathlib import Path


def test_crash_worker_and_builders_do_not_import_test_cases() -> None:
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "import sys; "
                "import tests.fixtures.consultant_crash_worker; "
                "import tests.fixtures.consultant_turn; "
                "from tests.fixtures.response_loop import response_at; "
                "assert response_at(2, final=True, tools=1).id == 'response_2'; "
                "assert not [name for name in sys.modules "
                "if name.startswith(('tests.unit.', 'tests.integration.'))]"
            ),
        ],
        cwd=Path(__file__).parents[2],
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=30,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
