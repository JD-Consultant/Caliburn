import { render, screen, within } from '@testing-library/react';
import { expect, it } from 'vitest';
import type { JobDescriptionDifferenceResponse } from '../../../shared/api/generated/types.gen';
import { jobDescription } from '../../../../tests/fixtures';
import { JobDescriptionDifference } from './JobDescriptionDifference';
import { citation } from '../sources/source-fixtures';

const before = {
  ...jobDescription,
  duties: [{ id: 'duty-1', name: '客戶服務', scope: null }],
  knowledge: [{ id: 'knowledge-1', name: '服務流程', description: null }],
  tasks: [
    {
      id: 'task-1',
      duty_id: 'duty-1',
      name: '回覆詢問',
      description: null,
      competency_level: null,
      outcomes: [{ id: 'outcome-1', text: '完整的回覆紀錄' }],
      requirements: [],
      knowledge_ids: ['knowledge-1'],
      skill_ids: [],
    },
  ],
};
const after = {
  ...before,
  job_title: '客服專員',
  knowledge: [
    ...before.knowledge,
    { id: 'knowledge-2', name: '個資保護', description: '依法處理客戶資料' },
  ],
  tasks: before.tasks.map((task) => ({
    ...task,
    duty_id: null,
    outcomes: [],
    knowledge_ids: ['knowledge-2', 'knowledge-1'],
  })),
};
const difference: JobDescriptionDifferenceResponse = {
  job_description_id: jobDescription.job_description_id,
  before_version: 1,
  after_version: 3,
  items: [
    {
      kind: 'job_description',
      id: jobDescription.job_description_id,
      change: 'modified',
      fields: [{ field: 'job_title', before: null, after: '客服專員' }],
    },
    {
      kind: 'task',
      id: 'task-1',
      change: 'modified',
      fields: [{ field: 'duty_id', before: 'duty-1', after: null }],
    },
    {
      kind: 'outcome',
      id: 'outcome-1',
      change: 'removed',
      fields: [{ field: 'text', before: '完整的回覆紀錄', after: null }],
    },
    {
      kind: 'knowledge',
      id: 'knowledge-2',
      change: 'added',
      fields: [
        { field: 'name', before: null, after: '個資保護' },
        { field: 'description', before: null, after: '依法處理客戶資料' },
      ],
    },
  ],
  collections: [
    {
      collection: 'knowledge_ids',
      owner_id: 'task-1',
      group: null,
      before_ids: ['knowledge-1'],
      after_ids: ['knowledge-2', 'knowledge-1'],
    },
  ],
};

it('將欄位、所屬職責、刪除的成果與引用順序顯示為業務名稱', () => {
  const { container } = render(
    <JobDescriptionDifference difference={difference} before={before} after={after} />,
  );
  expect(screen.getByText('職務名稱')).toBeVisible();
  expect(screen.getByText('所屬職責')).toBeVisible();
  expect(screen.getByText('客戶服務')).toBeVisible();
  expect(screen.getByText('未分類任務')).toBeVisible();
  expect(screen.getByRole('heading', { name: '工作成果 · 回覆詢問' })).toBeVisible();
  expect(screen.getByText('刪除')).toBeVisible();
  expect(screen.getByText('新增')).toBeVisible();
  expect(screen.getByText('依法處理客戶資料')).toBeVisible();
  const references = screen.getByRole('region', { name: '知識引用 · 回覆詢問' });
  expect(within(references).getByText('項目與順序變化')).toBeVisible();
  expect(within(references).getAllByRole('list')[1]?.textContent).toBe(
    '個資保護服務流程',
  );
  expect(container.textContent).not.toContain('knowledge-1');
  expect(container.textContent).not.toContain('duty_id');
});

it('後端淨差異為零時明示沒有內容差異', () => {
  render(
    <JobDescriptionDifference
      difference={{ ...difference, items: [], collections: [] }}
      before={before}
      after={before}
    />,
  );
  expect(screen.getByText('這兩個版本沒有內容差異。')).toBeVisible();
});

it('引用差異使用領域名稱與核對狀態，移除引用仍保留歷史來源入口', () => {
  const historical = { ...before, citations: [citation] };
  const { container } = render(
    <JobDescriptionDifference
      before={historical}
      after={before}
      difference={{
        ...difference,
        collections: [],
        items: [
          {
            kind: 'citation',
            id: citation.id,
            change: 'removed',
            fields: [
              { field: 'target_kind', before: 'job_description', after: null },
              {
                field: 'target_id',
                before: jobDescription.job_description_id,
                after: null,
              },
              { field: 'source_kind', before: 'memory', after: null },
              {
                field: 'item_id',
                before:
                  citation.source.kind === 'memory' ? citation.source.item_id : null,
                after: null,
              },
              { field: 'published_version', before: 3, after: null },
              { field: 'jd_changed', before: 1, after: null },
            ],
          },
        ],
      }}
    />,
  );
  expect(
    screen.getByRole('heading', { name: '來源引用 · 基本資料 · Memory 發布版 3' }),
  ).toBeVisible();
  expect(screen.getByText('待核對')).toBeVisible();
  expect(screen.getByRole('region', { name: '比較前版本 1 的來源' })).toBeVisible();
  expect(container.textContent).not.toContain(citation.id);
  expect(container.textContent).not.toContain(
    citation.source.kind === 'memory' ? citation.source.item_id : 'missing',
  );
});
