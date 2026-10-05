import unittest
from inputs import sentence_pieces

class InputIntegrity(unittest.TestCase):
    def test_sentence_boundaries_preserve_whole_text_and_origins(self):
        messages = ['我寫API。\n主管核准部署；我不能放行！','我不負責報價。還原演練由我執行']
        pieces = sentence_pieces(messages)
        self.assertEqual([r['text'] for r in pieces],['我寫API。','\n主管核准部署；我不能放行！','我不負責報價。','還原演練由我執行'])
        for i,text in enumerate(messages,1):
            selected = [r for r in pieces if r['message']==i]
            self.assertEqual(''.join(r['text'] for r in selected),text)
            self.assertEqual(selected[0]['start'],0)
            self.assertEqual(selected[-1]['end'],len(text))
            for r in selected:
                self.assertEqual(text[r['start']:r['end']],r['text'])

    def test_empty_messages_do_not_create_empty_queries(self):
        self.assertEqual(sentence_pieces(['']),[])

    def test_repeated_punctuation_is_not_lost_or_an_extra_query(self):
        self.assertEqual([r['text'] for r in sentence_pieces(['有完成嗎！？有。'])],['有完成嗎！？','有。'])

if __name__=='__main__':
    unittest.main()
