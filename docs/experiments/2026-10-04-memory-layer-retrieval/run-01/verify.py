"""Independent finite replay of frozen sources, all dense rankings and fusion."""
import math,numpy as np
from common import *
def main():
 check_manifest();check_manifest('capture-amendment-inputs.json');check_manifest('retrieval-code-manifest.json');check_manifest('query-input-manifest.json')
 prior=read(HERE/'prior-seals.json')
 for path,h in prior.items():assert sha(ROOT/path)==h,path
 qs=read(HERE/'queries.json');byq={q['query_id']:q for q in qs};vs={v['query_id']:v for v in read(HERE/'query-vectors.json')}
 docs=read(HERE/'corpus.json');bydoc={d['id']:d for d in docs};cases={c['case_id']:c for c in read(HERE/'cases.json')}
 rows=[r for r in read(PUBLIC/'chunks.json') if r['representation']=='document']
 raw={}
 for p in (PUBLIC/'vector-batches').glob('*.npz'):
  z=np.load(p,allow_pickle=False)
  for h,v in zip(z['hashes'],z['dense'],strict=True):raw[str(h)]=v
 matrix=np.asarray([raw[text_sha(r['text'])] for r in rows],dtype=np.float64);matrix/=np.linalg.norm(matrix,axis=1,keepdims=True)
 assert len(rows)==805 and all(r['text']==bydoc[r['parent_id']]['text'] for r in rows)
 allr={r['query_id']:r['ranking'] for r in read(HERE/'all-rankings.json')}
 maxerr=0
 for q in qs:
  assert q['text_sha256']==text_sha(q['text'])==vs[q['query_id']]['text_sha256']
  v=np.asarray(vs[q['query_id']]['dense'],dtype=np.float64);assert v.shape==(1024,) and np.isfinite(v).all();v/=np.linalg.norm(v)
  scores=matrix@v;expected=sorted([(rows[i]['parent_id'],float(s)) for i,s in enumerate(scores)],key=lambda t:(-t[1],t[0]))
  assert [i for i,s in expected]==[r['id'] for r in allr[q['query_id']]]
  maxerr=max(maxerr,max(abs(s-r['score']) for (i,s),r in zip(expected,allr[q['query_id']],strict=True)))
  assert maxerr<1e-12
  if q.get('layer') in ('work_situation','work_understanding'):
   snap=read(HERE/'snapshots'/f"{q['case_id']}.json");objects={o['object_id']:o for o in snap['objects']}
   chosen=[objects[r['object_id']] for r in q['object_revisions']]
   assert all(o['revision_id']==r['revision_id'] and o['layer']==q['layer'] for o,r in zip(chosen,q['object_revisions'],strict=True))
   assert q['snapshot_id']==snap['snapshot']['snapshot_id'] and q['text']=='\n\n'.join(o['content']['body'] for o in chosen)
 results=read(HERE/'results.json');assert len(results)==48
 graded={(r['case_id'],r['method']):r for r in read(HERE/'graded-results.json')}
 pairs=set()
 for r in results:
  assert all(qid in byq and byq[qid]['case_id']==r['case_id'] for qid in r['query_ids'])
  locals=[allr[qid][:20] for qid in r['query_ids']]
  # Recompute fusion directly, independent of the imported helper.
  if len(locals)==1:ordered=locals[0]
  else:
   sums={}
   for pool in locals:
    for rank,p in enumerate(pool):sums[p['id']]=sums.get(p['id'],0)+1/(2+rank)
   ordered=[{'id':i,'fusion_score':s} for i,s in sorted(sums.items(),key=lambda t:(-t[1],t[0]))]
  assert [v['id'] for v in ordered]==[v['id'] for v in r['merged_ranking']]
  assert len(r['selected'])==5 and len({p['id'] for p in r['selected']})==5
  assert [v['id'] for v in ordered[:5]]==[v['id'] for v in r['selected']]
  g=graded[(r['case_id'],r['method'])];assert [p['id'] for p in g['selected']]==[p['id'] for p in r['selected']]
  for p in g['selected']:
   validate_judgment(p['judgment'],cases[r['case_id']]['employee_statement'],bydoc[p['id']]['text']);pairs.add((r['case_id'],p['id']))
 assert len(read(HERE/'control-checks.json'))==16 and len(read(HERE/'benchmark.json'))==144
 assert len(read(HERE/'source-bindings.json'))==8 and all(r['all_reference_scopes_valid'] for r in read(HERE/'source-bindings.json'))
 dump('verification.json',{'cases':8,'methods':6,'groups':48,'top5_positions':240,'unique_graded_pairs':len(pairs),'queries':len(qs),'cosines_recomputed':805*len(qs),'max_score_error':maxerr,'prior_sealed_files_unchanged':len(prior),'original_controls_unchanged':16,'warm_trials':144,'published_source_scopes_verified':8,'scope':'finite synthetic retrieval comparison; not full-library relevance recall or JD completeness'})
 print('independent replay and prior artifact preservation passed')
if __name__=='__main__':main()
