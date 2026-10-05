"""Audit this fixed local conversion run; never modify PDF or OCS JSON data."""

import json
import subprocess
from collections import Counter
from hashlib import sha256
from pathlib import Path

from jd_ocs_indexer.ingestion.normalizer import normalize
from jd_ocs_indexer.models.ocs import OCSDocument

ROOT = Path(__file__).resolve().parents[3]
EVIDENCE = Path(__file__).resolve().parent
PDFS = ROOT / "apps/pdf-to-json/data/pdfs"
OUTPUT = ROOT / "apps/pdf-to-json/data/json-checked-2026-10-04"
DIAGNOSTICS = OUTPUT.with_name(OUTPUT.name + ".diagnostics")


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def main():
    manifest = read_json(DIAGNOSTICS / "input-manifest.json")
    batch = read_json(DIAGNOSTICS / "batch-report.json")
    sources = {item["source"]: item for item in manifest["files"]}
    results = {item["source"]: item for item in batch["files"]}
    assert (
        len(sources)
        == len(manifest["files"])
        == len(batch["files"])
        == len(results)
        == 908
    )
    assert set(sources) == set(results) == {path.name for path in PDFS.glob("*.pdf")}
    counts = Counter(item["status"] for item in results.values())
    assert set(counts) <= {"converted", "rejected", "excluded"}
    assert dict(counts) == batch["summary"]
    assert counts["excluded"] == 40
    for name, entry in sources.items():
        digest = sha256((PDFS / name).read_bytes()).hexdigest()
        assert digest == entry["source_sha256"] == results[name]["source_sha256"]
        if results[name]["status"] == "excluded":
            assert "歷史資料" in name

    converted = {
        Path(name).with_suffix(".json").name
        for name, result in results.items()
        if result["status"] == "converted"
    }
    assert converted == {path.name for path in OUTPUT.glob("*.json")}
    stats = Counter()
    for path in sorted(OUTPUT.glob("*.json")):
        model = OCSDocument.model_validate_json(path.read_text(encoding="utf-8"))
        normalize(model)  # Pure consumer; no database or embedding calls.
        stats["documents_loaded_and_normalized"] += 1
        stats["documents_with_uncoded_attitudes"] += any(
            item.code is None for item in model.ocs_attitude.attitudes
        )
        stats["documents_with_profile_level_six"] += model.ocs_profile.ocs_level == 6
        for unit in model.ocs_content.ocu_units:
            stats["units"] += 1
            for task in unit.tasks:
                stats["task_groups"] += 1
                stats["task_codes"] += len(task.task_codes)
                for block in task.competency_blocks:
                    stats["blocks"] += 1
                    stats["blocks_with_level_six"] += block.competency_level == 6
                    for field in ("indicators", "outputs", "knowledge", "skills"):
                        stats[field] += len(getattr(block, field))
    for data in ("apps/pdf-to-json/data/pdfs", "apps/ocs-indexer/data/jd-json"):
        check = subprocess.run(["git", "diff", "HEAD", "--quiet", "--", data], cwd=ROOT)
        assert check.returncode == 0, f"Tracked original data changed: {data}"
    old_count = len(list((ROOT / "apps/ocs-indexer/data/jd-json").glob("*.json")))
    assert old_count == 908
    verification = {
        "summary": batch["summary"],
        "manifest_and_results_unique": True,
        "source_hashes_match": True,
        "normal_output_exactly_matches_converted": True,
        "tracked_original_pdfs_and_json_unchanged_from_HEAD": True,
        "original_json_count": old_count,
        "consumer": "generated OCSDocument and pure normalize; no index or embedding",
        "counts": dict(stats),
    }
    (DIAGNOSTICS / "verification.json").write_text(
        json.dumps(verification, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    for name in (
        "input-manifest.json",
        "batch-report.json",
        "comparison.json",
        "verification.json",
    ):
        (EVIDENCE / name).write_bytes((DIAGNOSTICS / name).read_bytes())
    groups = {}
    for result in batch["files"]:
        if result["status"] != "rejected":
            continue
        reason = result["issues"][0]["message"]
        category = next(
            (
                label
                for text, label in (
                    ("Unmapped content cell", "儲存格位置無法唯一歸欄"),
                    ("Uncovered nested table", "重疊子表正文尚未證明被外表涵蓋"),
                    ("Invalid competency level", "級別文字無法依 1–6 契約判讀"),
                    ("Orphan content continuation", "尚未歸屬的延續列"),
                    ("Unsupported content", "尚未支援的表頭／版型"),
                )
                if text in reason
            ),
            "來源內容或任務／block 關係未通過檢核",
        )
        groups.setdefault(category, []).append((result["source"], reason))
    lines = [
        "# 本輪待處理 PDF",
        "",
        f"共 {counts['rejected']} 份；完整原因見 [整批結果](batch-report.json)。不在本輪正常 JSON 目錄中。",
        "",
    ]
    for category, entries in groups.items():
        lines.extend([f"## {category}（{len(entries)} 份）", ""])
        for name, reason in entries:
            lines.append(f"- **{name}**：{reason[:220].replace(chr(10), ' ')}")
        lines.append("")
    (EVIDENCE / "remaining.md").write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps(verification, ensure_ascii=False))


if __name__ == "__main__":
    main()
