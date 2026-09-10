import { chromium, expect } from "@playwright/test";
import { writeFile } from "node:fs/promises";
import { resolve } from "node:path";
const evidence = resolve(
  "../../../.superpowers/sdd/2026-09-10-jd-editor-core-implementation",
);
const browser = await chromium.launch({ channel: "chrome", headless: false }),
  context = await browser.newContext({
    viewport: { width: 1500, height: 1050 },
  });
let page = await context.newPage();
const result = {
    browser: browser.version(),
    channel: "chrome",
    headed: true,
    cases: [],
  },
  network = [],
  errors = [];
const observe = (p) => {
  p.on("request", (r) => {
    if (r.url().includes(":8091"))
      network.push({ method: r.method(), url: r.url(), body: r.postData() });
  });
  p.on("pageerror", (e) => errors.push(String(e)));
};
observe(page);
try {
  await page.goto("http://127.0.0.1:3001");
  await page.getByLabel("文件名稱").fill("離頁保護 " + Date.now());
  await page.getByRole("button", { name: "建立文件", exact: true }).click();
  await page.waitForURL("**/workspace/**");
  const url = page.url(),
    document = url.split("/").at(-1),
    key = "caliburn:jd-plate-clean-v2:submission:" + document;
  let editor = page.getByRole("textbox", { name: "職務說明書正文" });
  await expect(editor).toBeEditable();
  result.react = await page
    .locator(".editor-shell")
    .getAttribute("data-react-version");
  await editor.click();
  await page.keyboard.insertText("普通未保存");
  expect(await page.evaluate((key) => localStorage.getItem(key), key)).toBe(
    null,
  );
  let beforeunload;
  const dismiss = async (dialog) => {
    beforeunload = dialog.type();
    await dialog.dismiss();
  };
  page.once("dialog", dismiss);
  await page.reload().catch(() => {});
  expect(beforeunload).toBe("beforeunload");
  await expect(editor).toHaveText("普通未保存");
  result.cases.push(
    "real browser beforeunload dismissal protects ordinary dirty without claiming crash recovery",
  );
  await page.getByLabel("補充或更正你的工作").fill("尚未送出的聊天");
  await page.getByRole("link", { name: "← 我的職務說明書" }).click();
  const dialog = page.getByRole("dialog", { name: "未保存內容" });
  await expect(dialog).toBeVisible();
  await dialog.getByRole("button", { name: "保存後離開", exact: true }).click();
  await expect(page.getByRole("status")).toHaveText("已保存");
  expect(page.url()).toBe(url);
  await expect(page.getByLabel("補充或更正你的工作")).toHaveValue(
    "尚未送出的聊天",
  );
  expect(
    network.filter((r) => r.method === "POST" && r.url.endsWith("/runs")),
  ).toHaveLength(0);
  await dialog.getByRole("button", { name: "繼續編輯", exact: true }).click();
  result.cases.push(
    "app navigation saves JD but does not send or discard unsent chat",
  );
  // Close immediately after actual POST dispatch; retain the exact request locally.
  await page.getByLabel("補充或更正你的工作").fill("");
  await editor.click();
  await page.keyboard.press("Control+End");
  await page.keyboard.insertText("送出即關頁");
  const saveURL = `http://127.0.0.1:8091/documents/${document}/jd/manual-save`;
  let dispatched, serverDone;
  const observed = new Promise((resolve) => {
    dispatched = resolve;
  });
  const complete = new Promise((resolve) => {
    serverDone = resolve;
  });
  await page.route(saveURL, async (route) => {
    result.closedPayload = JSON.parse(route.request().postData());
    dispatched();
    try {
      result.closedReceipt = await (await route.fetch()).json();
    } finally {
      serverDone();
    }
    if (!page.isClosed()) await route.abort();
  });
  await page.getByRole("button", { name: "保存", exact: true }).click();
  await observed;
  await page.close({ runBeforeUnload: false });
  await complete;
  page = await context.newPage();
  observe(page);
  await page.goto(url);
  editor = page.getByRole("textbox", { name: "職務說明書正文" });
  await expect(editor).toBeEditable();
  await expect
    .poll(() => page.evaluate((key) => localStorage.getItem(key), key))
    .toBe(null);
  const head = await (
    await context.request.get(`http://127.0.0.1:8091/documents/${document}/jd`)
  ).json();
  expect(head.revision_ref).toBe(result.closedReceipt.result_revision_ref);
  expect(head.fragment).toEqual(result.closedPayload.value);
  result.saved = head;
  result.cases.push(
    "POST then immediate page close -> exact original receipt on reopen",
  );
  await page.screenshot({
    path: resolve(evidence, "task4-navigation-screen.png"),
  });
  result.ok = true;
} catch (error) {
  result.ok = false;
  result.failure = String(error);
  if (!page.isClosed())
    await page.screenshot({
      path: resolve(evidence, "task4-navigation-failure.png"),
    });
  throw error;
} finally {
  result.network = network;
  result.errors = errors;
  await writeFile(
    resolve(evidence, "task4-navigation-browser.json"),
    JSON.stringify(result, null, 2),
  );
  await context.close();
  await browser.close();
}
