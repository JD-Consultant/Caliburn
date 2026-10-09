"""Public transient updates cannot accumulate without a bounded subscriber."""

from uuid import uuid4

import pytest

from caliburn.workflows.consultant_activity import ConsultantActivityHub, PublicCommentaryUpdate


def test_app_exposes_only_the_current_activity_stream():
    from fastapi.testclient import TestClient

    from caliburn.bootstrap import create_app
    from caliburn.settings import Settings

    app = create_app(Settings())
    with TestClient(app):
        paths = app.openapi()["paths"]
        assert any(path.endswith("/activity-stream") for path in paths)
        assert not any(path.endswith("/commentary-stream") for path in paths)
        assert not hasattr(app.state, "consultant_commentary_hub")


async def test_publish_is_scoped_bounded_and_keeps_latest_accumulated_text() -> None:
    hub = ConsultantActivityHub(queue_capacity=2)
    file_id, execution_id = uuid4(), uuid4()
    with hub.subscribe(file_id, execution_id) as queue:
        with hub.subscribe(uuid4(), execution_id) as other_file:
            with hub.subscribe(file_id, uuid4()) as other_execution:
                for text in ("一", "一二", "一二三"):
                    hub.publish(
                        file_id,
                        execution_id,
                        PublicCommentaryUpdate(file_id, execution_id, "r", "m", text),
                    )
                assert queue.qsize() == 2
                assert queue.get_nowait().text == "一二"
                update = queue.get_nowait()
                assert (update.response_id, update.message_id, update.text) == ("r", "m", "一二三")
                assert other_file.empty() and other_execution.empty()


async def test_detach_and_no_subscriber_publish_do_not_replay_or_retain() -> None:
    hub = ConsultantActivityHub(max_subscribers=1)
    file_id, execution_id = uuid4(), uuid4()
    hub.publish(
        file_id, execution_id, PublicCommentaryUpdate(file_id, execution_id, "r", "m", "before")
    )
    with hub.subscribe(file_id, execution_id) as queue:
        assert queue.empty()
        hub.publish(
            file_id, execution_id, PublicCommentaryUpdate(file_id, execution_id, "r", "m", "during")
        )
        assert queue.qsize() == 1
    hub.publish(
        file_id, execution_id, PublicCommentaryUpdate(file_id, execution_id, "r", "m", "after")
    )
    assert queue.empty()
    with hub.subscribe(file_id, execution_id) as reconnected:
        assert reconnected.empty()


async def test_subscriber_capacity_is_released_and_oversized_updates_are_dropped() -> None:
    from caliburn.workflows.public_text_stream import PublicStreamCapacityError

    hub = ConsultantActivityHub(max_subscribers=1, max_update_chars=8)
    file_id, execution_id = uuid4(), uuid4()
    with hub.subscribe(file_id, execution_id) as queue:
        with pytest.raises(PublicStreamCapacityError), hub.subscribe(file_id, execution_id):
            pass
        hub.publish(
            file_id, execution_id, PublicCommentaryUpdate(file_id, execution_id, "r", "m", "x" * 9)
        )
        assert queue.empty()
        hub.publish(
            file_id, execution_id, PublicCommentaryUpdate(file_id, execution_id, "r", "m", "ok")
        )
        assert queue.get_nowait().text == "ok"
    with hub.subscribe(file_id, execution_id):
        pass


@pytest.mark.parametrize(
    "limits",
    [
        {"queue_capacity": 0},
        {"max_subscribers": 0},
        {"max_update_chars": 0},
    ],
)
def test_zero_limits_cannot_silently_create_an_unbounded_hub(limits: dict[str, int]) -> None:
    with pytest.raises(ValueError, match="positive"):
        ConsultantActivityHub(**limits)
