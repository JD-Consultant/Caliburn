import { render, screen } from '@testing-library/react';
import { expect, test } from 'vitest';
import type { CandidateJdPreview } from '../../shared/api/generated/consultant-turn';
import { JdCandidatePreview } from './JdCandidatePreview';

test('one candidate renders grouped and unassigned work with read-only related collections', () => {
  const candidate: CandidateJdPreview = {
    profile: {
      job_title: '<b>候選職稱</b>',
      organization_unit: null,
      reports_to: null,
      purpose: '職務目的',
    },
    work: {
      revision_id: '10000000-0000-4000-8000-000000000001',
      areas: [{ area_id: 'area', title: '交付職責', scope_text: '交付範圍' }],
      tasks: [
        {
          task_id: 'task',
          area_id: 'area',
          title: '頁面交付',
          description: '任務內容',
          outcomes: [{ detail_id: 'outcome', text: '可用頁面' }],
          requirements: [{ detail_id: 'requirement', text: '核對設計' }],
        },
        {
          task_id: 'unassigned',
          area_id: null,
          title: '支援任務',
          description: null,
          outcomes: [],
          requirements: [],
        },
      ],
      capabilities: [
        {
          capability_id: 'knowledge',
          kind: 'knowledge',
          name: '瀏覽器知識',
          description: '渲染流程',
        },
      ],
      task_links: [{ task_id: 'task', capability_id: 'knowledge' }],
      collaborators: [{ collaborator_id: 'collaborator', name: '設計師', scope_text: '討論規格' }],
      conditions: [{ condition_id: 'condition', kind: 'schedule_travel', text: '不固定出差' }],
    },
  };
  render(<JdCandidatePreview candidate={candidate} />);
  for (const text of [
    '<b>候選職稱</b>',
    '交付職責',
    '頁面交付',
    '可用頁面',
    '核對設計',
    '未歸屬任務',
    '支援任務',
    '渲染流程',
    '討論規格',
    '工時與出差',
    '不固定出差',
  ]) {
    expect(screen.getByText(text)).toBeVisible();
  }
  expect(screen.getAllByText('知識：瀏覽器知識')).toHaveLength(2);
  expect(screen.queryByRole('button')).not.toBeInTheDocument();
  expect(document.querySelector('b')).toBeNull();
});
