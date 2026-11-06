"""Explicit local maintenance: convert, clean, validate or index OCS documents."""

import argparse
import json
from pathlib import Path

from ocs_contract.models import OCSDocument

from caliburn.modules.occupation_reference.bootstrap import open_reference_resources
from caliburn.modules.occupation_reference.configuration import (
    load_reference_configuration,
)
from caliburn.modules.occupation_reference.domain.source import build_reference
from caliburn.modules.occupation_reference.infrastructure.cleaning import (
    clean_json_files,
)
from caliburn.modules.occupation_reference.infrastructure.pdf.batch import convert_pdfs
from caliburn.modules.occupation_reference.infrastructure.pdf.validators.schema import (
    OCSSchemaValidator,
)
from caliburn.modules.occupation_reference.infrastructure.qdrant.store import (
    index_references,
)


def validate_json(source: Path) -> int:
    """Validate the generated OCS shape and content rules without changing input."""
    try:
        document = OCSDocument.model_validate_json(source.read_bytes())
    except (OSError, ValueError) as error:
        valid, errors = False, [str(error)]
    else:
        valid, errors = OCSSchemaValidator().validate(document)
    print(json.dumps({"valid": valid, "errors": errors}))
    return 0 if valid else 1


def create_index(source: Path, configuration_path: Path, *, batch_size: int) -> int:
    """Select explicit JSON versions, preserving source bytes and old indexes."""
    if not source.is_dir():
        raise ValueError("selected source directory does not exist")
    documents = [
        build_reference(
            path.read_bytes().decode("utf-8"),
            source_file=path.relative_to(source).as_posix(),
        )
        for path in sorted(source.rglob("*.json"))
    ]
    configuration = load_reference_configuration(configuration_path)
    with open_reference_resources(configuration) as resources:
        count = index_references(
            resources.client,
            configuration.collection,
            documents,
            resources.models,
            batch_size=batch_size,
        )
    print(json.dumps({"collection": configuration.collection, "point_count": count}))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    convert = commands.add_parser("convert-pdf", help="Convert selected OCS PDFs")
    convert.add_argument("source", type=Path)
    convert.add_argument("output", type=Path)
    convert.add_argument("--diagnostics", type=Path, required=True)
    convert.add_argument("--exclude-historical", action="store_true")
    clean = commands.add_parser("clean-json", help="Write separate cleaned OCS JSON")
    clean.add_argument("source", type=Path)
    clean.add_argument("output", type=Path)
    clean.add_argument("--diagnostics", type=Path, required=True)
    validate = commands.add_parser("validate-json", help="Validate selected OCS JSON")
    validate.add_argument("source", type=Path)
    index = commands.add_parser("index", help="Build only a new Qdrant collection")
    index.add_argument("source", type=Path)
    index.add_argument("--config", type=Path, required=True)
    index.add_argument("--batch-size", type=int, default=32)
    arguments = parser.parse_args(argv)
    if arguments.command == "convert-pdf":
        summary = convert_pdfs(
            arguments.source,
            arguments.output,
            arguments.diagnostics,
            exclude_historical=arguments.exclude_historical,
        )
        print(json.dumps(summary))
        return 1 if summary["rejected"] else 0
    if arguments.command == "validate-json":
        return validate_json(arguments.source)
    if arguments.command == "clean-json":
        cleaning_summary = clean_json_files(
            arguments.source, arguments.output, arguments.diagnostics
        )
        print(json.dumps(cleaning_summary))
        return 1 if cleaning_summary["rejected"] else 0
    return create_index(
        arguments.source, arguments.config, batch_size=arguments.batch_size
    )
