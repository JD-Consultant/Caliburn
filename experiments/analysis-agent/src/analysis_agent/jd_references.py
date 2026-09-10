"""Finite issued-reference bindings in the existing graph checkpoint.

Strings are locators, never evidence that a read happened. No document cache,
SQL, token service, or alternate source owner lives here.
"""
from copy import deepcopy
from uuid import NAMESPACE_URL, uuid5
import json
from analysis_agent.sources import parse_reference


def elements(nodes):
    for node in nodes:
        if 'type' in node:
            yield node
            yield from elements(node.get('children', []))


def source_refs(value):
    if isinstance(value, list):
        return list(dict.fromkeys(ref for item in value for ref in source_refs(item)))
    if isinstance(value, dict):
        return list(dict.fromkeys([*value.get('source_refs', []),
            *(ref for key, item in value.items() if key != 'source_refs' for ref in source_refs(item))]))
    return []


class IssuedReferences:
    def __init__(self, scope, bindings, *, input_id=None):
        self.input_id = input_id
        self.scope = scope
        self.bindings = deepcopy(bindings)

    def issue(self, kind, *, ref=None, **record):
        record = {'kind': kind, 'document': self.scope.document_id, **record}
        ref = ref or 'jd:' + str(uuid5(NAMESPACE_URL, json.dumps(record, sort_keys=True, ensure_ascii=False)))
        if ref in self.bindings and self.bindings[ref] != record:
            raise ValueError('Issued JD reference identity collision')
        self.bindings[ref] = record
        return ref

    def require(self, ref, kind, *, writable=False):
        record = self.bindings.get(ref)
        if not record or record.get('kind') != kind:
            raise ValueError('JD reference was not issued for this use')
        if record.get('document') != self.scope.document_id:
            raise ValueError('JD reference belongs to another document')
        if writable and (record.get('access') != 'current_base' or not record.get('content_supplied')
                or (self.input_id is not None and record.get('input') != self.input_id)):
            raise ValueError('JD target requires a current content read')
        return record


def validate_sources(references, issued, reader):
    for reference in references:
        if reference not in issued:
            raise ValueError('Source reference was not issued by a saved input or original read')
        binding = issued[reference]
        ref = parse_reference(reference, reader.document_id)
        if binding.get('current_input'):
            if ref['last'] != binding['current_input']:
                raise ValueError('Current source identity mismatch')
            page = reader.read(reference)
            if not any(s['message_id'] == binding['current_input'] and s['role'] == 'user' for s in page['segments']):
                # A long preceding question may occupy page one; validate the
                # canonical message rather than pretending its preview was read.
                from langchain_core.messages import HumanMessage
                snapshot = reader._snapshot(ref['checkpoint'])
                if not any(isinstance(m, HumanMessage) and m.id == binding['current_input'] for m in snapshot.values['messages']):
                    raise ValueError('Saved employee source is unavailable')
        else:
            reader._extraction_range(reference)
            reader.read(reference)
