"""Research-only structured public chunks and deterministic parent aggregation."""
import sys
from pathlib import Path
from collections import defaultdict
import math

sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'2026-10-04-occupation-retrieval'))
from evaluation import clean_text


def normalized_parts(parts):
    return list(dict.fromkeys(value for part in parts if (value:=clean_text(part).replace('\n',''))))


def task_parts(task):
    parts=[i.get('name') or '' for i in task['task_codes']]
    for block in task['competency_blocks']:
        parts.extend(i.get('name') or '' for i in block['outputs'])
        parts.extend(i.get('text') or '' for i in block['indicators'])
    return parts


def build_chunks(document,granularity):
    if granularity not in ('task','unit'):raise ValueError('unknown granularity')
    parent=document['ocs_profile']['ocs_code']; rows=[]
    def add(kind,parts,unit_index=None,task_index=None,codes=None):
        text='\n'.join(normalized_parts(parts))
        if text:
            rows.append({'chunk_id':f'{parent}:{kind}:{unit_index}:{task_index}',
                         'parent_id':parent,'kind':kind,'text':text,
                         'unit_index':unit_index,'task_index':task_index,'task_codes':codes or []})
    add('overview',[document['ocs_profile'].get('job_description') or ''])
    for ui,unit in enumerate(document['ocs_content']['ocu_units'],1):
        if granularity=='unit':
            parts=[unit.get('ocu_name') or '']; codes=[]
            for task in unit['tasks']:
                parts.extend(task_parts(task)); codes.extend(i['code'] for i in task['task_codes'])
            add('unit',parts,ui,codes=codes)
        else:
            for ti,task in enumerate(unit['tasks'],1):
                add('task',[unit.get('ocu_name') or '',*task_parts(task)],ui,ti,
                    [i['code'] for i in task['task_codes']])
    return rows


def aggregate(rows,method,candidate_limit=20):
    if method not in ('max','mean3'):raise ValueError('unknown aggregation')
    groups=defaultdict(list); seen=set()
    for row in rows:
        if row['chunk_id'] in seen:raise ValueError('duplicate chunk')
        if not math.isfinite(row['score']):raise ValueError('non-finite score')
        seen.add(row['chunk_id']); groups[row['parent_id']].append(row)
    parents=[]
    for parent,hits in groups.items():
        top=sorted(hits,key=lambda r:(-r['score'],r['chunk_id']))[:3]
        parents.append({'id':parent,'max_score':top[0]['score'],'top_chunks':top,
                        'available_chunks':len(hits)})
    pool=sorted(parents,key=lambda r:(-r['max_score'],r['id']))[:candidate_limit]
    for row in pool:
        row['score']=row['max_score'] if method=='max' else sum(h['score'] for h in row['top_chunks'])/len(row['top_chunks'])
    return sorted(pool,key=lambda r:(-r['score'],r['id']))
