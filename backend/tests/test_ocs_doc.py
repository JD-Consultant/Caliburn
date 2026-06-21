"""Pure tests for app.services.ocs_doc (D27 T2). No DB, no async."""

from app.services.ocs_doc import skeleton, assemble_final, validate


TOP_KEYS = {"version_info", "ocs_profile", "ocs_content", "ocs_attitude", "notes"}


def _profile():
    return {
        "ocs_code": "FSI3311-001v3",
        "occupation_name": "金融服務人員",
        "job_description": "處理金融業務",
        "ocs_level": 3,
    }


def _units_tasks():
    return [
        {
            "task_name": "接待客戶",
            "unit_id": "T1",
            "unit_title": "客戶服務",
            "indexer_ref": {"ocs_code": "FSI3311-001v3", "task_id": "T1.1"},
        },
        {
            "task_name": "處理申訴",
            "unit_id": "T1",
            "unit_title": "客戶服務",
            "indexer_ref": {"ocs_code": "FSI3311-001v3", "task_id": "T1.2"},
        },
        {
            "task_name": "撰寫報告",
            "unit_id": "T2",
            "unit_title": "行政作業",
            # no task_id -> should be synthesized
            "indexer_ref": {"ocs_code": "FSI3311-001v3"},
        },
    ]


def test_skeleton_shape_and_grouping():
    doc = skeleton(_profile(), _units_tasks())

    # 5 top-level keys
    assert set(doc.keys()) >= TOP_KEYS

    # ocs_name has both keys
    assert "job_category_name" in doc["ocs_profile"]["ocs_name"]
    assert doc["ocs_profile"]["ocs_name"]["occupation_name"] == "金融服務人員"
    assert doc["ocs_profile"]["ocs_code"] == "FSI3311-001v3"

    units = doc["ocs_content"]["ocu_units"]
    assert len(units) == 2

    # real unit_ids preserved in first-seen order
    assert [u["ocu_code"] for u in units] == ["T1", "T2"]
    assert units[0]["ocu_name"] == "客戶服務"

    # multi-task unit has 2 tasks
    assert len(units[0]["tasks"]) == 2
    assert len(units[1]["tasks"]) == 1

    # task_codes use real task_ids when given
    assert units[0]["tasks"][0]["task_codes"][0]["code"] == "T1.1"
    assert units[0]["tasks"][1]["task_codes"][0]["code"] == "T1.2"
    # synthesize f"{ocu_code}.{t}" when missing task_id
    assert units[1]["tasks"][0]["task_codes"][0]["code"] == "T2.1"
    assert units[1]["tasks"][0]["task_codes"][0]["name"] == "撰寫報告"

    # exactly one empty block per task
    for u in units:
        for t in u["tasks"]:
            assert len(t["competency_blocks"]) == 1
            blk = t["competency_blocks"][0]
            assert blk["competency_level"] is None
            assert blk["indicators"] == []
            assert blk["outputs"] == []
            assert blk["knowledge"] == []
            assert blk["skills"] == []

    assert doc["ocs_attitude"]["attitudes"] == []
    assert "prerequisites" in doc["notes"]
    assert "supplements" in doc["notes"]

    # a skeleton SHOULD validate clean
    assert validate(doc) == []


def test_skeleton_synthetic_unit_bucket():
    # no unit info → unit code synthesised T1, name left BLANK for the user to
    # fill (cherry-pick semantics); task renumbered sequentially T1.1.
    tasks = [{"task_name": "孤兒任務", "indexer_ref": {}}]
    doc = skeleton(_profile(), tasks)
    units = doc["ocs_content"]["ocu_units"]
    assert len(units) == 1
    assert units[0]["ocu_code"] == "T1"
    assert units[0]["ocu_name"] == ""
    assert units[0]["tasks"][0]["task_codes"][0]["code"] == "T1.1"


def test_assemble_final_strips_frontend_keys():
    draft = skeleton(_profile(), _units_tasks())
    draft["_pool"] = {"knowledge": [{"code": "K99", "name": "x"}], "skills": [], "attitudes": []}
    draft["ocs_content"]["ocu_units"][0]["_uid"] = "u-abc"
    draft["ocs_content"]["ocu_units"][0]["tasks"][0]["_tid"] = "t-abc"
    out = assemble_final(draft)
    assert "_pool" not in out
    assert "_uid" not in out["ocs_content"]["ocu_units"][0]
    assert "_tid" not in out["ocs_content"]["ocu_units"][0]["tasks"][0]
    assert validate(out) == []


def test_assemble_final_completes_and_no_mutation():
    draft = skeleton(_profile(), _units_tasks())
    import copy
    snapshot = copy.deepcopy(draft)

    result = assemble_final(draft)

    assert validate(result) == []
    assert result["version_info"]["versions"]  # non-empty
    rec = result["version_info"]["versions"][0]
    assert rec["ocs_code"] == "FSI3311-001v3"
    assert rec["ocs_name"] == "金融服務人員"

    # input not mutated
    assert draft == snapshot


def test_assemble_final_fills_missing_blocks():
    draft = {
        "ocs_profile": {
            "ocs_code": "X",
            "ocs_name": {"job_category_name": None, "occupation_name": "Y"},
            "category": {"job_categories": [], "occupations": [], "industries": []},
            "job_description": "",
            "ocs_level": None,
        },
        "ocs_content": {
            "ocu_units": [
                {
                    "ocu_code": "T1",
                    "ocu_name": "u",
                    "tasks": [
                        {
                            "task_codes": [{"code": "T1.1", "name": "t"}],
                            # no competency_blocks at all
                        }
                    ],
                }
            ]
        },
        # missing version_info / ocs_attitude / notes
    }
    result = assemble_final(draft)
    assert validate(result) == []


def test_validate_missing_notes():
    doc = skeleton(_profile(), _units_tasks())
    del doc["notes"]
    errors = validate(doc)
    assert len(errors) >= 1
    assert any("notes" in e for e in errors)


def test_validate_empty_task_codes():
    doc = skeleton(_profile(), _units_tasks())
    doc["ocs_content"]["ocu_units"][0]["tasks"][0]["task_codes"] = []
    errors = validate(doc)
    assert len(errors) >= 1
    assert any("task_codes" in e for e in errors)


def test_validate_block_missing_knowledge():
    doc = skeleton(_profile(), _units_tasks())
    del doc["ocs_content"]["ocu_units"][0]["tasks"][0]["competency_blocks"][0]["knowledge"]
    errors = validate(doc)
    assert len(errors) >= 1
    assert any("knowledge" in e for e in errors)


def test_validate_attitudes_not_list():
    doc = skeleton(_profile(), _units_tasks())
    doc["ocs_attitude"]["attitudes"] = {"oops": "dict"}
    errors = validate(doc)
    assert len(errors) >= 1
    assert any("attitudes" in e for e in errors)
