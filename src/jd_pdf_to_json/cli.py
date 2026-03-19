"""CLI entry point."""

import typer
from pathlib import Path
from jd_pdf_to_json.utils.logger import logger

app = typer.Typer(
    help="OCS vocational competency PDF to JSON converter",
    no_args_is_help=True,
)


@app.command()
def convert(
    pdf_path: Path = typer.Argument(..., help="Input PDF file", exists=True),
    output_path: Path = typer.Option(
        None, "--output", "-o", help="Output JSON file (default: input_name.json)"
    ),
    validate: bool = typer.Option(True, "--validate", help="Enable schema validation"),
) -> None:
    """Convert single OCS PDF to JSON."""
    if output_path is None:
        output_path = pdf_path.with_suffix(".json")
    
    logger.info(f"Converting {pdf_path} → {output_path}")
    logger.info(f"Validation: {'enabled' if validate else 'disabled'}")
    
    # TODO: Implement conversion pipeline
    typer.echo("✓ Conversion pipeline to be implemented")


@app.command()
def batch(
    input_dir: Path = typer.Argument(..., help="Directory with PDFs", exists=True),
    output_dir: Path = typer.Option(..., "--output", "-o", help="Output directory"),
) -> None:
    """Batch convert OCS PDFs from directory."""
    logger.info(f"Batch converting PDFs from {input_dir}")
    logger.info(f"Output directory: {output_dir}")
    
    # TODO: Implement batch conversion
    typer.echo("✓ Batch conversion pipeline to be implemented")


@app.command()
def validate(
    json_path: Path = typer.Argument(..., help="JSON file to validate", exists=True),
) -> None:
    """Validate OCS JSON against schema."""
    logger.info(f"Validating {json_path}")
    
    # TODO: Implement validation
    typer.echo("✓ Validation pipeline to be implemented")


@app.callback()
def main(
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable verbose logging"),
) -> None:
    """OCS PDF to JSON Converter."""
    if verbose:
        from jd_pdf_to_json.utils.logger import logger
        logger.enable("jd_pdf_to_json")


if __name__ == "__main__":
    app()
