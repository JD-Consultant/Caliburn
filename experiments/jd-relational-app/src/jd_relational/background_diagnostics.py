"""Small allowlisted diagnostic sink for isolated background failures."""

import logging


LOG = logging.getLogger("caliburn.jd.background")


def record_background_failure(
    event_code: str,
    *,
    document_id: str | None = None,
    attempted: int | None = None,
) -> None:
    metadata = {"event_code": event_code}
    if document_id is not None:
        metadata["document_id"] = document_id
    if attempted is not None:
        metadata["attempted"] = attempted
    try:
        LOG.warning(event_code, extra=metadata)
    except Exception:
        pass
