"""Run the installed, unchanged app with this batch's shared SDK transport fence."""

import httpx2
import uvicorn
import json
from datetime import datetime
from decimal import Decimal
from pathlib import Path

import caliburn.bootstrap as bootstrap
from caliburn.adapters.openai_responses import create_responses_client
from batch_guard import BatchGuard, GuardedTransport


resume = Path('/witness/resume-state-06.json')
renewed_window = resume.exists()
if not resume.exists():
    resume = Path('/witness/resume-state-05.json')
    renewed_window = resume.exists()
if not resume.exists():
    resume = Path('/witness/resume-state-04.json')
if not resume.exists():
    resume = Path('/witness/resume-state-03.json')
if not resume.exists():
    resume = Path('/witness/resume-state-02.json')
if not resume.exists():
    resume = Path('/witness/resume-state.json')
state = json.loads(resume.read_text(encoding='utf-8')) if resume.exists() else None
boundaries = ({'limit': Decimal(state['approved_total_limit_usd']),
               'deadline': datetime.fromisoformat(state['approved_deadline_at'])}
              if renewed_window else {})
guard = (BatchGuard.restore(state, '/witness/provider-trace.jsonl', **boundaries)
         if state is not None else BatchGuard())


def guarded_client(*, api_key, timeout_seconds):
    transport = GuardedTransport(guard, httpx2.AsyncHTTPTransport(retries=0), "/witness/provider-trace.jsonl")
    client = httpx2.AsyncClient(transport=transport, timeout=timeout_seconds,
                              follow_redirects=False, trust_env=False)
    return create_responses_client(api_key=api_key, timeout_seconds=timeout_seconds, http_client=client)


bootstrap.create_responses_client = guarded_client
uvicorn.run(bootstrap.create_app(), host="0.0.0.0", port=8100, log_level="warning")
