import { EditableText } from '../editing/EditableText';
import { useJobDescriptionEditor } from '../editing/useJobDescriptionEditor';
import { catalogOperations, type CatalogKind } from './catalog-operations';
import { CreatePanel, NamedCreateForm } from './EditorForms';
import { DeleteButton } from './DeleteButton';
import { OrderControls } from './OrderControls';
import { focusTask } from './task-navigation';
import { SourceBadge } from '../sources/SourceBadge';

export function CatalogEditor({ kind }: { kind: CatalogKind }) {
  const { jobDescription: jd, blocked, editingKey, execute } = useJobDescriptionEditor();
  const operations = catalogOperations[kind];
  const { label, marker } = operations;
  const items = jd[kind];
  return (
    <div className="jd-catalog">
      <div className="jd-collection-heading">
        <h3>
          {label} {marker}
        </h3>
        <CreatePanel title={`新增${label}`} draftKey={`new:${kind}`}>
          {(close) => (
            <NamedCreateForm
              draftKey={`new:${kind}`}
              nameLabel={`${label}名稱`}
              descriptionLabel={`${label}說明（選填）`}
              submitLabel={`建立${label}`}
              disabled={blocked}
              onDone={close}
              onCreate={(name, description) =>
                execute((current) =>
                  operations.add(current.workspace_id, current.job_description_id, {
                    expected_version: current.version,
                    name,
                    description,
                  }),
                )
              }
            />
          )}
        </CreatePanel>
      </div>
      <p className="jd-editor-hint">共用定義；修改後會用於所有引用任務。</p>
      <ul className="jd-editor-list" aria-label={`${label}定義`}>
        {items.map((item) => {
          const uses = jd.tasks.filter((task) =>
            task[operations.referenceField].includes(item.id),
          );
          return (
            <li key={item.id} id={`jd-${kind}-${item.id}`}>
              <div className="jd-content-row">
                <div className="jd-content-main">
                  <EditableText
                    draftKey={`${kind}.${item.id}.name`}
                    label={`${label}名稱`}
                    hideLabel
                    value={item.name}
                    required
                    onSave={(value, current) =>
                      operations.update(
                        current.workspace_id,
                        current.job_description_id,
                        item.id,
                        { expected_version: current.version, name: value },
                      )
                    }
                  />
                </div>
                <div className="jd-item-tools">
                  <SourceBadge
                    targetKind={kind === 'knowledge' ? 'knowledge' : 'skill'}
                    targetId={item.id}
                  />
                  <OrderControls
                    id={item.id}
                    label={item.name}
                    items={items}
                    disabled={blocked || editingKey !== null}
                    onMove={(beforeId) =>
                      execute((current) =>
                        operations.move(
                          current.workspace_id,
                          current.job_description_id,
                          item.id,
                          { expected_version: current.version, before_id: beforeId },
                        ),
                      )
                    }
                  />
                  <DeleteButton
                    label={`${label}「${item.name}」`}
                    description={`刪除「${item.name}」會解除 ${String(uses.length)} 個任務的引用；任務本身會保留。`}
                    disabled={blocked || editingKey !== null}
                    onDelete={() =>
                      execute((current) =>
                        operations.remove(
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
                draftKey={`${kind}.${item.id}.description`}
                label={`${label}說明`}
                value={item.description}
                multiline
                onSave={(value, current) =>
                  operations.update(
                    current.workspace_id,
                    current.job_description_id,
                    item.id,
                    {
                      expected_version: current.version,
                      description: value === '' ? null : value,
                    },
                  )
                }
              />
              <div className="jd-catalog-uses">
                <span>{uses.length === 0 ? '尚無任務引用' : '引用任務：'}</span>
                {uses.map((task) => (
                  <a
                    href={`#jd-task-${task.id}`}
                    key={task.id}
                    onClick={() => focusTask(task.id)}
                  >
                    {task.name}
                  </a>
                ))}
              </div>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
