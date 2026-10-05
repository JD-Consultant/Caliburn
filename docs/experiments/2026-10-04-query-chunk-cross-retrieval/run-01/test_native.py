import unittest
from types import SimpleNamespace as Obj
from native import canonical_hits

class NativeBoundary(unittest.TestCase):
    def test_raw_float32_tie_is_sorted_using_saved_float64_cosines(self):
        groups=[Obj(id='B',hits=[Obj(id=0,payload={'parent_id':'B','chunk_id':'b'},score=.609)]),
                Obj(id='A',hits=[Obj(id=1,payload={'parent_id':'A','chunk_id':'a'},score=.60899996)])]
        rows=[{'parent_id':'B','chunk_id':'b'},{'parent_id':'A','chunk_id':'a'}]
        hits=canonical_hits(groups,rows,[.60899998,.60899998])
        self.assertEqual([h['parent_id'] for h in sorted(hits,key=lambda h:(-h['score'],h['parent_id']))],['A','B'])
        self.assertEqual(hits[0]['native_score'],.609)

    def test_material_native_score_error_is_rejected(self):
        group=Obj(id='A',hits=[Obj(id=0,payload={'parent_id':'A','chunk_id':'a'},score=.4)])
        with self.assertRaises(ValueError):canonical_hits([group],[{'parent_id':'A','chunk_id':'a'}],[.6])

if __name__=='__main__':unittest.main()
