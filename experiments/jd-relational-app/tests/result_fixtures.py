"""Synthetic observations for contract tests, never evidence of a real commit."""


def observed_result(status="no_change", phase=None):
    success = status in {"committed", "no_change"}
    unbound = status in {"busy", "archived", "operation_conflict"} or phase == "unbound"
    confirmed = not unbound and status != "outcome_unknown" and phase != "unconfirmed"
    next_action = {"invalid_input": "correct_arguments", "target_missing": "reread_current",
                   "stale_view": "reread_current", "relationship_conflict": "correct_arguments",
                   "dependent_items": "resolve_dependencies"}.get(status, "stop")
    if success:
        next_action = "continue"
    elif not confirmed and not unbound:
        next_action = "reconcile_operation"
    return {"status": status, "effect": "changed" if status == "committed" else "unknown" if status == "outcome_unknown" else "unchanged",
            "receipt_durability": "confirmed" if confirmed else "unconfirmed",
            "operation_ref": None if unbound else "issued-operation",
            "result_revision_ref": "issued-result" if success else None,
            "change_ref": "issued-change" if status == "committed" else None,
            "error": None if success else {"code": status, "message": "合成結果；不代表執行過資料庫操作。", "related_refs": []},
            "next_action": next_action}
