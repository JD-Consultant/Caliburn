# Usage Guide

## Quick Start

### Convert a Single PDF

```bash
uv run jd-convert convert input.pdf --output output.json

# Or use default output name (input.json)
uv run jd-convert convert input.pdf
```

### Batch Convert PDFs

```bash
uv run jd-convert batch ./pdf_folder --output ./output_folder
```

### Validate JSON File

```bash
uv run jd-convert validate output.json
```

## CLI Commands

### `convert` - Convert Single PDF

```
Usage: jd-convert convert [OPTIONS] PDF_PATH

Arguments:
  PDF_PATH              Input PDF file

Options:
  --output, -o PATH     Output JSON file (default: input_name.json)
  --validate            Enable schema validation (default: True)
  --help                Show help message
```

**Example:**
```bash
uv run jd-convert convert ./samples/housekeeping.pdf -o housekeeping.json --validate
```

### `batch` - Batch Convert PDFs

```
Usage: jd-convert batch [OPTIONS] INPUT_DIR

Arguments:
  INPUT_DIR             Directory with PDF files

Options:
  --output, -o PATH     Output directory (required)
  --help                Show help message
```

**Example:**
```bash
uv run jd-convert batch ./raw_pdfs --output ./converted_json
```

### `validate` - Validate JSON

```
Usage: jd-convert validate [OPTIONS] JSON_PATH

Arguments:
  JSON_PATH             JSON file to validate

Options:
  --help                Show help message
```

**Example:**
```bash
uv run jd-convert validate converted.json
```

## Python API Usage

### Basic Conversion Pipeline

```python
from pathlib import Path
from jd_pdf_to_json.parsers import PDFPlumberParser
from jd_pdf_to_json.transformers import BaseOCSTransformer
from jd_pdf_to_json.validators import OCSSchemaValidator
from jd_pdf_to_json.writers import JSONWriter

# 1. Parse PDF
parser = PDFPlumberParser()
raw_data = parser.parse(Path("input.pdf"))

# 2. Transform to OCS model
# TODO: Implement OCS-specific transformer
# transformer = OCSTransformer()
# model = transformer.transform(raw_data)

# 3. Validate
validator = OCSSchemaValidator()
is_valid, errors = validator.validate(model)

if not is_valid:
    print(f"Validation errors:\n{errors}")
    exit(1)

# 4. Write to JSON
writer = JSONWriter()
writer.write(model, Path("output.json"))
```

## Working with Data Models

### Creating OCS Document

```python
from jd_pdf_to_json.core.models import (
    OCSDocument, OCSProfile, OCSName, 
    OCSCategory, CategoryItem, OCSContent
)

# Build category
category = OCSCategory(
    job_categories=[
        CategoryItem(name="金融財務／證券及投資", code="FSI")
    ],
    occupations=[
        CategoryItem(name="證券金融交易員及經紀人", code="3311")
    ],
    industries=[
        CategoryItem(
            name="金融及保險業／證券期貨及金融輔助業（證券業）",
            code="K6611"
        )
    ]
)

# Build profile
profile = OCSProfile(
    ocs_code="FSI3311-001v3",
    ocs_name=OCSName(
        job_category_name=None,
        occupation_name="證券業-受託買賣業務人員"
    ),
    category=category,
    job_description="...",
    ocs_level=3
)

# Create document
doc = OCSDocument(
    ocs_profile=profile,
    ocs_content=OCSContent(),
)

# Validate
validator = OCSSchemaValidator()
is_valid, errors = validator.validate(doc)
```

### Reading and Modifying JSON

```python
import json
from jd_pdf_to_json.core.models import OCSDocument

# Load from JSON
with open("output.json") as f:
    data = json.load(f)
    doc = OCSDocument(**data)

# Modify
doc.ocs_profile.ocs_level = 4

# Save back
with open("modified.json", "w", encoding="utf-8") as f:
    json.dump(doc.model_dump(), f, indent=2, ensure_ascii=False)
```

## Configuration

### Via Environment Variables

```bash
export JD_PDF_LOG_LEVEL=DEBUG
export JD_PDF_OUTPUT_ENCODING=utf-8
```

### Via Config File

Create `config.yaml` in project root:

```yaml
parsing:
  extraction_method: pdfplumber
  timeout: 60

validation:
  enable_strict_mode: true
  
output:
  format: json
  encoding: utf-8
  indent: 2
```

## Troubleshooting

### PDF Not Recognized as OCS Format

**Symptom:** "PDF validation failed: not OCS format"

**Solution:**
1. Ensure PDF contains OCS-related keywords (職能基準, 工作任務, etc.)
2. Check if PDF is encrypted or corrupted
3. Try with `--validate=false` to skip source validation

### Schema Validation Errors

**Symptom:** "knowledge_k missing code or name"

**Solution:**
1. Check JSON structure matches schema (see [README](../README.md))
2. Ensure all knowledge/skill items have both `code` and `name`
3. Run `validate` command for detailed error messages

### Memory Issues with Large Batches

**Symptom:** "MemoryError" when batch processing

**Solution:**
```bash
# Process smaller batches
uv run jd-convert batch ./pdf_folder --output ./output_folder

# Or implement streaming in custom script
```

## Advanced Usage

### Custom Transformer

See [Extending Guide](guide_extending.md) for creating custom transformers.

### Integrating with Other Tools

```python
# As part of data pipeline
import subprocess
result = subprocess.run([
    "uv", "run", "jd-convert", "convert", 
    "input.pdf", "-o", "output.json"
], capture_output=True)
```

## Related Documentation

- [Installation Guide](guide_installation.md)
- [Data Schema](../README.md)
- [Architecture](../ARCHITECTURE.md)
- [Extending Guide](guide_extending.md)
