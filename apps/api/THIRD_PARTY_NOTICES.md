# Third-party source notices

## OpenAI Agents Python — V4A section parser

`src/caliburn/adapters/v4a_parser.py` adapts the section/chunk parsing algorithm
from `src/agents/apply_diff.py` in OpenAI Agents Python. It does **not** import
the Agents SDK, its runner, or its first-match text locator.

- Original source: [commit 6b62225f03d34833d409fcdac608f0860509dfd5](https://github.com/openai/openai-agents-python/blob/6b62225f03d34833d409fcdac608f0860509dfd5/src/agents/apply_diff.py).
- Original file SHA-256: `d09b0c15365b389b58a3d71c4cadfb6719c76ee1f9d3fe253a6e51a743e31e1d`.
- Checked newer source on 2026-09-30: [18de65134083ee8cbdb84ae30a34c1f30ef4cb86](https://github.com/openai/openai-agents-python/blob/18de65134083ee8cbdb84ae30a34c1f30ef4cb86/src/agents/apply_diff.py), SHA-256 `bb2fd2b0f9846ab22743934c61b0886eabc59dcddacbe871e0c906a9ad23fb53`; section algorithm unchanged, upstream EOF matching differs.
- License: **MIT, Copyright (c) 2025 OpenAI**. Full notice is included in
  [`src/caliburn/adapters/_openai_agents_license.txt`](src/caliburn/adapters/_openai_agents_license.txt)
  and accompanies the parser in the built Python package.

Local changes: immutable typed hunk/chunk values; standalone full-consumption
body parser; no create/delete/move/path operation; numeric unified headers and
trailing data rejected; context-free insertion requires explicit EOF. Matching,
scan limits, unique qualification, byte-preserving application and persistence
are Caliburn responsibilities, not guarantees attributed to the original helper.

## RapidFuzz dependency

`rapidfuzz==3.14.6` supplies Levenshtein similarity; no library source is copied.
Its MIT license is included with the installed distribution. Caliburn's
candidate enumeration, qualification thresholds and ambiguity rejection are
not library guarantees. Dependency artifacts and hashes are in `uv.lock`.
