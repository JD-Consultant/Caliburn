"""Freeze TOP+dense trial choice; old holdout is a regression, not unseen evidence."""

import json
import sys

from experiment import Embeddings, sorted_ranking, sparse_scores
from prepare import HERE, sha, write_json
from validation import parameter_and_database_checks


def validate(run_name):
    run = HERE / run_name
    run.mkdir(exist_ok=False)
    corpus = json.loads((HERE / "corpus.json").read_text(encoding="utf-8"))
    probes = json.loads((HERE / "probes.json").read_text(encoding="utf-8"))
    model = Embeddings()
    documents = model.get([row["texts"]["top"] for row in corpus], "TOP")
    queries = model.get([case["text"] for case in probes], "probes")
    write_json(run / "manifest.json", {"purpose": "Validate whole-B2 pilot choice TOP+dense, old holdout is regression only",
        "base_manifest_sha256": sha(HERE / "manifest.json"), "runtime": model.runtime,
        "script_sha256": sha(HERE / "validate_final_candidate.py"),
        "validation_sha256": sha(HERE / "validation.py"), "environment_sha256": sha(HERE / "environment.json"),
        "input_choice_source": "run-03/input-summary.json",
        "method_choice_source": "memory-01/memory-method-summary.json",
        "fresh_holdout": False})
    outputs = {case["case_id"]: {
        "dense": sorted_ranking(documents[0] @ queries[0][index], corpus),
        "sparse": sorted_ranking(sparse_scores(queries[1][index], documents[1]), corpus)}
        for index, case in enumerate(probes)}
    parameter_and_database_checks(run, corpus, probes, "top", "dense", documents, queries, outputs)
    write_json(run / "complete.json", {"selected_input": "B_b2", "selected_representation": "top",
        "selected_method": "dense", "cache_sha256": sha(model.path),
        "cache_byte_prefix_length": model.path.stat().st_size,
        "cache_path": model.path.relative_to(HERE).as_posix(), "used_cache_keys": sorted(model.used_keys),
        "fresh_holdout": False, "production_adoption": False})
    model.client.close()


if __name__ == "__main__":
    validate(sys.argv[1])
