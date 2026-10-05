"""A corrupted retained list must not be accepted merely because scores are saved."""
import copy
import importlib.util
import unittest
from pathlib import Path
from unittest.mock import patch

import verify


class AuditContract(unittest.TestCase):
    def test_changed_database_returned_ids_are_detected(self):
        original = verify.lines

        def changed(name):
            rows = original(name)
            if name == 'database-checks.jsonl':
                rows = copy.deepcopy(rows)
                rows[0]['returned_ids'][0] = 'wrong-id'
            return rows

        with patch.object(verify, 'lines', side_effect=changed):
            with self.assertRaises(AssertionError):
                verify.check()

    def auditors(self):
        spec = importlib.util.spec_from_file_location('passage_verify', Path(verify.__file__).parent / 'passage-pool' / 'verify.py')
        child = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(child)
        return (verify, child)

    def test_forged_development_selection_is_detected(self):
        for module in self.auditors():
            with self.subTest(module=str(module.HERE)):
                original = module.read
                summaries = copy.deepcopy(original('parameter-summary-development.json'))
                for row in summaries:
                    row['development']['complete_queries'] = 0
                forged = next(r for r in summaries if (r['method'], r['n'], r['cosine'], r['k'], r['cross']) == ('rerank', 20, .7, 5, .7))
                forged['development']['complete_queries'] = forged['development']['positive_queries']
                selection = copy.deepcopy(original('selection-development.json'))
                selection['chosen'] = {'dense_only': None, 'rerank': forged}

                def changed(name):
                    return {'parameter-summary-development.json': summaries,
                            'selection-development.json': selection}.get(name) if name in ('parameter-summary-development.json', 'selection-development.json') else original(name)

                with patch.object(module, 'read', side_effect=changed), patch.object(Path, 'write_text'), patch('builtins.print'):
                    with self.assertRaises(AssertionError):
                        module.check()

    def test_missing_selected_comparison_is_detected(self):
        module = self.auditors()[1]
        original = module.read
        with patch.object(module, 'read', side_effect=lambda name: [] if name == 'comparison.json' else original(name)), patch.object(Path, 'write_text'), patch('builtins.print'):
            with self.assertRaises(AssertionError):
                module.check()

    def test_changed_retained_document_is_detected(self):
        original = verify.lines

        def changed(name):
            rows = original(name)
            if name == 'final-metrics.jsonl':
                rows = copy.deepcopy(rows)
                row = next(r for r in rows if r['selected_ids'])
                row['selected_ids'][0] = 'wrong-id'
            return rows

        verify.lines = changed
        try:
            with self.assertRaises(AssertionError):
                verify.check()
        finally:
            verify.lines = original


if __name__ == '__main__':
    unittest.main()
