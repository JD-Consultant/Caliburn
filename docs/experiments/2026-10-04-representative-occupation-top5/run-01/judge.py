"""Bounded direct-provider blind grading; reuse existing credentials and pricing."""
import asyncio
import random
import sys
import time
from decimal import Decimal
from datetime import datetime, timezone
from pipeline import *

sys.path.insert(0,str(ROOT / 'apps/api/src'))
from caliburn.adapters.openai_credentials import read_openai_api_key
from caliburn.adapters.openai_models import model_profile
from caliburn.adapters.openai_responses import create_responses_client


async def main(phase):
    check_manifest()
    manifest = read(HERE / 'execution-manifest.json')
    cases = {c['case_id']:c for c in read(PARENT / 'cases-v1.json')['cases']}
    corpus = {d['id']:d for d in read(HERE / 'corpus.json')}
    if phase == 'calibrate':
        jobs = [{'job_id':row['id'],'employee':row['employee'],'reference':row['reference'],
                 'expected_grade':row['expected_grade'],'main_facets':[]} for row in read(HERE / 'calibration-cases.json')]
    else:
        assert read(HERE / 'calibration-summary.json')['all_anchors_matched'] is True
        unique = sorted({(r['case_id'],d['id']) for r in read(HERE / 'results.json') for d in r['selected']})
        random.Random(20261004).shuffle(unique)
        jobs = [{'job_id':f'J{i:03d}','case_id':case,'document_id':ident,
                 'employee':cases[case]['employee_statement'],'reference':corpus[ident]['text'],
                 'main_facets':cases[case]['major_work_facets']} for i,(case,ident) in enumerate(unique,1)]
    prior_usage = []
    usage_path = HERE / 'judge-usage.jsonl'
    if usage_path.exists():
        prior_usage = [json.loads(line) for line in usage_path.read_text(encoding='utf-8').splitlines()]
    spent = sum((Decimal(row['accounted_usd']) for row in prior_usage),Decimal(0))
    assert spent < Decimal(manifest['max_cost_usd'])
    calls = len(prior_usage)
    reserved = Decimal(0)
    profile = model_profile('gpt-6-luna')
    prompt = (HERE / 'judge-prompt.txt').read_text(encoding='utf-8')
    schema = read(HERE / 'judge-schema.json')
    (HERE / 'judge-trials').mkdir(exist_ok=True)
    dump(f'judge-{phase}-jobs.json',jobs)
    client = create_responses_client(api_key=read_openai_api_key(ROOT / 'apps/api/.env'),timeout_seconds=120)
    start = time.monotonic()
    lock, semaphore = asyncio.Lock(), asyncio.Semaphore(3)
    results = []

    async def execute(job):
        nonlocal spent, reserved, calls
        async with semaphore:
            if time.monotonic()-start > 1800:
                raise TimeoutError('judge batch deadline')
            text = json.dumps({'employee_statement':job['employee'],'known_major_work_facets':job['main_facets'],
                               'reference_body':job['reference']},ensure_ascii=False)
            instructions = prompt + '\n若有提供 known_major_work_facets，main_work 使用那些主要工作面向的原名稱；沒有代表就留空。'
            payload = {'model':'gpt-6-luna','instructions':instructions,'input':[{'role':'user','content':text}],
                       'reasoning':{'effort':'high'},'text':{'format':{'type':'json_schema','name':'representative_work_v2','strict':True,'schema':schema}},
                       'tools':[],'store':False,'background':False,'stream':False,'service_tier':'default','max_output_tokens':4096}
            prefix = 'judge-trials/' + phase + '-' + job['job_id']
            dump(prefix+'-request.json',payload)
            # Never send expected_grade, source ID, title, retrieval method or rank.
            tick = time.perf_counter()
            counted = await client.responses.input_tokens.count(model=payload['model'],instructions=instructions,
                        input=payload['input'],text=payload['text'],tools=[])
            dump(prefix+'-count.json',{'response':counted.model_dump(mode='json'),'seconds':time.perf_counter()-tick})
            allowance = profile.pricing.reserve_response_cost(input_tokens=counted.input_tokens,max_output_tokens=4096)
            async with lock:
                if calls >= 107 or spent+reserved+allowance > Decimal('1.00'):
                    raise ValueError('bounded judge allowance exhausted')
                reserved += allowance; calls += 1
            tick = time.perf_counter()
            try:
                response = await client.responses.create(**payload)
            except Exception as error:
                # Unknown provider cost remains conservatively charged at its reservation.
                async with lock:
                    reserved -= allowance; spent += allowance
                    row = {'phase':phase,'job_id':job['job_id'],'accounted_usd':str(allowance),'usage_known':False,
                           'error_type':type(error).__name__,'status_code':getattr(error,'status_code',None)}
                    with usage_path.open('a',encoding='utf-8') as stream:
                        stream.write(json.dumps(row)+'\n')
                dump(prefix+'-failure.json',row)
                raise RuntimeError('provider call failed; raw request retained, no automatic retry') from None
            elapsed = time.perf_counter()-tick
            dump(prefix+'-response.json',response.model_dump(mode='json'))
            cost = profile.pricing.estimate_response_cost(response)
            accounted = cost if cost is not None else allowance
            async with lock:
                reserved -= allowance; spent += accounted
                row = {'phase':phase,'job_id':job['job_id'],'requested_model':'gpt-6-luna','resolved_model':response.model,
                       'seconds':elapsed,'usage':response.usage.model_dump(mode='json') if response.usage else None,
                       'estimated_usd':str(cost) if cost is not None else None,'accounted_usd':str(accounted),'usage_known':cost is not None,
                       'service_tier':response.service_tier,'reservation_usd':str(allowance)}
                with usage_path.open('a',encoding='utf-8') as stream:
                    stream.write(json.dumps(row)+'\n')
            if cost is None or response.status != 'completed':
                raise ValueError('provider usage unknown or response incomplete; stop judging')
            judgment = validate_judgment(json.loads(response.output_text),job['employee'],job['reference'])
            if job['main_facets'] and any(facet not in job['main_facets'] for facet in judgment['main_work']):
                raise ValueError('main facet outside fixed employee facts')
            result = {'job_id':job['job_id'],'phase':phase,'judgment':judgment,'seconds':elapsed,
                      'employee_sha256':text_sha(job['employee']),'document_sha256':text_sha(job['reference']),
                      **{key:job[key] for key in ('case_id','document_id','expected_grade') if key in job}}
            if phase == 'calibrate':
                result['anchor_matched'] = judgment['grade'] == job['expected_grade']
            dump(prefix+'-judgment.json',result)
            results.append(result)
            print(f"{phase} {job['job_id']}: {judgment['grade']} ({elapsed:.1f}s)",flush=True)

    failures = []
    try:
        # Calibration may finish its seven predeclared anchors; formal grading never starts before it passes.
        outcomes = await asyncio.gather(*(execute(job) for job in jobs),return_exceptions=True)
        failures = [{'job_id':job['job_id'],'type':type(outcome).__name__,'message':str(outcome)}
                    for job,outcome in zip(jobs,outcomes,strict=True) if isinstance(outcome,BaseException)]
    finally:
        await client.close()
    summary = {'phase':phase,'jobs':len(jobs),'completed':len(results),'failures':failures,'elapsed_seconds':time.monotonic()-start,
               'estimated_or_reserved_total_usd':str(spent),'all_anchors_matched':not failures and all(r.get('anchor_matched',True) for r in results)}
    dump('calibration-summary.json' if phase=='calibrate' else 'grading-summary.json',summary)
    dump('calibration-results.json' if phase=='calibrate' else 'judgments.json',sorted(results,key=lambda row:row['job_id']))
    print(json.dumps(summary,ensure_ascii=False),flush=True)
    if failures or not summary['all_anchors_matched']:
        raise SystemExit(2)


if __name__ == '__main__':
    asyncio.run(main(sys.argv[1]))
