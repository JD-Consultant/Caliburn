"""Write hash-addressed semantic verifier policy documents."""

from __future__ import annotations

import json
from pathlib import Path

from .turn_interpret import TURN_INTERPRET_VERIFIER_POLICY_V1


POLICY_DIR = Path(__file__).with_name("verifier_policies")


def write_verifier_policies(policy_dir: Path = POLICY_DIR) -> list[Path]:
    policy_dir.mkdir(parents=True, exist_ok=True)
    path = policy_dir / "turn-interpret-verifier.1.0.0.json"
    path.write_text(
        json.dumps(
            TURN_INTERPRET_VERIFIER_POLICY_V1.model_dump(mode="json"),
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return [path]


if __name__ == "__main__":
    for item in write_verifier_policies():
        print(item)
