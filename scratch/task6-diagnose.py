import json
from pathlib import Path
from analysis_agent.windows_lifecycle import bootstrap
bootstrap()
import sys
sys.path.insert(0,'tests')
from jd_offline_service import resources,text_of
from analysis_agent.service import current_values
wire=json.loads(Path('../../scratch/task6-e2e-wire.jsonl').read_text(encoding='utf8').splitlines()[-1])
notice=next(json.loads(text_of(i)) for i in wire['input'] if i.get('role')=='user' and 'app_jd_context' in json.dumps(i))
with resources() as s:
 c=s._context(notice['document'])
 v=current_values(c.graph.get_state(c.config,subgraphs=True))
 print(json.dumps([{k:b.get(k) for k in ('name','invalid','closed','base')} for b in v.get('jd_bindings',{}).values()],ensure_ascii=False))
