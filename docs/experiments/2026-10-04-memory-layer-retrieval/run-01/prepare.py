from common import *
def main():
 cases=read(CROSS/'cases.json');queries=read(CROSS/'queries.json');vectors=read(CROSS/'query-vectors.json')
 assert len(cases)==8
 hc={c['case_id']:c for c in read(H/'cases.json')}
 messages={}
 inputs=[CROSS/n for n in ('cases.json','queries.json','query-vectors.json','corpus.json','collections.json','reused-judgments.json','judgments.json')]
 for c in cases:
  if c['case_id'].startswith('F'):
   msgs=[{'interview_sequence':1,'speaker':'app','text':'請介紹您的職務與實際負責的工作。'},{'interview_sequence':2,'speaker':'employee','text':c['employee_statement']}]
  else:
   source=ROOT/hc[c['case_id']]['source_path'];assert sha(source)==hc[c['case_id']]['source_sha256'];inputs.append(source)
   turns=read(source)['turns'];assert len(turns)==hc[c['case_id']]['turn_count']
   msgs=[{'interview_sequence':1,'speaker':'app','text':'請介紹您的職務與實際負責的工作。'}]
   for i,t in enumerate(turns,1):
    assert t['turn']==i and t['status']=='completed'
    msgs += [{'interview_sequence':2*i,'speaker':'employee','text':t['employee']},{'interview_sequence':2*i+1,'speaker':'consultant','text':t['consultant']}]
   assert '\n'.join(t['employee'] for t in turns)==c['employee_statement']
  messages[c['case_id']]=msgs
 dump('cases.json',cases);dump('replay-messages.json',messages);dump('original-queries.json',queries);dump('original-vectors.json',vectors)
 dump('corpus.json',read(CROSS/'corpus.json'));dump('collections.json',read(CROSS/'collections.json'))
 grades=read(CROSS/'reused-judgments.json')+read(CROSS/'judgments.json')
 assert len({(j['case_id'],j['document_id']) for j in grades})==len(grades)==125
 dump('reused-judgments.json',grades)
 # Keep a baseline of all prior sealed retrieval artifacts, without editing a seal.
 old={}
 for p in EXP.glob('2026-10-04-*/**/artifact-hashes.json'):
  if HERE in p.parents:continue
  if not any(w in str(p) for w in ('retrieval','occupation','rerank','passage')):continue
  d=read(p);d=d.get('files',d)
  for rel,v in d.items():
   target=p.parent/rel
   if not target.is_file():raise ValueError('sealed source missing: '+str(target))
   expected=v if isinstance(v,str) else v['sha256']
   actual=sha(target)
   if actual!=expected:raise ValueError('prior seal changed: '+str(target))
   old[str(target.relative_to(ROOT)).replace('\\','/')]=actual
 dump('prior-seals.json',old)
 inputs += [p for p in HERE.iterdir() if p.is_file() and p.name not in ('progress.md','input-manifest.json','execution-manifest.json')]
 inputs += [ROOT/'docs/plans/2026-10-04-memory-layer-retrieval.md',F/'judge-prompt-02.txt',H/'judge-prompt.txt',H/'judge-schema.json']
 inputs += [ROOT/'apps/api/src/caliburn/agents'/n/'instructions.py' for n in ('work_situation_analyst','work_understanding_analyst')]
 inputs += [ROOT/'docs/experiments/product-validation/data/memory-compaction-publish-2026-10-04/experiment.py',ROOT/'docs/experiments/product-validation/data/design-comparisons-2026-10-04/provider_observations.py']
 dump('input-manifest.json',{'inputs':{str(p.relative_to(ROOT)).replace('\\','/'):{'sha256':sha(p)} for p in inputs}})
 dump('execution-manifest.json',{'max_cost_usd':'1.00','max_calls':160,'input_manifest_sha256':sha(HERE/'input-manifest.json'),'model':'gpt-6-luna','effort':'high'})
 print('8 paired cases, 30 original controls, 125 reusable judgments, '+str(len(old))+' prior sealed files')
if __name__=='__main__':main()
