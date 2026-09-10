import { chromium, expect } from "@playwright/test";
import { writeFile } from "node:fs/promises";
import { resolve } from "node:path";
const evidence = resolve(
  "../../../.superpowers/sdd/2026-09-10-jd-editor-core-implementation",
);
const browser = await chromium.launch({ channel: "chrome", headless: false });
const context = await browser.newContext({
  viewport: { width: 1500, height: 1050 },
});
await context.grantPermissions(["clipboard-read", "clipboard-write"], {
  origin: "http://127.0.0.1:3001",
});
const page = await context.newPage();
const errors = [],
  network = [];
const result = {
  browser: browser.version(),
  channel: "chrome",
  headed: true,
  OS_IME: "NOT RUN",
  cases: [],
};
page.on("pageerror", (error) => errors.push(String(error)));
page.on("request", (r) => {
  if (r.url().includes(":8091"))
    network.push({ method: r.method(), url: r.url(), body: r.postData() });
});
const saved = async (document) =>
  (
    await context.request.get(`http://127.0.0.1:8091/documents/${document}/jd`)
  ).json();
try {
  await page.goto("http://127.0.0.1:3001");
  await page.getByLabel("文件名稱").fill("真輸入驗收 " + Date.now());
  await page.getByRole("button", { name: "建立文件", exact: true }).click();
  await page.waitForURL("**/workspace/**");
  const document = page.url().split("/").at(-1);
  result.document = document;
  const editor = page.getByRole("textbox", { name: "職務說明書正文" });
  await expect(editor).toBeEditable();
  await editor.click();
  await page.keyboard.insertText("工作工作");
  await expect(editor).toHaveText("工作工作");
  await page.keyboard.press("End");
  await expect
    .poll(() => page.evaluate(() => window.getSelection()?.anchorOffset))
    .toBe(4);
  await page.keyboard.down("Shift");
  await page.keyboard.press("ArrowLeft");
  await page.keyboard.press("ArrowLeft");
  await page.keyboard.up("Shift");
  await expect(page.getByText("已選取正文", { exact: true })).toBeVisible();
  result.selectedText = await page.evaluate(() =>
    window.getSelection()?.toString(),
  );
  expect(result.selectedText).toBe("工作");
  await page.getByLabel("補充或更正你的工作").fill("請改選取");
  await page.getByRole("button", { name: "請AI改這段", exact: true }).click();
  await expect
    .poll(async () => JSON.stringify((await saved(document)).fragment), {
      timeout: 30000,
    })
    .toContain("第二處修正");
  const afterAI = await saved(document);
  expect(afterAI.fragment[0].children.map((x) => x.text).join("")).toBe(
    "工作第二處修正",
  );
  result.cases.push(
    "true duplicate selection -> dirty save -> jd_read -> replace_selection",
  );
  result.selectionRequest = network.find(
    (r) => r.method === "POST" && r.url.endsWith("/runs"),
  );
  expect(JSON.parse(result.selectionRequest.body).text).toBe("請改選取");
  expect(
    [
      JSON.parse(result.selectionRequest.body).jd_selection.range.anchor.offset,
      JSON.parse(result.selectionRequest.body).jd_selection.range.focus.offset,
    ].sort(),
  ).toEqual([2, 4]);
  await expect(editor).toBeEditable({ timeout: 30000 });
  await editor.click();
  await page.keyboard.press("Control+End");
  await page.keyboard.insertText("手");
  await page.keyboard.press("Control+z");
  await expect(editor).toHaveText("工作第二處修正");
  await page.keyboard.press("Control+z");
  await expect(editor).toHaveText("工作工作");
  await page.keyboard.press("Control+Shift+z");
  await expect(editor).toHaveText("工作第二處修正");
  await page.keyboard.press("Control+Shift+z");
  await expect(editor).toHaveText("工作第二處修正手");
  result.cases.push("AI batch + manual undo/redo separation");
  await page.evaluate(() => {
    window.__task4Events = [];
    const editor = document.querySelector("[contenteditable=true]");
    for (const type of [
      "compositionstart",
      "compositionupdate",
      "compositionend",
      "beforeinput",
      "input",
    ])
      editor.addEventListener(type, (event) =>
        window.__task4Events.push({
          type: event.type,
          data: event.data,
          inputType: event.inputType,
          isComposing: event.isComposing,
        }),
      );
  });
  const cdp = await context.newCDPSession(page);
  await page.keyboard.press("Control+End");
  await cdp.send("Input.imeSetComposition", {
    text: "職",
    selectionStart: 1,
    selectionEnd: 1,
  });
  await cdp.send("Input.imeSetComposition", {
    text: "職務",
    selectionStart: 2,
    selectionEnd: 2,
  });
  await cdp.send("Input.insertText", { text: "職務" });
  await expect(editor).toContainText("手職務");
  await cdp.send("Input.imeSetComposition", {
    text: "取消",
    selectionStart: 2,
    selectionEnd: 2,
  });
  await cdp.send("Input.imeSetComposition", {
    text: "",
    selectionStart: 0,
    selectionEnd: 0,
  });
  await expect(editor).not.toContainText("取消");
  result.cases.push("CDP composition update/commit/cancel");
  result.events = await page.evaluate(() => window.__task4Events);
  await page.getByRole("button", { name: "保存", exact: true }).click();
  await expect(page.getByRole("status")).toHaveText("已保存");
  const beforeReopen = await saved(document);
  await page.reload();
  await expect(editor).toBeEditable();
  expect((await saved(document)).fragment).toEqual(beforeReopen.fragment);
  result.cases.push("save/reload exact IDs/value");
  await editor.click();
  await page.keyboard.press("Control+a");
  const copiedText = beforeReopen.fragment[0].children.map((leaf) => leaf.text).join("");
  await expect.poll(() => page.evaluate(() => window.getSelection()?.toString())).toBe(copiedText);
  await expect(page.getByText("已選取正文", { exact: true })).toBeVisible();
  await page.keyboard.press("Control+c");
  await expect.poll(() => page.evaluate(() => navigator.clipboard.readText())).toBe(copiedText);
  await page.keyboard.press("ArrowRight");
  await page.keyboard.press("End");
  await page.keyboard.press("Enter");
  await page.keyboard.press("Control+v");
  await page.getByRole("button", { name: "保存", exact: true }).click();
  await expect(page.getByRole("status")).toHaveText("已保存");
  const pasted = await saved(document);
  const ids = pasted.fragment.map((x) => x.id);
  expect(new Set(ids).size).toBe(ids.length);
  expect(pasted.fragment.length).toBeGreaterThan(1);
  expect(pasted.fragment[1].children).toEqual(beforeReopen.fragment[0].children);
  expect(pasted.fragment[1].type).toBe(beforeReopen.fragment[0].type);
  expect(pasted.fragment[1].id).not.toBe(beforeReopen.fragment[0].id);
  result.cases.push("native clipboard exact content/marks and fresh paragraph IDs");
  result.saved = pasted;
  result.react = await page.evaluate(() => {
    const hook = window.__REACT_DEVTOOLS_GLOBAL_HOOK__;
    return hook?.renderers
      ? [...hook.renderers.values()].map((r) => ({
          version: r.version,
          package: r.rendererPackageName,
        }))
      : null;
  });
  await page.screenshot({
    path: resolve(evidence, "task4-input-screen.png"),
    fullPage: true,
  });
  result.ax = await page.locator("main").ariaSnapshot();
  result.ok = true;
} catch (error) {
  result.ok = false;
  result.failure = String(error);
  await page.screenshot({
    path: resolve(evidence, "task4-input-failure.png"),
    fullPage: true,
  });
  throw error;
} finally {
  result.errors = errors;
  result.network = network;
  await writeFile(
    resolve(evidence, "task4-input-browser.json"),
    JSON.stringify(result, null, 2),
  );
  await context.close();
  await browser.close();
}
