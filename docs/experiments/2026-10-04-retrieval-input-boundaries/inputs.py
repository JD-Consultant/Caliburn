"""Lossless sentence boundary probe, not a semantic work-fact extractor."""
import re

def sentence_pieces(messages):
    return [{'text':match.group(),'message':index,'start':match.start(),'end':match.end()}
            for index,text in enumerate(messages,1)
            for match in re.finditer(r'.*?[。！？]+|.+$',text,flags=re.DOTALL)]
