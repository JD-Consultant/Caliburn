"""Test configuration and fixtures."""

import pytest
from pathlib import Path


@pytest.fixture
def sample_pdf_dir() -> Path:
    """Return path to sample PDFs directory."""
    return Path(__file__).parent / "fixtures" / "sample_pdfs"


@pytest.fixture
def expected_output_dir() -> Path:
    """Return path to expected outputs directory."""
    return Path(__file__).parent / "fixtures" / "expected_outputs"


@pytest.fixture
def tmp_output_dir(tmp_path) -> Path:
    """Return a temporary directory for test outputs."""
    return tmp_path / "outputs"
