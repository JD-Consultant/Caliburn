from datetime import datetime, timezone
import json
from pathlib import Path
import re
import sys
import sqlalchemy as sa
sys.path.insert(0, 'S:/caliburn/experiments/jd-relational-app/src')
from jd_relational.storage import schema as db
from jd_relational.storage.rows import read_domain
from jd_relational.snapshots import snapshot_from_domain, snapshot_digest

target = Path(sys.argv[1]).resolve()
assert target.parent == Path('S:/caliburn/.research-tmp')
assert re.fullmatch(r'jd-ui-gate-[0-9a-f]{32}', target.name)
stage = sys.argv[2]
assert stage in {'catalog', 'held', 'recovered', 'dialog'}
config = json.loads((target/'fixture.json').read_text())
database = 'caliburn_jd_setup_test_' + target.name.removeprefix('jd-ui-gate-')
assert config['database'] == database and config['port'] == 55436
url = sa.URL.create('postgresql+psycopg', username='jd_test', password='jd-local-test-only', host='127.0.0.1', port=55436, database=database)
engine = sa.create_engine(url, connect_args={'connect_timeout': 5})
report = dict(stage=stage, checked_at_utc=datetime.now(timezone.utc).isoformat(), database=database,
              port=55436, mode='REPEATABLE READ / READ ONLY', provider_calls=0, database_writes=0)
with engine.connect().execution_options(isolation_level='REPEATABLE READ') as connection:
    with connection.begin():
        connection.exec_driver_sql('SET TRANSACTION READ ONLY')
        assert connection.exec_driver_sql('SELECT current_database(),current_user').one() == (database, 'jd_test')
        documents = connection.execute(sa.select(db.jd_document)).mappings().all()
        assert len(documents) == 1
        document = documents[0]['id']
        assert documents[0]['title'] == '保存回覆遺失驗收'
        assert documents[0]['archived'] is False and documents[0]['metadata_version'] == 1
        report.update(archived=False, metadata_version=1, catalog_unchanged=True)
        head = connection.execute(sa.select(db.jd_head).where(db.jd_head.c.document_id == document)).mappings().one()
        revisions = connection.execute(sa.select(db.jd_revision).where(db.jd_revision.c.document_id == document).order_by(db.jd_revision.c.revision_number)).mappings().all()
        operations = connection.execute(sa.select(db.jd_operation).where(db.jd_operation.c.document_id == document)).mappings().all()
        current = read_domain(connection, document, str(head['current_revision_id']))
        snapshot = snapshot_from_domain(current)
        assert snapshot == revisions[-1]['snapshot']
        assert snapshot_digest(snapshot) == revisions[-1]['content_digest']
        report.update(document_id=document, head_revision_id=str(head['current_revision_id']),
            revision_number=head['revision_number'], revision_count=len(revisions), operation_count=len(operations),
            tasks=list(current['tasks']), task_count=len(current['tasks']), content_digest=snapshot_digest(snapshot),
            operation_ids=[str(x['operation_id']) for x in operations], current_equals_head_snapshot=True)
        if stage == 'catalog':
            assert head['revision_number'] == 1 and not operations and not current['tasks']
        else:
            gate = json.loads((target/'gate.committed.json').read_text())
            assert head['revision_number'] == 2 and len(revisions) == 2 and len(operations) == 1 and len(current['tasks']) == 1
            assert str(operations[0]['operation_id']) == gate['operation_id']
            assert str(head['current_revision_id']) == gate['result_revision_id']
            assert operations[0]['status'] == 'committed'
            task = next(iter(current['tasks'].values()))
            assert task['name'] == '定期檢查'
            assert task['description'] == '僅檢查服務合約內系統，發現異常時記錄並通知負責人。'
            report['original_operation_matches_committed_gate'] = True
            if stage == 'held':
                held = json.loads((target/'gate.held.json').read_text())
                assert held['response_start_forwarded'] is False
                assert not (target/'gate.finished.json').exists()
                assert not (target/'gate.release.request').exists()
                report['verified_committed_before_response_forwarded'] = True
            else:
                previous = json.loads((target/'db-held.json').read_text())
                for key in ('document_id','head_revision_id','revision_number','revision_count','operation_count','tasks','content_digest','operation_ids'):
                    assert report[key] == previous[key], key
                observed = json.loads((target/'writer.observations.json').read_text())
                assert observed['operations'] == report['operation_ids']
                report['unchanged_after_browser_recovery'] = True
engine.dispose()
(target/f'db-{stage}.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps(report, ensure_ascii=False))
