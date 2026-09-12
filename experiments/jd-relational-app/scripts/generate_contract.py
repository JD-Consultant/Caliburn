"""Run pinned standard generators; check mode never rewrites committed outputs."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
SCHEMAS = [("jd-work", "models.py"), ("jd-result", "results.py"), ("jd-http", "http_results.py"),
           ("jd-snapshot", "snapshots.py"), ("jd-read", "reads.py")]
OUTPUT = ROOT / "src" / "jd_relational" / "generated"


def run(command: list[str]) -> str:
    result = subprocess.run(
        command,
        cwd=ROOT,
        encoding="utf-8",
        capture_output=True,
        env={**os.environ, "PYTHONUTF8": "1"},
        check=False,
    )
    if result.returncode:
        # Preserve the first generator failure instead of proceeding to later output.
        sys.stderr.write(result.stdout)
        sys.stderr.write(result.stderr)
        raise SystemExit(result.returncode)
    if result.stderr:
        sys.stderr.write(result.stderr)
    return result.stdout.replace("\r\n", "\n")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    options = parser.parse_args()
    # Both standard CLIs support stdout. No intermediate files are necessary,
    # and --check cannot accidentally replace an existing generated artifact.
    expected = {}
    for name, python_output in SCHEMAS:
        schema = ROOT / "contracts" / f"{name}.schema.json"
        references = (["--external-ref-mapping",
                       f"{ROOT / 'contracts' / 'jd-result.schema.json'}=jd_relational.generated.results"]
                      if name == "jd-http" else [])
        expected[python_output] = run(
            [
                sys.executable,
                "-m",
                "datamodel_code_generator",
                "--input", str(schema),
                "--input-file-type", "jsonschema",
                "--output-model-type", "pydantic_v2.BaseModel",
                "--target-python-version", "3.12",
                "--use-title-as-name",
                "--use-standard-collections",
                "--use-union-operator",
                "--strict-types", "str", "int", "bool",
                "--enum-field-as-literal", "all",
                "--formatters", "builtin",
                "--disable-timestamp",
                "--no-allow-remote-refs",
                "--fail-on-multi-module-stdout",
                *references,
            ]
        )
        expected[f"{name}.ts"] = run(
            [
                os.environ.get("NODE_BINARY", "node"),
                str(ROOT / "node_modules" / "json-schema-to-typescript" / "dist" / "src" / "cli.js"),
                "--input", str(schema),
                "--unreachableDefinitions",
            ]
        )
    if options.check:
        changed = [
            name for name, text in expected.items()
            if not (OUTPUT / name).exists()
            or (OUTPUT / name).read_bytes() != text.encode("utf-8")
        ]
        if changed:
            raise SystemExit("Contract generation differs: " + ", ".join(changed))
        print("Contract generation matches: Python and TypeScript.")
    else:
        OUTPUT.mkdir(parents=True, exist_ok=True)
        for name, text in expected.items():
            (OUTPUT / name).write_bytes(text.encode("utf-8"))
        print("Generated contract: Python and TypeScript.")


if __name__ == "__main__":
    main()
