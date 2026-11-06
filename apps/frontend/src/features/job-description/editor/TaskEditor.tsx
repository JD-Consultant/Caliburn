import { CompetencyLevelPicker } from './CompetencyLevelPicker';
import type { TaskResponse } from '../../../shared/api/generated/types.gen';
import * as api from '../content-api';
import { EditableText } from '../editing/EditableText';
import { useJobDescriptionEditor } from '../editing/useJobDescriptionEditor';
import { DeleteButton } from './DeleteButton';
import { CreatePanel, TextCreateForm } from './EditorForms';
import { OrderControls } from './OrderControls';
import { TaskReferencesEditor } from './TaskReferencesEditor';
import { TaskDestinationSelect } from './TaskDestinationSelect';
import { SourceBadge } from '../sources/SourceBadge';
import { FoldableItem } from './FoldableItem';

export function TaskEditor({ task }: { task: TaskResponse }) {
  const { jobDescription: jd, blocked, editingKey, execute } = useJobDescriptionEditor();
  const group = jd.tasks.filter((item) => item.duty_id === task.duty_id);
  return (
    <FoldableItem
      kind="task"
      name={task.name}
      id={`jd-task-${task.id}`}
      meta={
        <>
          <span className="jd-task-level">
            {task.competency_level === null
              ? '級別未填'
              : `第 ${String(task.competency_level)} 級`}
          </span>
          <SourceBadge targetKind="task" targetId={task.id} />
        </>
      }
      title={
        <EditableText
          draftKey={`tasks.${task.id}.name`}
          label="任務名稱"
          hideLabel
          className="jd-editable-title"
          value={task.name}
          required
          onSave={(value, current) =>
            api.updateTask(current.workspace_id, current.job_description_id, task.id, {
              expected_version: current.version,
              name: value,
            })
          }
        />
      }
    >
      <EditableText
        draftKey={`tasks.${task.id}.description`}
        label="任務說明"
        value={task.description}
        multiline
        onSave={(value, current) =>
          api.updateTask(current.workspace_id, current.job_description_id, task.id, {
            expected_version: current.version,
            description: value === '' ? null : value,
          })
        }
      />
      <div className="jd-task-metadata">
        <CompetencyLevelPicker
          label="任務職能級別"
          value={task.competency_level}
          disabled={blocked || editingKey !== null}
          onChange={(value) => {
            return execute((current) =>
              api.updateTask(current.workspace_id, current.job_description_id, task.id, {
                expected_version: current.version,
                competency_level: value,
              }),
            );
          }}
        />
        <div className="jd-item-tools">
          <TaskDestinationSelect task={task} />
          <OrderControls
            id={task.id}
            label={task.name}
            items={group}
            disabled={blocked || editingKey !== null}
            onMove={(beforeId) =>
              execute((current) =>
                api.moveTask(current.workspace_id, current.job_description_id, task.id, {
                  expected_version: current.version,
                  destination_duty_id: task.duty_id,
                  before_id: beforeId,
                }),
              )
            }
          />
          <DeleteButton
            label={`任務「${task.name}」`}
            description="此任務及其工作成果、工作要求將刪除。共用知識與技能定義會保留。"
            disabled={blocked || editingKey !== null}
            onDelete={() =>
              execute((current) =>
                api.deleteTask(
                  current.workspace_id,
                  current.job_description_id,
                  task.id,
                  current.version,
                ),
              )
            }
          />
        </div>
      </div>
      <div className="jd-task-text-groups">
        <TaskTextEditor task={task} kind="outcomes" />
        <TaskTextEditor task={task} kind="requirements" />
      </div>
      <div className="jd-task-references">
        <TaskReferencesEditor task={task} kind="knowledge" />
        <TaskReferencesEditor task={task} kind="skills" />
      </div>
    </FoldableItem>
  );
}

const textOperations = {
  outcomes: {
    label: '工作成果',
    marker: 'O',
    add: api.addOutcome,
    update: api.updateOutcome,
    remove: api.deleteOutcome,
    move: api.moveOutcome,
  },
  requirements: {
    label: '工作要求',
    marker: 'P',
    add: api.addRequirement,
    update: api.updateRequirement,
    remove: api.deleteRequirement,
    move: api.moveRequirement,
  },
};

function TaskTextEditor({
  task,
  kind,
}: {
  task: TaskResponse;
  kind: 'outcomes' | 'requirements';
}) {
  const { blocked, editingKey, execute } = useJobDescriptionEditor();
  const operations = textOperations[kind];
  const items = task[kind];
  return (
    <section>
      <div className="jd-collection-heading">
        <h5 className="jd-task-label">
          <span aria-hidden="true">{operations.marker}</span>
          {operations.label}
        </h5>
        <CreatePanel
          title={`新增${operations.label}`}
          draftKey={`new:${kind}:${task.id}`}
        >
          {(close) => (
            <TextCreateForm
              draftKey={`new:${kind}:${task.id}`}
              label={operations.label}
              onDone={close}
              disabled={blocked}
              onCreate={(text) =>
                execute((current) =>
                  operations.add(
                    current.workspace_id,
                    current.job_description_id,
                    task.id,
                    { expected_version: current.version, text },
                  ),
                )
              }
            />
          )}
        </CreatePanel>
      </div>
      <ol className="jd-editor-list jd-task-text-edit-list" aria-label={operations.label}>
        {items.map((item, index) => (
          <li key={item.id}>
            <span className="jd-item-number" aria-hidden="true">
              {String(index + 1).padStart(2, '0')}
            </span>
            <EditableText
              draftKey={`tasks.${task.id}.${kind}.${item.id}.text`}
              label={operations.label}
              hideLabel
              value={item.text}
              required
              multiline
              onSave={(value, current) =>
                operations.update(
                  current.workspace_id,
                  current.job_description_id,
                  task.id,
                  item.id,
                  { expected_version: current.version, text: value },
                )
              }
            />
            <div className="jd-item-tools">
              <OrderControls
                id={item.id}
                label={item.text}
                items={items}
                disabled={blocked || editingKey !== null}
                onMove={(beforeId) =>
                  execute((current) =>
                    operations.move(
                      current.workspace_id,
                      current.job_description_id,
                      task.id,
                      item.id,
                      { expected_version: current.version, before_id: beforeId },
                    ),
                  )
                }
              />
              <DeleteButton
                label={operations.label}
                description={`將刪除此筆${operations.label}：「${item.text}」。其他項目不受影響。`}
                disabled={blocked || editingKey !== null}
                onDelete={() =>
                  execute((current) =>
                    operations.remove(
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
      </ol>
    </section>
  );
}
