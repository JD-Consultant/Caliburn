"""PDF parser implementation using pdfplumber."""

from pathlib import Path
from jd_pdf_to_json.parsers.base import BasePDFParser
from jd_pdf_to_json.utils.logger import logger
from jd_pdf_to_json.utils.exceptions import PDFParsingError

try:
    import pdfplumber
except ImportError:
    raise ImportError("pdfplumber is required. Install with: uv pip install pdfplumber")


class PDFPlumberParser(BasePDFParser):
    """PDF parser using pdfplumber library."""

    def parse(self, pdf_path: Path) -> dict:
        """
        Parse PDF using pdfplumber.
        
        Args:
            pdf_path: Path to PDF file
            
        Returns:
            Raw extracted data including text and tables
        """
        if not pdf_path.exists():
            raise PDFParsingError(f"PDF file not found: {pdf_path}")
        
        try:
            with pdfplumber.open(pdf_path) as pdf:
                logger.info(f"Parsing PDF: {pdf_path.name} ({len(pdf.pages)} pages)")
                
                raw_data = {
                    "metadata": {
                        "filename": pdf_path.name,
                        "num_pages": len(pdf.pages),
                        "created_date": pdf.metadata.get("CreationDate"),
                        "producer": pdf.metadata.get("Producer"),
                    },
                    "pages": [],
                }
                
                for page_idx, page in enumerate(pdf.pages):
                    page_data = {
                        "page_number": page_idx + 1,
                        "text": page.extract_text(),
                        "tables": page.extract_tables(),
                        "height": page.height,
                        "width": page.width,
                    }
                    raw_data["pages"].append(page_data)
                
                logger.debug(f"Successfully parsed {len(pdf.pages)} pages")
                return raw_data
                
        except Exception as e:
            raise PDFParsingError(f"Failed to parse PDF {pdf_path.name}: {str(e)}") from e

    def validate_source(self, pdf_path: Path) -> bool:
        """
        Verify PDF is readable OCS format.
        
        Checks:
        - File is readable PDF
        - Contains expected OCS-related keywords
        """
        if not pdf_path.exists() or pdf_path.suffix.lower() != ".pdf":
            return False
        
        try:
            with pdfplumber.open(pdf_path) as pdf:
                if len(pdf.pages) == 0:
                    return False
                
                # Extract text from first page to check for OCS keywords
                first_page_text = pdf.pages[0].extract_text() or ""
                ocs_keywords = ["職能基準", "職能", "工作任務", "行為指標"]
                
                has_keyword = any(kw in first_page_text for kw in ocs_keywords)
                return has_keyword
                
        except Exception as e:
            logger.warning(f"Failed to validate source {pdf_path.name}: {str(e)}")
            return False
