"""Verify v2 block markdown uses (code) name format throughout.

Each block markdown should:
  - Use '#### 能力區塊 #N' heading (no synthetic block_title)
  - Show 工作活動 bullets as '(Pn.n.n) ...' format
  - Show 工作產出 bullets as '(On.n.n) name' format
  - Show 必備知識 bullets as '(Knn) name' format
  - Show 必備技能 bullets as '(Snn) name' format
"""

from __future__ import annotations

import re
from pathlib import Path

from jd_ocs_indexer.config import load_settings
from jd_ocs_indexer.ingestion.builder import BuilderContext, ChunkBuilder
from jd_ocs_indexer.ingestion.normalizer import normalize
from jd_ocs_indexer.ingestion.reader import OCSJSONReader
from jd_ocs_indexer.ingestion.renderer import MarkdownRenderer


def _section(text: str, marker: str, end_markers: list[str]) -> str:
    if marker not in text:
        return ""
    after = text.split(marker, 1)[1]
    for em in end_markers:
        if em in after:
            after = after.split(em, 1)[0]
    return after


def main() -> int:
    s = load_settings()
    reader = OCSJSONReader(s.source_root)
    builder = ChunkBuilder()
    renderer = MarkdownRenderer()
    errors: list[str] = []
    sample_block: str | None = None

    p_pattern = re.compile(r"\(P\d+(?:\.\d+)*\)")
    o_pattern = re.compile(r"\(O\d+(?:\.\d+)*\)")
    k_pattern = re.compile(r"\(K\d+\)")
    s_pattern = re.compile(r"\(S\d+\)")

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
            text = r.text

            # Heading is the new format
            block_headings = [ln for ln in text.splitlines() if ln.startswith("#### ")]
            for h in block_headings:
                if not re.match(r"#### 能力區塊( #\d+)?$", h.rstrip()):
                    errors.append(f"{r.chunk_key}: bad block heading {h!r}")

            # Each section uses (code) name
            kn = _section(text, "必備知識：", ["必備技能：", "## "])
            sk = _section(text, "必備技能：", ["## "])
            act = _section(text, "工作活動：", ["工作產出：", "必備知識：", "## "])

            if kn and not k_pattern.search(kn):
                errors.append(
                    f"{r.chunk_key}: 必備知識 section lacks (Knn) format"
                )
            if sk and not s_pattern.search(sk):
                errors.append(
                    f"{r.chunk_key}: 必備技能 section lacks (Snn) format"
                )
            if act and not p_pattern.search(act):
                errors.append(
                    f"{r.chunk_key}: 工作活動 section lacks (Pn.n.n) format"
                )

            if sample_block is None:
                sample_block = text

    if errors:
        for e in errors[:30]:
            print(f"  ERR: {e}")
        if len(errors) > 30:
            print(f"  ... ({len(errors)} total)")
        return 1

    print("OK: block markdown uses (code) name format")
    if sample_block:
        print("\n--- sample block markdown ---")
        print(sample_block)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
