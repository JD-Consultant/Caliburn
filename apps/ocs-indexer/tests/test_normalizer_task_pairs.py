from jd_ocs_indexer.models.ocs import OCSDocument
from jd_ocs_indexer.ingestion.normalizer import normalize


def _doc_with_partial_task() -> OCSDocument:
    return OCSDocument.model_validate({
        "ocs_profile": {"ocs_code": "OC1v1", "ocs_name": {"occupation_name": "JT"}},
        "ocs_content": {"ocu_units": [
            {"ocu_code": "U1", "ocu_name": "Unit 1", "tasks": [
                {"task_codes": [
                    {"code": "T1.1", "name": "任務一"},
                    {"code": "T1.2", "name": ""},
                    {"code": "T1.3", "name": "任務三"},
                ], "competency_blocks": []},
            ]},
        ]},
    })


def test_task_pairs_are_aligned():
    norm = normalize(_doc_with_partial_task())
    group = norm.units[0].task_groups[0]
    pairs = [(p.code, p.name) for p in group.tasks]
    assert pairs == [("T1.1", "任務一"), ("T1.3", "任務三")]
