import unittest
from projection import project_turns, query_from_units
from pipeline import validate_judgment


class SourcesTest(unittest.TestCase):
    def setUp(self):
        self.turns = [
            {'turn': 1, 'status': 'completed', 'employee': '我負責倉庫收貨。',
             'consultant': '我已寫進草稿。\n\n您會親自點收嗎？'},
            {'turn': 2, 'status': 'completed', 'employee': '會，但退貨由採購決定。',
             'consultant': '您也負責採購下單嗎？'},
        ]

    def test_preceding_question_not_unanswered_next_question(self):
        units = project_turns(self.turns, {2})
        text, spans = query_from_units(units, [1, 2])
        self.assertIn('您會親自點收嗎？', text)
        self.assertNotIn('我已寫進草稿', text)
        self.assertNotIn('您也負責採購下單嗎？', text)
        question = [s for s in spans if s['speaker'] == 'consultant'][0]
        self.assertEqual(question['turn'], 1)

    def test_single_paragraph_question_preserved_without_first_char_loss(self):
        self.turns[0]['consultant'] = '您會親自點收嗎？'
        units = project_turns(self.turns, {2})
        self.assertEqual(units[1]['question']['text'], '您會親自點收嗎？')

    def test_failed_turn_cannot_become_completed_source(self):
        self.turns[1]['status'] = 'failed'
        with self.assertRaises(ValueError):
            project_turns(self.turns, {2})

    def test_consultant_question_cannot_be_employee_evidence(self):
        value = {'grade': 3, 'uncertain': False, 'main_work': ['收貨'], 'reason': 'reason',
                 'evidence': [{'employee_quote': '您會親自點收嗎？', 'reference_quote': '收貨'}],
                 'limitations': []}
        with self.assertRaises(ValueError):
            validate_judgment(value, '\n'.join(t['employee'] for t in self.turns), '收貨')


if __name__ == '__main__':
    unittest.main()
