import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { expect, it } from 'vitest';
import type { CompactionView, StepView, TurnView } from '../../shared/api/generated';
import { TurnDetails } from './TurnDetails';

const stepCompaction: CompactionView = {
  response_id: 'compact-step',
  model_step: 1,
  usage: { input_tokens: 50, output_tokens: 10, total_tokens: 60 },
};
const turn: TurnView = {
  workspace_id: '00112233-4455-6677-8899-aabbccddeeff',
  turn_id: '11112233-4455-6677-8899-aabbccddeeff',
  status: 'completed',
  input: '合成輸入',
  output: '完成',
  interrupts: [],
  usage: null,
  compactions: [
    { response_id: 'compact-before', model_step: 0, usage: null },
    stepCompaction,
  ],
  created_at: '2026-11-06T00:00:00Z',
  updated_at: '2026-11-06T00:00:00Z',
};
const steps: StepView[] = [
  {
    model_step: 1,
    messages: ['已保存回覆'],
    reasoning_summary: ['公開推理摘要'],
    usage: { input_tokens: 100, output_tokens: 20, total_tokens: 120 },
    compactions: [stepCompaction],
    tool_calls: [
      {
        call_id: 'tool-1',
        name: 'write_plan',
        arguments: '{"body":"計畫"}',
        output: null,
        status: 'not_recorded',
      },
    ],
    interrupts: [],
  },
];

it('未知 R 用量不顯示為零；C 只按已採用原件展示，步與輪不重複累加', async () => {
  const user = userEvent.setup();
  const { rerender } = render(<TurnDetails turn={turn} steps={steps} />);
  await user.click(screen.getByText('處理紀錄與用量'));
  expect(screen.getByLabelText('本輪模型回覆用量')).toHaveTextContent('用量未知');
  expect(screen.getByLabelText('本輪模型回覆用量')).not.toHaveTextContent('0');
  expect(screen.getByText('輪前壓縮')).toBeVisible();
  expect(screen.getAllByText('compact-step')).toHaveLength(1);
  expect(screen.getByText(/已保存資訊，非帳單/)).toBeVisible();
  rerender(<TurnDetails turn={turn} steps={steps} />);
  expect(screen.getAllByText('compact-step')).toHaveLength(1);
  await user.click(screen.getByText('模型步 1'));
  expect(within(screen.getByLabelText('模型步 1 用量')).getByText(/120/)).toBeVisible();
});

it('工具未保存結果不宣稱未執行，原參數與公開摘要可讀', async () => {
  const user = userEvent.setup();
  render(<TurnDetails turn={turn} steps={steps} />);
  await user.click(screen.getByText('處理紀錄與用量'));
  await user.click(screen.getByText('模型步 1'));
  expect(screen.getByText('公開推理摘要')).toBeVisible();
  await user.click(screen.getByText('write_plan'));
  expect(screen.getByText(/尚未保存結果，不能據此判定是否已執行/)).toBeVisible();
  expect(screen.getByText('{"body":"計畫"}')).toBeVisible();
  expect(screen.queryByText('未執行')).not.toBeInTheDocument();
});
