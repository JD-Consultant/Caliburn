import unittest
from fusion import merge_pools

class FusionBehavior(unittest.TestCase):
    def test_shared_parent_is_one_result_and_both_queries_remain(self):
        a=[{'id':'A','score':.9},{'id':'B','score':.8}]
        b=[{'id':'B','score':.6},{'id':'C','score':.5}]
        result=merge_pools([a,b],['q1','q2'])
        self.assertEqual([r['id'] for r in result],['B','A','C'])
        self.assertAlmostEqual(result[0]['fusion_score'],1/3+1/2)
        self.assertEqual([r['query_id'] for r in result[0]['contributions']],['q1','q2'])

    def test_single_query_preserves_its_order_and_score(self):
        result=merge_pools([[{'id':'B','score':.7},{'id':'A','score':.6}]],['one'])
        self.assertEqual([r['id'] for r in result],['B','A'])
        self.assertEqual(result[0]['score'],.7)
        self.assertNotIn('fusion_score',result[0])

    def test_fusion_ties_are_by_parent_id(self):
        pools=[[{'id':'Z','score':.8}],[{'id':'A','score':.9}]]
        self.assertEqual([r['id'] for r in merge_pools(pools,['q1','q2'])],['A','Z'])

    def test_same_parent_cannot_contribute_twice_within_one_query(self):
        with self.assertRaises(ValueError):merge_pools([[{'id':'A','score':.9},{'id':'A','score':.8}]],['q'])

if __name__=='__main__':unittest.main()
