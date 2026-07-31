"""Probe U:丟棄式 grammar 探針,只問「移除 union 之後 grammar 能否編譯」。

**這是一次性實驗器材,不是產品程式。** 它不碰 PostgreSQL、不呼叫 `submit_employee_turn()`、
不動 production schema／prompt／application code。結果**不得**送進 application transition。

以 2026-07-31 那一次失敗請求為基礎(`output/job-analysis-live-smoke/<run>/turn-01.json`),
**只做一個機械轉換**:

```text
anyOf: [X, null]  →  X
```

Probe U 階段刻意**不做**:中性 sentinel(`""`／`0`／`"none"`／`[]`)、改 enum、改 property 數量或
名稱、改巢狀／陣列／`split_children`／`enablers` 結構、改 prompt／model／provider／route／
fallback、retry。輸出不需要有產品語意——這個 probe 不評估模型答得好不好。

**成本措辭保守**:先前一次 400 顯示 US$0,那是一次觀測,**不是官方的免費保證**。
因此送出前先算保守 reserve,超過 `--budget-usd`(預設且最大 US$0.05)就在 HTTP 之前停線。

用法(working directory:`apps/api`):

```powershell
uv run python scripts/job_analysis_grammar_probe.py --plan-only   # 離線:只印計數與 diff
uv run python scripts/job_analysis_grammar_probe.py               # 送出唯一一次 live request
```
"""

from __future__ import annotations

import argparse
import asyncio
import copy
import json
import os
import sys
from datetime import UTC, datetime
from decimal import Decimal
from hashlib import sha256
from pathlib import Path
from typing import Any

import httpx

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.config import settings  # noqa: E402
from app.job_analysis.providers import (  # noqa: E402
    CHAT_COMPLETIONS_URL,
    OpenRouterCatalogError,
    inspect_openrouter_execution,
)
from scripts.job_analysis_live_smoke import (  # noqa: E402
    METADATA_HEADERS,
    REPO_ROOT,
    canonical_request_json,
    fetch_endpoint_snapshot,
)


DEFAULT_CAPTURE_ROOT = REPO_ROOT / "output" / "job-analysis-live-smoke"
DEFAULT_OUTPUT_ROOT = REPO_ROOT / "output" / "job-analysis-grammar-probe"
PROBE_BUDGET_USD = Decimal("0.05")

# grammar 編譯發生在生成之前,所以 output 上限影響不到本 probe 的答案;把它壓到最低只是為了
# 讓「萬一編譯成功」的那一次落在 US$0.05 之內。這是成本上限逼出來的,不是第二個受測變因。
PROBE_MAX_OUTPUT_TOKENS = 16


class ProbeStopped(RuntimeError):
    """送出前的停線條件。不重試、不改條件再試。"""


# ── 純轉換與計數(離線可測)────────────────────────────────────────────────


def drop_nullable_unions(node: Any) -> Any:
    """`anyOf: [X, null]` → `X`。其餘一律原樣保留。

    只折疊「恰好兩個分支、其中一支是 `{"type": "null"}`」的 union。三支以上、或沒有 null 的
    union 都不動——那不是這次要測的變因。
    """
    if isinstance(node, list):
        return [drop_nullable_unions(item) for item in node]
    if not isinstance(node, dict):
        return node

    branches = node.get("anyOf")
    if isinstance(branches, list) and len(branches) == 2:
        kept = [b for b in branches if not (isinstance(b, dict) and b.get("type") == "null")]
        nulls = [b for b in branches if isinstance(b, dict) and b.get("type") == "null"]
        if len(kept) == 1 and len(nulls) == 1 and isinstance(kept[0], dict):
            merged = {k: v for k, v in node.items() if k != "anyOf"}
            # 分支自己的鍵優先:`anyOf` 外層通常只有 title/description 之類的裝飾。
            merged.update(kept[0])
            return drop_nullable_unions(merged)

    return {key: drop_nullable_unions(value) for key, value in node.items()}


def expand_refs(schema: dict[str, Any]) -> dict[str, Any]:
    """把 `$ref` 全部內聯,得到官方限制實際計數的形狀(§3／§4 的量測基礎)。"""
    defs = schema.get("$defs") or schema.get("definitions") or {}

    def walk(node: Any, depth: int = 0) -> Any:
        if depth > 200:
            raise RecursionError("schema appears recursive; unsupported by strict mode")
        if isinstance(node, list):
            return [walk(item, depth + 1) for item in node]
        if not isinstance(node, dict):
            return node
        ref = node.get("$ref")
        if isinstance(ref, str):
            merged = copy.deepcopy(defs[ref.rsplit("/", 1)[-1]])
            merged.update({k: v for k, v in node.items() if k != "$ref"})
            return walk(merged, depth + 1)
        return {k: walk(v, depth + 1) for k, v in node.items() if k != "$defs"}

    return walk(schema)


def count_schema(schema: dict[str, Any]) -> dict[str, int]:
    """官方限制關心的維度,一律以 `$ref` 展開後的形狀計數。"""
    flat = expand_refs(schema)
    totals = {
        "union_parameters": 0,
        "nullable_unions": 0,
        "optional_parameters": 0,
        "properties": 0,
        "enum_sites": 0,
        "enum_values": 0,
        "nesting_levels": 0,
    }

    def walk(node: Any, level: int) -> None:
        totals["nesting_levels"] = max(totals["nesting_levels"], level)
        if isinstance(node, list):
            for item in node:
                walk(item, level)
            return
        if not isinstance(node, dict):
            return

        branches = node.get("anyOf")
        if isinstance(branches, list):
            totals["union_parameters"] += 1
            types = [b.get("type") for b in branches if isinstance(b, dict)]
            if "null" in types:
                totals["nullable_unions"] += 1
                # strict 要求全欄位 required,optional 就是以 null union 表達的那些。
                totals["optional_parameters"] += 1
            for branch in branches:
                walk(branch, level)

        enum_values = node.get("enum")
        if isinstance(enum_values, list):
            totals["enum_sites"] += 1
            totals["enum_values"] += len(enum_values)

        properties = node.get("properties")
        if isinstance(properties, dict):
            totals["properties"] += len(properties)
            for sub in properties.values():
                walk(sub, level + 1)

        if "items" in node:
            walk(node["items"], level + 1)

    walk(flat, 0)
    return totals


def schema_hash(schema: dict[str, Any]) -> str:
    return sha256(canonical_request_json(schema).encode("utf-8")).hexdigest()


def build_probe_body(failed_body: dict[str, Any]) -> dict[str, Any]:
    """複製失敗請求,只換掉 schema 與 max_tokens。其餘欄位逐位元組保留。"""
    body = copy.deepcopy(failed_body)
    original = body["response_format"]["json_schema"]["schema"]
    body["response_format"]["json_schema"]["schema"] = drop_nullable_unions(original)
    body["max_tokens"] = PROBE_MAX_OUTPUT_TOKENS
    return body


def build_report(failed_body: dict[str, Any], probe_body: dict[str, Any]) -> dict[str, Any]:
    original = failed_body["response_format"]["json_schema"]["schema"]
    probe = probe_body["response_format"]["json_schema"]["schema"]
    unchanged = {
        key: failed_body.get(key) == probe_body.get(key)
        for key in ("model", "messages", "provider", "reasoning", "stream")
    }
    unchanged["response_format.json_schema.name"] = (
        failed_body["response_format"]["json_schema"]["name"]
        == probe_body["response_format"]["json_schema"]["name"]
    )
    unchanged["response_format.json_schema.strict"] = (
        failed_body["response_format"]["json_schema"]["strict"]
        == probe_body["response_format"]["json_schema"]["strict"]
    )
    return {
        "official_limits": {"optional_parameters": 24, "union_parameters": 16},
        "schema_sha256": {"original": schema_hash(original), "probe": schema_hash(probe)},
        "counts": {"original": count_schema(original), "probe": count_schema(probe)},
        "request_bytes": {
            "original": len(canonical_request_json(failed_body).encode("utf-8")),
            "probe": len(canonical_request_json(probe_body).encode("utf-8")),
        },
        "max_output_tokens": {
            "original": failed_body.get("max_tokens"),
            "probe": probe_body.get("max_tokens"),
        },
        "unchanged_fields": unchanged,
    }


# ── live probe ─────────────────────────────────────────────────────────────


def latest_failed_turn(capture_root: Path) -> Path:
    runs = sorted(p for p in capture_root.glob("*/turn-01.json"))
    if not runs:
        raise ProbeStopped(f"no captured turn-01.json under {capture_root}")
    return runs[-1]


def load_failed_body(path: Path) -> dict[str, Any]:
    turn = json.loads(path.read_text(encoding="utf-8"))
    request = turn.get("request")
    if not isinstance(request, dict) or not isinstance(request.get("body"), dict):
        raise ProbeStopped(f"{path} carried no request body")
    if turn.get("outcome") != "failed":
        raise ProbeStopped(f"{path} was not a failed turn; refusing to probe from it")
    return request["body"]


def reserve_usd(body: dict[str, Any], endpoint: Any) -> Decimal:
    """與 live smoke 同一條保守公式:UTF-8 byte 數當 input token 上界。"""
    input_upper = len(canonical_request_json(body).encode("utf-8"))
    return (
        Decimal(input_upper) * endpoint.prompt_price_per_token
        + Decimal(body["max_tokens"]) * endpoint.completion_price_per_token
    )


async def run_probe(*, capture_root: Path, output_root: Path, budget_usd: Decimal) -> int:
    api_key = settings.openrouter_api_key
    if not api_key:
        raise ProbeStopped("OPENROUTER_API_KEY is not configured")

    failed_path = latest_failed_turn(capture_root)
    failed_body = load_failed_body(failed_path)
    probe_body = build_probe_body(failed_body)
    report = build_report(failed_body, probe_body)
    report["source_capture"] = str(failed_path)

    if not all(report["unchanged_fields"].values()):
        raise ProbeStopped(f"probe changed more than the schema: {report['unchanged_fields']}")
    if report["counts"]["probe"]["union_parameters"] != 0:
        raise ProbeStopped("probe schema still carries union parameters")

    async with httpx.AsyncClient(timeout=30.0) as client:
        endpoint = await fetch_endpoint_snapshot(
            client,
            model=settings.job_analysis_model,
            tag=settings.job_analysis_provider,
            api_key=api_key,
        )

    reserve = reserve_usd(probe_body, endpoint)
    report["budget"] = {
        "limit_usd": str(budget_usd),
        "conservative_reserve_usd": str(reserve),
    }
    if reserve > budget_usd:
        raise ProbeStopped(
            f"conservative reserve US${reserve} exceeds the cap US${budget_usd}; "
            "not sending. Raise --budget-usd deliberately or shrink the probe."
        )

    run_id = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    output_dir = output_root / f"probe-u-{run_id}"
    output_dir.mkdir(parents=True, exist_ok=False)

    # 唯一一次 HTTP。沒有 retry loop,沒有 fallback。
    async with httpx.AsyncClient(timeout=settings.job_analysis_timeout_s) as client:
        response = await client.post(
            CHAT_COMPLETIONS_URL,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                **METADATA_HEADERS,
            },
            json=probe_body,
        )
    try:
        payload = response.json()
    except ValueError:
        payload = None

    evidence = inspect_openrouter_execution(
        payload if isinstance(payload, dict) else {},
        expected_model=endpoint.model_id,
        expected_endpoint=endpoint,
    )
    error = (payload or {}).get("error") if isinstance(payload, dict) else None
    upstream = (error or {}).get("metadata", {}).get("raw") if isinstance(error, dict) else None

    report.update(
        {
            "run_id": run_id,
            "generation_calls": 1,
            "retries": 0,
            "http_status": response.status_code,
            "grammar_compiled": response.status_code == 200 and error is None,
            "error": error,
            "upstream_raw": upstream,
            "route_evidence": {
                **evidence.model_dump(mode="json"),
                "quality_eligible": evidence.quality_eligible,
            },
            "usage": (payload or {}).get("usage") if isinstance(payload, dict) else None,
            "cost_usd": str(evidence.cost_usd) if evidence.cost_usd is not None else None,
            "applied_to_application_state": False,
        }
    )
    (output_dir / "probe-u.json").write_text(
        json.dumps(
            {"report": report, "request_body": probe_body, "response_body": payload},
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )

    print(json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2))
    print(f"\ncapture: {output_dir / 'probe-u.json'}")
    return 0 if report["grammar_compiled"] else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Probe U: does removing unions let the grammar compile?")
    parser.add_argument("--plan-only", action="store_true", help="offline: print counts and diff, send nothing")
    parser.add_argument("--budget-usd", type=Decimal, default=PROBE_BUDGET_USD)
    parser.add_argument("--capture-root", type=Path, default=DEFAULT_CAPTURE_ROOT)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    args = parser.parse_args(argv)

    if not Decimal("0") < args.budget_usd <= PROBE_BUDGET_USD:
        print(f"--budget-usd must be within (0, {PROBE_BUDGET_USD}]", file=sys.stderr)
        return 2

    try:
        if args.plan_only:
            failed_body = load_failed_body(latest_failed_turn(args.capture_root))
            report = build_report(failed_body, build_probe_body(failed_body))
            print(json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2))
            return 0
        if sys.platform == "win32":
            asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        return asyncio.run(
            run_probe(
                capture_root=args.capture_root,
                output_root=args.output_root,
                budget_usd=args.budget_usd,
            )
        )
    except (ProbeStopped, OpenRouterCatalogError) as error:
        print(json.dumps({"status": "stopped", "reason": str(error)}, ensure_ascii=False))
        return 1


if __name__ == "__main__":  # pragma: no cover - CLI entry
    raise SystemExit(main())
