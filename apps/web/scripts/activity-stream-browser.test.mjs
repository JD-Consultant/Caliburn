/** Real Chromium EventSource over HTTP; no model, database or existing application process. */
import assert from 'node:assert/strict';
import { test } from 'node:test';
import process from 'node:process';
import { spawn } from 'node:child_process';
import { once } from 'node:events';
import { setTimeout as delay } from 'node:timers/promises';
import { fileURLToPath } from 'node:url';
import { chromium } from '@playwright/test';
import { createServer } from 'vite';

test('production hook recovers CLOSED 503 and stops after 204; dev HTML rejects frames', async (t) => {
  let mode = 'recover';
  let streams = 0;
  const methods = [];
  const timers = new Set();
  const active = {
    job_file_id: '10000000-0000-4000-8000-000000000001',
    execution_id: '20000000-0000-4000-8000-000000000002',
    status: 'active',
    pause_requested: false,
    input_text: '合成工作內容',
    commentary: [],
    candidate: null,
    plan_preview: null,
    allowed_controls: [],
  };
  const vite = await createServer({
    root: fileURLToPath(new URL('../', import.meta.url)),
    server: { host: '127.0.0.1', port: 0, strictPort: true, hmr: false, watch: null },
    plugins: [
      {
        name: 'synthetic-activity-http',
        configureServer(server) {
          server.middlewares.use((request, response, next) => {
            if (request.url === '/__activity-test') {
              response.setHeader('Content-Type', 'text/html');
              response.end(
                '<html><div id="root"></div><script type="module" src="/tests/fixtures/activity-stream-browser.ts"></script></html>',
              );
              return;
            }
            if (!request.url?.startsWith('/api/')) {
              next();
              return;
            }
            methods.push(request.method);
            if (request.url.endsWith('/activity-stream')) {
              streams++;
              if (mode === 'terminal' || streams === 1) {
                response.writeHead(mode === 'terminal' ? 204 : 503).end();
                return;
              }
              response.writeHead(200, {
                'Content-Type': 'text/event-stream',
                'Cache-Control': 'no-store',
              });
              const event = (text) =>
                response.write(
                  `event: commentary\ndata: ${JSON.stringify({
                    job_file_id: active.job_file_id,
                    execution_id: active.execution_id,
                    response_id: 'fixture-response',
                    message_id: 'fixture-message',
                    text,
                  })}\n\n`,
                );
              event('恢復後第一段');
              const timer = setTimeout(() => event('恢復後後續片段'), 300);
              timers.add(timer);
              request.on('close', () => {
                clearTimeout(timer);
                timers.delete(timer);
              });
              return;
            }
            response.setHeader('Content-Type', 'application/json');
            response.end(
              JSON.stringify(
                request.url.endsWith('/reasoning-summaries')
                  ? []
                  : { ...active, status: mode === 'terminal' ? 'completed' : 'active' },
              ),
            );
          });
        },
      },
    ],
  });
  await vite.listen();
  const origin = `http://127.0.0.1:${vite.httpServer.address().port}`;
  console.log(JSON.stringify({ fixturePid: process.pid, fixtureOrigin: origin }));
  t.after(async () => {
    timers.forEach(clearTimeout);
    await vite.close();
  });
  const browser = await chromium.launch({
    ...(process.env.CALIBURN_E2E_CHROMIUM_PATH
      ? { executablePath: process.env.CALIBURN_E2E_CHROMIUM_PATH }
      : {}),
  });
  t.after(() => browser.close());
  const page = await browser.newPage();
  await page.goto(`${origin}/__activity-test`);
  await page.getByText('恢復後後續片段', { exact: false }).waitFor();
  assert.equal(streams, 2);
  assert.ok(methods.every((method) => method === 'GET'));
  await page.goto('about:blank');
  mode = 'terminal';
  streams = 0;
  methods.length = 0;
  await page.goto(`${origin}/__activity-test`);
  await page.waitForFunction(() =>
    globalThis.document.querySelector('output')?.textContent?.includes('"disconnected":true'),
  );
  await page.waitForTimeout(8_000);
  assert.equal(streams, 1, '204 with confirmed terminal GET must not create another EventSource');
  assert.ok(methods.every((method) => method === 'GET'));
  const top = await page.goto(origin);
  assert.equal(top.headers()['content-security-policy'], "frame-ancestors 'none'");
  assert.ok(await page.locator('#root').count());
  await page.goto('about:blank');
  await page.setContent(`<iframe src="${origin}"></iframe>`);
  const deniedFrame = page.frames().find((frame) => frame !== page.mainFrame());
  console.log(JSON.stringify({ devFrameUrl: deniedFrame?.url() }));
  assert.equal(deniedFrame?.url(), 'chrome-error://chromewebdata/');
  const apiRoot = fileURLToPath(new URL('../../api/', import.meta.url));
  const backend = spawn(
    `${apiRoot}/.venv/Scripts/python.exe`,
    ['tests/fixtures/html_security_server.py'],
    {
      cwd: apiRoot,
      windowsHide: true,
      stdio: ['ignore', 'pipe', 'inherit'],
    },
  );
  t.after(async () => {
    if (backend.exitCode === null) {
      const exited = once(backend, 'exit');
      backend.kill();
      await exited;
    }
  });
  const [announcement] = await once(backend.stdout, 'data');
  const apiOrigin = JSON.parse(announcement.toString()).origin;
  console.log(JSON.stringify({ fixturePid: backend.pid, fixtureOrigin: apiOrigin }));
  let ready = false;
  for (let attempt = 0; attempt < 50 && !ready; attempt++) {
    ready = await fetch(apiOrigin).then(
      (response) => response.ok,
      () => false,
    );
    if (!ready) await delay(100);
  }
  assert.ok(ready, 'synthetic Python server must be accepting HTTP before browser navigation');
  const html = await page.goto(apiOrigin);
  assert.equal(html.headers()['content-security-policy'], "frame-ancestors 'none'");
  await page.locator('#protected').waitFor();
  await page.goto('about:blank');
  await page.setContent(`<iframe src="${apiOrigin}"></iframe>`);
  const deniedApiFrame = page.frames().find((frame) => frame !== page.mainFrame());
  assert.equal(deniedApiFrame?.url(), 'chrome-error://chromewebdata/');
  console.log(
    JSON.stringify({
      chromium: browser.version(),
      recoveredStreamRequests: 2,
      terminalStreamRequests: streams,
      iframeBlocked: true,
      productionMiddlewareIframeBlocked: true,
    }),
  );
  await page.close();
});
