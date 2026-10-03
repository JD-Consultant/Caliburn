/**
 * Which JD texts can be edited in place and the one bounded change that saves each. The editor
 * components only see an `InlineField`: they know nothing about tasks, areas or wire shapes.
 */
import type {
  Area,
  Capability,
  Collaborator,
  Condition,
  Detail,
  WorkTask,
} from '../../shared/api/generated/jd-work-view';
import type { ProfileField } from '../../shared/api/generated/revise-jd-profile-request';
import type { WorkIntent } from './jd-work-api';
import { profileLabels } from './profile-command';
import type { ProfileIntent } from './profile-command';

/** One change an inline editor can ask for: to the JD's collections or to its basic data. */
export type InlineIntent = WorkIntent | ProfileIntent;

export interface InlineField {
  /** Identifies the field among all editable fields, e.g. `task:<id>:title`. */
  key: string;
  /** Names the field for its edit button and input, e.g. 任務名稱. */
  label: string;
  /** The saved text; null when not provided. */
  value: string | null;
  multiline: boolean;
  /** The one change that saves the edited text; an empty string clears an optional field. */
  intentFor: (text: string) => InlineIntent;
}

function blankToNull(text: string): string | null {
  return text === '' ? null : text;
}

function taskField(task: WorkTask, field: 'title' | 'description'): InlineField {
  return {
    key: `task:${task.task_id}:${field}`,
    label: field === 'title' ? '任務名稱' : '工作內容',
    value: task[field],
    multiline: field === 'description',
    intentFor: (text) => ({
      collection: 'tasks',
      change: {
        action: 'revise_task',
        task_id: task.task_id,
        changes: [{ action: 'set_field', field, value: blankToNull(text) }],
      },
    }),
  };
}

export const taskTitleField = (task: WorkTask): InlineField => taskField(task, 'title');
export const taskDescriptionField = (task: WorkTask): InlineField => taskField(task, 'description');

/** An outcome or requirement of a task; `label` already carries its place in the list, e.g. 工作成果 1. */
export function detailTextField(taskId: string, detail: Detail, label: string): InlineField {
  return {
    key: `detail:${detail.detail_id}`,
    label,
    value: detail.text,
    multiline: true,
    intentFor: (text) => ({
      collection: 'tasks',
      change: {
        action: 'revise_task',
        task_id: taskId,
        changes: [{ action: 'revise_detail', detail_id: detail.detail_id, text }],
      },
    }),
  };
}

/** The next outcome or requirement of a task, still empty; `label` names its place, e.g. 工作成果 2. */
export function newDetailField(
  taskId: string,
  kind: 'outcome' | 'requirement',
  label: string,
): InlineField {
  return {
    key: `new-detail:${taskId}:${kind}`,
    label,
    value: null,
    multiline: true,
    intentFor: (text) => ({
      collection: 'tasks',
      change: {
        action: 'revise_task',
        task_id: taskId,
        changes: [{ action: 'add_detail', kind, text }],
      },
    }),
  };
}

function areaField(area: Area, field: 'title' | 'scope_text'): InlineField {
  return {
    key: `area:${area.area_id}:${field}`,
    label: field === 'title' ? '職責名稱' : '職責範圍',
    value: area[field],
    multiline: field === 'scope_text',
    intentFor: (text) => ({
      collection: 'areas',
      change: {
        action: 'revise_area',
        area_id: area.area_id,
        changes: [{ field, value: blankToNull(text) }],
      },
    }),
  };
}

export const areaTitleField = (area: Area): InlineField => areaField(area, 'title');
export const areaScopeField = (area: Area): InlineField => areaField(area, 'scope_text');

function capabilityField(capability: Capability, field: 'name' | 'description'): InlineField {
  const kind = capability.kind === 'knowledge' ? '知識' : '技能';
  return {
    key: `capability:${capability.capability_id}:${field}`,
    label: `${kind}${field === 'name' ? '名稱' : '說明'}`,
    value: capability[field],
    multiline: field === 'description',
    intentFor: (text) => ({
      collection: 'capabilities',
      change: {
        action: 'revise_capability',
        capability_id: capability.capability_id,
        changes: [{ field, value: blankToNull(text) }],
      },
    }),
  };
}

export const capabilityNameField = (capability: Capability): InlineField =>
  capabilityField(capability, 'name');
export const capabilityDescriptionField = (capability: Capability): InlineField =>
  capabilityField(capability, 'description');

function collaboratorField(collaborator: Collaborator, field: 'name' | 'scope_text'): InlineField {
  return {
    key: `collaborator:${collaborator.collaborator_id}:${field}`,
    label: field === 'name' ? '協作對象名稱' : '協作範圍',
    value: collaborator[field],
    multiline: field === 'scope_text',
    intentFor: (text) => ({
      collection: 'collaborators',
      change: {
        action: 'revise_collaborator',
        collaborator_id: collaborator.collaborator_id,
        changes: [{ field, value: blankToNull(text) }],
      },
    }),
  };
}

export const collaboratorNameField = (collaborator: Collaborator): InlineField =>
  collaboratorField(collaborator, 'name');
export const collaboratorScopeField = (collaborator: Collaborator): InlineField =>
  collaboratorField(collaborator, 'scope_text');

/** A condition's text is required: only its category can be missing, and that is changed in the dialog. */
export function conditionTextField(condition: Condition): InlineField {
  return {
    key: `condition:${condition.condition_id}:text`,
    label: '條件內容',
    value: condition.text,
    multiline: true,
    intentFor: (text) => ({
      collection: 'conditions',
      change: {
        action: 'revise_condition',
        condition_id: condition.condition_id,
        changes: [{ field: 'text', value: text }],
      },
    }),
  };
}

/** A basic-data field. Emptying it clears it; the title, unit, reporting line and purpose may all be unknown. */
export function profileTextField(field: ProfileField, value: string | null): InlineField {
  return {
    key: `profile:${field}`,
    label: profileLabels[field],
    value,
    multiline: field === 'purpose',
    intentFor: (text) => ({
      collection: 'profile',
      changes: [
        text === ''
          ? { action: 'clear_field', field }
          : { action: 'set_field', field, value: text },
      ],
    }),
  };
}

/** The next responsibility, still unnamed: created with its name only; its scope is then edited in place. */
export const newAreaField: InlineField = {
  key: 'new-area',
  label: '職責名稱',
  value: null,
  multiline: false,
  intentFor: (text) => ({
    collection: 'areas',
    change: { action: 'create_area', title: text, scope_text: null },
  }),
};
