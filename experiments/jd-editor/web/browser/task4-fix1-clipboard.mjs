import { chromium, expect } from "@playwright/test";
import { writeFile } from "node:fs/promises";
import { resolve } from "node:path";
const evidence = resolve("../../../.superpowers/sdd/2026-09-10-jd-editor-core-implementation");
const browser = await chromium.launch({ channel: "chrome", headless: false });
const context = await browser.newContext({ viewport: { width: 1500, height: 1050 } });
await context.grantPermissions(["clipboard-read", "clipboard-write"], { origin: "http://127.0.0.1:3001" });
const page = await context.newPage();
const result = { browser: browser.version(), channel: "chrome", headed: true, OS_IME: "NOT RUN", network: [], errors: [] };
page.on("pageerror", (error) => result.errors.push(String(error)));
page.on("request", (r) => result.network.push({ method: r.method(), url: r.url(), body: r.postData() }));
const api = "http://127.0.0.1:8091";
try {
  const created = await context.request.post(api + "/documents", { data: { title: "受控 clipboard 保真", request_key: crypto.randomUUID() } });
  expect(created.status()).toBe(201);
  const { id } = await created.json(); result.document = id;
  const path = `${api}/documents/${id}/jd`;
  const head = await (await context.request.get(path)).json();
  const fragment = structuredClone(head.fragment);
  fragment[0].children = [{ text: "複製", bold: true }, { text: "保真內容" }];
  expect((await context.request.post(path + "/manual-save", { data: { request_key: crypto.randomUUID(), base_revision_ref: head.revision_ref, value: fragment } })).status()).toBe(200);
  result.original = fragment;
  await page.goto(`http://127.0.0.1:3001/workspace/${id}`);
  const editor = page.getByRole("textbox", { name: "職務說明書正文" });
  await expect(editor).toBeEditable();
  await page.evaluate(async () => {
    await navigator.clipboard.writeText("CONTROLLED SENTINEL MUST NOT PASTE");
    window.__clipboardEvents = [];
    for (const type of ["copy", "paste"]) document.addEventListener(type, (event) => {
      window.__clipboardEvents.push({ type, selected: window.getSelection()?.toString(),
        types: [...event.clipboardData.types], text: event.clipboardData.getData("text/plain"),
        html: event.clipboardData.getData("text/html"), fragment: event.clipboardData.getData("application/x-slate-fragment") });
    });
  });
  await editor.click();
  await page.keyboard.press("Home");
  await page.keyboard.press("Shift+End");
  await expect.poll(() => page.evaluate(() => window.getSelection()?.toString())).toBe("複製保真內容");
  await expect(page.getByText("已選取正文", { exact: true })).toBeVisible();
  result.selection = await page.evaluate(() => ({ text: window.getSelection()?.toString(), anchor: window.getSelection()?.anchorOffset, focus: window.getSelection()?.focusOffset }));
  await page.keyboard.press("Control+c");
  await expect.poll(() => page.evaluate(() => navigator.clipboard.readText())).toBe("複製保真內容");
  result.clipboard = await page.evaluate(async () => {
    const records = [];
    for (const item of await navigator.clipboard.read()) {
      const values = {};
      for (const type of item.types) values[type] = await (await item.getType(type)).text();
      records.push(values);
    }
    return records;
  });
  await page.keyboard.press("ArrowRight");
  await page.keyboard.press("End");
  await page.keyboard.press("Enter");
  await page.keyboard.press("Control+v");
  await expect(editor).toHaveText("複製保真內容複製保真內容");
  await page.getByRole("button", { name: "保存", exact: true }).click();
  await expect(page.getByRole("status")).toHaveText("已保存");
  const saved = await (await context.request.get(path)).json();
  expect(saved.fragment).toHaveLength(2);
  expect(saved.fragment[0]).toEqual(fragment[0]);
  expect(saved.fragment[1].type).toBe(fragment[0].type);
  expect(saved.fragment[1].children).toEqual(fragment[0].children);
  expect(saved.fragment[1].id).not.toBe(fragment[0].id);
  expect(new Set(saved.fragment.map((node) => node.id)).size).toBe(2);
  result.saved = saved;
  result.events = await page.evaluate(() => window.__clipboardEvents);
  await page.reload();
  await expect(editor).toBeEditable();
  expect((await (await context.request.get(path)).json()).fragment).toEqual(saved.fragment);
  await expect(editor).toHaveText("複製保真內容複製保真內容");
  await page.screenshot({ path: resolve(evidence, "task4-fix1-clipboard-screen.png"), fullPage: true });
  result.ok = true;
} catch (error) {
  result.failure = String(error); result.ok = false;
  result.events = await page.evaluate(() => window.__clipboardEvents ?? []);
  throw error;
} finally {
  await writeFile(resolve(evidence, "task4-fix1-clipboard-browser.json"), JSON.stringify(result, null, 2));
  await context.close(); await browser.close();
}
