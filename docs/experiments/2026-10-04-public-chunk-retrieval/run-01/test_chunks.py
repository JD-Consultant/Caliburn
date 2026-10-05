import unittest
from chunks import build_chunks, aggregate


class ChunkBehavior(unittest.TestCase):
    def setUp(self):
        self.doc = {'ocs_profile': {'ocs_code':'DOC', 'job_description':'工作概述',
                    'ocs_name':{'occupation_name':'不要加入的職稱'}},
                    'ocs_content':{'ocu_units':[{'ocu_name':'前置作業','tasks':[
                      {'task_codes':[{'code':'T1.1','name':'確認需求'},{'code':'T1.2','name':'整理需求'}],
                       'competency_blocks':[{'outputs':[{'code':'O1','name':'需求清單'}],
                          'indicators':[{'code':'P1','text':'P1 核對規格及數量。'}],
                          'knowledge':[{'name':'機密知識'}],'skills':[]}]},
                      {'task_codes':[{'code':'T1.3','name':'安排作業'}],
                       'competency_blocks':[{'outputs':[],'indicators':[{'text':'依確認需求安排作業。'}]}]}]}]}}

    def test_task_keeps_relationship_and_multiple_codes_once(self):
        rows = build_chunks(self.doc,'task')
        tasks = [r for r in rows if r['kind']=='task']
        self.assertEqual(len(tasks),2)
        self.assertEqual(tasks[0]['task_codes'],['T1.1','T1.2'])
        self.assertEqual(tasks[0]['text'],'前置作業\n確認需求\n整理需求\n需求清單\n核對規格及數量。')
        self.assertNotIn('安排作業',tasks[0]['text'])
        self.assertNotIn('不要加入的職稱',tasks[0]['text'])
        self.assertNotIn('機密知識',tasks[0]['text'])

    def test_unit_keeps_all_tasks_and_overview_is_separate(self):
        rows = build_chunks(self.doc,'unit')
        self.assertEqual(len(rows),2)
        self.assertEqual(rows[0]['kind'],'overview')
        self.assertEqual(rows[0]['text'],'工作概述')
        self.assertIn('安排作業',rows[1]['text'])
        self.assertIn('核對規格及數量。',rows[1]['text'])
        self.assertNotIn('工作概述',rows[1]['text'])

    def test_collapse_and_mean3_only_reranks_same_parent_pool(self):
        rows=[{'parent_id':'A','chunk_id':'a1','score':.9},
              {'parent_id':'A','chunk_id':'a2','score':.1},
              {'parent_id':'A','chunk_id':'a3','score':.1},
              {'parent_id':'B','chunk_id':'b1','score':.8},
              {'parent_id':'C','chunk_id':'c1','score':.79}]
        maximum = aggregate(rows,'max',candidate_limit=2)
        mean = aggregate(rows,'mean3',candidate_limit=2)
        self.assertEqual([r['id'] for r in maximum],['A','B'])
        self.assertEqual([r['id'] for r in mean],['B','A'])
        self.assertEqual(mean[0]['score'],.8)
        self.assertNotIn('C',[r['id'] for r in mean])

    def test_tie_order_and_duplicate_chunk_rejected(self):
        rows=[{'parent_id':'Z','chunk_id':'z','score':.5},
              {'parent_id':'A','chunk_id':'a','score':.5}]
        self.assertEqual([r['id'] for r in aggregate(rows,'max')],['A','Z'])
        with self.assertRaises(ValueError):aggregate(rows+rows[:1],'max')


if __name__=='__main__':unittest.main()
