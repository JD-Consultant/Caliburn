from typing import get_args
from jd_ocs_indexer.models.chunk import ChunkLevel


def test_task_is_a_valid_chunk_level():
    members = get_args(ChunkLevel)
    assert "task" in members
    assert "profile" in members
