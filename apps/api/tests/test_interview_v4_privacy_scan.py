import json

from evals.interview_v4.privacy_scan import scan_case


def test_privacy_scan_reports_categories_and_locations_without_source_text(tmp_path):
    secret = "王小明"
    (tmp_path / "transcript.jsonl").write_text(
        json.dumps({"seq": 1, "role": "employee", "text": f"我叫{secret}"}, ensure_ascii=False)
        + "\n",
        encoding="utf-8",
    )
    (tmp_path / "observed_document.json").write_text(
        json.dumps({"note": "password=hunter2"}),
        encoding="utf-8",
    )

    report = scan_case(tmp_path)

    assert report["finding_counts"] == {"PERSON_CUE": 1, "SECRET_ASSIGNMENT": 1}
    assert report["manual_review_still_required"] is True
    assert secret not in json.dumps(report, ensure_ascii=False)
    assert "hunter2" not in json.dumps(report, ensure_ascii=False)


def test_owner_confirmed_synthetic_case_keeps_findings_without_privacy_hold(tmp_path):
    (tmp_path / "case.json").write_text(
        json.dumps({"privacy": {"status": "synthetic"}}),
        encoding="utf-8",
    )
    (tmp_path / "transcript.jsonl").write_text(
        json.dumps({"seq": 1, "role": "employee", "text": "某某股份有限公司"},
                   ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    report = scan_case(tmp_path)

    assert report["finding_counts"] == {"ORGANIZATION_CUE": 1}
    assert report["manual_review_still_required"] is False
