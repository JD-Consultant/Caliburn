"""Failure-oriented guards for research selection and evidence, not model truth."""
import unittest

from pipeline import fuse, validate_judgment


class SelectionGuards(unittest.TestCase):
    def test_dedup_does_not_inflate_a_query_or_exceed_final_five(self):
        pools = [[{'id': 'a'}, {'id': 'a'}, {'id': 'b'}, {'id': 'c'}],
                 [{'id': 'd'}, {'id': 'e'}, {'id': 'f'}]]
        rows = fuse(pools, 2)
        self.assertEqual(next(r['fusion_score'] for r in rows if r['id'] == 'a'), 0.5)
        self.assertEqual(len({r['id'] for r in rows[:5]}), 5)
        self.assertEqual(next(r['query_contributions'] for r in rows if r['id'] == 'a'), [{'query': 1, 'rank': 0, 'contribution': 0.5}])

    def test_equal_fusion_scores_have_a_stable_source_order(self):
        self.assertEqual([r['id'] for r in fuse([[{'id': 'z'}], [{'id': 'a'}]], 2)], ['a', 'z'])

    def test_strong_single_rank_can_beat_multiple_weak_ranks(self):
        pools = [[{'id': 'main'}] + [{'id': f'x{i}'} for i in range(10)] + [{'id': 'local'}],
                 [{'id': f'y{i}'} for i in range(11)] + [{'id': 'local'}]]
        rows = {r['id']: r for r in fuse(pools, 2)}
        self.assertGreater(rows['main']['fusion_score'], rows['local']['fusion_score'])


class EvidenceGuards(unittest.TestCase):
    def test_a_high_grade_with_another_employees_quote_is_rejected(self):
        judgment = {'grade': 3, 'uncertain': False, 'main_work': ['開發畫面'], 'reason': '直接代表',
                    'evidence': [{'employee_quote': '我維修冷氣', 'reference_quote': '製作網頁'}], 'limitations': []}
        with self.assertRaisesRegex(ValueError, 'employee evidence'):
            validate_judgment(judgment, '我開發畫面', '製作網頁')

    def test_uncertain_cannot_be_silently_given_a_numeric_grade(self):
        judgment = {'grade': 1, 'uncertain': True, 'main_work': [], 'reason': '資訊不足', 'evidence': [], 'limitations': []}
        with self.assertRaisesRegex(ValueError, 'uncertainty'):
            validate_judgment(judgment, '我做資訊工作', '製作網頁')

    def test_grade_three_requires_a_named_main_domain_and_evidence(self):
        judgment = {'grade': 3, 'uncertain': False, 'main_work': [], 'reason': '相關', 'evidence': [], 'limitations': []}
        with self.assertRaisesRegex(ValueError, 'strong representative'):
            validate_judgment(judgment, '我開發畫面', '製作網頁')


if __name__ == '__main__':
    unittest.main()
