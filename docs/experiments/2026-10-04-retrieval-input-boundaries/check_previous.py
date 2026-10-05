"""Read-only checks of earlier seals, including both historical manifest shapes."""
from support import *
results = []
for name in ('2026-10-04-occupation-retrieval','2026-10-04-occupation-retrieval-generalization',
             '2026-10-04-retrieve-rerank','2026-10-04-retrieval-passage-quota'):
    folder = HERE.parent/name
    manifest = read(folder/'artifact-hashes.json'); files = manifest.get('files',manifest)
    for filename,entry in files.items():
        expected = entry if isinstance(entry,str) else entry['sha256']
        assert sha(folder/filename)==expected,(name,filename)
        if isinstance(entry,dict):
            assert (folder/filename).stat().st_size==entry['bytes']
    results.append({'experiment':name,'sealed_files':len(files),'all_sealed_hashes_unchanged':True,
                    'manifest_sha256':sha(folder/'artifact-hashes.json')})
dump('previous-seals.json',results)
print(json.dumps(results,indent=2))
