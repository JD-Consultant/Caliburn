import { readFileSync } from "node:fs";
export const fixture = JSON.parse(
  readFileSync(
    new URL("../../fixtures/r2-canonical.json", import.meta.url),
    "utf8",
  ),
);
export const expectedMove = JSON.parse(
  readFileSync(
    new URL("../../fixtures/expected-task8-move.json", import.meta.url),
    "utf8",
  ),
);
export const profile = {
  format_version: 2,
  engine_profile: "jd-plate-clean-v2",
} as const;
export const clone = <T>(x: T): T => structuredClone(x);
export const p = (id: string, text = "重複文字", extra = {}) => ({
  type: "p",
  id,
  children: [{ text, ...extra }],
});
export function elements(value: any[]): any[] {
  return value.flatMap((n) => (n.children ? [n, ...elements(n.children)] : []));
}
export const byId = (value: any[], id: string) =>
  elements(value).find((n) => n.id === id);
