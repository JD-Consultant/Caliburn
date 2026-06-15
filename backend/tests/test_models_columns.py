from app.models import CompanyTask, JobProfile


def test_company_task_has_provenance_columns():
    cols = set(CompanyTask.__table__.columns.keys())
    assert {"source", "indexer_ref"} <= cols


def test_job_profile_has_selected_ocs_code():
    assert "selected_ocs_code" in JobProfile.__table__.columns.keys()
