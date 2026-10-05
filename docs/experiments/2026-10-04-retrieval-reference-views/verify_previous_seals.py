"""Check old sealed packets without running or writing into them."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
NAMES = ["occupation-retrieval", "occupation-retrieval-generalization", "retrieve-rerank",
         "retrieval-passage-quota", "retrieval-input-boundaries"]
EXPECTED_COUNTS = [132, 69, 86, 96, 78]


def main():
    results = []
    for name, expected_count in zip(NAMES, EXPECTED_COUNTS):
        directory = HERE.parent / f"2026-10-04-{name}"
        seal = directory / "artifact-hashes.json"
        manifest = json.loads(seal.read_text(encoding="utf-8"))
        files = manifest.get("files", manifest)
        if len(files) != expected_count:
            raise ValueError(f"Seal scope changed: {name}")
        for filename, identity in files.items():
            raw = (directory / filename).read_bytes()
            expected = identity if isinstance(identity, str) else identity["sha256"]
            if hashlib.sha256(raw).hexdigest() != expected:
                raise ValueError(f"Sealed artifact changed: {name}/{filename}")
            if isinstance(identity, dict) and len(raw) != identity["bytes"]:
                raise ValueError(f"Sealed size changed: {name}/{filename}")
        results.append({"experiment": directory.name, "sealed_files": len(files),
                        "all_sealed_hashes_unchanged": True,
                        "seal_sha256": hashlib.sha256(seal.read_bytes()).hexdigest()})
    with (HERE / "previous-seals.json").open("x", encoding="utf-8", newline="\n") as out:
        json.dump(results, out, ensure_ascii=False, indent=2)
        out.write("\n")
    print(json.dumps(results, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
