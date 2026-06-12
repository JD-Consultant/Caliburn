"""Verify v2 pair structure produced by normalizer.

Invariants checked:
  - Every k_pair / s_pair / output_pair / evidence pair has non-empty code AND name
  - Every attitude_pair has non-empty code AND name
  - Parallel arrays (k_codes, s_codes, output_codes, indicator_codes,
    knowledge_terms, skill_terms, output_names, indicator_texts) are
    derived from pairs and therefore aligned by index
"""

from __future__ import annotations

from pathlib import Path

from jd_ocs_indexer.config import load_settings
from jd_ocs_indexer.ingestion.normalizer import normalize
from jd_ocs_indexer.ingestion.reader import OCSJSONReader


def main() -> int:
    s = load_settings()
    reader = OCSJSONReader(s.source_root)
    errors: list[str] = []
    files_checked = 0
    pair_count = 0

    for loaded, fail in reader.iter_loaded(Path("tests/fixtures")):
        if fail is not None:
            errors.append(f"PARSE FAIL {fail.rel_path}: {fail.error}")
            continue
        assert loaded is not None
        norm = normalize(loaded.document)
        files_checked += 1

        # Attitude pairs
        for ap in norm.attitude_pairs:
            if not ap.code or not ap.name:
                errors.append(f"{loaded.rel_path}: empty attitude pair {ap}")
            pair_count += 1
        if len(norm.attitude_codes) != len(norm.attitude_pairs):
            errors.append(
                f"{loaded.rel_path}: attitude_codes/pairs len mismatch "
                f"{len(norm.attitude_codes)}/{len(norm.attitude_pairs)}"
            )

        for u in norm.units:
            for g in u.task_groups:
                for b in g.blocks:
                    # Each pair list is non-empty pairs
                    for kp in b.k_pairs:
                        if not kp.code or not kp.name:
                            errors.append(f"{loaded.rel_path}: bad k_pair {kp}")
                        pair_count += 1
                    for sp in b.s_pairs:
                        if not sp.code or not sp.name:
                            errors.append(f"{loaded.rel_path}: bad s_pair {sp}")
                        pair_count += 1
                    for op in b.output_pairs:
                        if not op.code or not op.name:
                            errors.append(f"{loaded.rel_path}: bad output_pair {op}")
                        pair_count += 1
                    for ev in b.evidence:
                        if not ev.code or not ev.name:
                            errors.append(f"{loaded.rel_path}: bad evidence {ev}")
                        pair_count += 1

                    # Parallel arrays derived from pairs — invariants
                    if [p.code for p in b.k_pairs] != b.k_codes:
                        errors.append(
                            f"{loaded.rel_path}/block#{b.block_order}: "
                            f"k_codes drift from k_pairs"
                        )
                    if [p.name for p in b.k_pairs] != b.knowledge_terms:
                        errors.append(
                            f"{loaded.rel_path}/block#{b.block_order}: "
                            f"knowledge_terms drift from k_pairs"
                        )
                    if [p.code for p in b.s_pairs] != b.s_codes:
                        errors.append(
                            f"{loaded.rel_path}/block#{b.block_order}: "
                            f"s_codes drift from s_pairs"
                        )
                    if [p.code for p in b.output_pairs] != b.output_codes:
                        errors.append(
                            f"{loaded.rel_path}/block#{b.block_order}: "
                            f"output_codes drift from output_pairs"
                        )
                    if [p.code for p in b.evidence] != b.indicator_codes:
                        errors.append(
                            f"{loaded.rel_path}/block#{b.block_order}: "
                            f"indicator_codes drift from evidence"
                        )

    print(f"files: {files_checked}, pairs checked: {pair_count}")
    if errors:
        for e in errors[:30]:
            print(f"  ERR: {e}")
        print(f"  ... ({len(errors)} total)" if len(errors) > 30 else "")
        return 1
    print("OK: all pairs well-formed and parallel arrays aligned")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
