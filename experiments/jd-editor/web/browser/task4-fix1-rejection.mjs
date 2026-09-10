import { chromium, expect } from "@playwright/test";
import { writeFile } from "node:fs/promises";
import { resolve } from "node:path";
const evidence = resolve("../../../.superpowers/sdd/2026-09-10-jd-editor-core-implementation");
const browser = await chromium.launch({ channel: "chrome", headless: false });
const context = await browser.newContext({ viewport: { width: 1500, height: 1050 } });
const page = await context.newPage();
const result = { browser: browser.version(), channel: "chrome", headed: true, OS_IME: "NOT RUN", network: [], errors: [] };
page.on("pageerror", (error) => result.errors.push(String(error)));
page.on("request", (r) => result.network.push({ method: r.method(), url: r.url(), body: r.postData() }));
const api = "http://127.0.0.1:8091";
const editor = page.getByRole("textbox", { name: "職務說明書正文" });
const cache = (id) => page.evaluate((key) => localStorage.getItem("caliburn:jd-plate-clean-v2:submission:" + key), id);
async function create() {
  const reply = await context.request.post(api + "/documents", { data: { title: "拒絕／未知驗證", request_key: crypto.randomUUID() } });
  expect(reply.status()).toBe(201);
  const document = await reply.json();
  await page.goto(`http://127.0.0.1:3001/workspace/${document.id}`);
  await expect(editor).toBeEditable();
  return document;
}
try {
  const document = await create();
  await editor.click(); await page.keyboard.insertText("明確拒絕仍保留候選");
  await page.getByLabel("補充或更正你的工作").fill("不能丟掉的原問句");
  const archived = await context.request.patch(`${api}/documents/${document.id}`, { data: { command: "set_archived", archived: true, expected_metadata_version: 1 } });
  expect(archived.status()).toBe(200);
  const rejection = page.waitForResponse((r) => r.url().endsWith("/jd/manual-save") && r.request().method() === "POST");
  await page.getByRole("button", { name: "保存", exact: true }).click();
  const response = await rejection;
  expect(response.status()).toBe(409);
  result.rejection = await response.json();
  expect(result.rejection.admission).toBe("not_admitted");
  await expect(page.getByRole("button", { name: "捨棄這份候選", exact: true })).toBeEnabled();
  result.rejectedCandidate = JSON.parse(await cache(document.id));
  expect(result.rejection.request_key).toBe(result.rejectedCandidate.request_key);
  expect(result.rejectedCandidate.value[0].children).toEqual([{ text: "明確拒絕仍保留候選" }]);
  await expect(page.getByLabel("補充或更正你的工作")).toHaveValue("不能丟掉的原問句");
  const acceptedHead = await (await context.request.get(`${api}/documents/${document.id}/jd`)).json();
  expect(acceptedHead.fragment[0].children).toEqual([{ text: "" }]);
  page.once("dialog", (dialog) => dialog.accept());
  await page.getByRole("button", { name: "捨棄這份候選", exact: true }).click();
  expect(await cache(document.id)).toBeNull();
  result.rejectedDocument = document.id;
  // A separate document avoids treating archived metadata as the unknown lock.
  page.once("dialog", (dialog) => dialog.accept());
  const unknown = await create();
  await editor.click(); await page.keyboard.insertText("網路未知必須保留");
  await page.route("**/jd/manual-save", (route) => route.abort("connectionfailed"));
  await page.getByRole("button", { name: "保存", exact: true }).click();
  await expect(page.getByRole("button", { name: "捨棄這份候選", exact: true })).toBeDisabled();
  await expect(page.locator('[aria-label="職務說明書正文"]')).toHaveAttribute("contenteditable", "false");
  result.unknownCandidate = JSON.parse(await cache(unknown.id));
  expect(result.unknownCandidate.value[0].children).toEqual([{ text: "網路未知必須保留" }]);
  result.unknownDocument = unknown.id;
  await page.screenshot({ path: resolve(evidence, "task4-fix1-rejection-screen.png"), fullPage: true });
  result.ok = true;
} catch (error) { result.ok = false; result.failure = String(error); throw error; }
finally {
  await writeFile(resolve(evidence, "task4-fix1-rejection-browser.json"), JSON.stringify(result, null, 2));
  await context.close(); await browser.close();
}
