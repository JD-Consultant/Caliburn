"""Durable request artifact and closure across rebuilt PostgreSQL clients."""
import os
from uuid import uuid4

import pytest
from langchain_core.messages import HumanMessage, ToolMessage
from langgraph.checkpoint.postgres import PostgresSaver
from psycopg.conninfo import conninfo_to_dict, make_conninfo

from analysis_agent.conversation import close_turn, send_input
from test_consolidation import call, done
from test_consolidation_request import (
    InterruptAfterSavedNotice, LoseNoticeResult, notification_harness, notify,
)


@pytest.mark.parametrize('interruption', ['none', 'before_receipt', 'after_receipt'])
def test_pg_reopen_preserves_request_and_safely_closes_interrupted_notification(interruption):
    dsn = os.environ.get('Q019_TEST_DATABASE_URL')
    if not dsn:
        pytest.skip('Dedicated q019_agent_test required; notification durability NOT verified')
    params = conninfo_to_dict(dsn)
    assert params.get('dbname') == 'q019_agent_test'
    assert params.get('host') in ('localhost', '127.0.0.1')
    assert params.get('port') == '55433'
    assert 1 <= int(params.get('connect_timeout', '0')) <= 10
    dsn = make_conninfo(dsn, options='-c statement_timeout=10000 -c lock_timeout=5000')
    document = 'q019-test-' + str(uuid4())
    middleware = (LoseNoticeResult(),) if interruption == 'before_receipt' else (InterruptAfterSavedNotice(),)
    try:
        with PostgresSaver.from_conn_string(dsn) as saver:
            saver.setup()
            with notification_harness(saver, document, () if interruption == 'none' else middleware) as h:
                if interruption == 'none':
                    notify(h, 'z-input', count=2)
                else:
                    h.replies.append(call('request_memory_consolidation'))
                    with pytest.raises(RuntimeError, match='injected'):
                        send_input(h.root, h.config, HumanMessage('第一個網站案例。', id='z-input'))
                    assert h.reader.pending_consolidation_turns() == []
        # New clients and graph; no original in-process signal/flag survives.
        with PostgresSaver.from_conn_string(dsn) as saver:
            with notification_harness(saver, document) as h:
                if interruption != 'none':
                    closed = close_turn(h.root, h.config, reason='cancelled', quiescent=True)
                    receipts = [m for m in closed['messages'] if isinstance(m, ToolMessage)]
                    assert len(receipts) == 1
                    assert receipts[0].status == ('error' if interruption == 'before_receipt' else 'success')
                first = h.root.get_state(h.config).values
                assert bool(h.reader.pending_consolidation_turns()) == (interruption != 'before_receipt')
                assert not h.sent, 'Reading and safely closing must not call either model'
                cursor = h.reader.capture('z-input', first['messages'][-1].id)
                second = notify(h, 'a-input')
                expected = [{'input_id': 'a-input', 'end_id': second['messages'][-1].id}]
                assert h.reader.pending_consolidation_turns(after_reference=cursor) == expected
                latest = h.reader.capture('a-input', second['messages'][-1].id)
                assert h.reader.pending_consolidation_turns(after_reference=latest) == []
                assert [m.id for m in second['messages'] if isinstance(m, HumanMessage)] == ['z-input', 'a-input']
        with PostgresSaver.from_conn_string(dsn) as saver:
            with notification_harness(saver, document) as h:
                assert h.reader.pending_consolidation_turns(after_reference=cursor) == expected
                assert h.reader.pending_consolidation_turns(after_reference=latest) == []
                assert not h.sent
    finally:
        with PostgresSaver.from_conn_string(dsn) as saver:
            saver.delete_thread(document)
