from app.graph_v3.state import InterviewState, new_state


def test_new_state_has_v3_shape():
    s = new_state(job_profile_id="p1", job_title="工程師", job_summary="做事")
    assert s["current_step"] == "pick_profile"
    assert s["profile"]["selected_ocs_code"] is None
    assert s["tasks"] == [] and s["ksa"] == {"knowledge": [], "skills": [], "attitudes": []}
