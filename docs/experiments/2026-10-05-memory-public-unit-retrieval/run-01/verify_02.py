"""Independent source, all cosine, two-stage fusion and fresh rerank replay."""
import copy,math,numpy as np
import common as owner
from common import *

def fusion(pools):
 if len(pools)==1:return [r['id'] for r in pools[0]]
 values={}
 for pool in pools:
  assert len({r['id'] for r in pool})==len(pool)
  for rank,row in enumerate(pool):values[row['id']]=values.get(row['id'],0)+1/(2+rank)
 return [i for i,s in sorted(values.items(),key=lambda r:(-r[1],r[0]))]

def query_binding(q,v,original):
 assert q['query_id']==v['query_id'] and q['case_id']==original['case_id']
 assert q['text']==original['text'] and text_sha(q['text'])==q['text_sha256']==v['text_sha256']
 if q.get('layer')=='work_understanding':
  snap=read(MEM/'snapshots'/f"{q['case_id']}.json");objs={o['object_id']:o for o in snap['objects']};chosen=[objs[r['object_id']] for r in q['object_revisions']]
  assert q['snapshot_id']==snap['snapshot']['snapshot_id'] and q['text']=='\n\n'.join(o['content']['body'] for o in chosen)
  assert all(o['revision_id']==r['revision_id'] and o['layer']=='work_understanding' for o,r in zip(chosen,q['object_revisions'],strict=True))

def pair_binding(p,byq,docs):
 assert p['query_sha256']==text_sha(byq[p['query_id']]['text']) and p['document_sha256']==text_sha(docs[p['id']]['text'])
 assert p['cache_reused'] is False and math.isfinite(p['logit'])
 assert p['logit']==max(w['logit'] for w in p['windows'])
 assert all(w['pair_tokens']<=8192 for w in p['windows'])
 assert sum(w['document_tokens'] for w in p['windows'])-64*(len(p['windows'])-1)==p['document_tokens']

def main(outname):
 manifests=['input-manifest.json','rerank-input-manifest.json','benchmark-code-manifest.json','benchmark-amendment-inputs.json','judge-code-manifest.json','analysis-code-manifest.json','analysis-amendment-inputs.json','recovery-code-manifest.json','judge-amendment-inputs.json']
 for name in manifests:
  if (HERE/name).exists():check_manifest(name)
 prior=read(HERE/'prior-seals.json')
 for path,h in prior.items():assert sha(ROOT/path)==h,path
 qs=read(HERE/'queries.json');byq={q['query_id']:q for q in qs};vs={v['query_id']:v for v in read(HERE/'query-vectors.json')};original={q['query_id']:q for q in read(MEM/'queries.json')}
 for q in qs:query_binding(q,vs[q['query_id']],original[q['query_id']])
 chunks=read(PUBLIC/'chunks.json');raw={}
 for path in (PUBLIC/'vector-batches').glob('*.npz'):
  z=np.load(path,allow_pickle=False)
  for h,v in zip(z['hashes'],z['dense'],strict=True):raw[str(h)]=v
 allr={(r['query_id'],r['representation']):r for r in read(HERE/'all-rankings.json')};expected_pools={};maxerr=0;cosines=0
 for rep in ('document','task'):
  rows=[r for r in chunks if r['representation']==rep];matrix=np.asarray([raw[text_sha(r['text'])] for r in rows],dtype=np.float64);matrix/=np.linalg.norm(matrix,axis=1,keepdims=True)
  for q in qs:
   v=np.asarray(vs[q['query_id']]['dense'],dtype=np.float64);assert v.shape==(1024,) and np.isfinite(v).all();v/=np.linalg.norm(v);scores=matrix@v;cosines+=len(scores);saved=allr[(q['query_id'],rep)];assert len(saved['chunk_scores'])==len(rows)
   parents={}
   for row,s,hit in zip(rows,scores,saved['chunk_scores'],strict=True):
    assert row['parent_id']==hit['parent_id'] and row['chunk_id']==hit['chunk_id'];maxerr=max(maxerr,abs(float(s)-hit['score']));parents.setdefault(row['parent_id'],[]).append((row['chunk_id'],float(s)))
   ranked=sorted([(ident,max(s for _,s in vals)) for ident,vals in parents.items()],key=lambda x:(-x[1],x[0]));assert len(ranked)==805
   assert [i for i,s in ranked]==[r['id'] for r in saved['parents']]
   for (ident,s),record in zip(ranked,saved['parents'],strict=True):
    assert abs(s-record['score'])<1e-12
    top=sorted(parents[ident],key=lambda x:(-x[1],x[0]))[:3];assert [i for i,s in top]==[h['chunk_id'] for h in record['top_chunks']]
   expected_pools[(q['query_id'],rep)]=[{'id':i} for i,s in ranked[:20]]
 assert maxerr<1e-12
 base=read(HERE/'results.json');rr=read(HERE/'rerank-results.json');assert len(base)==len(rr)==48
 for r in base:
  locals=[]
  for qid,pool in zip(r['query_ids'],r['query_pools'],strict=True):
   d=expected_pools[(qid,'document')];t=expected_pools[(qid,'task')]
   ids=[p['id'] for p in d] if r['representation']=='D' else [p['id'] for p in t] if r['representation']=='T' else fusion([d,t])[:20]
   assert ids==[p['id'] for p in pool] and len(ids)==len(set(ids))==20;locals.append([{'id':i} for i in ids])
  expected=fusion(locals);assert expected==[p['id'] for p in r['merged_ranking']] and expected[:5]==[p['id'] for p in r['selected']]
 pairs=[json.loads(s) for s in (HERE/'rerank-pairs.jsonl').read_text(encoding='utf-8').splitlines()];docs={d['id']:d for d in read(HERE/'corpus.json')};values={(p['query_id'],p['id']):p for p in pairs}
 needed={(qid,p['id']) for r in base for qid,pool in zip(r['query_ids'],r['query_pools'],strict=True) for p in pool};assert len(values)==len(pairs) and set(values)==needed
 for p in pairs:pair_binding(p,byq,docs)
 for r in rr:
  parent=next(p for p in base if p['case_id']==r['case_id'] and p['method']+'-R'==r['method']);locals=[]
  for qid,pool,actual in zip(parent['query_ids'],parent['query_pools'],r['query_pools'],strict=True):
   ids=sorted([p['id'] for p in pool],key=lambda i:(-values[(qid,i)]['logit'],i));assert ids==[p['id'] for p in actual];locals.append([{'id':i} for i in ids])
  expected=fusion(locals);assert expected==[p['id'] for p in r['merged_ranking']] and expected[:5]==[p['id'] for p in r['selected']]
 controls=read(HERE/'control-checks.json');assert len(controls)==24 and all(c['same_prior_top5'] for c in controls)
 for r in base:
  if r['representation']=='D':old=next(p for p in read(MEM/'results.json') if p['case_id']==r['case_id'] and p['method']==('O-W' if r['variant']=='O' else 'B2-S'))
  elif r['method']=='O-T':old=next(p for p in read(CROSS/'results.json') if p['case_id']==r['case_id'] and p['method']=='W-Tmax')
  else:continue
  assert [p['id'] for p in old['selected']]==[p['id'] for p in r['selected']]
 warm=read(HERE/'benchmark.json');rw=[];fresh=[]
 if (HERE/'rerank-benchmark.json').exists():
  rw=read(HERE/'rerank-benchmark.json');fresh=[json.loads(s) for s in (HERE/'rerank-benchmark-pairs.jsonl').read_text(encoding='utf-8').splitlines()]
  assert len(rw)==144 and len(fresh)==sum(t['fresh_gpu_pairs'] for t in rw)==3600
  for p in fresh:pair_binding(p,byq,docs)
  for index,t in enumerate(rw):
   request=read(HERE/'benchmark-requests'/f'{index:03}.json');answer=read(HERE/'benchmark-responses'/f'{index:03}.json');source=next(r for r in base if r['case_id']==t['case_id'] and r['method']+'-R'==t['method'])
   assert request['query_ids']==source['query_ids'] and [[p['id'] for p in pool] for pool in request['pools']]==[[p['id'] for p in pool] for pool in source['query_pools']]
   now=[p for p in fresh if p['task_id']==t['case_id']+'-'+t['method']+'-'+str(t['repeat'])];assert len(now)==t['fresh_gpu_pairs'];lookup={(p['query_id'],p['id']):p['logit'] for p in now};locals=[]
   for qid,pool,actual in zip(request['query_ids'],request['pools'],answer['query_pools'],strict=True):
    ids=sorted([p['id'] for p in pool],key=lambda i:(-lookup[(qid,i)],i));assert ids==[p['id'] for p in actual];locals.append([{'id':i} for i in ids])
   assert fusion(locals)[:5]==answer['selected_ids']==t['selected_ids']
 assert len(warm)==144
 for t in warm+rw:
  result=next(r for r in base+rr if r['case_id']==t['case_id'] and r['method']==t['method']);assert t['selected_ids']==[p['id'] for p in result['selected']]
 negative=[]
 q=copy.deepcopy(qs[0]);q['text']+=' altered'
 try:query_binding(q,vs[q['query_id']],original[q['query_id']])
 except AssertionError:negative.append('changed query text rejected')
 try:merge_pools([[{'id':'a'},{'id':'a'}]],['q'])
 except ValueError:negative.append('duplicate parent in local pool rejected')
 saved_read=owner.read;manifest=copy.deepcopy(read(HERE/'input-manifest.json'));manifest['inputs'][next(iter(manifest['inputs']))]['sha256']='0'*64;owner.read=lambda p:manifest
 try:check_manifest()
 except ValueError:negative.append('changed source hash rejected')
 finally:owner.read=saved_read
 assert len(negative)==3
 used=read(HERE/'used-prior-judgments.json');new=read(HERE/'judgments-final.json') if (HERE/'judgments-final.json').exists() else []
 grades={(j['case_id'],j['document_id']):j for j in used+new};allpairs={(r['case_id'],p['id']) for r in base+rr for p in r['selected']};grading_complete=allpairs<=set(grades)
 for (cid,ident),j in grades.items():
  case=next(c for c in read(HERE/'cases.json') if c['case_id']==cid);assert j['employee_sha256']==text_sha(case['employee_statement']) and j['document_sha256']==text_sha(docs[ident]['text']);validate_judgment(j['judgment'],case['employee_statement'],docs[ident]['text'])
 dump(outname,{'cases':8,'methods':12,'groups':96,'positions':480,'queries':20,'cosines_recomputed':cosines,'max_cosine_error':maxerr,'quality_rerank_pairs':len(values),'warm_dense_trials':len(warm),'warm_rerank_trials':len(rw),'fresh_warm_rerank_pairs':len(fresh),'controls_unchanged':24,'prior_sealed_files_unchanged':len(prior),'negative_probes':negative,'unique_selected_pairs':len(allpairs),'validated_grades':len(grades),'grading_complete':grading_complete,'scope':'finite observed synthetic retrieval comparison; not full-corpus relevance recall/JD completeness'})
 print(f'{cosines} cosines, {len(values)} quality pairs, {len(fresh)} fresh timing pairs verified; grades complete={grading_complete}')
if __name__=='__main__':main(sys.argv[1] if len(sys.argv)>1 else 'verification.json')
