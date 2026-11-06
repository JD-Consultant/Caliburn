/** 任務閱讀與局部收合；共用 K/S 名稱不改寫引用的正式順序。 */
import { ChevronDown } from 'lucide-react';
import { useId, useState } from 'react';
import type {
  JobDescriptionResponse,
  TaskResponse,
} from '../../shared/api/generated/types.gen';

type TaskListProps = {
  tasks: JobDescriptionResponse['tasks'];
  knowledgeNames: ReadonlyMap<string, string>;
  skillNames: ReadonlyMap<string, string>;
};

export function TaskList({ tasks, knowledgeNames, skillNames }: TaskListProps) {
  if (tasks.length === 0)
    return <p className="jd-empty jd-empty-tasks">尚未建立任務。</p>;

  return (
    <div className="jd-task-list">
      {tasks.map((task) => (
        <TaskRow
          key={task.id}
          task={task}
          knowledgeNames={knowledgeNames}
          skillNames={skillNames}
        />
      ))}
    </div>
  );
}

function TaskRow({
  task,
  knowledgeNames,
  skillNames,
}: Omit<TaskListProps, 'tasks'> & { task: TaskResponse }) {
  const [expanded, setExpanded] = useState(true);
  const id = useId();
  const titleId = `${id}-title`;
  const contentId = `${id}-content`;

  return (
    <div className="jd-task">
      <div className="jd-task-heading">
        <h4>
          <button
            id={titleId}
            type="button"
            className="jd-task-toggle"
            aria-expanded={expanded}
            aria-controls={contentId}
            onClick={() => setExpanded(!expanded)}
          >
            <ChevronDown aria-hidden="true" size={17} />
            <span>{task.name}</span>
          </button>
        </h4>
        <span className="jd-task-level">
          {task.competency_level === null
            ? '級別未填'
            : `第 ${String(task.competency_level)} 級`}
        </span>
      </div>
      <div
        id={contentId}
        role="region"
        aria-labelledby={titleId}
        hidden={!expanded}
        className="jd-task-content"
      >
        <p
          className={
            task.description !== null
              ? 'jd-task-description'
              : 'jd-task-description jd-empty'
          }
        >
          {task.description !== null ? task.description : '尚未填寫任務說明。'}
        </p>
        <div className="jd-task-text-groups">
          <TaskTextList
            title="工作成果"
            marker="O"
            items={task.outcomes}
            emptyText="尚未填寫成果。"
          />
          <TaskTextList
            title="工作要求"
            marker="P"
            items={task.requirements}
            emptyText="尚未填寫要求。"
          />
        </div>
        <div className="jd-task-references">
          <TaskReferences
            label="知識 K"
            ids={task.knowledge_ids}
            names={knowledgeNames}
          />
          <TaskReferences label="技能 S" ids={task.skill_ids} names={skillNames} />
        </div>
      </div>
    </div>
  );
}

function TaskTextList({
  title,
  marker,
  items,
  emptyText,
}: {
  title: string;
  marker: string;
  items: TaskResponse['outcomes'];
  emptyText: string;
}) {
  return (
    <div>
      <h5 className="jd-task-label">
        <span aria-hidden="true">{marker}</span>
        {title}
      </h5>
      {items.length === 0 ? (
        <p className="jd-empty">{emptyText}</p>
      ) : (
        <ol className="jd-task-text-list" aria-label={title}>
          {items.map((item) => (
            <li key={item.id}>{item.text}</li>
          ))}
        </ol>
      )}
    </div>
  );
}

function TaskReferences({
  label,
  ids,
  names,
}: {
  label: string;
  ids: readonly string[];
  names: ReadonlyMap<string, string>;
}) {
  return (
    <div className="jd-reference-row">
      <p>{label}</p>
      {ids.length === 0 ? (
        <span className="jd-empty">尚未連結</span>
      ) : (
        <ul aria-label={label} className="jd-reference-list">
          {ids.map((id) => (
            <li key={id}>{names.get(id) ?? '無法對應的項目'}</li>
          ))}
        </ul>
      )}
    </div>
  );
}
