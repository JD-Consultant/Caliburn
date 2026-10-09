"""Generate the OCS Python contract, or compare it without changing working files."""

import argparse
import subprocess
import sys
from pathlib import Path
from tempfile import TemporaryDirectory


def generate_contract(root: Path, *, check: bool) -> bool:
    target = root / "src/ocs_contract/models.py"
    with TemporaryDirectory(prefix="caliburn-ocs-codegen-") as directory:
        output = Path(directory) / "models.py"
        subprocess.run(
            [
                sys.executable,
                "-m",
                "datamodel_code_generator",
                "--input",
                "schema/ocs-document.schema.json",
                "--input-file-type",
                "jsonschema",
                "--output",
                str(output),
                "--output-model-type",
                "pydantic_v2.BaseModel",
                "--use-standard-collections",
                "--use-union-operator",
                "--use-schema-description",
                "--target-python-version",
                "3.11",
                "--disable-timestamp",
                "--formatters",
                "black",
                "isort",
            ],
            cwd=root,
            check=True,
        )
        generated = output.read_text(encoding="utf-8")
        if check:
            # Python source may be checked out with LF or CRLF. Never rewrite either.
            matches = (
                target.exists() and target.read_text(encoding="utf-8") == generated
            )
            if not matches:
                print(
                    "OCS models differ from schema; run pnpm --filter @caliburn/ocs-contract codegen."
                )
            return matches
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(generated, encoding="utf-8", newline="\n")
        return True


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check", action="store_true", help="Compare without writing source files"
    )
    options = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    try:
        return 0 if generate_contract(root, check=options.check) else 1
    except subprocess.CalledProcessError as error:
        print(
            f"OCS generator failed with exit code {error.returncode}.", file=sys.stderr
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
