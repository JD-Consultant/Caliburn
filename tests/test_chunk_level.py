from typing import get_args
from jd_ocs_indexer.models.chunk import ChunkLevel


def test_chunk_levels_are_exactly_profile_and_task():
    members = get_args(ChunkLevel)
    assert set(members) == {"profile", "task"}
