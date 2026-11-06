import type {
  ConditionKind,
  ConditionResponse,
} from '../../../shared/api/generated/types.gen';
import * as api from '../content-api';
import { EditableText } from '../editing/EditableText';
import { useJobDescriptionEditor } from '../editing/useJobDescriptionEditor';
import { DeleteButton } from './DeleteButton';
import { CreatePanel, NamedCreateForm, TextCreateForm } from './EditorForms';
import { OrderControls } from './OrderControls';
import { conditionLabels } from '../labels';
import { FoldableSection } from './FoldableSection';
import { SourceBadge } from '../sources/SourceBadge';

const kinds = Object.keys(conditionLabels) as ConditionKind[];

export function ConditionsEditor() {
  const { jobDescription: jd, blocked, editingKey, execute } = useJobDescriptionEditor();
  return (
    <FoldableSection
      id="jd-conditions"
      title="協作與條件"
      count={jd.collaborations.length + jd.conditions.length}
    >
      <div className="jd-condition-group">
        <div className="jd-collection-heading">
          <h3>協作對象</h3>
          <CreatePanel title="新增協作對象" draftKey="new:collaboration">
            {(close) => (
              <NamedCreateForm
                draftKey="new:collaboration"
                nameLabel="協作對象名稱"
                descriptionLabel="協作範圍（選填）"
                submitLabel="建立協作對象"
                onDone={close}
                disabled={blocked}
                onCreate={(collaborator_name, scope) =>
                  execute((current) =>
                    api.addCollaboration(
                      current.workspace_id,
                      current.job_description_id,
                      {
                        expected_version: current.version,
                        collaborator_name,
                        scope,
                      },
                    ),
                  )
                }
              />
            )}
          </CreatePanel>
        </div>
        <ul className="jd-editor-list" aria-label="協作對象">
          {jd.collaborations.map((item) => (
            <li key={item.id}>
              <div className="jd-content-row">
                <div className="jd-content-main">
                  <EditableText
                    draftKey={`collaborations.${item.id}.collaborator_name`}
                    label="協作對象名稱"
                    hideLabel
                    value={item.collaborator_name}
                    required
                    onSave={(value, current) =>
                      api.updateCollaboration(
                        current.workspace_id,
                        current.job_description_id,
                        item.id,
                        { expected_version: current.version, collaborator_name: value },
                      )
                    }
                  />
                </div>
                <div className="jd-item-tools">
                  <SourceBadge targetKind="collaboration" targetId={item.id} />
                  <OrderControls
                    id={item.id}
                    label={item.collaborator_name}
                    items={jd.collaborations}
                    disabled={blocked || editingKey !== null}
                    onMove={(beforeId) =>
                      execute((current) =>
                        api.moveCollaboration(
                          current.workspace_id,
                          current.job_description_id,
                          item.id,
                          { expected_version: current.version, before_id: beforeId },
                        ),
                      )
                    }
                  />
                  <DeleteButton
                    label={`協作對象「${item.collaborator_name}」`}
                    description="將刪除此協作對象及其範圍。"
                    disabled={blocked || editingKey !== null}
                    onDelete={() =>
                      execute((current) =>
                        api.deleteCollaboration(
                          current.workspace_id,
                          current.job_description_id,
                          item.id,
                          current.version,
                        ),
                      )
                    }
                  />
                </div>
              </div>
              <EditableText
                draftKey={`collaborations.${item.id}.scope`}
                label="協作範圍"
                value={item.scope}
                multiline
                onSave={(value, current) =>
                  api.updateCollaboration(
                    current.workspace_id,
                    current.job_description_id,
                    item.id,
                    {
                      expected_version: current.version,
                      scope: value === '' ? null : value,
                    },
                  )
                }
              />
            </li>
          ))}
        </ul>
      </div>
      {kinds.map((kind) => (
        <div className="jd-condition-group" key={kind}>
          <div className="jd-collection-heading">
            <h3>{conditionLabels[kind]}</h3>
            <CreatePanel
              title={`新增${conditionLabels[kind]}`}
              draftKey={`new:condition:${kind}`}
            >
              {(close) => (
                <TextCreateForm
                  draftKey={`new:condition:${kind}`}
                  label={conditionLabels[kind]}
                  onDone={close}
                  disabled={blocked}
                  onCreate={(text) =>
                    execute((current) =>
                      api.addCondition(current.workspace_id, current.job_description_id, {
                        expected_version: current.version,
                        kind,
                        text,
                      }),
                    )
                  }
                />
              )}
            </CreatePanel>
          </div>
          <ul className="jd-editor-list" aria-label={conditionLabels[kind]}>
            {jd.conditions
              .filter((item) => item.kind === kind)
              .map((item) => (
                <ConditionEditor key={item.id} condition={item} />
              ))}
          </ul>
        </div>
      ))}
    </FoldableSection>
  );
}

function ConditionEditor({ condition }: { condition: ConditionResponse }) {
  const { jobDescription: jd, blocked, editingKey, execute } = useJobDescriptionEditor();
  const order = jd.conditions.filter((item) => item.kind === condition.kind);
  return (
    <li>
      <div className="jd-content-row">
        <div className="jd-content-main">
          <EditableText
            draftKey={`conditions.${condition.id}.text`}
            label={conditionLabels[condition.kind]}
            hideLabel
            value={condition.text}
            multiline
            required
            onSave={(value, current) =>
              api.updateCondition(
                current.workspace_id,
                current.job_description_id,
                condition.id,
                { expected_version: current.version, text: value },
              )
            }
          />
        </div>
        <div className="jd-item-tools">
          <SourceBadge targetKind="condition" targetId={condition.id} />
          <label className="jd-condition-select">
            <span className="sr-only">條件分類</span>
            <select
              value={condition.kind}
              disabled={blocked || editingKey !== null}
              onChange={(event) => {
                const kind = kinds.find((item) => item === event.target.value);
                if (kind)
                  void execute((current) =>
                    api.reclassifyCondition(
                      current.workspace_id,
                      current.job_description_id,
                      condition.id,
                      { expected_version: current.version, kind },
                    ),
                  );
              }}
            >
              {kinds.map((kind) => (
                <option value={kind} key={kind}>
                  {conditionLabels[kind]}
                </option>
              ))}
            </select>
          </label>
          <OrderControls
            id={condition.id}
            label={condition.text}
            items={order}
            disabled={blocked || editingKey !== null}
            onMove={(beforeId) =>
              execute((current) =>
                api.moveCondition(
                  current.workspace_id,
                  current.job_description_id,
                  condition.id,
                  { expected_version: current.version, before_id: beforeId },
                ),
              )
            }
          />
          <DeleteButton
            label={conditionLabels[condition.kind]}
            description={`將刪除此條件：「${condition.text}」。`}
            disabled={blocked || editingKey !== null}
            onDelete={() =>
              execute((current) =>
                api.deleteCondition(
                  current.workspace_id,
                  current.job_description_id,
                  condition.id,
                  current.version,
                ),
              )
            }
          />
        </div>
      </div>
    </li>
  );
}
