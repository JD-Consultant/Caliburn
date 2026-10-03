/** After an editor opened from a control closes, focus goes back to that control, so keyboard users keep their place. */
import { useEffect, useRef } from 'react';
import type { RefObject } from 'react';

export function useFocusReturn(open: boolean): RefObject<HTMLButtonElement | null> {
  const control = useRef<HTMLButtonElement>(null);
  const wasOpen = useRef(false);
  useEffect(() => {
    if (open) wasOpen.current = true;
    else if (wasOpen.current) {
      wasOpen.current = false;
      control.current?.focus();
    }
  }, [open]);
  return control;
}
