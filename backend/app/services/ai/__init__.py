"""AI proposal services (D28).

Pure, stateless functions behind the ``/ai/*`` endpoints. Each takes EXPLICIT
inputs (task, note/description, catalog candidates, an optional ``LlmPort``) and
returns a structured proposal — NO DB, NO FastAPI, NOT bound to a caller. This is
the design §I constraint: the ✨ panel calls them today; a future autonomous
interview agent reuses the same functions unchanged.

Shared rules:
- catalog-first: standard items come from the indexer (occupation ``competencies``
  filtered per task_code); the LLM only personalises / filters / drafts custom content.
- no LLM (key absent) or no note → degrade to catalog-only (never crash, never empty
  when catalog is available).
- every proposed item carries ``source: "catalog" | "ai"`` (+ a one-line ``reason``
  for K/S).
"""
