"""Pure preparation guards for this fixed-candidate experiment."""

import importlib.util
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
FIRST = HERE.parent / "2026-10-04-occupation-retrieval"


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def generation_messages(case):
    questions = ["請描述目前實際負責的工作、對象與做到的範圍。",
                 "請補充本人如何處理、判斷與交付，以及決定權和例外。",
                 "還有哪些工作、頻率、更正或尚未確認的責任界線？"]
    if len(case["employee_messages"]) != 3 or any(not text.strip() for text in case["employee_messages"]):
        raise ValueError("Three nonempty employee messages required")
    messages = []
    for index, (question, text) in enumerate(zip(questions, case["employee_messages"], strict=True)):
        messages.extend([
            {"interview_sequence": index * 2 + 1, "speaker": "app" if index == 0 else "consultant", "text": question},
            {"interview_sequence": index * 2 + 2, "speaker": "employee", "text": text}])
    return messages


def published_b2(snapshot):
    if not any(item["layer"] == "work_understanding" for item in snapshot["objects"]):
        return None
    # Generation runs in the API environment; retrieval's NumPy dependency is lazy.
    sys.path.insert(0, str(FIRST))
    try:
        from prepare import memory_case
    finally:
        sys.path.pop(0)
    prepared = memory_case("extraction", "extraction", snapshot, "diagnostic baseline", [], {}, "", [])
    text = prepared["inputs"]["B_b2"]
    if not text.strip():
        raise ValueError("Published B2 has an empty body")
    return text


def decision(case, ranking):
    sys.path.insert(0, str(FIRST))
    try:
        from evaluation import ranking_metrics
    finally:
        sys.path.pop(0)
    metrics = ranking_metrics([key for key, _ in ranking], case["grades"])
    primary = {key for key, grade in case["grades"].items() if grade == 3}
    return {**metrics, "expected_abstain": case["kind"] != "positive",
            "primary_in_top10": bool(primary & {key for key, _ in ranking[:10]}) if primary else None,
            "legacy_threshold": 0.675,
            "legacy_threshold_accepts": bool(ranking and ranking[0][1] >= 0.675)}
