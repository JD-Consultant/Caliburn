# Third-party source notices

## OpenAI Agents Python — V4A section parser

`src/caliburn/shared/domain/text_editing/patches.py` adapts the section/chunk parsing algorithm
from `src/agents/apply_diff.py` in OpenAI Agents Python. It does **not** import
the Agents SDK, its runner, or its first-match text locator.

- Original source: [commit 6b62225f03d34833d409fcdac608f0860509dfd5](https://github.com/openai/openai-agents-python/blob/6b62225f03d34833d409fcdac608f0860509dfd5/src/agents/apply_diff.py).
- Original file SHA-256: `d09b0c15365b389b58a3d71c4cadfb6719c76ee1f9d3fe253a6e51a743e31e1d`.
- Checked newer source on 2026-09-30: [18de65134083ee8cbdb84ae30a34c1f30ef4cb86](https://github.com/openai/openai-agents-python/blob/18de65134083ee8cbdb84ae30a34c1f30ef4cb86/src/agents/apply_diff.py), SHA-256 `bb2fd2b0f9846ab22743934c61b0886eabc59dcddacbe871e0c906a9ad23fb53`; section algorithm unchanged, upstream EOF matching differs.
- License: **MIT, Copyright (c) 2025 OpenAI**. Full notice is included in
  [`src/caliburn/shared/domain/text_editing/_openai_agents_license.txt`](src/caliburn/shared/domain/text_editing/_openai_agents_license.txt)
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

## Occupation reference dependencies and model weights

`occupation_reference` uses the following distributions through their public
APIs; their source is not copied into this backend. Installed distributions
retain their own full license notices. Exact artifacts and hashes are in
`uv.lock`.

| Dependency | Responsibility | License |
|---|---|---|
| Qdrant Python client | Vector storage and exact grouped queries | Apache-2.0 |
| pdfplumber | PDF text and table extraction | [MIT](https://github.com/jsvine/pdfplumber/blob/v0.11.10/LICENSE.txt) |
| HTTPX | HTTP transport error classification at the Qdrant boundary | BSD-3-Clause |
| PyTorch (`local-models` extra) | Local tensor inference | BSD-3-Clause core; bundled components have additional notices in the wheel |
| Transformers (`local-models` extra) | Fixed local tokenizer and encoder loading | Apache-2.0 |
| jsonschema (development only) | PDF output validation against the formal OCS schema | MIT |

The separately obtained [BGE-M3 fixed snapshot](https://huggingface.co/BAAI/bge-m3/tree/5617a9f61b028005a4858fdac845db406aefb181)
declares MIT; the [BGE reranker fixed snapshot](https://huggingface.co/BAAI/bge-reranker-v2-m3/tree/953dc6f6f85a1b2dbfca4c34a2796e7dde08d41e)
declares Apache-2.0. Weights are not included in the repository or downloaded by
the running module. Preserve the model repository's notices when distributing
weights. PDF source selection, source fidelity, publication readiness and
full-document reranking policy remain Caliburn responsibilities.
