"""Recompute observed execution/usage/graph facts; no model or database calls."""

import argparse
import json
from collections import Counter
from decimal import Decimal
from pathlib import Path

from caliburn.adapters.openai_pricing import GPT_6_LUNA_STANDARD_2026_09_30 as PRICING

HERE = Path(__file__).resolve().parent


def load(path):
    return json.loads(path.read_text(encoding='utf-8'))


def observed_cost(usage):
    tokens = usage['input_tokens']
    rates = PRICING.long_context if tokens > 272000 else PRICING.short_context
    details = usage.get('input_tokens_details') or {}
    cached, writes = details.get('cached_tokens'), details.get('cache_write_tokens')
    if type(cached) is int and type(writes) is int and 0 <= cached + writes <= tokens:
        cost = ((tokens - cached - writes) * rates.input_usd_per_million
                + cached * rates.cached_input_usd_per_million
                + writes * rates.cache_write_usd_per_million)
    else:
        cost = tokens * rates.cache_write_usd_per_million
    return (cost + usage['output_tokens'] * rates.output_usd_per_million) / 1000000


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', required=True)
    parser.add_argument('--database', required=True)
    args = parser.parse_args()
    rows = [json.loads(line) for line in (HERE / 'provider-trace.jsonl').read_text(encoding='utf-8').splitlines()]
    occupied, spent = Decimal(0), Decimal(0)
    outstanding, tools, totals = {}, Counter(), Counter()
    for row in rows:
        if row['event'] == 'admitted':
            new_occupied = Decimal(row['occupied_usd'])
            outstanding[row['attempt']] = new_occupied - occupied
            occupied = new_occupied
        elif row['event'] == 'received':
            usage = row['usage']
            if usage:
                spent += observed_cost(usage)
                outstanding.pop(row['attempt'])
                totals.update({key: usage[key] for key in ['input_tokens', 'output_tokens', 'total_tokens']})
                totals['cached_tokens'] += usage['input_tokens_details'].get('cached_tokens', 0)
                totals['reasoning_tokens'] += usage.get('output_tokens_details', {}).get('reasoning_tokens', 0)
            occupied = Decimal(row['occupied_usd'])
            tools.update(item['name'] for item in row.get('output', []) if item['type'] == 'function_call')
        elif row['event'] == 'rate_limited':
            occupied = Decimal(row['occupied_usd'])
    assert occupied == spent + sum(outstanding.values(), Decimal(0)), 'accounting mismatch'
    turns = [{"file": path.name, "status": result['status']['status'],
              "execution_id": result['status']['execution_id'],
              "elapsed_seconds": result['elapsed_seconds'],
              "last_consultant_text": result['interviews']['messages'][-1]['interview_text']}
             for path in sorted(HERE.glob('turn-*-result.json')) for result in [load(path)]]
    db = load(HERE / args.database)
    graph = []
    revisions = {row['revision_id']: row for row in db['memory_object_revisions']}
    formal = {row['source_id']: row['interview_sequence'] for row in db['formal_interviews']}
    for snapshot in db['memory_snapshots']:
        members = [row for row in db['memory_position_members'] if row['position_id'] == snapshot['position_id']]
        selected = {row['object_id']: row['revision_id'] for row in members}
        selected_revisions = set(selected.values())
        issues = []
        if len(members) != len(selected):
            issues.append('duplicate object identity in snapshot')
        if any(revision not in revisions for revision in selected_revisions):
            issues.append('missing selected revision')
        links = [row for row in db['memory_situation_references'] if row['revision_id'] in selected_revisions]
        for link in links:
            if selected.get(link['source_object_id']) != link['source_revision_id']:
                issues.append({'inconsistent_situation_reference': link})
        interview_links = [row for row in db['memory_interview_references'] if row['revision_id'] in selected_revisions]
        for link in interview_links:
            sequence = formal.get(link['source_id'])
            if sequence is None or sequence > snapshot['covered_through_sequence']:
                issues.append({'outside_covered_interview_reference': link})
        graph.append({'snapshot_id': snapshot['snapshot_id'], 'covered_through_sequence': snapshot['covered_through_sequence'],
                      'objects': len(members), 'situation_links': len(links), 'interview_links': len(interview_links), 'issues': issues})
    result = {'first_outbound_at': rows[0]['time'], 'last_journal_at': rows[-1]['time'],
              'fee_is_local_estimate_not_invoice': True,
              'spent_usd': str(spent), 'occupied_usd': str(occupied),
              'unsettled_reservations': {key: str(value) for key, value in outstanding.items()},
              'observed_token_totals': dict(totals), 'tools_returned_by_model': dict(tools),
              'journal_events': dict(Counter(row['event'] for row in rows)),
              'turn_counts': dict(Counter(row['status'] for row in turns)), 'turns': turns,
              'database_executions': dict(Counter((row['kind'] + ':' + row['status']) for row in db['executions'])),
              'published_memory_graph': graph}
    with (HERE / args.output).open('x', encoding='utf-8') as output:
        json.dump(result, output, ensure_ascii=False, indent=2)
    print(json.dumps({key: result[key] for key in ['spent_usd', 'occupied_usd', 'turn_counts', 'database_executions', 'published_memory_graph']}, ensure_ascii=False))


if __name__ == '__main__':
    main()
