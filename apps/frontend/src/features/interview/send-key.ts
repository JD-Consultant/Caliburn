import type { KeyboardEvent } from 'react';

/** The Enter used to confirm an IME choice belongs to the input method. */
export function isSendKey({ key, shiftKey, nativeEvent }: KeyboardEvent): boolean {
  return (
    key === 'Enter' &&
    !shiftKey &&
    !nativeEvent.isComposing &&
    nativeEvent.keyCode !== 229
  );
}
