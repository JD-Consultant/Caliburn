import unittest
from audit_boundaries import check_task
from support import prior

class BoundaryEvidence(unittest.TestCase):
    def test_matching_request_id_cannot_relabel_an_input_variant(self):
        expected = {'request_id':'E01-joined_employee-1','case_id':'E01','variant':'joined_employee','repeat':1,
                    'config':{'method':'quota_rerank','n':20,'k':5}}
        row = {**expected,'variant':'original_messages','database_searches':[{'passage':1,'limit':20}]}
        with self.assertRaises(AssertionError):
            check_task(row,expected,{'passages':['same text']})

    def test_one_reference_may_support_multiple_work_topics(self):
        topics = [{'topic_id':'a','secondary':False,'support':[{'id':'shared'}]},
                  {'topic_id':'b','secondary':True,'support':[{'id':'shared'}]}]
        result = prior.coverage(['shared'],topics)
        self.assertEqual((result['covered'],result['total'],result['secondary_covered']),(2,2,1))

    def test_a_work_topic_may_have_alternative_supporting_sources(self):
        topics = [{'topic_id':'same_action','secondary':False,'support':[{'id':'source_a'},{'id':'source_b'}]}]
        result = prior.coverage(['source_b'],topics)
        self.assertEqual((result['covered'],result['total']),(1,1))

    def test_combining_jd_tasks_does_not_erase_a_missing_work_aspect(self):
        topics = [{'topic_id':'interface','jd_group':'one_combined_task','secondary':False,'support':[{'id':'front'}]},
                  {'topic_id':'service','jd_group':'one_combined_task','secondary':False,'support':[{'id':'back'}]}]
        result = prior.coverage(['back'],topics)
        self.assertEqual((result['covered'],result['total'],result['missing']),(1,2,['interface']))
        self.assertFalse(result['complete'])

if __name__=='__main__':
    unittest.main()
