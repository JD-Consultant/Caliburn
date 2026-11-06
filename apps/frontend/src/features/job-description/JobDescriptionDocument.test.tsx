import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it } from 'vitest';
import type { JobDescriptionResponse } from '../../shared/api/generated/types.gen';
import { JobDescriptionDocument } from './JobDescriptionDocument';

it('歷史預覽導覽不命中同頁隱藏的目前 JD', async () => {
  render(
    <>
      <div hidden>
        <h2 id="jd-basic" tabIndex={-1}>
          隱藏目前稿
        </h2>
      </div>
      <JobDescriptionDocument jobDescription={jobDescription} idPrefix="history-jd-7" />
    </>,
  );
  const link = screen.getByRole('link', { name: '基本資料' });
  expect(link).toHaveAttribute('href', '#history-jd-7-basic');
  await userEvent.setup().click(link);
  expect(screen.getByRole('heading', { name: '基本資料' })).toHaveFocus();
});

const jobDescription: JobDescriptionResponse = {
  job_description_id: '10000000-0000-4000-8000-000000000001',
  workspace_id: '10000000-0000-4000-8000-000000000002',
  version: 7,
  job_title: '產品設計師',
  organization_unit: '產品設計部',
  reports_to: '設計主管',
  purpose: '釐清使用需求，讓產品容易理解與操作。',
  baseline_competency_level: 4,
  duties: [
    { id: 'duty-b', name: '驗證使用體驗', scope: '在發布前確認操作流程。' },
    { id: 'duty-a', name: '整理設計規範', scope: null },
  ],
  tasks: [
    {
      id: 'task-b',
      duty_id: 'duty-b',
      name: '規劃核心操作流程',
      description: '依據需求製作原型，與團隊確認。',
      competency_level: 5,
      outcomes: [
        { id: 'outcome-b', text: '主要情境與例外狀況的流程圖。' },
        { id: 'outcome-a', text: '可供團隊驗證的互動原型。' },
      ],
      requirements: [{ id: 'requirement-a', text: '涵蓋空白、錯誤與完成狀態。' }],
      knowledge_ids: ['knowledge-b', 'knowledge-a'],
      skill_ids: ['skill-a'],
    },
    {
      id: 'task-a',
      duty_id: 'duty-b',
      name: '執行使用測試',
      description: null,
      competency_level: null,
      outcomes: [],
      requirements: [],
      knowledge_ids: [],
      skill_ids: [],
    },
    {
      id: 'task-unclassified',
      duty_id: null,
      name: '追蹤上線回饋',
      description: '確認上線後遇到的問題。',
      competency_level: null,
      outcomes: [],
      requirements: [],
      knowledge_ids: [],
      skill_ids: [],
    },
  ],
  knowledge: [
    { id: 'knowledge-a', name: '互動設計原則', description: '理解介面操作與回饋。' },
    { id: 'knowledge-b', name: '使用者研究方法', description: '理解訪談與測試方法。' },
  ],
  skills: [
    { id: 'skill-a', name: '互動原型製作', description: '製作能驗證流程的原型。' },
  ],
  collaborations: [
    { id: 'collaboration-b', collaborator_name: '前端工程師', scope: '確認實作限制。' },
    { id: 'collaboration-a', collaborator_name: '產品經理', scope: null },
  ],
  conditions: [
    { id: 'condition-a', kind: 'work_environment', text: '主要於辦公室工作。' },
    { id: 'condition-b', kind: 'schedule_travel', text: '每季至客戶現場訪談。' },
    {
      id: 'condition-c',
      kind: 'shared_authority',
      text: '可提出設計建議，發布由主管核定。',
    },
    { id: 'condition-d', kind: 'shared_collaboration', text: '與研究團隊共享訪談結果。' },
    { id: 'condition-e', kind: 'qualification', text: '需具備產品設計相關實務經驗。' },
  ],
};

describe('JobDescriptionDocument', () => {
  it('完整呈現四章、任務內容與各自有序的共用知識技能引用', () => {
    render(<JobDescriptionDocument jobDescription={jobDescription} />);

    expect(screen.getByRole('heading', { level: 1, name: '產品設計師' })).toBeVisible();
    expect(
      screen.getAllByRole('heading', { level: 2 }).map((heading) => heading.textContent),
    ).toEqual(['基本資料', '職責與任務', '知識與技能', '協作與條件']);
    const basic = within(screen.getByRole('region', { name: '基本資料' }));
    expect(basic.getByText('產品設計部')).toBeVisible();
    expect(basic.getByText('設計主管')).toBeVisible();
    expect(basic.getByText('釐清使用需求，讓產品容易理解與操作。')).toBeVisible();
    expect(basic.getByText('第 4 級')).toBeVisible();

    const duties = within(screen.getByRole('region', { name: '職責與任務' }));
    expect(
      duties.getAllByRole('heading', { level: 3 }).map((heading) => heading.textContent),
    ).toEqual(['驗證使用體驗', '整理設計規範', '未分類任務']);
    expect(
      duties.getAllByRole('heading', { level: 4 }).map((heading) => heading.textContent),
    ).toEqual(['規劃核心操作流程', '執行使用測試', '追蹤上線回饋']);
    expect(duties.getByText('在發布前確認操作流程。')).toBeVisible();
    const task = within(screen.getByRole('region', { name: '規劃核心操作流程' }));
    expect(task.getByText('依據需求製作原型，與團隊確認。')).toBeVisible();
    expect(duties.getByText('第 5 級')).toBeVisible();
    expect(
      within(task.getByRole('list', { name: '工作成果' }))
        .getAllByRole('listitem')
        .map((item) => item.textContent),
    ).toEqual(['主要情境與例外狀況的流程圖。', '可供團隊驗證的互動原型。']);
    expect(
      within(task.getByRole('list', { name: '工作要求' }))
        .getAllByRole('listitem')
        .map((item) => item.textContent),
    ).toEqual(['涵蓋空白、錯誤與完成狀態。']);
    expect(task.getAllByRole('listitem').map((item) => item.textContent)).toEqual([
      '主要情境與例外狀況的流程圖。',
      '可供團隊驗證的互動原型。',
      '涵蓋空白、錯誤與完成狀態。',
      '使用者研究方法',
      '互動設計原則',
      '互動原型製作',
    ]);
    const catalog = within(screen.getByRole('region', { name: '知識與技能' }));
    expect(
      catalog.getAllByRole('heading', { level: 4 }).map((heading) => heading.textContent),
    ).toEqual(['互動設計原則', '使用者研究方法', '互動原型製作']);
    expect(catalog.getByText('理解介面操作與回饋。')).toBeVisible();
    expect(catalog.getByText('製作能驗證流程的原型。')).toBeVisible();

    const conditions = within(screen.getByRole('region', { name: '協作與條件' }));
    expect(conditions.getByText('前端工程師')).toBeVisible();
    expect(conditions.getByText('確認實作限制。')).toBeVisible();
    expect(conditions.getByText('產品經理')).toBeVisible();
    expect(
      within(conditions.getByRole('list', { name: '共通條件' }))
        .getAllByRole('listitem')
        .map((item) => item.textContent),
    ).toEqual([
      '工作環境主要於辦公室工作。',
      '工時與出差每季至客戶現場訪談。',
      '共通權限可提出設計建議，發布由主管核定。',
      '共通協作與研究團隊共享訪談結果。',
      '資格條件需具備產品設計相關實務經驗。',
    ]);
  });

  it('任務預設可讀，鍵盤收合與展開後恢復完整內容且保留焦點', async () => {
    const user = userEvent.setup();
    render(<JobDescriptionDocument jobDescription={jobDescription} />);
    const toggle = screen.getByRole('button', { name: '規劃核心操作流程' });
    const content = screen.getByRole('region', { name: '規劃核心操作流程' });

    expect(toggle).toHaveAttribute('aria-expanded', 'true');
    expect(content).toBeVisible();
    toggle.focus();
    await user.keyboard('{Enter}');
    expect(toggle).toHaveAttribute('aria-expanded', 'false');
    expect(content).not.toBeVisible();
    expect(toggle).toHaveFocus();
    await user.keyboard(' ');
    expect(toggle).toHaveAttribute('aria-expanded', 'true');
    expect(content).toBeVisible();
    expect(within(content).getByText('可供團隊驗證的互動原型。')).toBeVisible();
    expect(toggle).toHaveFocus();
  });

  it.each([
    { name: '驗證使用體驗', taskName: '規劃核心操作流程' },
    { name: '未分類任務', taskName: '追蹤上線回饋' },
  ])('$name 預設展開，鍵盤可收起底下任務且保留標題與焦點', async ({ name, taskName }) => {
    const user = userEvent.setup();
    render(<JobDescriptionDocument jobDescription={jobDescription} />);
    const toggle = screen.getByRole('button', { name });
    const tasks = screen.getByRole('region', { name });
    const taskToggle = within(tasks).getByRole('button', { name: taskName });

    expect(toggle).toHaveAttribute('aria-expanded', 'true');
    expect(toggle).toHaveAttribute('aria-controls', tasks.id);
    expect(tasks).toHaveAttribute('aria-labelledby', toggle.id);
    expect(taskToggle).toBeVisible();
    toggle.focus();
    await user.keyboard('{Enter}');
    expect(toggle).toHaveAttribute('aria-expanded', 'false');
    expect(tasks).not.toBeVisible();
    expect(taskToggle).not.toBeVisible();
    expect(screen.queryByRole('button', { name: taskName })).not.toBeInTheDocument();
    expect(screen.getByRole('heading', { level: 3, name })).toBeVisible();
    expect(screen.getByText('在發布前確認操作流程。')).toBeVisible();
    expect(toggle).toHaveFocus();

    await user.keyboard(' ');
    expect(toggle).toHaveAttribute('aria-expanded', 'true');
    expect(tasks).toBeVisible();
    expect(taskToggle).toBeVisible();
    expect(toggle).toHaveFocus();
  });

  it('重開職責保留各任務自己的收合狀態，其他職責不受影響', async () => {
    const user = userEvent.setup();
    render(<JobDescriptionDocument jobDescription={jobDescription} />);
    const dutyToggle = screen.getByRole('button', { name: '驗證使用體驗' });
    const taskToggle = screen.getByRole('button', { name: '規劃核心操作流程' });

    await user.click(taskToggle);
    await user.click(dutyToggle);
    expect(screen.getByRole('button', { name: '未分類任務' })).toHaveAttribute(
      'aria-expanded',
      'true',
    );
    expect(screen.getByRole('button', { name: '追蹤上線回饋' })).toBeVisible();
    expect(screen.getByRole('button', { name: '整理設計規範' })).toHaveAttribute(
      'aria-expanded',
      'true',
    );

    await user.click(dutyToggle);
    expect(screen.getByRole('button', { name: '規劃核心操作流程' })).toHaveAttribute(
      'aria-expanded',
      'false',
    );
    expect(screen.getByText('依據需求製作原型，與團隊確認。')).not.toBeVisible();
    expect(screen.getByRole('button', { name: '執行使用測試' })).toHaveAttribute(
      'aria-expanded',
      'true',
    );
    expect(screen.getByRole('region', { name: '執行使用測試' })).toBeVisible();
  });

  it('空白 JD 保留四章與定位入口，選填欄位和空清單明示尚未填寫', async () => {
    const user = userEvent.setup();
    render(
      <JobDescriptionDocument
        jobDescription={{
          ...jobDescription,
          job_title: null,
          organization_unit: null,
          reports_to: null,
          purpose: null,
          baseline_competency_level: null,
          duties: [],
          tasks: [],
          knowledge: [],
          skills: [],
          collaborations: [],
          conditions: [],
        }}
      />,
    );

    expect(screen.getByRole('heading', { level: 1, name: '職務說明書' })).toBeVisible();
    expect(screen.getAllByRole('heading', { level: 2 })).toHaveLength(4);
    expect(
      within(screen.getByRole('region', { name: '基本資料' })).getAllByText('尚未填寫'),
    ).toHaveLength(5);
    expect(screen.getByText('尚未建立職責與任務。')).toBeVisible();
    expect(screen.getByText('尚未填寫知識。')).toBeVisible();
    expect(screen.getByText('尚未填寫技能。')).toBeVisible();
    expect(screen.getByText('尚未填寫協作對象。')).toBeVisible();
    expect(screen.getByText('尚未填寫共通條件。')).toBeVisible();
    const navigation = screen.getByRole('navigation', { name: 'JD 章節' });
    for (const link of within(navigation).getAllByRole('link')) {
      const targetId = link.getAttribute('href')?.slice(1);
      expect(targetId).toBeTruthy();
      expect(document.getElementById(targetId ?? '')).toHaveTextContent(
        link.textContent ?? '',
      );
      await user.click(link);
      expect(document.getElementById(targetId ?? '')).toHaveFocus();
    }
    expect(screen.queryByRole('textbox')).not.toBeInTheDocument();
  });
});
