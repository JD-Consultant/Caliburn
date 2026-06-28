from app.core.domain.ocs_doc import assemble_final


def _has_underscore_key(node) -> bool:
    if isinstance(node, dict):
        if any(k.startswith("_") for k in node):
            return True
        return any(_has_underscore_key(v) for v in node.values())
    if isinstance(node, list):
        return any(_has_underscore_key(v) for v in node)
    return False


def test_assemble_final_strips_underscore_keys_at_every_depth():
    draft = {
        "version_info": {"versions": []},
        "ocs_profile": {
            "ocs_code": "AAA-001",
            "ocs_name": {"occupation_name": "x"},
            "category": {
                "job_categories": [{"code": "J", "name": "n", "_id": "u1", "_src": "official"}],
                "occupations": [],
                "industries": [],
            },
        },
        "ocs_content": {
            "ocu_units": [
                {
                    "ocu_code": "T1",
                    "ocu_name": "u",
                    "_uid": "uu",
                    "tasks": [
                        {
                            "task_codes": [{"code": "T1.1", "name": "t"}],
                            "_tid": "tt",
                            "_notes": "raw",
                            "competency_blocks": [
                                {
                                    "competency_level": 1,
                                    "indicators": [{"code": "P1.1.1", "text": "p", "_id": "i1", "_src": "custom"}],
                                    "outputs": [{"code": "O1.1.1", "name": "o", "_id": "o1", "_ref": {"ocs_code": "X"}}],
                                    "knowledge": [{"code": "K01", "name": "k", "_id": "k1", "_src": "official"}],
                                    "skills": [],
                                }
                            ],
                        }
                    ],
                }
            ]
        },
        "ocs_attitude": {"attitudes": [{"code": "A01", "name": "a", "_id": "a1", "_src": "official"}]},
        "notes": {"prerequisites": [], "supplements": []},
        "_pool": {"junk": 1},
    }
    out = assemble_final(draft)
    assert not _has_underscore_key(out)
