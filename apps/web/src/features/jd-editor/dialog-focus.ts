/** Transition completion must not steal focus from a user who already started editing. */
export function focusDialogInput(input: HTMLInputElement | null): void {
  if (!input) return;
  const active = document.activeElement;
  if (
    active instanceof HTMLElement &&
    input.closest('[role="dialog"]')?.contains(active) &&
    active.matches('input, textarea, button, [role="combobox"], [contenteditable="true"]')
  )
    return;
  input.focus();
}
