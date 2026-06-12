"""Verify v2 cleanly removed synthetic block_title and block_id.

Invariants:
  - block payload `block_title` is None for every block chunk
  - block payload `block_id` is None for every block chunk
  - block markdown headings match '#### 能力區塊( #N)?' exactly, no synthetic
    fallback strings (no leftover output[0] name or indicator text snippets)
"""

from __future__ import annotations

import re
from pathlib import Path

from jd_ocs_indexer.config import load_settings
from jd_ocs_indexer.ingestion.builder import BuilderContext, ChunkBuilder
from jd_ocs_indexer.ingestion.normalizer import normalize
from jd_ocs_indexer.ingestion.reader import OCSJSONReader
from jd_ocs_indexer.ingestion.renderer import MarkdownRenderer


def main() -> int:
    s = load_settings()
    reader = OCSJSONReader(s.source_root)
    builder = ChunkBuilder()
    renderer = MarkdownRenderer()
    errors: list[str] = []
    block_heading_pattern = re.compile(r"#### 能力區塊( #\d+)?$")
    blocks_checked = 0

    for loaded, fail in reader.iter_loaded(Path("tests/fixtures")):
        if fail is not None:
            continue
        assert loaded is not None
        norm = normalize(loaded.document)
        ctx = BuilderContext(
            source_root_alias=s.source_root_alias,
            source_file=loaded.rel_path,
            source_json_hash=loaded.source_json_hash,
            schema_version=s.schema_version,
            embedding_provider=s.embedding_provider,
        )
        records = builder.build(norm, ctx)
        renderer.render(norm, records)

        for r in records:
            if r.chunk_level != "block":
                continue
            blocks_checked += 1
            p = r.payload

            if p.get("block_title") is not None:
                errors.append(
                    f"{r.chunk_key}: block_title={p['block_title']!r} should be None"
                )
            if p.get("block_id") is not None:
                errors.append(
                    f"{r.chunk_key}: block_id={p['block_id']!r} should be None"
                )

            # Markdown heading must match exact pattern
            block_headings = [
                ln for ln in r.text.splitlines() if ln.startswith("#### ")
            ]
            for h in block_headings:
                stripped = h.rstrip()
                if not block_heading_pattern.match(stripped):
                    errors.append(f"{r.chunk_key}: unexpected block heading {stripped!r}")

    if errors:
        for e in errors[:30]:
            print(f"  ERR: {e}")
        if len(errors) > 30:
            print(f"  ... ({len(errors)} total)")
        return 1

    print(f"OK: block_title/block_id None on all {blocks_checked} block chunks, "
          f"headings clean")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
