"""Assemble OCS sections from one detached PDF extraction."""

from ocs_contract.models import OCSDocument

from ..errors import TransformationError
from ..parsers.models import PDFDocument
from .sections import (
    attitude_extractor,
    content_extractor,
    notes_extractor,
    profile_extractor,
    version_extractor,
)


def transform_document(raw_data: PDFDocument) -> OCSDocument:
    """Assemble an OCS candidate from detached extraction data."""
    try:
        version_info = version_extractor.extract_version_info(raw_data)

        ocs_profile = profile_extractor.extract_profile(raw_data, version_info)

        ocs_content = content_extractor.extract_content(raw_data)

        ocs_attitude = attitude_extractor.extract_attitude(raw_data)

        notes = notes_extractor.extract_notes(raw_data)

        return OCSDocument(
            version_info=version_info,
            ocs_profile=ocs_profile,
            ocs_content=ocs_content,
            ocs_attitude=ocs_attitude,
            notes=notes,
        )

    except Exception as e:
        raise TransformationError(f"Failed to transform PDF: {str(e)}") from e
