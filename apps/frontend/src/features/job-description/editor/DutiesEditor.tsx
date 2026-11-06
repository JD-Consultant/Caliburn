import type { DutyResponse } from '../../../shared/api/generated/types.gen';
import { addDuty, addTask, deleteDuty, moveDuty, updateDuty } from '../content-api';
import { EditableText } from '../editing/EditableText';
import { useJobDescriptionEditor } from '../editing/useJobDescriptionEditor';
import { CreatePanel, NamedCreateForm } from './EditorForms';
import { DeleteButton } from './DeleteButton';
import { OrderControls } from './OrderControls';
import { TaskCreateForm } from './TaskCreateForm';
import { TaskEditor } from './TaskEditor';
import { FoldableSection } from './FoldableSection';
import { FoldableItem } from './FoldableItem';
import { SourceBadge } from '../sources/SourceBadge';

export function DutiesEditor() {
  const { jobDescription: jd, blocked, execute } = useJobDescriptionEditor();
  return (
    <FoldableSection id="jd-duties" title="職責與任務" count={jd.duties.length}>
      <div className="jd-collection-heading">
        <p className="jd-section-count">
          {jd.duties.length} 項職責 · {jd.tasks.length} 項任務
        </p>
        <CreatePanel title="新增職責" draftKey="new:duty">
          {(close) => (
            <NamedCreateForm
              draftKey="new:duty"
              nameLabel="職責名稱"
              descriptionLabel="職責範圍（選填）"
              submitLabel="建立職責"
              disabled={blocked}
              onDone={close}
              onCreate={(name, scope) =>
                execute((current) =>
                  addDuty(current.workspace_id, current.job_description_id, {
                    expected_version: current.version,
                    name,
                    scope,
                  }),
                )
              }
            />
          )}
        </CreatePanel>
      </div>
      {jd.duties.map((duty) => (
        <DutyEditor key={duty.id} duty={duty} />
      ))}

      <FoldableItem id="jd-unclassified" kind="duty" name="未分類任務" title="未分類任務">
        <TaskGroup dutyId={null} />
      </FoldableItem>
    </FoldableSection>
  );
}

function DutyEditor({ duty }: { duty: DutyResponse }) {
  const { jobDescription: jd, blocked, editingKey, execute } = useJobDescriptionEditor();
  const count = jd.tasks.filter((task) => task.duty_id === duty.id).length;
  return (
    <FoldableItem
      id={`jd-duty-${duty.id}`}
      kind="duty"
      name={duty.name}
      title={
        <EditableText
          draftKey={`duties.${duty.id}.name`}
          label="職責名稱"
          hideLabel
          className="jd-editable-title"
          value={duty.name}
          required
          onSave={(value, current) =>
            updateDuty(current.workspace_id, current.job_description_id, duty.id, {
              expected_version: current.version,
              name: value,
            })
          }
        />
      }
      meta={
        <>
          <span className="jd-section-count">{count} 項任務</span>
          <SourceBadge targetKind="duty" targetId={duty.id} />
        </>
      }
    >
      <div className="jd-item-tools">
        <OrderControls
          id={duty.id}
          label={duty.name}
          items={jd.duties}
          disabled={blocked || editingKey !== null}
          onMove={(beforeId) =>
            execute((current) =>
              moveDuty(current.workspace_id, current.job_description_id, duty.id, {
                expected_version: current.version,
                before_id: beforeId,
              }),
            )
          }
        />
        <DeleteButton
          label={`職責「${duty.name}」`}
          description={`刪除職責後，所屬 ${String(count)} 項任務會移到未分類；任務與內容會保留。`}
          disabled={blocked || editingKey !== null}
          onDelete={() =>
            execute((current) =>
              deleteDuty(
                current.workspace_id,
                current.job_description_id,
                duty.id,
                current.version,
              ),
            )
          }
        />
      </div>
      <EditableText
        draftKey={`duties.${duty.id}.scope`}
        label="職責範圍"
        value={duty.scope}
        multiline
        onSave={(value, current) =>
          updateDuty(current.workspace_id, current.job_description_id, duty.id, {
            expected_version: current.version,
            scope: value === '' ? null : value,
          })
        }
      />
      <TaskGroup dutyId={duty.id} />
    </FoldableItem>
  );
}

function TaskGroup({ dutyId }: { dutyId: string | null }) {
  const { jobDescription: jd, blocked, execute } = useJobDescriptionEditor();
  const tasks = jd.tasks.filter((task) => task.duty_id === dutyId);
  return (
    <div className="jd-task-list">
      <div className="jd-collection-heading jd-task-group-heading">
        <span className="jd-section-count">任務 · {tasks.length}</span>
        <CreatePanel title="新增任務" draftKey={`new:task:${dutyId ?? 'unclassified'}`}>
          {(close) => (
            <TaskCreateForm
              jobDescription={jd}
              dutyId={dutyId}
              disabled={blocked}
              onDone={close}
              onCreate={(body) =>
                execute((current) =>
                  addTask(current.workspace_id, current.job_description_id, {
                    ...body,
                    expected_version: current.version,
                  }),
                )
              }
            />
          )}
        </CreatePanel>
      </div>
      {tasks.map((task) => (
        <TaskEditor key={task.id} task={task} />
      ))}
      {tasks.length === 0 && <p className="jd-empty jd-empty-tasks">尚未建立任務。</p>}
    </div>
  );
}
