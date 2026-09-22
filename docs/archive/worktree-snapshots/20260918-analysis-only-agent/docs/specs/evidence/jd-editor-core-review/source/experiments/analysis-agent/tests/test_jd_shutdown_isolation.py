"""One uncertain document must not prevent shutdown checks for others."""
from analysis_agent.publication import PublicationUncertain
from test_service import service_harness


def test_close_continues_after_one_manual_reconciliation_is_uncertain(tmp_path, monkeypatch):
    with service_harness(tmp_path) as (service, sent, _):
        documents = [service.create_document(title)['id'] for title in ('待確認文件', '另一份文件')]
        for document in documents:
            service._context(document)
        checked = []

        def reconcile(context):
            checked.append(context.reader.document_id)
            if context.reader.document_id == documents[0]:
                raise PublicationUncertain('Injected unavailable receipt boundary')

        monkeypatch.setattr(service, '_reconcile_manual', reconcile)
        service.jd = object()  # Only enables the real shutdown seam; no JD call is faked as successful.
        try:
            service.close()
        finally:
            service.jd = None
        assert checked == documents
        assert not service.accepting
        assert sent == []
