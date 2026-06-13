from jd_ocs_indexer.api import service


def _block(ocs, uorder, uid, utitle, tids, ttls, acts):
    return {
        "ocs_code": ocs, "chunk_level": "block", "job_title": "JT-" + ocs,
        "unit_order": uorder, "unit_id": uid, "unit_title": utitle,
        "task_ids": tids, "task_titles": ttls, "work_activity_terms": acts,
    }


def test_task_pool_groups_and_sorts(make_qdrant):
    blocks = [
        _block("OC1", 2, "U2", "Unit Two", ["T2.1"], ["t21"], ["actA"]),
        _block("OC1", 1, "U1", "Unit One", ["T1.1"], ["t11"], ["actB", "actC"]),
    ]
    fake = make_qdrant(scroll_pages=[(blocks, None)])
    out = service.build_task_pool(fake, "coll", ocs_codes=["OC1"], activity_examples=1)
    g = out["groups"][0]
    assert g["ocs_code"] == "OC1" and g["job_title"] == "JT-OC1"
    assert [u["unit_id"] for u in g["units"]] == ["U1", "U2"]
    assert g["units"][0]["tasks"][0]["task_id"] == "T1.1"
    assert g["units"][0]["tasks"][0]["activity_examples"] == ["actB"]


def test_task_pool_multi_task_block(make_qdrant):
    blocks = [_block("OC1", 1, "U1", "U1", ["T1.1", "T1.2"], ["t11", "t12"], ["actX"])]
    fake = make_qdrant(scroll_pages=[(blocks, None)])
    out = service.build_task_pool(fake, "coll", ocs_codes=["OC1"], activity_examples=2)
    tasks = out["groups"][0]["units"][0]["tasks"]
    assert [t["task_id"] for t in tasks] == ["T1.1", "T1.2"]
    assert all(t["activity_examples"] == ["actX"] for t in tasks)


def test_task_pool_preserves_request_order(make_qdrant):
    blocks = [
        _block("OC2", 1, "U", "U", ["T1"], ["t"], []),
        _block("OC1", 1, "U", "U", ["T1"], ["t"], []),
    ]
    fake = make_qdrant(scroll_pages=[(blocks, None)])
    out = service.build_task_pool(fake, "coll", ocs_codes=["OC1", "OC2"])
    assert [g["ocs_code"] for g in out["groups"]] == ["OC1", "OC2"]


def test_task_pool_titles_shorter_than_ids(make_qdrant):
    # defensive: task_titles can be shorter than task_ids (None filtered upstream)
    blocks = [_block("OC1", 1, "U1", "U1", ["T1.1", "T1.2"], ["only-one"], ["a"])]
    fake = make_qdrant(scroll_pages=[(blocks, None)])
    out = service.build_task_pool(fake, "coll", ocs_codes=["OC1"])
    tasks = {t["task_id"]: t["task_title"] for t in out["groups"][0]["units"][0]["tasks"]}
    assert tasks == {"T1.1": "only-one", "T1.2": None}


def test_task_pool_scroll_paginates(make_qdrant):
    # _scroll_all must consume every page until offset is None (shared primitive).
    page1 = [_block("OC1", 1, "U1", "Unit One", ["T1.1"], ["t11"], ["a1"])]
    page2 = [_block("OC1", 2, "U2", "Unit Two", ["T2.1"], ["t21"], ["a2"])]
    fake = make_qdrant(scroll_pages=[(page1, "cursor"), (page2, None)])
    out = service.build_task_pool(fake, "coll", ocs_codes=["OC1"])
    assert [u["unit_id"] for u in out["groups"][0]["units"]] == ["U1", "U2"]
