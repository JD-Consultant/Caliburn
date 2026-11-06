import { CompetencyLevelPicker } from './CompetencyLevelPicker';
import type {
  AddTaskRequest,
  JobDescriptionResponse,
  NewDefinitionRequest,
} from '../../../shared/api/generated/types.gen';
import { EditorForm, FormField } from './EditorForms';
import { isRecord, useCreationDraft } from './useCreationDraft';

export type TaskCreateFormProps = {
  jobDescription: JobDescriptionResponse;
  dutyId: string | null;
  disabled?: boolean;
  onCreate: (body: Omit<AddTaskRequest, 'expected_version'>) => Promise<boolean>;
  onDone: () => void;
};

export function TaskCreateForm({
  jobDescription,
  dutyId,
  disabled,
  onCreate,
  onDone,
}: TaskCreateFormProps) {
  const draft = useCreationDraft<TaskDraft>(
    `new:task:${dutyId ?? 'unclassified'}`,
    '新增任務',
    {
      name: '',
      description: '',
      level: null,
      outcomes: [],
      requirements: [],
      knowledgeIds: [],
      skillIds: [],
      knowledge: [],
      skills: [],
    },
    isTaskDraft,
  );
  const {
    name,
    description,
    level,
    outcomes,
    requirements,
    knowledgeIds,
    skillIds,
    knowledge,
    skills,
  } = draft.value;
  const incomplete =
    !name ||
    [...outcomes, ...requirements].some((item) => !item.text) ||
    [...knowledge, ...skills].some((item) => !item.name);
  return (
    <EditorForm
      submitLabel="建立任務"
      onDone={() => {
        draft.discard();
        onDone();
      }}
      disabled={disabled || incomplete}
      onSubmit={() =>
        onCreate({
          name: name,
          description: description === '' ? null : description,
          duty_id: dutyId,
          competency_level: level,
          outcomes: outcomes.map((item) => item.text),
          requirements: requirements.map((item) => item.text),
          knowledge: [
            ...knowledgeIds.map((id) => ({ kind: 'existing' as const, id })),
            ...knowledge.map(definitionBody),
          ],
          skills: [
            ...skillIds.map((id) => ({ kind: 'existing' as const, id })),
            ...skills.map(definitionBody),
          ],
        })
      }
    >
      <FormField
        label="任務名稱"
        value={name}
        onChange={(value) => draft.setValue({ ...draft.value, name: value })}
        required
      />
      <FormField
        label="任務說明（選填）"
        value={description}
        onChange={(value) => draft.setValue({ ...draft.value, description: value })}
        multiline
      />
      <CompetencyLevelPicker
        label="任務職能級別"
        value={level}
        onChange={(value) => draft.setValue({ ...draft.value, level: value })}
      />
      <details className="jd-progressive-form">
        <summary>一併加入成果、要求與知識技能</summary>
        <DraftTextList
          label="工作成果"
          items={outcomes}
          onChange={(value) => draft.setValue({ ...draft.value, outcomes: value })}
        />
        <DraftTextList
          label="工作要求"
          items={requirements}
          onChange={(value) => draft.setValue({ ...draft.value, requirements: value })}
        />
        <DraftDefinitions
          label="知識"
          existing={jobDescription.knowledge}
          selected={knowledgeIds}
          onSelect={(value) => draft.setValue({ ...draft.value, knowledgeIds: value })}
          items={knowledge}
          onChange={(value) => draft.setValue({ ...draft.value, knowledge: value })}
        />
        <DraftDefinitions
          label="技能"
          existing={jobDescription.skills}
          selected={skillIds}
          onSelect={(value) => draft.setValue({ ...draft.value, skillIds: value })}
          items={skills}
          onChange={(value) => draft.setValue({ ...draft.value, skills: value })}
        />
      </details>
    </EditorForm>
  );
}

type TextDraft = { key: string; text: string };
type DefinitionDraft = NewDefinitionRequest & { key: string };
type TaskDraft = {
  name: string;
  description: string;
  level: number | null;
  outcomes: TextDraft[];
  requirements: TextDraft[];
  knowledgeIds: string[];
  skillIds: string[];
  knowledge: DefinitionDraft[];
  skills: DefinitionDraft[];
};

function isTextDraft(value: unknown): value is TextDraft {
  return (
    isRecord(value) && typeof value.key === 'string' && typeof value.text === 'string'
  );
}
function isDefinitionDraft(value: unknown): value is DefinitionDraft {
  return (
    isRecord(value) &&
    typeof value.key === 'string' &&
    value.kind === 'new' &&
    typeof value.name === 'string' &&
    (value.description === null || typeof value.description === 'string')
  );
}
function isTaskDraft(value: unknown): value is TaskDraft {
  return (
    isRecord(value) &&
    typeof value.name === 'string' &&
    typeof value.description === 'string' &&
    (value.level === null ||
      (typeof value.level === 'number' &&
        Number.isInteger(value.level) &&
        value.level >= 1 &&
        value.level <= 6)) &&
    Array.isArray(value.outcomes) &&
    value.outcomes.every(isTextDraft) &&
    Array.isArray(value.requirements) &&
    value.requirements.every(isTextDraft) &&
    Array.isArray(value.knowledgeIds) &&
    value.knowledgeIds.every((id: unknown) => typeof id === 'string') &&
    Array.isArray(value.skillIds) &&
    value.skillIds.every((id: unknown) => typeof id === 'string') &&
    Array.isArray(value.knowledge) &&
    value.knowledge.every(isDefinitionDraft) &&
    Array.isArray(value.skills) &&
    value.skills.every(isDefinitionDraft)
  );
}

function definitionBody(item: DefinitionDraft): NewDefinitionRequest {
  return {
    kind: 'new',
    name: item.name,
    description: item.description === '' ? null : (item.description ?? null),
  };
}

function DraftTextList({
  label,
  items,
  onChange,
}: {
  label: string;
  items: TextDraft[];
  onChange: (items: TextDraft[]) => void;
}) {
  return (
    <div className="jd-draft-group">
      <h5>{label}</h5>
      {items.map((item, index) => (
        <div className="jd-draft-row" key={item.key}>
          <FormField
            label={`${label} ${String(index + 1)}`}
            value={item.text}
            required
            multiline
            onChange={(text) =>
              onChange(
                items.map((row) => (row.key === item.key ? { ...row, text } : row)),
              )
            }
          />
          <button
            type="button"
            className="text-button"
            aria-label={`移除${label} ${String(index + 1)}`}
            onClick={() => onChange(items.filter((row) => row.key !== item.key))}
          >
            移除
          </button>
        </div>
      ))}
      <button
        type="button"
        className="text-button"
        onClick={() => onChange([...items, { key: crypto.randomUUID(), text: '' }])}
      >
        加入{label}
      </button>
    </div>
  );
}

function DraftDefinitions({
  label,
  existing,
  selected,
  onSelect,
  items,
  onChange,
}: {
  label: string;
  existing: JobDescriptionResponse['knowledge'];
  selected: string[];
  onSelect: (ids: string[]) => void;
  items: DefinitionDraft[];
  onChange: (items: DefinitionDraft[]) => void;
}) {
  return (
    <div className="jd-draft-group">
      <h5>{label}</h5>
      {existing.length > 0 && (
        <fieldset className="jd-definition-picker">
          <legend>引用既有{label}</legend>
          {existing.map((item) => (
            <label key={item.id}>
              <input
                type="checkbox"
                checked={selected.includes(item.id)}
                onChange={(event) =>
                  onSelect(
                    event.target.checked
                      ? [...selected, item.id]
                      : selected.filter((id) => id !== item.id),
                  )
                }
              />
              {item.name}
            </label>
          ))}
        </fieldset>
      )}
      {items.map((item, index) => (
        <div className="jd-draft-definition" key={item.key}>
          <FormField
            label={`新${label}名稱 ${String(index + 1)}`}
            value={item.name}
            required
            onChange={(name) =>
              onChange(
                items.map((row) => (row.key === item.key ? { ...row, name } : row)),
              )
            }
          />
          <FormField
            label={`新${label}說明 ${String(index + 1)}（選填）`}
            value={item.description ?? ''}
            multiline
            onChange={(description) =>
              onChange(
                items.map((row) =>
                  row.key === item.key ? { ...row, description } : row,
                ),
              )
            }
          />
          <button
            type="button"
            className="text-button"
            aria-label={`移除新${label} ${String(index + 1)}`}
            onClick={() => onChange(items.filter((row) => row.key !== item.key))}
          >
            移除
          </button>
        </div>
      ))}
      <button
        type="button"
        className="text-button"
        onClick={() =>
          onChange([
            ...items,
            { key: crypto.randomUUID(), kind: 'new', name: '', description: '' },
          ])
        }
      >
        加入新{label}
      </button>
    </div>
  );
}
