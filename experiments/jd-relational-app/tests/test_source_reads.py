"""Reading back the interview behind one JD marker, and refusing the rest.

Counter-examples are fixed in docs/specs/2026-09-14-jd-source-readback-slice.md.
No provider, no connection: the one source owner is represented by a stand-in
that answers exactly as it does, including its own error codes.
"""

import pytest

from jd_relational.conversation_sources import ConversationSourceError, SourceExcerpt, SourceMessage
from jd_relational.reads import ReadError
from jd_relational.source_reads import SourceReadService

DOCUMENT = "0d6de1cd-52e0-4b2f-9a19-5f0e86a2ed6a"
OTHER = "9b1f1f3c-0f17-4e6a-9a1a-6a0c0c9a1b22"
REF = "interview-source:opaque"
WORDS = "我每週固定巡檢產線設備，發現異常會記錄並通知負責人。"


class Owner:
    """The real owner's contract: it either returns an excerpt or its own code."""

    def __init__(self, *, code=None, messages=None):
        self.code, self.messages, self.asked = code, messages, []

    def read(self, source_ref, document_id):
        self.asked.append((source_ref, document_id))
        if self.code:
            raise ConversationSourceError(self.code)
        return SourceExcerpt(source_ref, tuple(self.messages))


def excerpt():
    return [SourceMessage(message_id="m1", role="user", text=WORDS),
            SourceMessage(message_id="m2", role="assistant", text="我把它整理成一項任務。")]


def test_the_employees_own_words_come_back_with_who_said_what():
    owner = Owner(messages=excerpt())
    page = SourceReadService(owner).read(DOCUMENT, {"source_ref": REF})
    assert owner.asked == [(REF, DOCUMENT)]
    assert page["view"] == "source_read" and page["access"] == "history"
    assert page["source_ref"] == REF
    assert [(row["role"], row["text"]) for row in page["messages"]] == [
        ("user", WORDS), ("assistant", "我把它整理成一項任務。")]


def test_the_consultants_own_wording_is_labelled_and_not_passed_off_as_the_employee():
    page = SourceReadService(Owner(messages=excerpt())).read(DOCUMENT, {"source_ref": REF})
    said_by_employee = [row["text"] for row in page["messages"] if row["role"] == "user"]
    assert said_by_employee == [WORDS], "an assistant line was presented as the employee's"


def test_a_reference_this_document_cannot_claim_is_refused():
    owner = Owner(code="invalid_ref")
    with pytest.raises(ReadError) as error:
        SourceReadService(owner).read(OTHER, {"source_ref": REF})
    assert error.value.code == "invalid_ref"


def test_a_source_that_is_gone_says_so_instead_of_returning_nothing():
    """An empty answer would read as 'you never said anything'. It must not."""
    with pytest.raises(ReadError) as error:
        SourceReadService(Owner(code="source_not_available")).read(DOCUMENT, {"source_ref": REF})
    assert error.value.code == "target_missing"


@pytest.mark.parametrize("arguments", [
    {}, {"source_ref": ""}, {"source_ref": None}, {"source_ref": 1},
    {"source_ref": REF, "document_id": DOCUMENT}, {"source_ref": ["a"]},
])
def test_an_unusable_request_never_reaches_the_owner(arguments):
    owner = Owner(messages=excerpt())
    with pytest.raises(ReadError) as error:
        SourceReadService(owner).read(DOCUMENT, arguments)
    assert error.value.code == "invalid_input"
    assert owner.asked == [], "a bad request was forwarded to the source owner"


def test_an_unexpected_owner_failure_stays_a_safe_code():
    class Exploding(Owner):
        def read(self, source_ref, document_id):
            raise RuntimeError("connection to 127.0.0.1:55436 failed: password ...")

    with pytest.raises(ReadError) as error:
        SourceReadService(Exploding()).read(DOCUMENT, {"source_ref": REF})
    assert error.value.code == "read_failed"
    assert "password" not in str(error.value)


def test_the_service_has_no_way_to_write():
    for forbidden in ("execute", "save", "edit", "write", "commit"):
        assert not hasattr(SourceReadService(Owner(messages=excerpt())), forbidden), forbidden
