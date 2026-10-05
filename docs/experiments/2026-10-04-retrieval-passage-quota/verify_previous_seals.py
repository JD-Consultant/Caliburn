"""Read-only check of earlier sealed artifacts; excluded status receipts are mutable."""
from common import *
rows = []
for name in ('2026-10-04-occupation-retrieval','2026-10-04-occupation-retrieval-generalization','2026-10-04-retrieve-rerank'):
    path = HERE.parent/name
    manifest = read(path/'artifact-hashes.json')
    files = manifest.get('files',manifest)
    for filename,entry in files.items():
        assert sha(path/filename)==entry['sha256'],(name,filename)
        assert (path/filename).stat().st_size==entry['bytes']
    rows.append({'experiment':name,'sealed_files':len(files),'all_sealed_hashes_unchanged':True,
                 'manifest_sha256':sha(path/'artifact-hashes.json')})
dump('previous-seals-check.json',rows)
print(json.dumps(rows,indent=2))
