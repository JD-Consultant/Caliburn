"""Seal completed evidence, then independently reread every sealed file."""
from datetime import datetime,timezone
from pipeline import *

def main():
    assert read(HERE/'final-audit-02.json')['passed']
    assert (HERE/'review.md').is_file()
    files={}
    for path in sorted(HERE.rglob('*')):
        if not path.is_file() or '__pycache__' in path.parts or path.name=='artifact-hashes.json':continue
        files[str(path.relative_to(HERE)).replace('\\','/') ]={'sha256':sha(path),'bytes':path.stat().st_size}
    dump('artifact-hashes.json',{'created_utc':datetime.now(timezone.utc).isoformat(),'files':files,
                              'excluded':['artifact-hashes.json','__pycache__']})
    for name,record in read(HERE/'artifact-hashes.json')['files'].items():
        assert (HERE/name).stat().st_size==record['bytes'] and sha(HERE/name)==record['sha256'],name
    print(f'{len(files)} artifacts sealed and reread; no prior files replaced',flush=True)

if __name__=='__main__':main()
