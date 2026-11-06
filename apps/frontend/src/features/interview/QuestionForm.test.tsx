import { act, fireEvent, render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { expect, it, vi } from 'vitest';
import type {
  AnswerTurnRequest,
  QuestionExchange,
  SavedQuestion,
} from '../../shared/api/generated';
import { QuestionForm } from './QuestionForm';
import { HttpError } from '../../shared/api/http';

const [primaryQuestion, toolsQuestion, extraQuestion] = [
  {
    message_id: '00112233-4455-6677-8899-aabbccddeeff',
    question_ref: 'message_101',
    header: '主要工作',
    question: '主要負責哪項工作？',
    options: [
      { label: '服務', description: '接待顧客' },
      { label: '開發', description: null },
    ],
    multi_select: false,
  },
  {
    message_id: '11112233-4455-6677-8899-aabbccddeeff',
    question_ref: 'message_102',
    header: null,
    question: '使用哪些工具？',
    options: [
      { label: '表單', description: null },
      { label: '電話', description: null },
    ],
    multi_select: true,
  },
  {
    message_id: '22112233-4455-6677-8899-aabbccddeeff',
    question_ref: 'message_103',
    header: null,
    question: '還有什麼補充？',
    options: [],
    multi_select: false,
  },
] satisfies [SavedQuestion, SavedQuestion, SavedQuestion];
const exchange: QuestionExchange = {
  model_step: 2,
  call_id: 'question-call',
  status: 'waiting',
  answers: null,
  questions: [primaryQuestion, toolsQuestion, extraQuestion],
};

it('所有題目均回答或明確略過才送出同一完整題組', async () => {
  const user = userEvent.setup();
  const submit = vi.fn<(body: AnswerTurnRequest) => Promise<void>>().mockResolvedValue();
  render(<QuestionForm exchange={exchange} onSubmit={submit} />);
  const button = screen.getByRole('button', { name: '送出全部回答' });
  expect(button).toBeDisabled();
  const primary = within(screen.getByRole('group', { name: '主要負責哪項工作？' }));
  await user.click(primary.getByRole('radio', { name: /服務/ }));
  await user.click(primary.getByRole('radio', { name: '開發' }));
  expect(primary.getByRole('radio', { name: /服務/ })).not.toBeChecked();
  const tools = within(screen.getByRole('group', { name: '使用哪些工具？' }));
  await user.click(tools.getByRole('checkbox', { name: '表單' }));
  await user.click(tools.getByRole('checkbox', { name: '電話' }));
  await user.type(tools.getByRole('textbox', { name: '自行補充' }), '  保留原文  ');
  expect(button).toBeDisabled();
  await user.click(
    within(screen.getByRole('group', { name: '還有什麼補充？' })).getByRole('checkbox', {
      name: '略過此題',
    }),
  );
  await user.click(button);
  expect(submit).toHaveBeenCalledExactlyOnceWith({
    model_step: 2,
    call_id: 'question-call',
    answers: [
      {
        question_message_id: primaryQuestion.message_id,
        selected: ['開發'],
        custom: null,
      },
      {
        question_message_id: toolsQuestion.message_id,
        selected: ['表單', '電話'],
        custom: '  保留原文  ',
      },
      {
        question_message_id: extraQuestion.message_id,
        selected: [],
        custom: null,
      },
    ],
  });
});

it('提交失敗保留回答，送出期間不重複提交', async () => {
  const user = userEvent.setup();
  let reject: (error: Error) => void = () => undefined;
  const submit = vi.fn<(body: AnswerTurnRequest) => Promise<void>>().mockImplementation(
    () =>
      new Promise<void>((_resolve, fail) => {
        reject = fail;
      }),
  );
  render(
    <QuestionForm
      exchange={{ ...exchange, questions: [extraQuestion] }}
      onSubmit={submit}
    />,
  );
  await user.type(screen.getByRole('textbox', { name: '自行補充' }), '保留這個回答');
  await user.click(screen.getByRole('button', { name: '送出全部回答' }));
  expect(screen.getByRole('button', { name: '正在送出回答…' })).toBeDisabled();
  fireEvent.submit(screen.getByRole('form', { name: '回答顧問問題' }));
  expect(submit).toHaveBeenCalledTimes(1);
  await act(async () => {
    reject(new Error('connection lost'));
    await Promise.resolve();
  });
  expect(screen.getByRole('textbox', { name: '自行補充' })).toHaveValue('保留這個回答');
  expect(screen.getByRole('textbox', { name: '自行補充' })).toBeDisabled();
  expect(screen.getByRole('alert')).toHaveTextContent('回答尚未確認');
  submit.mockResolvedValue();
  await user.click(screen.getByRole('button', { name: '重新確認原回答' }));
  expect(submit).toHaveBeenNthCalledWith(2, submit.mock.calls[0]?.[0]);
});

it('明確輸入拒絕可修正草稿，未知結果不能冒充輸入拒絕', async () => {
  const user = userEvent.setup();
  const submit = vi
    .fn<(body: AnswerTurnRequest) => Promise<void>>()
    .mockRejectedValue(new HttpError(422, {}));
  render(
    <QuestionForm
      exchange={{ ...exchange, questions: [extraQuestion] }}
      onSubmit={submit}
    />,
  );
  await user.type(screen.getByRole('textbox', { name: '自行補充' }), '原回答');
  await user.click(screen.getByRole('button', { name: '送出全部回答' }));
  expect(screen.getByRole('textbox', { name: '自行補充' })).toBeEnabled();
  expect(screen.getByRole('alert')).toHaveTextContent('回答不符合要求');
});

it('已保存回答只讀，舊 interrupt 不使題組重新可答', () => {
  render(
    <QuestionForm
      exchange={{
        ...exchange,
        status: 'answered',
        answers: [
          {
            question_message_id: primaryQuestion.message_id,
            selected: ['服務'],
            custom: null,
          },
          {
            question_message_id: toolsQuestion.message_id,
            selected: [],
            custom: '紙本',
          },
          {
            question_message_id: extraQuestion.message_id,
            selected: [],
            custom: null,
          },
        ],
      }}
      onSubmit={vi.fn()}
    />,
  );
  expect(screen.getByText('回答已保存')).toBeVisible();
  expect(screen.queryByRole('button', { name: '送出全部回答' })).not.toBeInTheDocument();
  expect(screen.queryByRole('textbox')).not.toBeInTheDocument();
  expect(screen.getByText('紙本')).toBeVisible();
  expect(screen.getByText('已略過')).toBeVisible();
});

it('切換題組不沿用前一題組的局部答案', async () => {
  const user = userEvent.setup();
  const { rerender } = render(<QuestionForm exchange={exchange} onSubmit={vi.fn()} />);
  await user.type(
    within(screen.getByRole('group', { name: primaryQuestion.question })).getByRole(
      'textbox',
    ),
    '前一組草稿',
  );
  rerender(
    <QuestionForm
      exchange={{ ...exchange, call_id: 'next-call', model_step: 3 }}
      onSubmit={vi.fn()}
    />,
  );
  expect(
    within(screen.getByRole('group', { name: primaryQuestion.question })).getByRole(
      'textbox',
    ),
  ).toHaveValue('');
});

it('選過單選後可清除選擇，只送出自行補充的原文', async () => {
  const user = userEvent.setup();
  const submit = vi.fn<(body: AnswerTurnRequest) => Promise<void>>().mockResolvedValue();
  render(
    <QuestionForm
      exchange={{ ...exchange, questions: [primaryQuestion] }}
      onSubmit={submit}
    />,
  );
  await user.click(screen.getByRole('radio', { name: /服務/ }));
  await user.type(
    screen.getByRole('textbox', { name: '自行補充' }),
    '  我只負責品質稽核  ',
  );
  await user.click(screen.getByRole('button', { name: '清除選擇' }));
  expect(screen.getByRole('radio', { name: /服務/ })).not.toBeChecked();
  expect(screen.getByRole('textbox', { name: '自行補充' })).toHaveValue(
    '  我只負責品質稽核  ',
  );
  await user.click(screen.getByRole('button', { name: '送出全部回答' }));
  expect(submit).toHaveBeenCalledExactlyOnceWith({
    model_step: exchange.model_step,
    call_id: exchange.call_id,
    answers: [
      {
        question_message_id: primaryQuestion.message_id,
        selected: [],
        custom: '  我只負責品質稽核  ',
      },
    ],
  });
});
