"""Run the two locked generators against one schema source, or check for drift."""

import argparse
import difflib
import json
import subprocess
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from urllib.parse import unquote, urlsplit

API_ROOT = Path(__file__).resolve().parents[1]
WEB_ROOT = API_ROOT.parent / "web"


def stage_contract_schemas(
    schemas: list[Path], directory: Path, *, contracts_root: Path
) -> dict[Path, Path]:
    """Stage trusted local references under one generator input base; never fetch URLs."""
    if len({schema.name for schema in schemas}) != len(schemas):
        raise ValueError("Canonical schemas must have unique filenames across families")
    contracts_root = contracts_root.resolve()
    known = {schema.resolve() for schema in schemas}
    staged = {schema: directory / schema.name for schema in schemas}

    def relocate(value: object, source: Path) -> object:
        if isinstance(value, list):
            return [relocate(item, source) for item in value]
        if not isinstance(value, dict):
            return value
        result = {key: relocate(item, source) for key, item in value.items()}
        reference = result.get("$ref")
        if not isinstance(reference, str) or reference.startswith("#"):
            return result
        parsed = urlsplit(reference)
        if parsed.scheme or parsed.netloc or parsed.query:
            raise ValueError("Canonical contracts only permit local schema references")
        target = (source.parent / unquote(parsed.path)).resolve()
        if not target.is_relative_to(contracts_root) or target not in known:
            raise ValueError("Schema references must resolve to a canonical contract")
        result["$ref"] = target.name + ("#" + parsed.fragment if parsed.fragment else "")
        return result

    directory.mkdir(parents=True, exist_ok=True)
    for schema, target in staged.items():
        content = relocate(json.loads(schema.read_text(encoding="utf-8")), schema)
        target.write_text(
            json.dumps(content, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
    return staged


def generate(check: bool, schema_names: list[str] | None = None) -> bool:
    matches = True
    schemas = [
        schema
        for family in ("http", "tools")
        for schema in sorted((API_ROOT / "contracts" / family).glob("*.schema.json"))
    ]
    all_schemas = schemas
    if schema_names is not None:
        available = {schema.name for schema in schemas}
        if unknown := set(schema_names) - available:
            raise ValueError(f"Unknown schemas: {sorted(unknown)}")
        schemas = [schema for schema in schemas if schema.name in schema_names]
    with TemporaryDirectory(prefix="caliburn-codegen-") as directory:
        staged = stage_contract_schemas(
            all_schemas, Path(directory) / "schemas", contracts_root=API_ROOT / "contracts"
        )
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
                    str(staged[schema]),
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
    parser.add_argument(
        "--schema",
        action="append",
        help="Generate only this schema filename; repeat to select more.",
    )
    arguments = parser.parse_args()
    sys.exit(0 if generate(arguments.check, arguments.schema) else 1)
