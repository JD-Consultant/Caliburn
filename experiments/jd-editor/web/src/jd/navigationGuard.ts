export async function mayLeave(
  state: { dirty: boolean; chat: boolean },
  choice: "save" | "stay" | "discard",
  save: () => Promise<boolean>,
) {
  if (choice === "stay") return false;
  if (choice === "discard") return true;
  if (state.dirty && !(await save())) return false;
  return !state.chat;
}
export function guardUnload(event: BeforeUnloadEvent) {
  event.preventDefault();
  event.returnValue = "";
}
