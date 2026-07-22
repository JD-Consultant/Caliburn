"""Write committed turn-eval JSON Schemas (V3-5 §5).

Deterministic export: same models -> byte-identical files. The focused
contracts test re-derives every schema and fails on drift, so schema changes
always land in the same commit as the model change.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable

from .contracts import (
    TurnEvalBatchPlan,
    TurnEvalBatchReport,
    TurnEvalCase,
    TurnEvalCaseReport,
    TurnEvalGold,
    TurnEvalGraderResult,
    TurnEvalInitialFixture,
    TurnEvalPriorInterpretationSeed,
    TurnEvalReferenceOutput,
    TurnEvalReviewDecision,
    TurnEvalTranscriptTurn,
    TurnEvalTrial,
)

SCHEMA_DIR = Path(__file__).with_name("schemas")

SchemaFactory = Callable[[], dict[str, Any]]

SCHEMA_EXPORTS: dict[str, tuple[str, str, SchemaFactory]] = {
    "turn-eval-case.v2.schema.json": (
        "https://caliburn.local/schemas/turn-eval-case.v2.schema.json",
        "Caliburn interview vNext turn eval case descriptor v2",
        TurnEvalCase.model_json_schema,
    ),
    "turn-eval-transcript.v2.schema.json": (
        "https://caliburn.local/schemas/turn-eval-transcript.v2.schema.json",
        "Caliburn interview vNext turn eval transcript turn v2",
        TurnEvalTranscriptTurn.model_json_schema,
    ),
    "turn-eval-initial-fixture.v2.schema.json": (
        "https://caliburn.local/schemas/turn-eval-initial-fixture.v2.schema.json",
        "Caliburn interview vNext turn eval initial fixture v2",
        TurnEvalInitialFixture.model_json_schema,
    ),
    "turn-eval-gold.v2.schema.json": (
        "https://caliburn.local/schemas/turn-eval-gold.v2.schema.json",
        "Caliburn interview vNext turn eval gold criteria v2",
        TurnEvalGold.model_json_schema,
    ),
    "turn-eval-reference-output.v2.schema.json": (
        "https://caliburn.local/schemas/turn-eval-reference-output.v2.schema.json",
        "Caliburn interview vNext turn eval reference output v2",
        TurnEvalReferenceOutput.model_json_schema,
    ),
    "turn-eval-batch-plan.v2.schema.json": (
        "https://caliburn.local/schemas/turn-eval-batch-plan.v2.schema.json",
        "Caliburn interview vNext turn eval batch plan v2",
        TurnEvalBatchPlan.model_json_schema,
    ),
    "turn-eval-trial.v2.schema.json": (
        "https://caliburn.local/schemas/turn-eval-trial.v2.schema.json",
        "Caliburn interview vNext turn eval trial record v2",
        TurnEvalTrial.model_json_schema,
    ),
    "turn-eval-grader-result.v2.schema.json": (
        "https://caliburn.local/schemas/turn-eval-grader-result.v2.schema.json",
        "Caliburn interview vNext turn eval grader result v2",
        TurnEvalGraderResult.model_json_schema,
    ),
    "turn-eval-review-decision.v2.schema.json": (
        "https://caliburn.local/schemas/turn-eval-review-decision.v2.schema.json",
        "Caliburn interview vNext turn eval review decision v2",
        TurnEvalReviewDecision.model_json_schema,
    ),
    "turn-eval-case-report.v2.schema.json": (
        "https://caliburn.local/schemas/turn-eval-case-report.v2.schema.json",
        "Caliburn interview vNext turn eval case report v2",
        TurnEvalCaseReport.model_json_schema,
    ),
    "turn-eval-batch-report.v2.schema.json": (
        "https://caliburn.local/schemas/turn-eval-batch-report.v2.schema.json",
        "Caliburn interview vNext turn eval batch report v2",
        TurnEvalBatchReport.model_json_schema,
    ),
    "turn-eval-prior-interpretation-seed.v1.schema.json": (
        "https://caliburn.local/schemas/turn-eval-prior-interpretation-seed.v1.schema.json",
        "Caliburn interview vNext adjudicated prior interpretation seed v1",
        TurnEvalPriorInterpretationSeed.model_json_schema,
    ),
}

HISTORICAL_SCHEMAS = frozenset(
    {
        "turn-eval-case.v1.schema.json",
        "turn-eval-transcript.v1.schema.json",
        "turn-eval-initial-fixture.v1.schema.json",
        "turn-eval-gold.v1.schema.json",
        "turn-eval-reference-output.v1.schema.json",
        "turn-eval-batch-plan.v1.schema.json",
        "turn-eval-trial.v1.schema.json",
        "turn-eval-grader-result.v1.schema.json",
        "turn-eval-review-decision.v1.schema.json",
        "turn-eval-case-report.v1.schema.json",
        "turn-eval-batch-report.v1.schema.json",
    }
)


def published_schema(filename: str) -> dict[str, Any]:
    schema_id, title, factory = SCHEMA_EXPORTS[filename]
    schema = factory()
    schema["$id"] = schema_id
    schema["title"] = title
    return schema


def write_schemas(schema_dir: Path = SCHEMA_DIR) -> list[Path]:
    schema_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for filename in SCHEMA_EXPORTS:
        path = schema_dir / filename
        path.write_text(
            json.dumps(published_schema(filename), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        written.append(path)
    return written


if __name__ == "__main__":
    for item in write_schemas():
        print(item)
