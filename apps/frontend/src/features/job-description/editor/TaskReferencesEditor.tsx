import { IconAction } from '../../../shared/ui/IconAction';
import { CloseIcon } from '../../../shared/ui/icons';
import { useRef, useState } from 'react';
import type { TaskResponse } from '../../../shared/api/generated/types.gen';
import { useJobDescriptionEditor } from '../editing/useJobDescriptionEditor';
import { catalogOperations, type CatalogKind } from './catalog-operations';
import { CreatePanel, EditorForm, NamedCreateForm } from './EditorForms';
import { OrderControls } from './OrderControls';
import { navigateJdLink } from './jd-navigation';

export function TaskReferencesEditor({
  task,
  kind,
}: {
  task: TaskResponse;
  kind: CatalogKind;
}) {
  const { jobDescription: jd, blocked, editingKey, execute } = useJobDescriptionEditor();
  const operations = catalogOperations[kind];
  const ids = task[operations.referenceField];
  const names = new Map(jd[kind].map((item) => [item.id, item.name]));
  const order = ids.map((id) => ({ id, label: names.get(id) ?? '找不到共用定義' }));
  return (
    <section
      className="jd-reference-editor"
      aria-label={`${task.name}的${operations.label}`}
    >
      <div className="jd-collection-heading jd-reference-heading">
        <h5>
          {operations.label} {operations.marker}
        </h5>
        <CreatePanel
          title={`引用既有${operations.label}`}
          triggerLabel="引用既有"
          draftKey={`link:${kind}:${task.id}`}
        >
          {(close) => <LinkDefinitionForm task={task} kind={kind} onDone={close} />}
        </CreatePanel>
        <CreatePanel
          title={`建立並引用新${operations.label}`}
          triggerLabel="建立並引用"
          draftKey={`new:${kind}-link:${task.id}`}
        >
          {(close) => <CreateAndLinkDefinition task={task} kind={kind} onDone={close} />}
        </CreatePanel>
      </div>
      <ul className="jd-editor-list jd-reference-edit-list">
        {order.map((item) => (
          <li key={item.id}>
            <a href={`#jd-${kind}-${item.id}`} onClick={navigateJdLink}>
              {item.label}
            </a>
            <div className="jd-item-tools">
              <OrderControls
                id={item.id}
                label={item.label}
                items={order}
                disabled={blocked || editingKey !== null}
                onMove={(beforeId) =>
                  execute((current) =>
                    operations.moveReference(
                      current.workspace_id,
                      current.job_description_id,
                      task.id,
                      item.id,
                      { expected_version: current.version, before_id: beforeId },
                    ),
                  )
                }
              />
              <UnlinkReferenceButton
                disabled={blocked || editingKey !== null}
                label={`解除${operations.label}「${item.label}」的引用`}
                onUnlink={() =>
                  execute((current) =>
                    operations.unlink(
                      current.workspace_id,
                      current.job_description_id,
                      task.id,
                      item.id,
                      current.version,
                    ),
                  )
                }
              />
            </div>
          </li>
        ))}
      </ul>
    </section>
  );
}

function UnlinkReferenceButton({
  label,
  disabled,
  onUnlink,
}: {
  label: string;
  disabled: boolean;
  onUnlink: () => Promise<boolean>;
}) {
  const pendingRef = useRef(false);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState(false);
  async function unlink() {
    if (pendingRef.current || disabled) return;
    pendingRef.current = true;
    setPending(true);
    try {
      await onUnlink();
    } catch {
      setError(true);
    } finally {
      pendingRef.current = false;
      setPending(false);
    }
  }
  return (
    <>
      <IconAction
        label={label}
        disabled={disabled || pending}
        onClick={() => {
          void unlink();
        }}
      >
        <CloseIcon />
      </IconAction>
      {error && <span role="alert">無法解除引用，請先核對目前內容。</span>}
    </>
  );
}

function LinkDefinitionForm({
  task,
  kind,
  onDone,
}: {
  task: TaskResponse;
  kind: CatalogKind;
  onDone: () => void;
}) {
  const { jobDescription: jd, blocked, execute } = useJobDescriptionEditor();
  const operations = catalogOperations[kind];
  const candidates = jd[kind].filter(
    (item) => !task[operations.referenceField].includes(item.id),
  );
  const [selected, setSelected] = useState('');
  return (
    <EditorForm
      submitLabel={`引用${operations.label}`}
      cancelLabel="取消"
      onDone={onDone}
      disabled={blocked || !candidates.some((item) => item.id === selected)}
      onSubmit={() =>
        execute((current) =>
          operations.link(
            current.workspace_id,
            current.job_description_id,
            task.id,
            selected,
            { expected_version: current.version },
          ),
        )
      }
    >
      <label className="jd-form-field">
        選取{operations.label}
        <select
          value={selected}
          onChange={(event) => setSelected(event.target.value)}
          required
        >
          <option value="">{candidates.length ? '請選擇' : '沒有可引用的項目'}</option>
          {candidates.map((item) => (
            <option key={item.id} value={item.id}>
              {item.name}
            </option>
          ))}
        </select>
      </label>
    </EditorForm>
  );
}

function CreateAndLinkDefinition({
  task,
  kind,
  onDone,
}: {
  task: TaskResponse;
  kind: CatalogKind;
  onDone: () => void;
}) {
  const { blocked, execute } = useJobDescriptionEditor();
  const operations = catalogOperations[kind];
  return (
    <NamedCreateForm
      nameLabel={`${operations.label}名稱`}
      descriptionLabel={`${operations.label}說明（選填）`}
      submitLabel={`建立並引用${operations.label}`}
      draftKey={`new:${kind}-link:${task.id}`}
      onDone={onDone}
      disabled={blocked}
      onCreate={(name, description) =>
        execute((current) =>
          operations.createAndLink(
            current.workspace_id,
            current.job_description_id,
            task.id,
            { expected_version: current.version, name, description },
          ),
        )
      }
    />
  );
}
