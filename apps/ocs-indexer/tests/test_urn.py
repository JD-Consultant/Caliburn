# tests/test_urn.py
from jd_ocs_indexer.api import urn

def test_urn_scheme():
    assert urn.occupation_urn("OC1v2") == "ocs:OC1v2"
    assert urn.unit_urn("OC1v2", "T1") == "ocs:OC1v2:U:T1"
    assert urn.task_urn("OC1v2", "T1.1") == "ocs:OC1v2:T:T1.1"
    assert urn.item_urn("OC1v2", "K", "K01") == "ocs:OC1v2:K:K01"
