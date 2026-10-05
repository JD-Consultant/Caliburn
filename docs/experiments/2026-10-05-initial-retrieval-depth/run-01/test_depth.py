"""Meaningful boundaries and unknown-label integrity for initial retrieval."""
import importlib.util
import pathlib
import unittest

HERE = pathlib.Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("depth", HERE / "evaluate.py")
depth = importlib.util.module_from_spec(spec)
spec.loader.exec_module(depth)


class DepthTests(unittest.TestCase):
    def test_rank_forty_is_not_in_twenty_but_is_in_forty(self):
        dense = [f"d{i}" for i in range(39)] + ["target"]
        task = [f"t{i}" for i in range(40)]
        self.assertNotIn("target", depth.candidate_union(dense, task, 20))
        self.assertIn("target", depth.candidate_union(dense, task, 40))

    def test_two_routes_deduplicate_parent_but_query_pools_stay_separate(self):
        self.assertEqual(depth.candidate_union(["a", "b"], ["b", "c"], 2), ["a", "b", "c"])

    def test_duplicate_parent_in_a_route_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "duplicate"):
            depth.candidate_union(["a", "a"], ["b", "c"], 2)

    def test_multiple_references_support_same_facet_once(self):
        targets = [{"id": "a", "main_work": ["front"]}, {"id": "b", "main_work": ["front", "back"]}]
        result = depth.facet_state(["front", "back"], targets, {"a", "b"})
        self.assertEqual(result["retained"], ["front", "back"])
        self.assertEqual(result["known_coverage"], 1.0)

    def test_no_judged_support_is_unknown_not_perfect_coverage(self):
        result = depth.facet_state(["course"], [], {"a"})
        self.assertEqual(result["unassessed"], ["course"])
        self.assertIsNone(result["known_coverage"])

    def test_known_missing_and_unassessed_are_separate(self):
        result = depth.facet_state(["front", "back", "course"], [{"id": "a", "main_work": ["front", "back"]}], set())
        self.assertEqual(result["missing"], ["front", "back"])
        self.assertEqual(result["unassessed"], ["course"])

    def test_unrecognized_facet_cannot_invent_work_support(self):
        with self.assertRaisesRegex(ValueError, "facet"):
            depth.facet_state(["front"], [{"id": "a", "main_work": ["invented"]}], {"a"})


if __name__ == "__main__":
    unittest.main()
