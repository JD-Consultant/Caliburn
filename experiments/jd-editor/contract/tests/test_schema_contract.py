import importlib
import json
from pathlib import Path
import pytest
from jsonschema import Draft202012Validator
ROOT = Path(__file__).resolve().parents[1]
PUBLIC = 'JdReadModelInput JdEditModelInput JdChangeReadModelInput JdReadRuntimeRequest JdEditRuntimeRequest JdChangeReadRuntimeRequest JdReadResult JdEditResult JdChangeReadResult JdManualSaveClientInput JdManualSaveRequest JdManualSaveResult JdPlateTransformRequest JdPlateTransformResult JdResolvedEditCommand JdPlateValidateValueRequest JdPlateValidateValueResult JdPlateReadSelectionRequest JdPlateReadSelectionResult JdDocumentValue JdActualChanges JdWriteResult'.split()
def test_generated_python_bytes_survive_lf_git_checkout():
    value = (ROOT / 'src/jd_editor_contract/models.py').read_bytes()
    assert b'\r' not in value, 'Generated Python must match the LF checkout used by check-codegen.'

def test_generated_public_imports():
    models = importlib.import_module('jd_editor_contract.models')
    for name in PUBLIC:
        assert getattr(models, name)
def test_schema_fixture_and_negative():
    schema = json.loads((ROOT / 'generated/jd-editor-v2.schema.json').read_text(encoding='utf-8'))
    validator = Draft202012Validator({'$ref':'#/$defs/JdDocumentValue', '$defs':schema['$defs']})
    value = json.loads((ROOT.parent / 'fixtures/r2-canonical.json').read_text(encoding='utf-8'))
    validator.validate(value)
    value[0]['children'][0]['score'] = 1
    assert list(validator.iter_errors(value))

def test_original_schema_enforces_write_result_conditions():
    schema = json.loads((ROOT / 'generated/jd-editor-v2.schema.json').read_text(encoding='utf-8'))
    validator = Draft202012Validator({'$ref':'#/$defs/JdWriteResult', '$defs':schema['$defs']})
    value = dict(status='busy', operation_ref=None, base_revision_ref=None, result_revision_ref=None,
                 change_ref=None, document_effect='unchanged', receipt_durability='unconfirmed',
                 actual_changes=None, error={'code':'busy','message':'Writer is active.','command_index':None}, next_action='wait')
    validator.validate(value)
    value['next_action'] = 'continue'
    assert list(validator.iter_errors(value))
    value.update(status='outcome_unknown', operation_ref='issued:operation', document_effect='unknown', next_action='reconcile_operation')
    validator.validate(value)
    value['result_revision_ref']='must-not-publish'
    assert list(validator.iter_errors(value))

@pytest.mark.parametrize('name', PUBLIC)
def test_each_public_definition_is_present(name):
    schema = json.loads((ROOT / 'generated/jd-editor-v2.schema.json').read_text(encoding='utf-8'))
    assert name in schema['$defs']
    Draft202012Validator.check_schema({'$ref':f'#/$defs/{name}', '$defs':schema['$defs']})

def test_full_fixture_through_generated_dto_preserves_representation():
    models = importlib.import_module('jd_editor_contract.models')
    value = json.loads((ROOT.parent / 'fixtures/r2-canonical.json').read_text(encoding='utf-8'))
    dto = models.JdPlateValidateValueRequest.model_validate({'profile':{'format_version':2,'engine_profile':'jd-plate-clean-v2'},'value':value})
    assert dto.model_dump(mode='json', exclude_unset=True)['value'] == value
