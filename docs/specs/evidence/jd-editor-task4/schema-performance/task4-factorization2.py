"""Scratch-only equivalent SSOT candidate; never modifies active schema."""
from copy import deepcopy
import difflib, hashlib, json, time
from pathlib import Path
from jsonschema import Draft202012Validator

HERE=Path(__file__).parent
ROOT=HERE.parents[2]
OUT=HERE/'task4-schema-candidate2'
cached=json.loads((HERE/'task4-schema-candidate/equivalence-results.json').read_text(encoding='utf-8'))
cached_cases={c['case']:c for c in cached['cases']}
OUT.mkdir(exist_ok=True)
raw=(ROOT/'docs/specs/contracts/jd-editor-v2.schema.json').read_bytes()
assert not (OUT/'before.schema.json').exists(), 'Do not overwrite first candidate evidence'
(OUT/'before.schema.json').write_bytes(raw)
old=json.loads(raw);new=deepcopy(old);defs=new['$defs']
composed=['JdSavedTaskChild','JdSavedKnowledgeSectionChild','JdSavedSkillsSectionChild']
changed=[]
def factor(value):
    if isinstance(value,list):
        for v in value:factor(v)
    elif isinstance(value,dict):
        if '$ref' in value:
            ref=value['$ref'];name=ref.split('/')[-1]
            if name.startswith('JdSaved') and name!='JdSavedElement':
                if name in composed:
                    del value['$ref']
                    value['oneOf']=[{'$ref':b['$ref']+'/allOf/1'} for b in defs[name]['oneOf']]
                    changed.append(ref)
                    return
                assert defs[name]['allOf'][0]=={'$ref':'#/$defs/JdSavedElement'}
                value['$ref']=ref+'/allOf/1';changed.append(ref)
        for v in value.values():factor(v)
factor(defs['JdSavedElement']['allOf'])
candidate=(json.dumps(new,ensure_ascii=False,indent=2)+'\n').encode()
(OUT/'candidate.schema.json').write_bytes(candidate)
(OUT/'candidate.diff').write_text(''.join(difflib.unified_diff(raw.decode().splitlines(True),candidate.decode().splitlines(True),fromfile='before',tofile='candidate')),encoding='utf-8')
Draft202012Validator.check_schema(new)
def validator(schema,name):return Draft202012Validator({'$ref':'#/$defs/'+name,'$defs':schema['$defs']},format_checker=Draft202012Validator.FORMAT_CHECKER)
results=[]
def compare(label,name,value,expected=None):
    answer=[cached_cases[label]['old'],validator(new,name).is_valid(value)]
    row={'case':label,'definition':name,'old':answer[0],'candidate':answer[1]}
    if expected is not None:row['expected']=expected
    results.append(row)
    assert answer[0]==answer[1],row
    if expected is not None:assert answer[0]==expected,row
    if len(results)%50==0:print('Compared',len(results),flush=True)
fixture=json.loads((ROOT/'experiments/jd-editor/fixtures/r2-canonical.json').read_text(encoding='utf-8'))
def nodes(value):
    for node in value:
        if 'type' in node:
            yield node
            yield from nodes(node['children'])
try:
    for file in ('r2-canonical.json','expected-task8-move.json','empty-mark.json'):
        value=json.loads((ROOT/'experiments/jd-editor/fixtures'/file).read_text(encoding='utf-8'))
        compare(file,'JdDocumentValue',value,True)
    for i,node in enumerate(nodes(fixture)):compare('existing element '+str(i),'JdSavedElement',node,True)
    # Each legal parent kind, plus separate section kinds; malformed descendants
    # retain all original outer containers rather than testing leaves alone.
    representatives={}
    for node in nodes(fixture):representatives.setdefault((node['type'],node.get('section_kind')),node)
    for kind,node in representatives.items():
        for label,children in [('scalar',None),('empty',[]),('text scalar',['x']),('empty object',[{}]),('unknown type',[{'type':'unknown','id':'bad','children':[{'text':'x'}]}]),('missing id',[{'type':'p','children':[{'text':'x'}]}]),('extra property',[{'type':'p','id':'bad','children':[{'text':'x'}],'score':1}]),('bad leaf mark',[{'type':'p','id':'bad','children':[{'text':'x','bold':None}]}])]:
            changed_node=deepcopy(node);changed_node['children']=children
            compare(str(kind)+' '+label,'JdSavedElement',changed_node,False)
    sample={'type':'p','id':'p','children':[{'text':'x'}]}
    for property,value in [('type','unknown'),('id',''),('score',1),('section_kind','work'),('colSizes',[1]),('source_refs',['']),('children',[{'text':'','bold':None}])]:
        mutated={**sample,property:value};compare('metadata '+property,'JdSavedElement',mutated,False)
    task=next(n for n in nodes(fixture) if n['type']=='jd_task')
    for group in ('jd_outcomes','jd_requirements'):
        missing=deepcopy(task);missing['children']=[n for n in missing['children'] if n['type']!=group];compare('missing '+group,'JdSavedElement',missing,False)
        extra=deepcopy(task);extra['children'].append(deepcopy(next(n for n in task['children'] if n['type']==group)));compare('duplicate '+group,'JdSavedElement',extra,False)
    # Standalone wrappers retain full element validation, not just shallow type.
    wrappers=[k for k in defs if k.startswith('JdSaved') and k not in {'JdSavedElement','JdSavedElementOfBodyType'}]
    for name in wrappers:
        # Find a shallow matching node with the smallest subtree first.
        eligible=sorted(list(nodes(fixture)),key=lambda n:len(json.dumps(n)))
        valid=next(n for n in eligible if validator(new,name).is_valid(n))
        compare('standalone '+name,name,valid,True)
        bad=deepcopy(valid);bad['children']=[{'text':'x','score':1}];compare('standalone malformed '+name,name,bad,False)
    timing=[]
    timing.append({**cached['timing'][0],'reused_same_sha256':True})
    for label,schema in [('candidate2',new)]:
        start=time.perf_counter();validator(schema,'JdDocumentValue').validate(fixture);timing.append({'schema':label,'seconds':time.perf_counter()-start})
    print(json.dumps({'cases':len(results),'timing':timing}),flush=True)
finally:
    (OUT/'equivalence-results.json').write_text(json.dumps({'before_sha256':hashlib.sha256(raw).hexdigest(),'candidate_sha256':hashlib.sha256(candidate).hexdigest(),'changed_references':changed,'cases':results,'timing':locals().get('timing')},ensure_ascii=False,indent=2),encoding='utf-8')
