"""Verify v2 profile-level all_*_pairs pools + builder writes pairs to payload.

Profile must contain OCS-wide aggregated K/S/A/output pools (`all_*_pairs`).
Block payload must contain k_pairs / s_pairs / output_pairs / evidence.
Unit payload must contain aggregated k_pairs / s_pairs / output_pairs.
"""

from __future__ import annotations

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
    sample_profile_payload = None

    for loaded, fail in reader.iter_loaded(Path("tests/fixtures")):
        if fail is not None:
            errors.append(f"PARSE {fail.rel_path}: {fail.error}")
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
            p = r.payload
            level = r.chunk_level

            if level == "block":
                # Block must have populated pair fields (since fixtures have full K/S)
                if not p.get("k_pairs"):
                    errors.append(f"{loaded.rel_path}/{r.chunk_key}: empty k_pairs")
                if not p.get("s_pairs"):
                    errors.append(f"{loaded.rel_path}/{r.chunk_key}: empty s_pairs")
                if "evidence" not in p:
                    errors.append(f"{loaded.rel_path}/{r.chunk_key}: missing evidence field")
                # evidence shape
                for ev in p.get("evidence", []):
                    if "indicator_code" not in ev or "activity_text" not in ev:
                        errors.append(
                            f"{loaded.rel_path}/{r.chunk_key}: evidence shape wrong {ev}"
                        )
                # k_pairs shape
                for kp in p.get("k_pairs", []):
                    if "code" not in kp or "name" not in kp:
                        errors.append(
                            f"{loaded.rel_path}/{r.chunk_key}: k_pair shape wrong {kp}"
                        )

            elif level == "unit":
                # Unit aggregated pairs
                if "k_pairs" not in p:
                    errors.append(f"{loaded.rel_path}/{r.chunk_key}: unit missing k_pairs")
                if "s_pairs" not in p:
                    errors.append(f"{loaded.rel_path}/{r.chunk_key}: unit missing s_pairs")

            elif level == "profile":
                for fld in ("all_k_pairs", "all_s_pairs", "all_a_pairs", "all_output_pairs"):
                    if fld not in p:
                        errors.append(f"{loaded.rel_path}: profile missing {fld}")
                # Profile pools must be non-empty (fixtures have content)
                if not p.get("all_k_pairs"):
                    errors.append(f"{loaded.rel_path}: profile all_k_pairs empty")
                if not p.get("all_s_pairs"):
                    errors.append(f"{loaded.rel_path}: profile all_s_pairs empty")
                if not p.get("all_a_pairs"):
                    errors.append(f"{loaded.rel_path}: profile all_a_pairs empty")
                # schema_version must be v2
                if p.get("schema_version") != "ocs-index-v2":
                    errors.append(
                        f"{loaded.rel_path}: schema_version={p.get('schema_version')} "
                        f"expected ocs-index-v2"
                    )
                # v2 skill cloud in markdown
                text = r.text
                if "## 核心知識領域" not in text:
                    errors.append(f"{loaded.rel_path}: profile missing '## 核心知識領域' section")
                if "## 核心技能" not in text:
                    errors.append(f"{loaded.rel_path}: profile missing '## 核心技能' section")
                # cloud bullets reasonably populated (fixtures all have 15+ K, 10+ S)
                k_section = (
                    text.split("## 核心知識領域")[1].split("## ")[0]
                    if "## 核心知識領域" in text
                    else ""
                )
                k_bullets = [ln for ln in k_section.splitlines() if ln.startswith("- ")]
                if len(k_bullets) < 5:
                    errors.append(
                        f"{loaded.rel_path}: profile 核心知識領域 only {len(k_bullets)} bullets"
                    )

                if sample_profile_payload is None:
                    sample_profile_payload = p

    if errors:
        for e in errors[:30]:
            print(f"  ERR: {e}")
        if len(errors) > 30:
            print(f"  ... ({len(errors)} total)")
        return 1

    print("OK: payload pair structures verified (block / unit / profile)")
    if sample_profile_payload is not None:
        print(
            f"  sample profile: all_k_pairs={len(sample_profile_payload['all_k_pairs'])}, "
            f"all_s_pairs={len(sample_profile_payload['all_s_pairs'])}, "
            f"all_a_pairs={len(sample_profile_payload['all_a_pairs'])}, "
            f"all_output_pairs={len(sample_profile_payload['all_output_pairs'])}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
