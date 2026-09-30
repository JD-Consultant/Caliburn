"""A deployed package must discover migration history without a source checkout."""

import json
import shutil
import subprocess
import sys
from pathlib import Path

import caliburn


def test_migration_history_is_available_outside_the_source_checkout(tmp_path: Path) -> None:
    package = tmp_path / "caliburn"
    shutil.copytree(
        Path(caliburn.__file__).parent,
        package,
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
    )
    result = subprocess.run(
        [
            sys.executable,
            "-I",
            "-B",
            "-c",
            "import json, sys; from pathlib import Path; "
            "sys.path.insert(0, sys.argv[1]); "
            "import caliburn; "
            "assert Path(caliburn.__file__).parent == Path(sys.argv[1]) / 'caliburn'; "
            "from caliburn.adapters.database import migration_config; "
            "from alembic.script import ScriptDirectory; "
            "scripts = ScriptDirectory.from_config(migration_config()); "
            "print(json.dumps([r.revision for r in scripts.walk_revisions()]))",
            str(tmp_path),
        ],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=30,
    )

    assert result.returncode == 0, result.stderr
    revisions = json.loads(result.stdout)
    assert "0001_job_files" in revisions
    assert "0019_optional_cost_limit" in revisions
