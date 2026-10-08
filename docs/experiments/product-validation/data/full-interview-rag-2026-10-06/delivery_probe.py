"""Separate free delivery/edit probes from the natural model interview."""

import argparse
import asyncio
import json
from pathlib import Path
from uuid import uuid4

import httpx2

HERE = Path(__file__).resolve().parent
BASE = 'http://127.0.0.1:8106'


def load(name):
    return json.loads((HERE / name).read_text(encoding='utf-8'))


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=['replay', 'manual'])
    action = parser.parse_args().action
    path = '/api/job-files/' + load('state.json')['file_id']
    async with httpx2.AsyncClient(base_url=BASE, headers={'Origin': BASE}, timeout=120, trust_env=False) as client:
        async def get(suffix):
            response = await client.get(path + suffix)
            response.raise_for_status()
            return response.json()
        if action == 'replay':
            original = load('turn-19-accepted.json')
            response = await client.post(path + '/inputs', json=load('turn-19-input.json'))
            response.raise_for_status()
            assert response.json()['execution_id'] == original['execution_id']
            result = {'original': original, 'replayed': response.json(), 'http_status': response.status_code,
                      'same_execution': True}
        else:
            current = (await get('/consultant-turns/current'))['turn']
            if current and current['status'] in ['active', 'paused']:
                raise RuntimeError('Do not edit a live consultant candidate')
            before = await get('/jd/conditions')
            old_sources = await get('/jd/sources')
            condition = next(item for item in before['conditions'] if item['kind'] == 'work_environment')
            value = condition['text'].replace('十五', '15')
            assert value != condition['text'], 'This probe only changes numeric typography'
            command = {'command_id': str(uuid4()), 'expected_revision_id': before['revision_id'],
                       'change': {'action': 'revise_condition', 'condition_id': condition['condition_id'],
                                  'changes': [{'field': 'text', 'value': value}]}}
            response = await client.post(path + '/jd/conditions', json=command)
            response.raise_for_status()
            after = await get('/jd/conditions')
            assert after == response.json()
            new_sources = await get('/jd/sources')
            refs = [item for item in new_sources['references'] if item['target']['item_id'] == condition['condition_id']]
            assert refs and all(item['jd_changed'] and item['needs_recheck'] for item in refs)
            reads = []
            for reference in refs:
                content = await get('/jd/sources/' + reference['citation_id'] + '?revision_id=' + new_sources['revision_id'])
                diff = await get('/jd/sources/' + reference['citation_id'] + '/changes?revision_id=' + new_sources['revision_id'])
                reads.append({'reference': reference, 'content': content, 'changes': diff})
            assert await get('/jd/sources') == new_sources, 'Read must not confirm a reference'
            repeated = await client.post(path + '/jd/conditions', json=command)
            repeated.raise_for_status()
            assert repeated.json() == response.json(), 'Replay created another JD revision'
            stale = {**command, 'command_id': str(uuid4())}
            conflict = await client.post(path + '/jd/conditions', json=stale)
            assert conflict.status_code == 409
            result = {'before': before, 'sources_before': old_sources, 'command': command, 'after': after,
                      'sources_after': new_sources, 'reads': reads, 'same_command_replay': True,
                      'stale_revision_status': conflict.status_code, 'stale_revision_error': conflict.json(),
                      'scope': 'Separate manual typography probe, not employee factual correction'}
    with (HERE / (action + '-delivery-probe.json')).open('x', encoding='utf-8') as output:
        json.dump(result, output, ensure_ascii=False, indent=2)
    print(json.dumps({'action': action, 'passed': True}, ensure_ascii=False))


if __name__ == '__main__':
    asyncio.run(main())
