"""Derived display context only; preserve all old frozen scoring labels."""
from common import *
from audit import check_quote
rows = []
for case in read(HERE/'development-cases.json'):
    for topic in case['topics']:
        joined = check_quote(case,topic,'development')
        if joined!=topic['employee_quote']:
            rows.append({'case_id':case['case_id'],'topic_id':topic['topic_id'],
              'original_anchor_quote':topic['employee_quote'],'employee_message_indices':topic['employee_message_indices'],
              'full_context_quote':joined,'note':'Legacy v4 uses one anchor quote plus context indices; scoring labels/source original untouched.'})
assert len(rows)==3
dump('quote-compatibility.json',{'frozen_cases_sha256':sha(HERE/'development-cases.json'),'legacy_cases':rows,
      'scope':'Only known old development format; new H01 joined quote remains required.'})
