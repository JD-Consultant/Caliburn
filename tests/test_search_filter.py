from jd_ocs_indexer.validation.search import build_filter


def _keys(flt):
    return [c.key for c in flt.must]


def test_build_filter_v3_supported_fields():
    flt = build_filter(level="task", ocs_code="OC1", is_current=True)
    assert _keys(flt) == ["chunk_level", "ocs_code", "is_current"]


def test_build_filter_empty_is_none():
    assert build_filter() is None


def test_build_filter_rejects_code_kwargs():
    # k_codes/s_codes/attitude_codes are gone in v3 — passing them must error
    import pytest
    with pytest.raises(TypeError):
        build_filter(k_codes=["K01"])
