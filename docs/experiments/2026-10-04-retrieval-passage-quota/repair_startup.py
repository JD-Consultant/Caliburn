"""Record environment import shadowing before any new model scores."""
import time
from common import *
initial = read(HERE/'execution-development.json')
sources = dict(initial['sources'])
for name in ('common.py','gpu_worker.py'):
    sources[name] = sha(HERE/name)
sources['development-startup-failure.txt'] = sha(HERE/'development-startup-failure.txt')
sources['repair_startup.py'] = sha(Path(__file__))
dump('execution-development-02.json',{**initial,'created_utc':time.time(),'sources':sources,
    'previous_manifest_sha256':sha(HERE/'execution-development.json'),
    'repair':'Docker installed evaluate package shadowed local helper; local helper takes sys.path priority. Initial run failed on import before weights or new scores.'})
