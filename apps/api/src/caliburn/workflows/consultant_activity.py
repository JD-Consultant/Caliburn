"""One live channel for both allowlisted public text kinds; legacy commentary stays compatible."""

from uuid import UUID

from caliburn.adapters.reasoning_summaries import PublicReasoningSummary
from caliburn.workflows.consultant_commentary import PublicCommentaryUpdate
from caliburn.workflows.public_text_stream import BoundedPublicTextHub

type PublicActivityUpdate = PublicReasoningSummary | PublicCommentaryUpdate


class ConsultantActivityHub(BoundedPublicTextHub[PublicActivityUpdate]):
    def publish(self, job_file_id: UUID, execution_id: UUID, update: PublicActivityUpdate) -> None:
        item_id = (
            update.item_id if isinstance(update, PublicReasoningSummary) else update.message_id
        )
        self._publish(
            job_file_id,
            execution_id,
            update,
            len(update.response_id) + len(item_id) + len(update.text),
        )
