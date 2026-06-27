# Installation Guide

## Prerequisites

- Python 3.11+
- `uv` package manager (https://docs.astral.sh/uv/getting-started/)

## Installation Steps

### 1. Install uv (if not already installed)

```bash
# On Windows (PowerShell)
powershell -Command "irm https://astral.sh/uv/install.ps1 | iex"

# On macOS/Linux
curl -LsSf https://astral.sh/uv/install.sh | sh

# Or via pip
pip install uv
```

### 2. Clone and Setup Project

```bash
git clone <repository-url>
cd jd-pdf-to-json

# Create virtual environment and install dependencies
uv sync --all-extras

# Or for minimal installation (without dev tools)
uv sync
```

### 3. Verify Installation

```bash
# Check CLI is accessible
uv run jd-convert --help

# Run tests to verify setup
uv run pytest --version
uv run pytest tests/ -v
```

## Development Setup

### Install with Development Tools

```bash
# Full installation with all development dependencies
uv sync --all-extras

# Verify tools are installed
uv run black --version
uv run ruff --version
uv run mypy --version
uv run pytest --version
```

### Common Development Commands

```bash
# Format code with black
uv run black src/ tests/

# Lint with ruff
uv run ruff check src/ tests/

# Type checking with mypy
uv run mypy src/

# Run tests with coverage
uv run pytest tests/ --cov=src/jd_pdf_to_json --cov-report=html

# Run specific test
uv run pytest tests/test_parsers.py::test_pdf_parsing -v

# Interactive Python REPL with project dependencies
uv run python
```

## Docker Setup (Optional)

If you prefer containerized development:

```bash
# Build Docker image (TODO: Dockerfile setup)
docker build -t jd-pdf-to-json .

# Run container
docker run -it jd-pdf-to-json
```

## Troubleshooting

### Issue: `uv command not found`

**Solution:**
```bash
# Ensure uv is in PATH
export PATH="$HOME/.local/bin:$PATH"  # Linux/macOS
```

### Issue: Python version mismatch

**Solution:**
```bash
# Check Python version
python --version  # Should be 3.11+

# Use uv to install required Python version
uv python pin 3.11

# Or specify explicitly
uv sync --python 3.11
```

### Issue: pdfplumber not found

**Solution:**
```bash
# Ensure dependencies are installed
uv sync

# Or manually install
uv pip install pdfplumber
```

### Issue: Tests fail with import errors

**Solution:**
```bash
# Regenerate environment
uv sync --force

# Or try
uv run pytest tests/ -v
```

## Next Steps

1. Read [Usage Guide](guide_usage.md) to learn how to convert PDFs
2. Check [Architecture Guide](../ARCHITECTURE.md) for project structure
3. Review [Data Schema](../README.md) for JSON format details
