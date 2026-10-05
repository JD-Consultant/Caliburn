import unittest

from selection import per_passage


class PassageRetention(unittest.TestCase):
    def test_late_secondary_work_has_its_own_retained_slot(self):
        pools = [[{'id':'main-a','score':.9},{'id':'main-b','score':.8},{'id':'rare','score':.4}],
                 [{'id':'rare','score':.65},{'id':'main-b','score':.5},{'id':'main-a','score':.45}]]
        scores = {(1,'main-a'):5.,(1,'main-b'):4.,(1,'rare'):-9.,
                  (2,'main-a'):-8.,(2,'main-b'):-6.,(2,'rare'):-.1}
        result = per_passage(pools,scores,2,1,True)
        self.assertEqual({r['id'] for r in result},{'main-a','rare'})
        rare = next(r for r in result if r['id']=='rare')
        self.assertEqual(rare['matches'][0]['passage'],2)
        self.assertEqual(rare['matches'][0]['logit'],-.1)

    def test_duplicate_reference_retains_both_passage_origins(self):
        pools = [[{'id':'common','score':.9},{'id':'a','score':.8}],
                 [{'id':'common','score':.9},{'id':'b','score':.8}]]
        scores = {(1,'common'):5.,(1,'a'):4.,(2,'common'):5.,(2,'b'):4.,(1,'b'):-1.,(2,'a'):-1.}
        result = per_passage(pools,scores,2,2,True)
        self.assertEqual({r['id'] for r in result},{'common','a','b'})
        common = next(r for r in result if r['id']=='common')
        self.assertEqual([m['passage'] for m in common['matches']],[1,2])
        self.assertEqual(len(result),3)

    def test_missing_required_pair_is_rejected(self):
        pools = [[{'id':'a','score':.8}],[{'id':'b','score':.7}]]
        with self.assertRaises(ValueError):
            per_passage(pools,{(1,'a'):3.},1,1,True)

    def test_dense_only_also_preserves_the_secondary_passage(self):
        pools = [[{'id':'a','score':.9},{'id':'b','score':.8}],
                 [{'id':'rare','score':.6},{'id':'b','score':.5}]]
        result = per_passage(pools,{},2,1,False)
        self.assertEqual({r['id'] for r in result},{'a','rare'})


if __name__=='__main__':
    unittest.main()
