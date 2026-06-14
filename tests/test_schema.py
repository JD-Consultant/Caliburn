from jd_ocs_indexer.store import schema


def test_v3_indexes_are_the_nine_global_filterable_fields():
    keys = [name for name, _ in schema.PAYLOAD_INDEXES]
    assert keys == [
        "chunk_level", "ocs_code", "ocs_code_base", "job_title",
        "is_current", "version", "ocs_level",
        "industry_codes", "occupation_codes",
    ]


def test_v3_drops_ocs_local_and_constant_indexes():
    keys = {name for name, _ in schema.PAYLOAD_INDEXES}
    for dropped in ("k_codes", "s_codes", "attitude_codes", "task_ids",
                    "unit_id", "schema_version", "embedding_provider", "competency_level"):
        assert dropped not in keys
