"""Write version-addressed context policy documents."""

from __future__ import annotations

import json
from pathlib import Path

from .context import CONTEXT_POLICIES, context_policy_filename


POLICY_DIR = Path(__file__).with_name("context_policies")


def write_context_policies(policy_dir: Path = POLICY_DIR) -> list[Path]:
    policy_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for (name, version), policy in CONTEXT_POLICIES.items():
        path = policy_dir / context_policy_filename(name, version)
        path.write_text(
            json.dumps(policy.model_dump(mode="json"), ensure_ascii=False, indent=2)
            + "\n",
            encoding="utf-8",
        )
        written.append(path)
    return written


if __name__ == "__main__":
    for item in write_context_policies():
        print(item)
