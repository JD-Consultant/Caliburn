"""Tampered evidence must fail the audit rather than trust pass markers."""
import copy
import unittest
from audit import check_native,check_summaries,check_quote,check_benchmark_task

class EvidenceIntegrity(unittest.TestCase):
    def test_benchmark_id_does_not_authorize_a_different_config(self):
        expected = {'request_id':'E01-global_rerank-1','case_id':'E01','repeat':1,'config':{'method':'global_rerank','n':200,'k':20}}
        row = {**expected,'config':{'method':'quota_rerank','n':20,'k':5},'database_searches':[]}
        with self.assertRaises(AssertionError):
            check_benchmark_task(row,expected,{'passages':['a']})

    def test_claimed_db_http_timing_requires_every_passage_search(self):
        expected = {'request_id':'E01-global_rerank-1','case_id':'E01','repeat':1,'config':{'method':'global_rerank','n':200,'k':20}}
        row = {**expected,'database_searches':[]}
        with self.assertRaises(AssertionError):
            check_benchmark_task(row,expected,{'passages':['a','b']})

    def test_saved_legacy_anchor_is_valid_but_returns_full_context(self):
        case = {'case_id':'E02','employee_messages':['原第一段','原第二段']}
        topic = {'topic_id':'E02-T03','employee_message':1,'employee_message_indices':[1,2],'employee_quote':'原第一段'}
        self.assertEqual(check_quote(case,topic,'development'),'原第一段\n原第二段')

    def test_new_multisegment_quote_cannot_use_legacy_exception(self):
        case = {'case_id':'H01','employee_messages':['第一段','第二段']}
        topic = {'topic_id':'H01-T01','employee_message':1,'employee_message_indices':[1,2],'employee_quote':'第一段'}
        with self.assertRaises(AssertionError):
            check_quote(case,topic,'holdout')

    def test_wrong_native_score_is_rejected_even_with_matching_ids(self):
        q = {'pools':[[{'id':'a','score':.7}]]}
        search = {'passage':1,'limit':1,'exact':True,'seconds':.01,'returned':[{'id':'a','score':.8}]}
        with self.assertRaises(AssertionError):
            check_native(q,search)

    def test_missing_parameter_comparison_is_rejected(self):
        config = {'method':'quota_rerank','n':20,'k':3}
        with self.assertRaises(AssertionError):
            check_summaries([], [config], [])

    def test_summary_pass_marker_cannot_replace_coverage(self):
        config = {'method':'quota_rerank','n':20,'k':3}
        row = {**config,'case_id':'a','total':2,'covered':1,'complete':False,'secondary_total':1,
               'secondary_covered':0,'characters':100,'returned':2,'pair_comparisons':40}
        forged = {**config,'metrics':{'covered':2,'complete_cases':1}}
        with self.assertRaises(AssertionError):
            check_summaries([row],[config],[forged])

if __name__=='__main__':
    unittest.main()
