from jd_ocs_indexer.validation.search import build_filter


def test_build_filter_empty_returns_none():
    assert build_filter() is None


def test_build_filter_level_and_ocs():
    flt = build_filter(level="profile", ocs_code="SMS2512-002v1")
    assert [c.key for c in flt.must] == ["chunk_level", "ocs_code"]


def test_build_filter_codes_and_is_current():
    flt = build_filter(is_current=True, k_codes=["K05"], s_codes=["S03"], attitude_codes=["A01"])
    assert [c.key for c in flt.must] == ["is_current", "k_codes", "s_codes", "attitude_codes"]


def test_build_filter_is_current_false_is_included():
    flt = build_filter(is_current=False)
    assert flt is not None and flt.must[0].key == "is_current"
