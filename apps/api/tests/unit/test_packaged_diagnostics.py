"""診斷 CLI 隨套件交付，不依賴 checkout scripts 或模型 key。"""

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

import caliburn


def test_diagnostic_help_is_available_from_the_package_alone(tmp_path):
    shutil.copytree(
        Path(caliburn.__file__).parent,
        tmp_path / "caliburn",
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
    )
    result = subprocess.run(
        [
            sys.executable,
            "-I",
            "-X",
            "utf8",
            "-B",
            "-c",
            "import runpy, sys; from pathlib import Path; "
            "sys.path.insert(0, sys.argv.pop(1)); "
            "import caliburn; assert Path(caliburn.__file__).parent == Path.cwd() / 'caliburn'; "
            "runpy.run_module('caliburn.diagnostics', run_name='__main__')",
            str(tmp_path),
            "--help",
        ],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=30,
    )
    assert result.returncode == 0, result.stderr
    assert "--execution-id" in result.stdout
    assert "--full" in result.stdout


@pytest.mark.parametrize("stdout_encoding", ["ascii", "cp1252"])
def test_cli_redirects_readable_unicode_as_utf8_without_changing_json(stdout_encoding):
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            """
from caliburn.diagnostics import __main__ as cli
async def read_saved(*args, **kwargs):
    return [{"text": '\u76e4\u9ede\U0001f4cb "quoted"\\nnext'}]
cli.read_diagnostics = read_saved
raise SystemExit(cli.main())
""",
            "--execution-id",
            "00000000-0000-4000-8000-000000000001",
        ],
        env={
            **os.environ,
            "CALIBURN_DATABASE_URL": "postgresql://unused@127.0.0.1/unused",
            "PYTHONIOENCODING": stdout_encoding,
            "PYTHONUTF8": "0",
        },
        capture_output=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr
    output = result.stdout.decode("utf-8")
    assert "盤點📋" in output
    assert json.loads(output) == [{"text": '盤點📋 "quoted"\nnext'}]
