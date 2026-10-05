"""Pre-ranking review correction: source history is not this round's split."""
import time
from support import *
cases = read(HERE/'cases.json')
for case in cases:
    case['source_split'] = case['split']
    case['split'] = 'observed_regression'
dump('cases-observed.json',cases)
dump('input-amendment-01.json',{'created_utc':time.time(),'before_new_embeddings_or_rankings':True,
    'initial_cases_sha256':sha(HERE/'cases.json'),'effective_cases':'cases-observed.json',
    'effective_cases_sha256':sha(HERE/'cases-observed.json'),'script_sha256':sha(Path(__file__)),
    'scope':'All22 now observed_regression; historical source_split preserved. Employee messages/topics/grades untouched; original retained.'})
