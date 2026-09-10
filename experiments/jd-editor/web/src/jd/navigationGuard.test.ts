import { it, expect } from "vitest";
import { mayLeave } from "./navigationGuard";
it("save failure does not navigate and JD save does not submit pending chat", async () => {
  let saves = 0;
  expect(
    await mayLeave({ dirty: true, chat: true }, "save", async () => {
      saves++;
      return false;
    }),
  ).toBe(false);
  expect(saves).toBe(1);
  expect(
    await mayLeave({ dirty: true, chat: true }, "save", async () => true),
  ).toBe(false);
  expect(
    await mayLeave({ dirty: true, chat: true }, "discard", async () => {
      throw Error("must not save");
    }),
  ).toBe(true);
});
