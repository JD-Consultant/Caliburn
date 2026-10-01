from copy import deepcopy
import hashlib, json, sys
from pathlib import Path
from jsonschema import Draft202012Validator
HERE=Path(__file__).parent;ROOT=HERE.parents[2];OUT=HERE/'task4-schema-candidate2'
old=json.loads((OUT/'before.schema.json').read_text(encoding='utf-8'))
new=json.loads((OUT/'candidate.schema.json').read_text(encoding='utf-8'))
fixture=json.loads((ROOT/'experiments/jd-editor/fixtures/r2-canonical.json').read_text(encoding='utf-8'))
def nodes(values):
    for node in values:
        if 'type' in node:
            yield node
            yield from nodes(node['children'])
representatives={}
for node in nodes(fixture):representatives.setdefault((node['type'],node.get('section_kind')),node)
def valid(schema,name,value):return Draft202012Validator({'$ref':'#/$defs/'+name,'$defs':schema['$defs']}).is_valid(value)
cases=[]
def check(label,name,value,expected):
    results=[valid(s,name,value) for s in (old,new)]
    cases.append({'case':label,'definition':name,'old':results[0],'candidate':results[1],'expected':expected})
    assert results==[expected,expected],cases[-1]
try:
    for kind,node in representatives.items():
        for text in ('x',''):
            candidate=deepcopy(node);candidate['children']=[{'text':text}]
            expected=node['type'] in {'p','h1','h2','h3','lic'} or node['type']=='hr' and not text
            check(str(kind)+' pure leaf '+repr(text),'JdSavedElement',candidate,expected)
    for name,schema in new['$defs'].items():
        if name.startswith('JdSaved') and name!='JdSavedElement':
            check(name+' pure text',''+name,{'text':'x'},False)
            check(name+' unknown type',name,{'type':'unknown','id':'x','children':[{'text':'x'}]},False)
    task=deepcopy(next(n for n in nodes(fixture) if n['type']=='jd_task'))
    task['children']=[{'text':'would otherwise satisfy common children'},*[n for n in task['children'] if n['type'] in {'jd_outcomes','jd_requirements'}]]
    check('task body slot cannot be plain text','JdSavedElement',task,False)
    listitem=deepcopy(next(n for n in nodes(fixture) if n['type']=='li'))
    listitem['children'][0]={'text':'not lic'};check('list prefix lic cannot be plain text','JdSavedElement',listitem,False)
    for field in ('type','id','children'):
        bad={'type':'p','id':'p','children':[{'text':'x'}]};del bad[field];check('required '+field,'JdSavedElement',bad,False)
    bad=deepcopy(fixture);bad[0]['children'][0]['score']=1;check('existing forbidden score fixture','JdDocumentValue',bad,False)
    # Same actual generated DTO import, and exact clean-value round-trip.
    sys.path.insert(0,str(OUT/'src'))
    from jd_editor_contract import models
    assert Path(models.__file__).is_relative_to(OUT)
    dump=models.JdPlateValidateValueRequest.model_validate({'profile':{'format_version':2,'engine_profile':'jd-plate-clean-v2'},'value':fixture}).model_dump(mode='json',exclude_unset=True)
    assert dump['value']==fixture
    generated={'module':models.__file__,'r2_roundtrip_exact':True}
finally:
    (OUT/'supplement-results.json').write_text(json.dumps({'cases':cases,'generated':locals().get('generated')},ensure_ascii=False,indent=2),encoding='utf-8')
print(len(cases),'supplemental cases passed; generated r2 roundtrip exact')
