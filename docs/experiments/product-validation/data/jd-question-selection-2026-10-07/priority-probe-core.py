"""Isolated selection probe seams; no credential or database actions on import."""

import ast
import hashlib
import importlib.util
import json
import sys
import time
from collections.abc import Callable
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from types import ModuleType
from typing import Any

import httpx2

HERE = Path(__file__).resolve().parent
ROOT = next(path for path in HERE.parents if (path / "AGENTS.md").is_file())
INTPLAN = ROOT / "docs/experiments/product-validation/interview-plan-comparison-2026-10-07"


def load_module(name: str, path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


existing = load_module("priority_probe_existing_guard", INTPLAN / "guard.py")
DEADLINE = datetime.fromisoformat("2026-10-07T08:30:34+00:00")
_COUNTED_INPUT_LIMIT = "batch counted input token limit reached"
COUNTERS = {
    "generations": 256,
    "outbound": 600,
    "counted_input": 16000000,
    "compacts": 8,
}
GLOBAL_COUNTER_LIMITS = {
    "generations": 3000,
    "outbound": 7000,
    "counted_input": 180000000,
    "compacts": 32,
}
ARTIFACT_ROOT = Path(
    "C:/Users/chenb/.codex/visualizations/2026/10/06/01a11182-e198-7652-87d2-d90d10463ed1/caliburn-intplan-comparison"
)
OUTPUT_ROOT = ARTIFACT_ROOT / "question-priority-probe"
BEFORE = "- 依回答逐步釐清本人動作、工作對象、觸發與輸入、判斷依據、產出及用途、完成要求、\n  自主權限、交接和責任界線。優先問會改變責任、範圍、重要要求或專業判斷的缺口；\n  抽象說法可請員工舉最近實例，再區分正常做法與例外。\n".encode()
AFTER = "- 依回答逐步釐清本人動作、工作對象、觸發與輸入、判斷依據、產出及用途、完成要求、\n  自主權限、交接和責任界線。選下一問時，在目前可問的缺口之間比較：\n  員工給出不同答案，最可能使哪一項責任、範圍、重要要求或專業判斷的理解改變？\n  優先問影響較大且員工能具體回答的一題。抽象說法可請員工舉最近實例，\n  再區分正常做法與例外。\n".encode()
STUDY_CASES = [
    f"{p}-r{r}-{g}"
    for r in (1, 2)
    for p in ("warehouse", "course_admin")
    for g in (("P1", "P2") if r == 1 else ("P2", "P1"))
]
CASE_KEYS = (
    "warehouse_environment",
    "warehouse_errors",
    "warehouse_load",
    "unknown_is_not_unexplored",
    "refused",
    "excluded",
)


def file_hash(path: str | Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read_json(path: str | Path) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def constant(source: bytes, name: str) -> str:
    for node in ast.parse(source.decode("utf-8")).body:
        if isinstance(node, ast.Assign) and any(
            isinstance(t, ast.Name) and t.id == name for t in node.targets
        ):
            if (
                isinstance(node.value, ast.Call)
                and not node.value.args
                and not node.value.keywords
                and isinstance(node.value.func, ast.Attribute)
                and node.value.func.attr == "strip"
                and isinstance(node.value.func.value, ast.Constant)
                and isinstance(node.value.func.value.value, str)
            ):
                return node.value.func.value.value.strip()
            return ast.literal_eval(node.value)
    raise ValueError("Missing instruction constant")


def replace_candidate(source: bytes) -> bytes:
    if source.count(BEFORE) != 1 or AFTER in source:
        raise ValueError("Candidate must replace exactly one original bullet")
    return source.replace(BEFORE, AFTER, 1)


def validate_accounting(
    prior: dict[str, Any], inherited: dict[str, Any] | None = None
) -> dict[str, Any]:
    spent = Decimal(prior["spent_usd"])
    occupied = Decimal(prior["occupied_usd"])
    reserves = {key: Decimal(value) for key, value in prior["retained_reservations"].items()}
    if (
        not spent.is_finite()
        or spent < 0
        or not occupied.is_finite()
        or occupied != spent + sum(reserves.values(), Decimal(0))
        or any(not value.is_finite() or value <= 0 for value in reserves.values())
    ):
        raise ValueError("Invalid accounting")
    if any(type(prior[key]) is not int or prior[key] < 0 for key in COUNTERS):
        raise ValueError("Invalid cumulative counters")
    if inherited is not None:
        validate_accounting(inherited)
        if (
            spent < Decimal(inherited["spent_usd"])
            or any(prior[key] < inherited[key] for key in COUNTERS)
            or any(
                prior["retained_reservations"].get(key) != value
                for key, value in inherited["retained_reservations"].items()
            )
        ):
            raise ValueError("Original consumption or unknown reservations changed")
    return prior


def carrier(ledger_path: str | Path, lock_path: str | Path) -> dict[str, Any]:
    """Metadata only; all four quality verdict bodies remain unread."""
    state, lock = read_json(ledger_path), read_json(lock_path)
    if (
        lock.get("all_quality_locked") is not True
        or lock.get("ledger_sha256") != file_hash(ledger_path)
        or not exact_study_cases(lock.get("case_ids", []))
    ):
        raise ValueError("All formal study quality must be locked to final ledger")
    if not exact_study_cases(state.get("all_scheduled_cases", [])) or not exact_study_cases(
        state.get("completed_cases", [])
    ):
        raise ValueError("All eight formal cases must be complete")
    reviews = lock.get("reviews", [])
    if (
        len(reviews) != 4
        or len({item["path"] for item in reviews}) != 4
        or any(
            item.get("locked") is not True or file_hash(item["path"]) != item["sha256"]
            for item in reviews
        )
    ):
        raise ValueError("Four immutable quality reviews required")
    inherited = lock["inherited_guard"]
    if len(inherited.get("retained_reservations", {})) < 2:
        raise ValueError("Both original unknown reserves must be identified")
    return validate_accounting(state["guard"], inherited)


def exact_study_cases(value: Any) -> bool:
    return isinstance(value, list) and len(value) == 8 and set(value) == set(STUDY_CASES)


class ProbeGuard(existing.BatchGuard):
    def count(self, payload: dict[str, Any], tokens: int) -> None:
        stopped_before = self.stop_reason
        try:
            super().count(payload, tokens)
        except RuntimeError as error:
            # The inherited guard validated and received this count before its cap
            # rejection. Retain consumption, while preserving the original stop.
            if stopped_before is None and str(error) == _COUNTED_INPUT_LIMIT:
                self.counted_input += tokens
            raise

    def check(self, payload: dict[str, Any]) -> None:
        remaining = (DEADLINE - self.utc_clock()).total_seconds()
        if remaining <= 0:
            self.refuse("absolute deadline reached")
        if self.started is None:
            self.seconds = min(2700, remaining)
        super().check(payload)

    def reserve_count(self) -> None:
        # Conservative research estimate, not an official count-call price.
        if self.occupied + Decimal("0.0001") > self.limit:
            self.refuse("Count-call budget reached")
        self.spent += Decimal("0.0001")

    def outbound_attempt(self, payload: dict[str, Any]) -> None:
        super().outbound_attempt(payload)
        self.inspect_request(payload)
        if payload.get("reasoning", {}).get("effort", "high") != "high":
            self.refuse("Unapproved reasoning effort")
        if any(
            tool.get("name") in {"read_interview_plan", "edit_interview_plan"}
            for tool in payload.get("tools", [])
        ):
            self.refuse("Note capability may not be enabled")


def carried_guard(
    prior: dict[str, Any],
    *,
    now: datetime | None = None,
    clock: Callable[[], float] = time.monotonic,
    verify_frozen: Callable[[], None] = lambda: None,
) -> ProbeGuard:
    validate_accounting(prior)
    if any(prior[key] >= limit for key, limit in GLOBAL_COUNTER_LIMITS.items()):
        raise ValueError("Cumulative counter exhausted")
    limits = {
        key: min(GLOBAL_COUNTER_LIMITS[key], prior[key] + increment)
        for key, increment in COUNTERS.items()
    }
    utc_clock = (lambda: now) if now is not None else (lambda: datetime.now(UTC))
    current = utc_clock()
    seconds = min(2700, (DEADLINE - current).total_seconds())
    if seconds <= 0:
        raise ValueError("Absolute deadline expired")
    occupied = Decimal(prior["occupied_usd"])
    limit = min(Decimal("8.00"), occupied + Decimal("0.50"))
    if occupied >= limit:
        raise ValueError("Cumulative budget exhausted")
    guard = ProbeGuard(
        limit=limit,
        seconds=seconds,
        clock=clock,
        verify_frozen=verify_frozen,
        max_generations=limits["generations"],
        max_outbound=limits["outbound"],
        max_counted_input=limits["counted_input"],
        max_compacts=limits["compacts"],
    )
    guard.spent = Decimal(prior["spent_usd"])
    guard.attempts = {key: Decimal(value) for key, value in prior["retained_reservations"].items()}
    for key in COUNTERS:
        setattr(guard, key, prior[key])
    guard.utc_clock = utc_clock
    guard.inspect_request = lambda payload: None
    return guard


def inspect_public_request(
    payload: dict[str, Any],
    *,
    expected_instructions: str,
    private_answers: list[str],
    disclosed: set[str],
    private_criteria: tuple[str, ...] = (),
) -> None:
    """Byte leakage fence only; never interprets question quality or selects answers."""
    if "instructions" in payload and payload["instructions"] != expected_instructions:
        raise ValueError("Consultant method differs from its frozen arm")
    public_input = json.dumps(payload, ensure_ascii=False)
    if any(text in public_input for text in private_criteria):
        raise ValueError("Private assessment leaked into model payload")
    if any(answer not in disclosed and answer in public_input for answer in private_answers):
        raise ValueError("Unsubmitted private answer leaked into model payload")
    if any(
        case_key in public_input
        for case_key in (
            "warehouse_environment",
            "warehouse_errors",
            "warehouse_load",
            "unknown_is_not_unexplored",
            "target_answer",
            "normal_clarification",
        )
    ):
        raise ValueError("Private labels leaked into model payload")


def eligible_sources(selection: dict[str, Any], originals: list[dict[str, Any]]) -> list[str]:
    if selection.get("actually_submitted") is not True:
        return []
    return [
        item["source_id"]
        for item in originals
        if item["speaker"] == "employee"
        and item["interview_text"] == selection["answer"]
        and item["source_id"] not in selection.get("prior_source_ids", [])
    ]


class ProbeTransport(existing.GuardedTransport):
    async def handle_async_request(self, request: httpx2.Request) -> httpx2.Response:
        payload = None
        if request.url.path == "/v1/responses/input_tokens":
            payload = json.loads(request.content)
            self.guard.verify_frozen()
            self.guard.check(payload)
            self.guard.reserve_count()
        counted_before = self.guard.counted_input
        try:
            return await super().handle_async_request(request)
        except RuntimeError as error:
            if (
                payload is not None
                and str(error) == _COUNTED_INPUT_LIMIT
                and self.guard.counted_input > counted_before
            ):
                self.record(
                    "count",
                    fingerprint=existing.fingerprint(payload),
                    input_tokens=self.guard.counted_input - counted_before,
                    role=existing.role(payload),
                    input_sha256=existing.digest(payload.get("input", [])),
                    **self.guard.state(),
                )
            raise


def build_cases() -> list[dict[str, Any]]:
    base = {
        case["case_id"]: case
        for case in read_json(HERE.parent / "jd-condition-exploration-2026-10-07/cases.json")[
            "cases"
        ]
    }
    overrides = read_json(HERE / "case-overrides.json")
    cases = []
    for key in (
        "warehouse_environment",
        "warehouse_errors",
        "warehouse_load",
        "unknown_is_not_unexplored",
    ):
        case = json.loads(json.dumps(base[key]))
        case.pop("criteria")
        case.pop("case_id")
        if key in overrides:
            case["prior_employee_statements"].append(overrides[key]["append_statement"])
            case["employee_input"] = overrides[key]["employee_input"]
        case["max_turns"] = 3 if key in overrides else 1
        cases.append(case)
    for key, statement in [
        ("refused", "搬運方式這一塊我不想回答；其他工作可以談。"),
        (
            "excluded",
            "我不負責供應商退貨處理，那由採購辦理；我只按安排上架和登記，這段沒有變更。",
        ),
    ]:
        case = json.loads(json.dumps(base["warehouse_errors"]))
        case.pop("criteria")
        case.pop("case_id")
        case["prior_employee_statements"].append(statement)
        case["employee_input"] = statement
        case["max_turns"] = 1
        cases.append(case)
    return cases


def build_assessments(policy: dict[str, Any]) -> dict[str, Any]:
    """Private quality material; no assessment field is eligible for model/seed."""
    cases = read_json(HERE.parent / "jd-condition-exploration-2026-10-07/cases.json")["cases"]
    original = {case["case_id"]: case for case in cases}
    assessments = {
        key: {
            "criteria": original[key]["criteria"],
            "target": policy["answers"][key]["target_answer"]
            if key in policy["answers"]
            else original[key]["criteria"][0],
            "answer_limitations": "私人 target 是評閱基準，不是已披露原話。未在實際 employee_originals 取得的內容不能算已發現或有據入稿；取得後保留 target 全文的限定、未知及原職責界線。",
        }
        for key in CASE_KEYS[:4]
    }
    assessments["refused"] = {
        "target": "尊重員工對搬運方式的明確拒答；拒答不等於不負責。",
        "criteria": [
            "無員工本人重開或願意補充時，不以等義問題追問已拒答的搬運方式。",
            "可探索其他已知工作中有價值且可回答的缺口。",
            "不將拒答改寫為沒有搬運工作或不負責。",
        ],
        "answer_limitations": "只有員工原話明示拒答；未補造先前顧問問句，亦未否認原本搬運工作。",
    }
    assessments["excluded"] = {
        "target": "不再確認員工是否負責供應商退貨；不把明確排除寫成本人工作。",
        "criteria": [
            "沒有員工新的退貨線索時，不重問是否負責供應商退貨。",
            "保留採購負責退貨的界線，不把否認轉成本人職責。",
            "可探索實際已知上架工作中的其他缺口。",
        ],
        "answer_limitations": "員工只按安排上架和登記，供應商退貨由採購辦理；沒有本人重開該責任。",
    }
    return assessments


def quality_bundle(
    *,
    opaque_id: str,
    starting_formal_jd: dict[str, Any],
    starting_sources: dict[str, Any],
    formal_jd: dict[str, Any],
    assessment: dict[str, Any],
    interviews: dict[str, Any],
    trial_replies: list[dict[str, Any]],
    fixed_sources: dict[str, Any],
) -> dict[str, Any]:
    return {
        "opaque_id": opaque_id,
        "starting_formal_jd": starting_formal_jd,
        "starting_fixed_source_contents": starting_sources,
        "assessment": assessment,
        "formal_jd": formal_jd,
        "employee_originals": [
            {
                key: item[key]
                for key in (
                    "source_id",
                    "interview_sequence",
                    "speaker",
                    "interview_text",
                )
            }
            for item in interviews["messages"]
            if item["speaker"] == "employee"
        ],
        "questions": [
            item["exchange"]["consultant_reply"]["interview_text"] for item in trial_replies
        ],
        "fixed_source_contents": fixed_sources,
    }


def validate_selection(
    decision: dict[str, Any], question: str, policy: dict[str, Any], case_key: str
) -> str | None:
    if (
        decision.get("question_quote") != question
        or not decision.get("reason")
        or decision.get("review_method") != "semantic_review"
    ):
        raise ValueError("A frozen semantic review of the exact question is required")
    kind = decision.get("answer_kind")
    if kind == "stop":
        return None
    if kind == "unknown":
        return policy["unknown_reply"]
    if kind not in {"target_answer", "normal_clarification"}:
        raise ValueError("Unapproved employee answer")
    return policy["answers"][case_key][kind]


def answer_review_packet(
    *,
    opaque_id: str,
    question_quote: str,
    originals: list[dict[str, Any]],
    policy: dict[str, Any],
    case_key: str,
) -> dict[str, Any]:
    return {
        "opaque_id": opaque_id,
        "question_quote": question_quote,
        "answer_policy_rule": policy["rule"],
        "employee_originals": [
            {key: item[key] for key in ("speaker", "interview_text")}
            for item in originals
            if item["speaker"] == "employee"
        ],
        "answer_options": {
            "unknown": policy["unknown_reply"],
            "stop": None,
            **policy["answers"][case_key],
        },
        "instruction": "以問句語意選target_answer／normal_clarification／unknown／stop；不以關鍵字觸發，無問題或已收尾選stop。回答選擇不代表品質分數。",
    }


def verify_frozen(manifest: dict[str, Any]) -> None:
    for name, expected in manifest["files"].items():
        if file_hash(ROOT / name) != expected:
            raise ValueError("Frozen source changed")


def next_schedule() -> list[dict[str, Any]]:
    return [
        {
            "case_key": case_key,
            "repeat": repeat,
            "arm": arm,
            "trial": f"c{index:02}-r{repeat}-{arm}",
        }
        for repeat in (1, 2)
        for index, case_key in enumerate(CASE_KEYS, 1)
        for arm in (("B0", "B1") if repeat == 1 else ("B1", "B0"))
    ]
