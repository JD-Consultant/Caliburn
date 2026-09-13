/** A presentation projection of a complete, schema-validated read page.
 * Refs stay opaque. Stable keys are local to the caller's dataset/document scope.
 * Domain validity and writable-reference authority remain on the server.
 */
import type {
  ContainerRecord,
  FieldRecord,
  ItemRecord,
  ReadPage,
  RelationRecord,
  SectionRecord,
  SourceRecord,
} from "../../../src/jd_relational/generated/jd-read.ts";

export type FieldView = FieldRecord & { key: string; itemId: string | null };
export type ItemView = ItemRecord & { fields: FieldView[] };
export interface JdView {
  revisionRef: string;
  sections: SectionRecord[];
  items: ItemView[];
  fields: FieldView[];
  containers: ContainerRecord[];
  relations: RelationRecord[];
}

export const fieldLabels = {
  job_title: "職稱",
  organization_unit: "所屬單位",
  employee_name: "姓名",
  reports_to: "直屬主管",
  purpose: "職務目的",
  name: "名稱",
  description: "說明",
  scope_text: "範圍與邊界",
  text: "內容",
} satisfies Record<FieldRecord["name"], string>;

export const kindLabels = {
  duty: "職責",
  task: "任務",
  outcome: "成果",
  requirement: "要求",
  knowledge: "知識",
  skill: "技能",
  collaborator: "協作對象",
  work_environment: "工作環境",
  schedule_travel: "工時與出差",
  shared_authority: "共同權責界線",
  shared_collaboration: "共同協作",
  qualification: "任職條件",
} satisfies Record<ItemRecord["kind"], string>;

export function fieldKey(itemId: string | null, name: FieldRecord["name"]): string {
  return JSON.stringify([itemId, name]);
}

export function containerKey(view: JdView, container: ContainerRecord): string {
  const section = view.sections.find(section => section.section_ref === container.section_ref);
  const owner = container.owner_ref === null ? null : view.items.find(item => item.item_ref === container.owner_ref);
  if (!section || (container.owner_ref !== null && !owner)) invalid();
  return JSON.stringify([section.section_key, owner?.item_id ?? null, container.child_kind]);
}

function invalid(): never {
  throw new Error("invalid_read_view");
}

function addUnique(set: Set<string>, value: string): void {
  if (set.has(value)) invalid();
  set.add(value);
}

function resolve<T>(map: Map<string, T>, ref: string): T {
  const value = map.get(ref);
  if (value === undefined) invalid();
  return value;
}

export function projectView(page: ReadPage): JdView {
  // Pagination assembly belongs to the API client; a suffix is not a full view.
  if (page.format_version !== 2 || page.start_index !== 0 || page.has_more
      || page.next_cursor !== null || page.total_records !== page.records.length) invalid();

  const sections: SectionRecord[] = [];
  const containers: ContainerRecord[] = [];
  const items: ItemView[] = [];
  const fields: FieldView[] = [];
  const relations: RelationRecord[] = [];
  const fieldRecords: FieldRecord[] = [];
  const sources: SourceRecord[] = [];
  const sectionByRef = new Map<string, SectionRecord>();
  const containerByRef = new Map<string, ContainerRecord>();
  const itemByRef = new Map<string, ItemView>();
  const fieldByRef = new Map<string, FieldView>();
  const refs = new Set<string>();
  const sectionKeys = new Set<string>();
  const itemIds = new Set<string>();
  const fieldKeys = new Set<string>();
  const relationPairs = new Set<string>();

  // Collect first: records may arrive in any order after full-page assembly.
  for (const record of page.records) {
    switch (record.type) {
      case "section": {
        addUnique(refs, record.section_ref);
        addUnique(sectionKeys, record.section_key);
        const section = { ...record };
        sections.push(section);
        sectionByRef.set(section.section_ref, section);
        break;
      }
      case "container": {
        addUnique(refs, record.container_ref);
        const container = { ...record };
        containers.push(container);
        containerByRef.set(container.container_ref, container);
        break;
      }
      case "item": {
        addUnique(refs, record.item_ref);
        addUnique(itemIds, record.item_id);
        const item: ItemView = { ...record, fields: [] };
        items.push(item);
        itemByRef.set(item.item_ref, item);
        break;
      }
      case "field":
        addUnique(refs, record.field_ref);
        fieldRecords.push(record);
        break;
      case "task_capability":
        addUnique(relationPairs, JSON.stringify([record.task_ref, record.capability_ref]));
        relations.push({ ...record });
        break;
      case "source":
        sources.push(record);
        break;
      default:
        // A revision index has no document body to render with this projection.
        invalid();
    }
  }

  for (const container of containers) {
    resolve(sectionByRef, container.section_ref);
    if (container.owner_ref !== null
        && resolve(itemByRef, container.owner_ref).section_ref !== container.section_ref) invalid();
  }
  for (const item of items) {
    resolve(sectionByRef, item.section_ref);
    const container = resolve(containerByRef, item.container_ref);
    if (container.section_ref !== item.section_ref || container.child_kind !== item.kind) invalid();
  }
  for (const record of fieldRecords) {
    resolve(sectionByRef, record.section_ref);
    const item = record.item_ref === null ? null : resolve(itemByRef, record.item_ref);
    if (item !== null && item.section_ref !== record.section_ref) invalid();
    const itemId = item?.item_id ?? null;
    const key = fieldKey(itemId, record.name);
    addUnique(fieldKeys, key);
    const field = { ...record, itemId, key };
    fields.push(field);
    fieldByRef.set(field.field_ref, field);
    item?.fields.push(field);
  }
  for (const relation of relations) {
    resolve(sectionByRef, relation.section_ref);
    const task = resolve(itemByRef, relation.task_ref);
    const capability = resolve(itemByRef, relation.capability_ref);
    if (task.section_ref !== relation.section_ref || task.kind !== "task"
        || capability.kind !== relation.capability_kind) invalid();
  }
  // Sources are displayed elsewhere, but cannot hide dangling page associations.
  // Reusing one source for multiple targets is valid and is not deduplicated.
  for (const source of sources) {
    resolve(sectionByRef, source.section_ref);
    const target = itemByRef.get(source.target_ref) ?? fieldByRef.get(source.target_ref);
    if (target === undefined || target.section_ref !== source.section_ref) invalid();
    if (source.related_capability_ref !== null) {
      resolve(itemByRef, source.related_capability_ref);
      if (!relationPairs.has(JSON.stringify([source.target_ref, source.related_capability_ref]))) invalid();
    }
  }

  return { revisionRef: page.revision_ref, sections, items, fields, containers, relations };
}
