"""Bounded, non-durable public commentary delivery within one event loop."""

from dataclasses import dataclass
from uuid import UUID

from caliburn.workflows.public_text_stream import BoundedPublicTextHub
from caliburn.workflows.public_text_stream import (
    PublicStreamCapacityError as CommentaryCapacityError,
)

__all__ = ["CommentaryCapacityError", "ConsultantCommentaryHub", "PublicCommentaryUpdate"]


@dataclass(frozen=True, slots=True)
class PublicCommentaryUpdate:
    job_file_id: UUID
    execution_id: UUID
    response_id: str
    message_id: str
    text: str


class ConsultantCommentaryHub(BoundedPublicTextHub[PublicCommentaryUpdate]):
    def publish(
        self,
        job_file_id: UUID,
        execution_id: UUID,
        response_id: str,
        message_id: str,
        text: str,
    ) -> None:
        """Publish accumulated *public* text on the subscribers' event loop.

        No I/O, task creation, replay, or wait for consumers. Overflow drops the
        oldest update; oversized updates are dropped whole, never truncated.
        The caller alone selects public commentary (never raw SDK events).
        """
        update = PublicCommentaryUpdate(
            job_file_id,
            execution_id,
            response_id,
            message_id,
            text,
        )
        self._publish(
            job_file_id, execution_id, update, len(response_id) + len(message_id) + len(text)
        )
