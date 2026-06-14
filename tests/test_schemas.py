import pytest
from pydantic import ValidationError
from jd_ocs_indexer.api import schemas


def test_search_request_level_is_profile_or_task():
    schemas.SearchRequest(query="x", level="task")
    schemas.SearchRequest(query="x", level="profile")
    with pytest.raises(ValidationError):
        schemas.SearchRequest(query="x", level="block")


def test_search_filters_have_no_code_fields():
    f = schemas.SearchFilters()
    assert not hasattr(f, "k_codes") and not hasattr(f, "s_codes") and not hasattr(f, "attitude_codes")
    assert {"ocs_code", "is_current"} <= set(schemas.SearchFilters.model_fields)


def test_hit_v3_shape():
    fields = set(schemas.Hit.model_fields)
    assert {"id", "task_id", "task_title", "activity_examples", "output_pairs", "competency_level"} <= fields
    for gone in ("task_ids", "task_titles", "block_order", "unit_order", "snippet"):
        assert gone not in fields


def test_task_carries_id():
    assert "id" in schemas.Task.model_fields


def test_task_pool_request_nonempty():
    with pytest.raises(ValidationError):
        schemas.TaskPoolRequest(ocs_codes=[])
