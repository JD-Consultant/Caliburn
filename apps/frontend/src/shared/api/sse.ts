import type { TurnEvent } from './generated/types.gen';
import { turnEventNames } from './generated/events.gen';
import { validateTurnEvent } from './generated/validators';
import { InvalidResponseError } from './http';

interface TurnEventStreamOptions {
  signal: AbortSignal;
  onEvent: (event: TurnEvent) => void;
}

/** 瀏覽器處理 SSE framing；失聯即關閉，交由功能查回正式狀態。 */
export async function streamTurnEvents(
  path: string,
  { signal, onEvent }: TurnEventStreamOptions,
): Promise<void> {
  signal.throwIfAborted();
  return new Promise<void>((resolve, reject) => {
    const source = new EventSource('/api' + path);
    let closed = false;

    function close(): void {
      closed = true;
      source.close();
      source.removeEventListener('error', onError);
      source.removeEventListener('message', onMessage);
      for (const name of turnEventNames) source.removeEventListener(name, onMessage);
      signal.removeEventListener('abort', onAbort);
    }

    function stop(error: unknown): void {
      if (closed) return;
      close();
      reject(
        error instanceof Error
          ? error
          : new Error('Agent event stream failed', { cause: error }),
      );
    }

    function onError(): void {
      // EventSource 不公開 HTTP status，功能補讀可取得正式 HTTP 錯誤。
      stop(new TypeError('Agent event stream disconnected'));
    }

    function onAbort(): void {
      stop(signal.reason);
    }

    function onMessage(message: Event): void {
      if (closed) return;
      try {
        if (!(message instanceof MessageEvent) || typeof message.data !== 'string')
          throw new InvalidResponseError();
        const data: unknown = JSON.parse(message.data);
        const envelope = { event: message.type, data };
        if (!validateTurnEvent(envelope)) throw new InvalidResponseError();
        onEvent(envelope);
        // 沿 Agent stream_turn 的結束條件，關閉原生自動重連。
        if (
          !closed &&
          (envelope.event === 'resync_required' ||
            envelope.event === 'cancellation' ||
            (envelope.event === 'status' && envelope.data.status !== 'running'))
        ) {
          close();
          resolve();
        }
      } catch (error) {
        stop(error instanceof SyntaxError ? new InvalidResponseError() : error);
      }
    }

    source.addEventListener('error', onError);
    source.addEventListener('message', onMessage);
    for (const name of turnEventNames) source.addEventListener(name, onMessage);
    signal.addEventListener('abort', onAbort, { once: true });
  });
}
