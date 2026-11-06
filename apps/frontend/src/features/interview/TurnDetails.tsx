import { Box, Typography } from '@mui/material';
import type { StepView, TurnView, UsageView } from '../../shared/api/generated';
import { SafeMarkdown } from '../../shared/ui/SafeMarkdown';

export function TurnDetails({ turn, steps }: { turn: TurnView; steps: StepView[] }) {
  return (
    <Box component="details" sx={{ mt: 2, overflowWrap: 'anywhere' }}>
      <Typography
        component="summary"
        variant="body2"
        sx={{ cursor: 'pointer', color: 'text.secondary' }}
      >
        處理紀錄與用量
      </Typography>
      <Box sx={{ borderLeft: 2, borderColor: 'divider', pl: 2, mt: 1 }}>
        <Typography variant="caption" color="text.secondary">
          以下為已保存資訊，非帳單；不包含背景 Memory 模型費用。
        </Typography>
        <Usage label="本輪模型回覆用量" usage={turn.usage} />
        {(turn.compactions ?? []).length > 0 && (
          <Box component="section" aria-label="已採用的壓縮回覆" sx={{ my: 2 }}>
            <Typography variant="subtitle2">已採用的壓縮回覆（C）</Typography>
            {(turn.compactions ?? []).map((compaction) => (
              <Box key={compaction.response_id} sx={{ my: 1 }}>
                <Typography variant="body2">
                  {compaction.model_step === 0
                    ? '輪前壓縮'
                    : `模型步 ${compaction.model_step} 採用`}
                </Typography>
                <Typography variant="caption" component="p">
                  {compaction.response_id}
                </Typography>
                <Usage
                  label={`壓縮 ${compaction.response_id} 用量`}
                  usage={compaction.usage}
                />
              </Box>
            ))}
          </Box>
        )}
        {steps.length === 0 && (
          <Typography variant="body2">尚無已保存的模型步。</Typography>
        )}
        {steps.map((step) => (
          <Box component="details" key={step.model_step} sx={{ my: 1.5 }}>
            <Typography
              component="summary"
              variant="subtitle2"
              sx={{ cursor: 'pointer' }}
            >
              模型步 {step.model_step}
            </Typography>
            <Usage label={`模型步 ${step.model_step} 用量`} usage={step.usage} />
            {step.messages.map((message, index) => (
              <SafeMarkdown key={index} markdown={message} />
            ))}
            {step.reasoning_summary.length > 0 && (
              <Box
                component="section"
                aria-label="推理摘要"
                sx={{ color: 'text.secondary' }}
              >
                <Typography variant="caption">推理摘要</Typography>
                {step.reasoning_summary.map((summary, index) => (
                  <SafeMarkdown key={index} markdown={summary} />
                ))}
              </Box>
            )}
            {step.tool_calls.map((call) => (
              <Box component="details" key={call.call_id} sx={{ mt: 1 }}>
                <Typography
                  component="summary"
                  variant="body2"
                  sx={{ cursor: 'pointer' }}
                >
                  {call.name}
                </Typography>
                <Typography variant="caption">
                  {call.status === 'recorded'
                    ? '結果已保存'
                    : '尚未保存結果，不能據此判定是否已執行。'}
                </Typography>
                <Typography variant="caption" component="p">
                  呼叫：{call.call_id}
                </Typography>
                <Typography variant="subtitle2">原參數</Typography>
                <RawText text={call.arguments} />
                <Typography variant="subtitle2">結果</Typography>
                {call.output === null || call.output === undefined ? (
                  <Typography variant="body2">沒有已保存的結果正文。</Typography>
                ) : (
                  <RawText text={call.output} />
                )}
              </Box>
            ))}
          </Box>
        ))}
      </Box>
    </Box>
  );
}

function Usage({ label, usage }: { label: string; usage: UsageView | null }) {
  return (
    <Typography component="p" variant="caption" aria-label={label} sx={{ my: 1 }}>
      {label}：
      {usage === null
        ? '用量未知'
        : `輸入 ${usage.input_tokens.toLocaleString()} ／ 輸出 ${usage.output_tokens.toLocaleString()} ／ 合計 ${usage.total_tokens.toLocaleString()} tokens`}
    </Typography>
  );
}

function RawText({ text }: { text: string }) {
  return (
    <Box
      component="pre"
      sx={{
        whiteSpace: 'pre-wrap',
        overflowWrap: 'anywhere',
        fontSize: '0.8rem',
        bgcolor: 'action.hover',
        p: 1.5,
        borderRadius: 1,
      }}
    >
      {text}
    </Box>
  );
}
