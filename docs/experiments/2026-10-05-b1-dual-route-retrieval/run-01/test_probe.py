"""Boundary checks for this isolated offline probe, not production tests."""
import unittest
import numpy as np
from probe import score_route


class RouteTests(unittest.TestCase):
    def test_normalization_and_parent_max_avoid_chunk_count_votes(self):
        rows = [{'parent_id': 'a', 'chunk_id': 'a1'},
                {'parent_id': 'a', 'chunk_id': 'a2'},
                {'parent_id': 'b', 'chunk_id': 'b1'}]
        scores, parents = score_route(rows, np.array([[2., 0.], [2., 1.], [1., 0.]]), [10., 0.])
        self.assertEqual([p['id'] for p in parents], ['a', 'b'])
        self.assertEqual(parents[0]['score'], 1.)
        self.assertEqual(parents[1]['score'], 1.)
        self.assertEqual(len(parents), 2)
        self.assertAlmostEqual(scores[1], 2 / np.sqrt(5))

    def test_zero_query_rejected_instead_of_arbitrary_candidates(self):
        with self.assertRaises(ValueError):
            score_route([{'parent_id': 'a', 'chunk_id': 'a1'}], np.array([[1., 0.]]), [0., 0.])

    def test_nonfinite_vector_rejected(self):
        with self.assertRaises(ValueError):
            score_route([{'parent_id': 'a', 'chunk_id': 'a1'}], np.array([[float('nan'), 0.]]), [1., 0.])

    def test_duplicate_chunk_rejected(self):
        with self.assertRaises(ValueError):
            score_route([{'parent_id': 'a', 'chunk_id': 'same'}] * 2, np.array([[1., 0.], [0., 1.]]), [1., 0.])


if __name__ == '__main__':
    unittest.main()
