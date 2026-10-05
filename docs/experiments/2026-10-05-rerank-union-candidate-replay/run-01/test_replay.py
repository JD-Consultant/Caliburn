"""Selection-integrity counterexamples for the isolated union replay."""
import importlib.util
import pathlib
import unittest

HERE = pathlib.Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("union_replay", HERE / "replay.py")
replay = importlib.util.module_from_spec(spec)
spec.loader.exec_module(replay)


class UnionReplayTests(unittest.TestCase):
    def rows(self, ids):
        return [{"id": value, "score": 0} for value in ids]

    def test_task_only_candidate_beyond_fused_twenty_is_kept(self):
        dense = self.rows([f"d{i:02}" for i in range(20)])
        task = self.rows([f"t{i:02}" for i in range(20)])
        union = replay.union_candidates(dense, task)
        self.assertEqual(len(union), 40)
        scores = {item["id"]: (-1 if item["id"] != "t19" else 5) for item in union}
        ranked = replay.order_by_logit(union, scores)
        self.assertEqual(ranked[0]["id"], "t19")

    def test_parent_in_both_routes_is_scored_once_with_both_origins(self):
        union = replay.union_candidates(self.rows(["a", "b"]), self.rows(["b", "c"]))
        self.assertEqual([item["id"] for item in union], ["a", "b", "c"])
        self.assertEqual(union[1]["route_ranks"], {"D": 2, "T": 1})

    def test_missing_logit_does_not_borrow_another_query_score(self):
        with self.assertRaisesRegex(ValueError, "missing score"):
            replay.order_by_logit(self.rows(["missing"]), {})

    def test_changed_query_or_document_hash_is_rejected(self):
        good = {"query_sha256": "q", "document_sha256": "d", "logit": 1.0}
        self.assertEqual(replay.checked_logit(good, "q", "d"), 1.0)
        for query_hash, document_hash in [("changed", "d"), ("q", "changed")]:
            with self.assertRaisesRegex(ValueError, "source hash"):
                replay.checked_logit(good, query_hash, document_hash)

    def test_duplicate_route_parent_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "duplicate"):
            replay.union_candidates(self.rows(["a", "a"]), self.rows(["b"]))

    def test_nonfinite_logit_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "finite"):
            replay.order_by_logit(self.rows(["a"]), {"a": float("nan")})


if __name__ == "__main__":
    unittest.main()
