"""Bounded continuation: validated completed prefix and cumulative accounting only."""

import hashlib
import json
from decimal import Decimal
from pathlib import Path
from typing import Any

from main_support import StudyAllowance


def validate_prefix(folder: Path) -> dict[str, str]:
    exchanges = sorted(folder.glob("exchange-*.json"))
    products = sorted(folder.glob("product-*.json"))
    expected_exchanges = [
        folder / f"exchange-{index:03d}.json" for index in range(1, 52)
    ]
    expected_products = [folder / f"product-{index:03d}.json" for index in range(1, 52)]
    memories = [folder / f"memory-{event}.json" for event in ("e012", "e028", "e044")]
    if exchanges != expected_exchanges or products != expected_products:
        raise ValueError("Completed prefix must contain exactly events 1 through 51")
    for index, path in enumerate(exchanges, 1):
        if json.loads(path.read_text(encoding="utf-8"))["event_id"] != f"e{index:03d}":
            raise ValueError("Completed prefix has mismatched event identity")
    if not all(path.is_file() for path in memories):
        raise ValueError("Completed prefix is missing a published Memory")
    return {
        path.name: hashlib.sha256(path.read_bytes()).hexdigest()
        for path in [*exchanges, *products, *memories]
    }


class ContinuedAllowance(StudyAllowance):
    """Keep every prior attempted send, including failed e052, in the same US$2 bound."""

    def __init__(self, previous: dict[str, Any]) -> None:
        super().__init__(max_estimated_usd=Decimal("2.00"))
        self.occupied_usd = Decimal(previous["estimated_occupation_usd"]) + Decimal(
            "0.10"
        )
        self.generation_calls = previous["generation_calls"]
        self.compaction_calls = previous["compaction_calls"]
        self.outbound_calls = previous["outbound_calls"]
        self.input_tokens = previous["admitted_input_tokens"]
        if self.occupied_usd >= self.max_estimated_usd:
            raise ValueError("No remaining cumulative study allowance")
