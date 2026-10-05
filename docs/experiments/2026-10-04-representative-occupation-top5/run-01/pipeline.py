"""Bounded research helpers; no product service, schema or persistence wiring."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
PARENT = HERE.parent
OLD = PARENT.parent / '2026-10-04-retrieve-rerank'
DOC_CACHE = PARENT.parent / '2026-10-04-occupation-retrieval-generalization/cache/20f95996a7ef4d574c29bed8625e84277aee1a73b8d097f5b45b5320ddb27bd8.jsonl'
COLLECTION = 'ocs_eval_9401166158b64229ad96f9286d4f1b09'
MODEL_SHA = 'd9e3e081faff1eefb84019509b2f5558fd74c1a05a2c7db22f74174fcedb5286'


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def dump(name, value):
    path = HERE / name
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.write('\n')


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        while block := stream.read(8 * 1024 * 1024):
            digest.update(block)
    return digest.hexdigest()


def text_sha(text):
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def check_manifest(name='execution-manifest.json'):
    if name == 'execution-manifest.json' and (HERE / 'execution-manifest-02.json').exists():
        name = 'execution-manifest-02.json'
    for relative, expected in read(HERE / name)['inputs'].items():
        if sha(ROOT / relative) != expected['sha256']:
            raise ValueError('frozen input changed: ' + relative)


def fuse(pools, constant=2):
    if constant <= 0:
        raise ValueError('positive fusion constant required')
    rows = {}
    for index, pool in enumerate(pools, 1):
        seen = set()
        for rank, hit in enumerate(pool):
            ident = hit['id']
            if ident in seen:
                continue
            seen.add(ident)
            contribution = 1 / (constant + rank)
            row = rows.setdefault(ident, {'id': ident, 'fusion_score': 0, 'query_contributions': []})
            row['fusion_score'] += contribution
            row['query_contributions'].append({'query': index, 'rank': rank, 'contribution': contribution})
    return sorted(rows.values(), key=lambda row: (-row['fusion_score'], row['id']))


def validate_judgment(value, employee, reference):
    required = {'grade', 'uncertain', 'main_work', 'reason', 'evidence', 'limitations'}
    if set(value) != required or type(value['uncertain']) is not bool:
        raise ValueError('judgment fields invalid')
    grade = value['grade']
    if value['uncertain'] != (grade is None):
        raise ValueError('uncertainty and numeric grade conflict')
    if grade is not None and (type(grade) is not int or grade not in range(4)):
        raise ValueError('grade outside rubric')
    if not isinstance(value['reason'], str) or not value['reason'].strip():
        raise ValueError('reason missing')
    if any(not isinstance(value[field], list) for field in ('main_work', 'evidence', 'limitations')):
        raise ValueError('judgment collections invalid')
    if grade == 3 and (not value['main_work'] or not value['evidence']):
        raise ValueError('strong representative requires main work and evidence')
    if grade == 2 and not value['evidence']:
        raise ValueError('partial representative requires evidence')
    for item in value['evidence']:
        if set(item) != {'employee_quote', 'reference_quote'}:
            raise ValueError('evidence fields invalid')
        if not item['employee_quote'] or item['employee_quote'] not in employee:
            raise ValueError('employee evidence cannot be located')
        if not item['reference_quote'] or item['reference_quote'] not in reference:
            raise ValueError('reference evidence cannot be located')
    return value
