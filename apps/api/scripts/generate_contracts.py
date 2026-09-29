"""Run the two locked generators against one schema source, or check for drift."""

import argparse
import difflib
import subprocess
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

API_ROOT = Path(__file__).resolve().parents[1]
WEB_ROOT = API_ROOT.parent / "web"


def generate(check: bool) -> bool:
    matches = True
    schemas = [
        schema
        for family in ("http", "tools")
        for schema in sorted((API_ROOT / "contracts" / family).glob("*.schema.json"))
    ]
    with TemporaryDirectory(prefix="caliburn-codegen-") as directory:
        for schema in schemas:
            stem = schema.name.removesuffix(".schema.json")
            output_directory = Path("tools") if schema.parent.name == "tools" else Path()
            python_output = Path(directory) / output_directory / f"{stem.replace('-', '_')}.py"
            python_output.parent.mkdir(parents=True, exist_ok=True)
            subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "datamodel_code_generator",
                    "--input",
                    str(schema),
                    "--input-file-type",
                    "jsonschema",
                    "--no-allow-remote-refs",
                    "--strict-refs",
                    "--output",
                    str(python_output),
                    "--output-model-type",
                    "pydantic_v2.BaseModel",
                    "--target-python-version",
                    "3.14",
                    "--disable-timestamp",
                    "--use-standard-collections",
                    "--use-union-operator",
                    "--capitalize-enum-members",
                    "--field-constraints",
                    "--formatters",
                    "ruff-check",
                    "ruff-format",
                    "--strict-types",
                    "str",
                    "int",
                    "float",
                    "bool",
                ],
                check=True,
            )
            typescript = subprocess.run(
                ["node", str(WEB_ROOT / "scripts/generate-contract.mjs"), str(schema)],
                capture_output=True,
                text=True,
                encoding="utf-8",
                check=True,
            ).stdout
            outputs = {
                API_ROOT
                / "src/caliburn/contracts/generated"
                / output_directory
                / python_output.name: python_output.read_text(encoding="utf-8"),
                WEB_ROOT / "src/shared/api/generated" / output_directory / f"{stem}.ts": typescript,
            }
            if schema.parent.name == "tools":
                outputs[API_ROOT / "src/caliburn/contracts/generated/tools" / schema.name] = (
                    schema.read_text(encoding="utf-8", newline="")
                )
            for target, content in outputs.items():
                if check:
                    # Packaged schemas retain the authored wire, including its line endings.
                    newline = "" if target.suffix == ".json" else None
                    existing = (
                        target.read_text(encoding="utf-8", newline=newline)
                        if target.exists()
                        else ""
                    )
                    if existing != content:
                        matches = False
                        print(
                            "".join(
                                difflib.unified_diff(
                                    existing.splitlines(keepends=True),
                                    content.splitlines(keepends=True),
                                    fromfile=str(target),
                                    tofile="regenerated",
                                )
                            ),
                            end="",
                        )
                else:
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_text(content, encoding="utf-8", newline="\n")
    return matches


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    sys.exit(0 if generate(parser.parse_args().check) else 1)
