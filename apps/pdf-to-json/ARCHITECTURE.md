# Project Architecture

基於 Python `uv` 的模組化設計，支援 PDF 解析→轉換→驗證→輸出流程。

## 1. Project Structure

```
jd-pdf-to-json/
├── pyproject.toml                 # uv 專案配置
├── README.md                      # 資料規範
├── ARCHITECTURE.md                # 本文件
├── src/
│   └── jd_pdf_to_json/
│       ├── __init__.py
│       ├── cli.py                 # CLI entry point
│       ├── core/
│       │   ├── __init__.py
│       │   ├── config.py          # Configuration management
│       │   └── models.py          # Data models (Pydantic)
│       ├── parsers/
│       │   ├── __init__.py
│       │   ├── base.py            # Abstract PDF parser
│       │   └── pdf_parser.py      # Concrete PDF parser (pdfplumber)
│       ├── transformers/
│       │   ├── __init__.py
│       │   ├── base.py            # Abstract transformer
│       │   ├── ocs_transformer.py # OCS-specific mapper
│       │   └── field_mapper.py    # Field mapping logic
│       ├── validators/
│       │   ├── __init__.py
│       │   ├── schema.py          # JSON schema validation
│       │   └── business_rules.py  # Business rule validation
│       ├── writers/
│       │   ├── __init__.py
│       │   ├── base.py            # Abstract writer
│       │   └── json_writer.py     # JSON output writer
│       └── utils/
│           ├── __init__.py
│           ├── logger.py          # Logging utility
│           └── exceptions.py      # Custom exceptions
├── tests/
│   ├── __init__.py
│   ├── conftest.py                # pytest fixtures
│   ├── test_parsers.py
│   ├── test_transformers.py
│   ├── test_validators.py
│   ├── fixtures/
│   │   ├── sample_pdfs/           # Test PDF files
│   │   └── expected_outputs/      # Expected JSON outputs
│   └── integration/
│       └── test_end_to_end.py
├── examples/
│   ├── convert_single.py          # Single file conversion
│   └── batch_convert.py           # Batch processing
└── docs/
    ├── guide_installation.md      # Installation guide
    ├── guide_usage.md             # Usage guide
    └── guide_extending.md         # Extension guide
```

## 2. Module Responsibility

### 2.1 `core/models.py` - Data Models

使用 Pydantic v2 定義所有資料結構（與 JSON schema 一致）：

```python
from pydantic import BaseModel, Field
from typing import Optional, List

class VersionInfo(BaseModel):
    version: str
    ocs_code: str
    ocs_name: str
    status: str
    update_note: Optional[str] = None
    update_date: str

class OCSProfile(BaseModel):
    ocs_code: str
    ocs_name: dict[str, Optional[str]]  # job_category_name, occupation_name
    category: dict[str, List]           # job_categories, occupations, industries
    job_description: str
    ocs_level: int

class OCSDatabaseModel(BaseModel):
    """Top-level OCS document model"""
    version_info: dict[str, List[VersionInfo]]
    ocs_profile: OCSProfile
    ocs_content: dict  # Placeholder，需展開
    ocs_attitude: dict
    notes_and_appendix: dict
```

### 2.2 `parsers/base.py` - Abstract Parser

```python
from abc import ABC, abstractmethod
from pathlib import Path

class BasePDFParser(ABC):
    """Abstract base class for PDF parsers"""
    
    @abstractmethod
    def parse(self, pdf_path: Path) -> dict:
        """Parse PDF and extract raw data"""
        pass
    
    @abstractmethod
    def validate_source(self, pdf_path: Path) -> bool:
        """Verify PDF is readable OCS format"""
        pass
```

### 2.3 `transformers/base.py` - Abstract Transformer

```python
from abc import ABC, abstractmethod
from jd_pdf_to_json.core.models import OCSDatabaseModel

class BaseOCSTransformer(ABC):
    """Abstract transformer: raw data → OCS model"""
    
    @abstractmethod
    def transform(self, raw_data: dict) -> OCSDatabaseModel:
        """Transform parsed PDF data into structured OCS model"""
        pass
```

### 2.4 `validators/schema.py` - Schema Validation

```python
from jsonschema import validate, ValidationError
from jd_pdf_to_json.core.models import OCSDatabaseModel

class OCSSchemaValidator:
    """Validate against OCS JSON schema"""
    
    def validate(self, model: OCSDatabaseModel) -> tuple[bool, list[str]]:
        """
        Validate model against schema rules.
        Returns: (is_valid, error_messages)
        """
        errors = []
        
        # Rule 1: All top-level keys present
        required_keys = {'version_info', 'ocs_profile', 'ocs_content', 
                        'ocs_attitude', 'notes_and_appendix'}
        # ...
        
        # Rule 2: knowledge_k/skills_s must be objects with code+name
        # ...
        
        return len(errors) == 0, errors
```

### 2.5 `writers/json_writer.py` - JSON Output

```python
from pathlib import Path
from jd_pdf_to_json.core.models import OCSDatabaseModel

class JSONWriter:
    """Write OCS model to JSON file"""
    
    def write(self, model: OCSDatabaseModel, output_path: Path) -> None:
        """Write validated model to JSON with UTF-8 encoding"""
        output_path.write_text(
            model.model_dump_json(indent=2, ensure_ascii=False),
            encoding='utf-8'
        )
```

### 2.6 `cli.py` - Command-line Interface

```python
import typer
from pathlib import Path

app = typer.Typer(help="OCS PDF to JSON converter")

@app.command()
def convert(
    pdf_path: Path = typer.Argument(..., help="Input PDF file"),
    output_path: Path = typer.Option(..., help="Output JSON file"),
    validate: bool = typer.Option(True, help="Enable schema validation"),
) -> None:
    """Convert single OCS PDF to JSON"""
    # Implementation
    pass

@app.command()
def batch(
    input_dir: Path = typer.Argument(..., help="Directory with PDFs"),
    output_dir: Path = typer.Option(..., help="Output directory"),
) -> None:
    """Batch convert OCS PDFs"""
    # Implementation
    pass

if __name__ == "__main__":
    app()
```

## 3. Dependencies (pyproject.toml)

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "jd-pdf-to-json"
version = "0.1.0"
description = "Convert OCS vocational competency PDFs to structured JSON"
readme = "README.md"
requires-python = ">=3.11"
authors = [{name = "JD Consultant", email = "contact@jd.com"}]
license = {text = "MIT"}

dependencies = [
    "pydantic>=2.0,<3",           # Data validation
    "pdfplumber>=0.10,<1",        # PDF parsing
    "typer>=0.9,<1",              # CLI framework
    "jsonschema>=4.20,<5",        # Schema validation
]

[project.optional-dependencies]
dev = [
    "pytest>=7.4,<8",
    "pytest-cov>=4.1,<5",
    "black>=23.9,<24",            # Code formatter
    "ruff>=0.1,<1",               # Linter
    "mypy>=1.5,<2",               # Type checker
    "pytest-mock>=3.11,<4",       # Mocking for tests
]

[project.scripts]
jd-convert = "jd_pdf_to_json.cli:app"

[tool.uv]
dev-dependencies = [
    "pytest",
    "black",
    "ruff",
    "mypy",
]

[tool.black]
line-length = 100
target-version = ['py311']

[tool.ruff]
line-length = 100
select = ["E", "F", "W", "I"]

[tool.mypy]
python_version = "3.11"
check_untyped_defs = true
disallow_untyped_defs = false
warn_return_any = true
```

## 4. Data Flow

```
PDF File
   ↓
[PDFParser] → raw_dict (extracted text, tables)
   ↓
[OCSTransformer] → OCSDatabaseModel (structured)
   ↓
[SchemaValidator] → bool (pass/fail + errors)
   ↓ (if valid)
[JSONWriter] → JSON File (UTF-8)
```

## 5. Extensibility Points

### Add new PDF variant:
1. 建立新 Parser 繼承 `BasePDFParser`
2. 實作 `parse()` 與 `validate_source()`
3. 在 `cli.py` 中註冊

### Add new validation rule:
1. 在 `validators/business_rules.py` 新增 rule class
2. 在 `OCSSchemaValidator.validate()` 呼叫

### Add new output format:
1. 建立新 Writer 繼承 `BaseWriter`（待定義）
2. 在 `cli.py` 新增 `--format` 選項

## 6. Quality Assurance

- **Type Checking**: `mypy` 確保型別安全
- **Linting**: `ruff` 檢查程式碼風格
- **Formatting**: `black` 統一程式碼格式
- **Testing**: `pytest` + `pytest-cov` ≥80% coverage
- **Schema Validation**: Pydantic 模型 + JSON Schema

## 7. Development Workflow with uv

```bash
# Installation
uv sync --all-extras

# Run tests
uv run pytest --cov

# Format code
uv run black src/

# Type check
uv run mypy src/

# Run CLI
uv run jd-convert --help
uv run python -m jd_pdf_to_json.cli convert input.pdf --output output.json
```

## 8. Recommended Toolchain

| Task | Tool | Integration |
|------|------|-------------|
| Package mgmt | `uv` | Built-in, fastest |
| Virtual env | `uv` | Automatic |
| Linting | `ruff` | Fast Rust-based |
| Formatting | `black` | Opinionated, stable |
| Type checking | `mypy` | Strict mode |
| Testing | `pytest` | Pytest + plugins |
| PDF parsing | `pdfplumber` | Reliable extraction |
| CLI | `typer` | Async-ready |
| Validation | `pydantic` + `jsonschema` | Layered |

## 9. Version Strategy

- **Semantic Versioning**: MAJOR.MINOR.PATCH
- **Schema Evolution**: `schema_version` field in outputs
- **Backward Compatibility**: Always maintain previous schema support for N-1 versions
