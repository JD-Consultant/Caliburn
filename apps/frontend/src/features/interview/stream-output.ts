import type { ToolCallData, TurnEvent } from '../../shared/api/generated/types.gen';

export interface StreamOutput {
  step: number;
  text: string;
  reasoning: string;
  tools: ToolCallData[];
}
export function appendDelta(
  current: StreamOutput | null,
  event: TurnEvent,
): StreamOutput | null {
  if (
    event.event !== 'text_delta' &&
    event.event !== 'reasoning_summary_delta' &&
    event.event !== 'tool_call'
  )
    return current;
  const next =
    current?.step === event.data.model_step
      ? current
      : { step: event.data.model_step, text: '', reasoning: '', tools: [] };
  if (event.event === 'tool_call')
    return {
      ...next,
      tools: [
        ...next.tools.filter((tool) => tool.call_id !== event.data.call_id),
        event.data,
      ],
    };
  return event.event === 'text_delta'
    ? { ...next, text: next.text + event.data.delta }
    : { ...next, reasoning: next.reasoning + event.data.delta };
}
