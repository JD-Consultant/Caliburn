import json

from evals.interview_v4.candidate_metrics import summarize_candidate


def _write_json(path, value):
    path.write_text(json.dumps(value), encoding="utf-8")


def test_candidate_metrics_never_echoes_transcript_or_guard_text(tmp_path):
    secret = "confidential-customer-name"
    _write_json(tmp_path / "case.json", {"case_id": "CASE-001"})
    (tmp_path / "transcript.jsonl").write_text(
        json.dumps({"role": "employee", "text": secret}) + "\n",
        encoding="utf-8",
    )
    _write_json(tmp_path / "review_events.json", [{"decision": "accepted"}])
    _write_json(tmp_path / "observed_document.json", {"summary": secret})
    _write_json(tmp_path / "source_audit.json", {
        "fixture_provenance": {"initial_document": "unavailable"},
        "llm_calls": [{
            "role": "scribe",
            "model": "test-model",
            "duration_ms": 10,
            "prompt_tokens": 20,
            "completion_tokens": 5,
            "guard_verdicts": [f"verify-reject:op[2] quote:{secret}"],
        }],
    })

    metrics = summarize_candidate(tmp_path)
    serialized = json.dumps(metrics)
    assert secret not in serialized
    assert metrics["llm_calls"]["guard_categories"] == {"verify_reject": 1}
    assert metrics["llm_calls"]["verify_reject_checks"] == {"quote": 1}
    assert metrics["llm_calls"]["verify_reject_reasons"] == {"other": 1}
    assert metrics["transcript"]["characters_by_role"] == {"employee": len(secret)}

    _write_json(tmp_path / "case.json", {
        "case_id": "CASE-001",
        "privacy": {"status": "synthetic"},
    })
    synthetic_metrics = summarize_candidate(tmp_path)
    assert synthetic_metrics["privacy_prescreen"]["manual_review_still_required"] is False
