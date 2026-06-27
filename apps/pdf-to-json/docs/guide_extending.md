# Extending the Project

This guide explains how to extend jd-pdf-to-json with custom parsers, transformers, validators, and writers.

## Adding a Custom PDF Parser

### 1. Create Parser Class

Create a new file `src/jd_pdf_to_json/parsers/custom_parser.py`:

```python
from pathlib import Path
from jd_pdf_to_json.parsers.base import BasePDFParser
from jd_pdf_to_json.utils.exceptions import PDFParsingError

class CustomPDFParser(BasePDFParser):
    """Custom parser for specialized PDF formats."""
    
    def parse(self, pdf_path: Path) -> dict:
        """Parse PDF using custom logic."""
        if not pdf_path.exists():
            raise PDFParsingError(f"File not found: {pdf_path}")
        
        # Your custom parsing logic here
        raw_data = {
            "metadata": {...},
            "pages": [...],
        }
        return raw_data
    
    def validate_source(self, pdf_path: Path) -> bool:
        """Verify PDF is correct format."""
        # Your validation logic
        return True
```

### 2. Register in CLI

Edit `src/jd_pdf_to_json/cli.py`:

```python
from jd_pdf_to_json.parsers import PDFPlumberParser, CustomPDFParser

PARSER_OPTIONS = {
    "pdfplumber": PDFPlumberParser,
    "custom": CustomPDFParser,
}

@app.command()
def convert(
    pdf_path: Path = typer.Argument(...),
    output_path: Path = typer.Option(None, "--output", "-o"),
    parser: str = typer.Option("pdfplumber", "--parser"),
    validate: bool = typer.Option(True),
) -> None:
    """Convert PDF with selectable parser."""
    parser_class = PARSER_OPTIONS.get(parser, PDFPlumberParser)
    parser_instance = parser_class()
    # ...
```

### 3. Test Parser

Create `tests/test_custom_parser.py`:

```python
import pytest
from pathlib import Path
from jd_pdf_to_json.parsers import CustomPDFParser

def test_custom_parser(sample_pdf_dir):
    parser = CustomPDFParser()
    pdf_path = sample_pdf_dir / "sample.pdf"
    
    raw_data = parser.parse(pdf_path)
    assert raw_data is not None
    assert "pages" in raw_data
```

## Adding a Custom OCS Transformer

### 1. Create Transformer Class

Create `src/jd_pdf_to_json/transformers/ocs_transformer.py`:

```python
from jd_pdf_to_json.transformers.base import BaseOCSTransformer
from jd_pdf_to_json.core.models import OCSDocument, OCSProfile
from jd_pdf_to_json.utils.exceptions import TransformationError

class OCSTransformer(BaseOCSTransformer):
    """Transform parsed PDF data to OCS model."""
    
    def transform(self, raw_data: dict) -> OCSDocument:
        """Map raw extracted data to OCS structure."""
        try:
            # Extract version info
            version_info = self._extract_versions(raw_data)
            
            # Extract OCS profile
            profile = self._extract_profile(raw_data)
            
            # Extract content
            content = self._extract_content(raw_data)
            
            # Create document
            return OCSDocument(
                version_info=version_info,
                ocs_profile=profile,
                ocs_content=content,
            )
        except Exception as e:
            raise TransformationError(f"Transformation failed: {str(e)}") from e
    
    def _extract_profile(self, raw_data: dict) -> OCSProfile:
        """Extract profile section."""
        # Implementation specific to your PDF structure
        pass
    
    def _extract_versions(self, raw_data: dict):
        """Extract version history."""
        pass
    
    def _extract_content(self, raw_data: dict):
        """Extract OCU content."""
        pass
```

### 2. Register Transformer

In `src/jd_pdf_to_json/cli.py`:

```python
from jd_pdf_to_json.transformers import OCSTransformer

@app.command()
def convert(...):
    # ...
    transformer = OCSTransformer()
    model = transformer.transform(raw_data)
    # ...
```

## Adding Custom Validation Rules

### 1. Create Validation Rules

Extend `src/jd_pdf_to_json/validators/business_rules.py`:

```python
class CustomBusinessRuleValidator:
    """Custom business rule validations."""
    
    def validate_knowledge_codes(self, model: OCSDocument) -> list[str]:
        """Validate knowledge codes format."""
        errors = []
        for unit in model.ocs_content.ocu_units:
            for task in unit.tasks:
                for knowl in task.knowledge_k:
                    if not knowl.code.startswith("K"):
                        errors.append(
                            f"Invalid knowledge code format: {knowl.code}"
                        )
        return errors
    
    def validate_ocs_level_progression(self, model: OCSDocument) -> list[str]:
        """Validate competency levels increase progressively."""
        errors = []
        current_level = 0
        for unit in model.ocs_content.ocu_units:
            for task in unit.tasks:
                if task.competency_level < current_level:
                    errors.append(
                        f"Task {task.task_code}: level decreased "
                        f"from {current_level} to {task.competency_level}"
                    )
                current_level = task.competency_level
        return errors
```

### 2. Integrate in Validator

Edit `src/jd_pdf_to_json/validators/schema.py`:

```python
from jd_pdf_to_json.validators.business_rules import CustomBusinessRuleValidator

class OCSSchemaValidator:
    def __init__(self):
        self.business_validator = CustomBusinessRuleValidator()
    
    def validate(self, model: OCSDocument) -> Tuple[bool, List[str]]:
        errors = []
        
        # Existing validations...
        
        # Add custom business rules
        errors.extend(self.business_validator.validate_knowledge_codes(model))
        errors.extend(self.business_validator.validate_ocs_level_progression(model))
        
        return len(errors) == 0, errors
```

## Adding New Output Formats

### 1. Create Writer

Create `src/jd_pdf_to_json/writers/csv_writer.py`:

```python
from pathlib import Path
import csv
from jd_pdf_to_json.writers.base import BaseWriter
from jd_pdf_to_json.core.models import OCSDocument

class CSVWriter(BaseWriter):
    """Export OCS data to CSV format."""
    
    def write(self, model: OCSDocument, output_path: Path) -> None:
        """Write tasks to CSV."""
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_path, 'w', encoding='utf-8', newline='') as f:
            writer = csv.writer(f)
            
            # Header
            writer.writerow([
                'OCU Code', 'OCU Name', 'Task Code', 'Task Name', 
                'Level', 'Knowledge', 'Skills'
            ])
            
            # Data
            for unit in model.ocs_content.ocu_units:
                for task in unit.tasks:
                    knowledge = ', '.join(k.code for k in task.knowledge_k)
                    skills = ', '.join(s.code for s in task.skills_s)
                    
                    writer.writerow([
                        unit.ocu_code,
                        unit.ocu_name,
                        task.task_code,
                        task.task_name,
                        task.competency_level,
                        knowledge,
                        skills,
                    ])
```

### 2. Register Writer

In CLI or API:

```python
from jd_pdf_to_json.writers import JSONWriter, CSVWriter

OUTPUT_FORMATS = {
    "json": JSONWriter,
    "csv": CSVWriter,
}

@app.command()
def convert(
    pdf_path: Path,
    output_path: Path = None,
    format: str = typer.Option("json"),
):
    # ...
    writer_class = OUTPUT_FORMATS[format]
    writer = writer_class()
    writer.write(model, output_path)
```

## Testing Extensions

### 1. Create Test File

```python
import pytest
from pathlib import Path
from jd_pdf_to_json.transformers import OCSTransformer
from jd_pdf_to_json.core.models import OCSDocument

def test_ocs_transformer(sample_pdf_dir):
    transformer = OCSTransformer()
    raw_data = {
        # Sample data structure
    }
    
    model = transformer.transform(raw_data)
    
    assert isinstance(model, OCSDocument)
    assert model.ocs_profile.ocs_code == "..."
```

### 2. Run Tests

```bash
uv run pytest tests/test_extensions.py -v
```

## Best Practices

1. **Inherit from Base Classes**: Always extend `BasePDFParser`, `BaseOCSTransformer`, etc.
2. **Add Type Hints**: Use type annotations for clarity and mypy support
3. **Raise Custom Exceptions**: Use `PDFParsingError`, `TransformationError`, etc.
4. **Log Operations**: Use `logger` from `jd_pdf_to_json.utils.logger`
5. **Test Thoroughly**: Aim for >80% code coverage
6. **Document Code**: Include docstrings and usage examples
7. **Handle Errors**: Gracefully handle missing/malformed data

## Example: Complete Custom Extension

See `examples/` directory for complete working examples of:
- Custom PDF parser
- OCS transformers
- Custom validators
- Output format writers

## Contributing

To contribute extensions:

1. Follow the patterns in this guide
2. Add tests for your extension
3. Update documentation
4. Submit a pull request

---

For more details, see:
- [Architecture](../ARCHITECTURE.md)
- [Data Schema](../README.md)
