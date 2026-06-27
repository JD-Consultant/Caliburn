from app.graph_v3.state import new_state, task_key


def test_new_state_has_per_task_ksa():
    s = new_state(job_profile_id="p1", job_title="工程師")
    assert s["ksa"] == {"pool": {"knowledge": [], "skills": [], "attitudes": []},
                        "by_task": {}, "attitudes": [], "ks_index": 0}
    assert s["profile"]["selected_ocs_code"] is None


def test_task_key_prefers_indexer_task_id():
    assert task_key({"task_name": "巡檢", "indexer_ref": {"task_id": "T1"}}) == "T1"
    assert task_key({"task_name": "巡檢"}) == "巡檢"
