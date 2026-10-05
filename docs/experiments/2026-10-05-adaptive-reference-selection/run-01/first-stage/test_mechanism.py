"""CPU-only selection boundary tests; no app or model imports."""
import unittest
from evaluate import policies, select


class SelectionTests(unittest.TestCase):
    def setUp(self):
        self.pool = [{"id": str(i), "score": s} for i, s in enumerate((.9, .9, .75, .7))]

    def test_fixed_and_empty(self):
        self.assertEqual(select(self.pool, {"kind": "fixed", "value": 2}), self.pool[:2])
        self.assertEqual(select([], {"kind": "relative", "value": .1}), [])

    def test_absolute_inclusive_and_zero(self):
        self.assertEqual(select(self.pool, {"kind": "absolute", "value": .75}), self.pool[:3])
        self.assertEqual(select(self.pool, {"kind": "absolute", "value": .95}), [])

    def test_relative_own_top(self):
        shifted = [{**p, "score": p["score"] - .2} for p in self.pool]
        self.assertEqual([p["id"] for p in select(self.pool, {"kind": "relative", "value": .1})],
                         [p["id"] for p in select(shifted, {"kind": "relative", "value": .1})])

    def test_gap_keeps_upper_prefix_and_no_gap_keeps_all(self):
        self.assertEqual(select(self.pool, {"kind": "gap", "value": .1}), self.pool[:2])
        self.assertEqual(select(self.pool, {"kind": "gap", "value": .3}), self.pool)

    def test_floor_and_full(self):
        self.assertEqual(select(self.pool, {"kind": "absolute_floor", "value": .95, "floor": 3}), self.pool[:3])
        self.assertEqual(select(self.pool, {"kind": "full"}), self.pool)

    def test_grid_unique(self):
        rows = policies()
        self.assertEqual(len(rows), 271)
        self.assertEqual(len({r["policy_id"] for r in rows}), 271)


if __name__ == "__main__":
    unittest.main()
