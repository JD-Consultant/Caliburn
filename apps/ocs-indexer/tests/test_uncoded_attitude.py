"""Shared OCS contract values survive the consumer's pure normalization."""

from jd_ocs_indexer.ingestion.normalizer import normalize
from jd_ocs_indexer.models.ocs import OCSDocument


def test_uncoded_attitude_text_and_level_six_survive_normalization():
    source = OCSDocument.model_validate({
        "ocs_profile": {"ocs_code": "TEST1234", "ocs_level": 6},
        "ocs_attitude": {"attitudes": [{"code": None, "name": "來源沒有代碼的態度正文"}]},
        "ocs_content": {"ocu_units": [{"ocu_code": "T1", "tasks": [{
            "task_codes": [{"code": "T1.1", "name": "任務"}],
            "competency_blocks": [{"competency_level": 6}],
        }]}]},
    })
    result = normalize(source)
    assert result.attitude_terms == ["來源沒有代碼的態度正文"]
    assert [(pair.code, pair.name) for pair in result.attitude_pairs] == [("", "來源沒有代碼的態度正文")]
    assert result.attitude_codes == []
    assert result.ocs_level == 6
    assert result.units[0].task_groups[0].blocks[0].competency_level == 6
