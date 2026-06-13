import pytest
from pydantic import ValidationError

from jd_ocs_indexer.api.schemas import SearchRequest, TaskPoolRequest


def test_search_request_defaults():
    req = SearchRequest(query="hi")
    assert req.hybrid is True and req.top_k == 10
    assert req.include_text is False and req.text_lines == 6
    assert req.filters.is_current is None


def test_search_request_rejects_empty_query():
    with pytest.raises(ValidationError):
        SearchRequest(query="")


def test_search_request_top_k_bounds():
    with pytest.raises(ValidationError):
        SearchRequest(query="hi", top_k=0)
    with pytest.raises(ValidationError):
        SearchRequest(query="hi", top_k=51)


def test_task_pool_request_requires_codes():
    with pytest.raises(ValidationError):
        TaskPoolRequest(ocs_codes=[])
