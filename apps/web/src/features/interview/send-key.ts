import type { KeyboardEvent } from 'react';

/**
 * Enter sends and Shift+Enter breaks the line, as in every chat composer (ChatGPT, Claude, Slack,
 * Vercel AI Elements' PromptInput). The Enter that confirms an input-method choice (注音, Pinyin,
 * Kana) belongs to the input method and must never send.
 */
export function isSendKey({ key, shiftKey, nativeEvent }: KeyboardEvent): boolean {
  if (key !== 'Enter' || shiftKey || nativeEvent.isComposing) return false;
  // Safari ends the composition before the confirming keydown arrives, so `isComposing` is already
  // false there and only the legacy keyCode 229 still says "input method" (MDN, "keydown event").
  // eslint-disable-next-line @typescript-eslint/no-deprecated -- no current API carries this signal
  return nativeEvent.keyCode !== 229;
}
