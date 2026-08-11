from jd_ocs_indexer.models.ocs import OCSDocument
from jd_ocs_indexer.ingestion.normalizer import normalize


def _doc_with_partial_category() -> OCSDocument:
    return OCSDocument.model_validate({
        "ocs_profile": {
            "ocs_code": "OC1v1",
            "ocs_name": {"occupation_name": "JT"},
            "category": {
                "job_categories": [{"code": "FSI", "name": "金融財務"}],
                "occupations": [
                    {"code": "3311", "name": "經紀人"},
                    {"code": "X", "name": None},   # name missing — must stay aligned (lockstep)
                ],
                "industries": [{"code": "K6611", "name": "證券業"}],
            },
        },
    })


def test_category_pairs_are_lockstep_aligned():
    """occupations/industries with a missing name must not drift code↔name."""
    norm = normalize(_doc_with_partial_category())
    assert [(p.code, p.name) for p in norm.job_category_pairs] == [("FSI", "金融財務")]
    assert [(p.code, p.name) for p in norm.occupation_pairs] == [("3311", "經紀人"), ("X", "")]
    assert [(p.code, p.name) for p in norm.industry_pairs] == [("K6611", "證券業")]
