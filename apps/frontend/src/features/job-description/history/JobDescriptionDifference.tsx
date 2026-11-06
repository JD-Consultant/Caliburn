import { useId } from 'react';
import { Box, Chip } from '@mui/material';
import { conditionLabels } from '../labels';
import { JobDescriptionSourcesProvider } from '../sources/JobDescriptionSourcesProvider';
import { JobDescriptionSources } from '../sources/JobDescriptionSources';
import { citationTargetLabel } from '../sources/source-labels';
import type {
  CollectionDifferenceResponse,
  CollectionKind,
  FieldDifferenceResponse,
  ItemDifferenceResponse,
  ItemKind,
  JobDescriptionContentResponse,
  JobDescriptionDifferenceResponse,
} from '../../../shared/api/generated/types.gen';

const itemLabels: Record<ItemKind, string> = {
  job_description: '基本資料',
  duty: '職責',
  task: '任務',
  outcome: '工作成果',
  requirement: '工作要求',
  knowledge: '知識',
  skill: '技能',
  collaboration: '協作對象',
  condition: '共通條件',
  citation: '來源引用',
};
const collectionLabels: Record<CollectionKind, string> = {
  duties: '職責',
  tasks: '任務',
  knowledge: '知識',
  skills: '技能',
  collaborations: '協作對象',
  conditions: '共通條件',
  outcomes: '工作成果',
  requirements: '工作要求',
  knowledge_ids: '知識引用',
  skill_ids: '技能引用',
  citations: '來源引用',
};
const fieldLabels: Record<string, string> = {
  job_title: '職務名稱',
  organization_unit: '組織單位',
  reports_to: '直屬主管',
  purpose: '職務目的',
  baseline_competency_level: '基準職能級別',
  name: '名稱',
  scope: '範圍',
  description: '說明',
  duty_id: '所屬職責',
  competency_level: '職能級別',
  text: '內容',
  collaborator_name: '協作對象名稱',
  kind: '條件分類',
  workspace_id: '所屬工作區',
  target_kind: '引用目標類型',
  target_id: '引用目標',
  source_kind: '來源類型',
  message_id: '訪談來源',
  item_id: 'Memory 項目',
  published_version: '來源發布版本',
  jd_changed: 'JD 內容待核對',
};
const changeLabels = { added: '新增', removed: '刪除', modified: '修改' } as const;

function conditionName(value: string) {
  return (
    Object.entries(conditionLabels).find(([kind]) => kind === value)?.[1] ?? '共通條件'
  );
}

function contentNames(content: JobDescriptionContentResponse) {
  const names = new Map<string, string>([
    [content.job_description_id, content.job_title ?? '職務說明書'],
    ...content.duties.map((item): [string, string] => [item.id, item.name]),
    ...content.tasks.map((item): [string, string] => [item.id, item.name]),
    ...content.knowledge.map((item): [string, string] => [item.id, item.name]),
    ...content.skills.map((item): [string, string] => [item.id, item.name]),
    ...content.collaborations.map((item): [string, string] => [
      item.id,
      item.collaborator_name,
    ]),
    ...content.conditions.map((item): [string, string] => [item.id, item.text]),
  ]);
  for (const task of content.tasks) {
    for (const item of [...task.outcomes, ...task.requirements])
      names.set(item.id, item.text);
  }
  for (const citation of content.citations ?? [])
    names.set(
      citation.id,
      `${citationTargetLabel(citation, content)} · ${citation.source.kind === 'interview' ? '訪談原文' : `Memory 發布版 ${String(citation.source.published_version)}`}`,
    );
  return names;
}

function itemTitle(
  item: ItemDifferenceResponse,
  content: JobDescriptionContentResponse,
  names: Map<string, string>,
) {
  if (item.kind === 'job_description') return '基本資料';
  if (item.kind === 'outcome' || item.kind === 'requirement') {
    const task = content.tasks.find((task) =>
      [...task.outcomes, ...task.requirements].some((entry) => entry.id === item.id),
    );
    return `${itemLabels[item.kind]} · ${task?.name ?? '所屬任務'}`;
  }
  if (item.kind === 'condition') {
    const condition = content.conditions.find((entry) => entry.id === item.id);
    return `${itemLabels[item.kind]} · ${condition ? conditionLabels[condition.kind] : '條件內容'}`;
  }
  return `${itemLabels[item.kind]} · ${names.get(item.id) ?? '未命名項目'}`;
}

function fieldValue(
  field: string,
  value: FieldDifferenceResponse['before'],
  names: Map<string, string>,
): string {
  if (field === 'duty_id')
    return value === null ? '未分類任務' : (names.get(String(value)) ?? '所屬職責');
  if (value === null) return '未填寫';
  if (field === 'target_id') return names.get(String(value)) ?? '引用目標';
  if (field === 'target_kind')
    return Object.entries(itemLabels).find(([kind]) => kind === value)?.[1] ?? '引用目標';
  if (field === 'source_kind') return value === 'interview' ? '訪談' : 'Memory';
  if (field === 'message_id') return '固定訪談原文';
  if (field === 'item_id') return '固定 Memory 項目';
  if (field === 'published_version') return `發布版 ${String(value)}`;
  if (field === 'jd_changed') return value === 1 ? '待核對' : '未標示待核對';
  if (field === 'kind') return conditionName(String(value));
  if (field === 'workspace_id') return '本工作區';
  if (field === 'competency_level' || field === 'baseline_competency_level')
    return `第 ${String(value)} 級`;
  return String(value);
}

function collectionTitle(
  collection: CollectionDifferenceResponse,
  names: Map<string, string>,
) {
  const label = collectionLabels[collection.collection];
  if (collection.collection === 'tasks')
    return `${label} · ${collection.group === null ? '未分類任務' : (names.get(collection.group) ?? '所屬職責')}`;
  if (collection.collection === 'conditions')
    return `${label} · ${conditionName(collection.group ?? '')}`;
  if (
    ['outcomes', 'requirements', 'knowledge_ids', 'skill_ids'].includes(
      collection.collection,
    )
  )
    return `${label} · ${names.get(collection.owner_id) ?? '所屬任務'}`;
  return label;
}

export function JobDescriptionDifference({
  difference,
  before,
  after,
}: {
  difference: JobDescriptionDifferenceResponse;
  before: JobDescriptionContentResponse;
  after: JobDescriptionContentResponse;
}) {
  const id = useId();
  const beforeNames = contentNames(before);
  const afterNames = contentNames(after);
  const allNames = new Map([...beforeNames, ...afterNames]);
  if (difference.items.length === 0 && difference.collections.length === 0) {
    return (
      <>
        <p className="history-no-difference" role="status">
          這兩個版本沒有內容差異。
        </p>
        <ComparisonSources
          before={before}
          after={after}
          beforeVersion={difference.before_version}
          afterVersion={difference.after_version}
        />
      </>
    );
  }
  return (
    <div className="history-difference">
      <p className="history-comparison-summary">
        版本 {difference.before_version} → 版本 {difference.after_version}
      </p>
      {difference.items.map((item, index) => (
        <section
          className="history-change"
          key={`${item.kind}-${item.id}`}
          aria-labelledby={`${id}-item-${String(index)}`}
        >
          <div className="history-change-heading">
            <Chip
              size="small"
              label={changeLabels[item.change]}
              className={`history-change-kind history-change-${item.change}`}
            />
            <h3 id={`${id}-item-${String(index)}`}>
              {itemTitle(
                item,
                item.change === 'removed' ? before : after,
                item.change === 'removed' ? beforeNames : afterNames,
              )}
            </h3>
          </div>
          {item.fields.map((field) => (
            <div className="history-field-change" key={field.field}>
              <h4>{fieldLabels[field.field] ?? '其他欄位'}</h4>
              <div className="history-value-pair">
                <div>
                  <span className="history-value-label">
                    版本 {difference.before_version}
                  </span>
                  <p>
                    {item.change === 'added'
                      ? '尚未建立'
                      : fieldValue(field.field, field.before, beforeNames)}
                  </p>
                </div>
                <div>
                  <span className="history-value-label">
                    版本 {difference.after_version}
                  </span>
                  <p>
                    {item.change === 'removed'
                      ? '已刪除'
                      : fieldValue(field.field, field.after, afterNames)}
                  </p>
                </div>
              </div>
            </div>
          ))}
        </section>
      ))}
      {difference.collections.map((collection, index) => (
        <section
          className="history-change"
          key={`${collection.collection}-${collection.owner_id}-${collection.group ?? ''}`}
          aria-labelledby={`${id}-collection-${String(index)}`}
        >
          <div className="history-change-heading">
            <h3 id={`${id}-collection-${String(index)}`}>
              {collectionTitle(collection, allNames)}
            </h3>
          </div>
          <p className="history-value-label">項目與順序變化</p>
          <div className="history-value-pair">
            <div>
              <span className="history-value-label">
                版本 {difference.before_version}
              </span>
              <NameList ids={collection.before_ids} names={beforeNames} />
            </div>
            <div>
              <span className="history-value-label">版本 {difference.after_version}</span>
              <NameList ids={collection.after_ids} names={afterNames} />
            </div>
          </div>
        </section>
      ))}
      <ComparisonSources
        before={before}
        after={after}
        beforeVersion={difference.before_version}
        afterVersion={difference.after_version}
      />
    </div>
  );
}

function ComparisonSources({
  before,
  after,
  beforeVersion,
  afterVersion,
}: {
  before: JobDescriptionContentResponse;
  after: JobDescriptionContentResponse;
  beforeVersion: number;
  afterVersion: number;
}) {
  return (
    <Box sx={{ display: 'flex', gap: 2, flexWrap: 'wrap', my: 1 }}>
      {(
        [
          { content: before, version: beforeVersion, label: '比較前' },
          { content: after, version: afterVersion, label: '比較後' },
        ] as const
      ).map(
        ({ content, version, label }) =>
          (content.citations?.length ?? 0) > 0 && (
            <Box
              component="section"
              key={label}
              aria-label={`${label}版本 ${String(version)} 的來源`}
            >
              <span>
                {label}版本 {version}{' '}
              </span>
              <JobDescriptionSourcesProvider jobDescription={content} version={version}>
                <JobDescriptionSources />
              </JobDescriptionSourcesProvider>
            </Box>
          ),
      )}
    </Box>
  );
}

function NameList({ ids, names }: { ids: string[]; names: Map<string, string> }) {
  return ids.length === 0 ? (
    <p className="jd-empty">沒有項目</p>
  ) : (
    <ol>
      {ids.map((id) => (
        <li key={id}>{names.get(id) ?? '未命名項目'}</li>
      ))}
    </ol>
  );
}
