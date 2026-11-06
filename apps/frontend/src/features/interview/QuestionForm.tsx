import { useId, useState } from 'react';
import {
  Alert,
  Box,
  Button,
  Checkbox,
  FormControlLabel,
  Radio,
  Stack,
  TextField,
  Typography,
} from '@mui/material';
import type { AnswerTurnRequest, QuestionExchange } from '../../shared/api/generated';
import { HttpError, InvalidRequestError } from '../../shared/api/http';

interface Props {
  exchange: QuestionExchange;
  disabled?: boolean;
  onSubmit: (body: AnswerTurnRequest) => Promise<void>;
}

interface AnswerDraft {
  selected: string[];
  custom: string;
  skipped: boolean;
}

const emptyAnswer: AnswerDraft = { selected: [], custom: '', skipped: false };

/** A draft belongs to the displayed call; saved answers are rendered from the query. */
export function QuestionForm(props: Props) {
  if (props.exchange.status !== 'waiting')
    return <SavedAnswers exchange={props.exchange} />;
  return (
    <WaitingQuestions
      key={`${props.exchange.model_step}:${props.exchange.call_id}`}
      {...props}
    />
  );
}

function WaitingQuestions({ exchange, disabled = false, onSubmit }: Props) {
  const groupId = useId();
  const [drafts, setDrafts] = useState<Record<string, AnswerDraft>>({});
  const [sending, setSending] = useState(false);
  const [submitted, setSubmitted] = useState(false);
  const [pending, setPending] = useState<AnswerTurnRequest | null>(null);
  const [error, setError] = useState<string | null>(null);
  const locked = disabled || sending || submitted;
  const editingLocked = locked || pending !== null;
  const complete = exchange.questions.every((question) => {
    const draft = drafts[question.message_id];
    return (
      draft && (draft.skipped || draft.selected.length > 0 || draft.custom.trim() !== '')
    );
  });

  function update(questionId: string, change: Partial<AnswerDraft>): void {
    setDrafts((current) => ({
      ...current,
      [questionId]: { ...(current[questionId] ?? emptyAnswer), ...change },
    }));
  }

  async function submit(): Promise<void> {
    if (locked || !complete) return;
    const body = pending ?? {
      model_step: exchange.model_step,
      call_id: exchange.call_id,
      answers: exchange.questions.map((question) => {
        const draft = drafts[question.message_id] ?? emptyAnswer;
        return {
          question_message_id: question.message_id,
          selected: draft.skipped ? [] : draft.selected,
          custom: draft.skipped || draft.custom === '' ? null : draft.custom,
        };
      }),
    };
    setSending(true);
    setPending(body);
    setError(null);
    try {
      await onSubmit(body);
      setSubmitted(true);
    } catch (failure) {
      if (
        failure instanceof InvalidRequestError ||
        (failure instanceof HttpError && failure.status === 422)
      ) {
        setPending(null);
        setError('回答不符合要求，請檢查並修正內容。');
      } else {
        setError('回答尚未確認。原回答仍保留；重新確認時只會送出同一份回答。');
      }
    } finally {
      setSending(false);
    }
  }

  return (
    <Box
      component="form"
      aria-label="回答顧問問題"
      onSubmit={(event) => {
        event.preventDefault();
        void submit();
      }}
    >
      <Typography variant="subtitle2" sx={{ mb: 1 }}>
        請回答顧問問題
      </Typography>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
        每題可選擇選項、自行補充，或明確略過；完成後整批送出。
      </Typography>
      <Stack spacing={2}>
        {exchange.questions.map((question) => {
          const draft = drafts[question.message_id] ?? emptyAnswer;
          return (
            <Box
              component="fieldset"
              key={question.message_id}
              disabled={editingLocked}
              aria-label={question.question}
              sx={{
                minWidth: 0,
                m: 0,
                p: 2,
                border: 1,
                borderColor: 'divider',
                borderRadius: 2,
              }}
            >
              <Typography
                component="legend"
                variant="subtitle2"
                sx={{ overflowWrap: 'anywhere' }}
              >
                {question.question}
              </Typography>
              {question.header && (
                <Typography variant="caption" color="text.secondary">
                  {question.header}
                </Typography>
              )}
              <Stack>
                {(question.options ?? []).map((option) => (
                  <FormControlLabel
                    key={option.label}
                    disabled={editingLocked || draft.skipped}
                    control={
                      question.multi_select ? (
                        <Checkbox
                          checked={draft.selected.includes(option.label)}
                          onChange={(_event, checked) =>
                            update(question.message_id, {
                              selected: checked
                                ? (question.options ?? [])
                                    .filter(
                                      (item) =>
                                        item.label === option.label ||
                                        draft.selected.includes(item.label),
                                    )
                                    .map((item) => item.label)
                                : draft.selected.filter(
                                    (label) => label !== option.label,
                                  ),
                            })
                          }
                        />
                      ) : (
                        <Radio
                          name={`${groupId}-${question.message_id}`}
                          checked={draft.selected.includes(option.label)}
                          onChange={() =>
                            update(question.message_id, { selected: [option.label] })
                          }
                        />
                      )
                    }
                    label={
                      <Box sx={{ overflowWrap: 'anywhere' }}>
                        <Typography component="span" variant="body2">
                          {option.label}
                        </Typography>
                        {option.description && (
                          <Typography
                            component="span"
                            variant="body2"
                            color="text.secondary"
                          >
                            {' '}
                            — {option.description}
                          </Typography>
                        )}
                      </Box>
                    }
                  />
                ))}
              </Stack>
              {(question.options ?? []).length > 0 && (
                <Button
                  type="button"
                  size="small"
                  disabled={editingLocked || draft.skipped || draft.selected.length === 0}
                  onClick={() => update(question.message_id, { selected: [] })}
                >
                  清除選擇
                </Button>
              )}
              <TextField
                label="自行補充"
                size="small"
                multiline
                minRows={2}
                fullWidth
                value={draft.custom}
                disabled={editingLocked || draft.skipped}
                onChange={(event) =>
                  update(question.message_id, { custom: event.target.value })
                }
                sx={{ mt: 1 }}
              />
              <FormControlLabel
                disabled={editingLocked}
                control={
                  <Checkbox
                    checked={draft.skipped}
                    onChange={(_event, checked) =>
                      update(question.message_id, { skipped: checked })
                    }
                  />
                }
                label="略過此題"
              />
            </Box>
          );
        })}
        {error && <Alert severity="warning">{error}</Alert>}
        {submitted && (
          <Typography role="status">回答已送出，正在查回保存結果…</Typography>
        )}
        <Button type="submit" variant="contained" disabled={locked || !complete}>
          {sending
            ? '正在送出回答…'
            : pending !== null && !submitted
              ? '重新確認原回答'
              : '送出全部回答'}
        </Button>
      </Stack>
    </Box>
  );
}

function SavedAnswers({ exchange }: { exchange: QuestionExchange }) {
  return (
    <Box component="section" aria-label="已展示題組">
      <Typography variant="subtitle2">
        {exchange.status === 'answered' ? '回答已保存' : '此題組未回答'}
      </Typography>
      {exchange.questions.map((question) => {
        const answer = exchange.answers?.find(
          (item) => item.question_message_id === question.message_id,
        );
        return (
          <Box key={question.message_id} sx={{ my: 2, overflowWrap: 'anywhere' }}>
            <Typography variant="body2" sx={{ fontWeight: 600 }}>
              {question.question}
            </Typography>
            {answer ? (
              <>
                {(answer.selected ?? []).map((label) => (
                  <Typography key={label} variant="body2">
                    {label}
                  </Typography>
                ))}
                {answer.custom != null && answer.custom !== '' && (
                  <Typography variant="body2" sx={{ whiteSpace: 'pre-wrap' }}>
                    {answer.custom}
                  </Typography>
                )}
                {(answer.selected ?? []).length === 0 && !answer.custom && (
                  <Typography variant="body2" color="text.secondary">
                    已略過
                  </Typography>
                )}
              </>
            ) : (
              <Typography variant="body2" color="text.secondary">
                未回答
              </Typography>
            )}
          </Box>
        );
      })}
    </Box>
  );
}
