from tests.conftest import FakePoint


def test_fakepoint_carries_id():
    p = FakePoint(payload={"chunk_level": "task"}, score=0.5, id="abc-123")
    assert p.id == "abc-123"
    assert FakePoint(payload={}).id is None
