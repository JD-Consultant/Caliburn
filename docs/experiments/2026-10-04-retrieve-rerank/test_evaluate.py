import unittest

from evaluate import coverage, select, token_windows, pipeline


class RetrievalContract(unittest.TestCase):
    def test_reranker_cannot_restore_document_removed_by_broad_search(self):
        dense = [{'id':'A','score':0.8},{'id':'B','score':0.7},{'id':'C','score':0.6}]
        pairs = [{'id':'A','score':0.2},{'id':'B','score':0.9},{'id':'C','score':0.99}]
        self.assertEqual([r['id'] for r in pipeline(dense,pairs,2,None,1,0.5)],['B'])
        self.assertEqual(pipeline(dense,pairs,2,0.75,1,0.5),[])

    def test_secondary_topic_is_not_hidden_by_primary_role_hit(self):
        topics = [{'topic_id':'repair','secondary':False,'support':[{'id':'R'}]},
                  {'topic_id':'purchase','secondary':True,'support':[{'id':'P'}]}]
        result = coverage(['R'],topics)
        self.assertEqual(result, {'covered':1,'total':2,'coverage':0.5,'missing':['purchase'],
                                  'secondary_covered':0,'secondary_total':1,'complete':False})

    def test_threshold_removes_candidates_without_filling_from_below(self):
        rows = [{'id':'A','score':0.8},{'id':'B','score':0.69},{'id':'C','score':0.4}]
        self.assertEqual([x['id'] for x in select(rows,3,0.7)],['A'])
        self.assertEqual(select(rows,5,0.9),[])

    def test_empty_truth_is_not_one_hundred_percent_coverage(self):
        self.assertIsNone(coverage(['A'],[])['coverage'])

    def test_windows_preserve_tail_and_overlap(self):
        self.assertEqual(token_windows([100,101],list(range(10)),10,overlap=1),
                         [[0,1,2,3],[3,4,5,6],[6,7,8,9]])

    def test_query_cannot_be_silently_truncated(self):
        with self.assertRaisesRegex(ValueError,'query'):
            token_windows(list(range(8)),[1,2,3],10,overlap=1)


if __name__ == '__main__':
    unittest.main()
