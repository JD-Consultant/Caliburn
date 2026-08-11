"""Custom exception classes."""


class PDFParsingError(Exception):
    """Raised when PDF parsing fails."""
    pass


class ValidationError(Exception):
    """Raised when validation fails."""
    pass


class TransformationError(Exception):
    """Raised when data transformation fails."""
    pass


class ConfigurationError(Exception):
    """Raised when configuration is invalid."""
    pass
