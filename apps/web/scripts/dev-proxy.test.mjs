import assert from 'node:assert/strict';
import { once } from 'node:events';
import { mkdtemp, rm } from 'node:fs/promises';
import { createServer as createHttpServer } from 'node:http';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import process from 'node:process';
import { test } from 'node:test';
import { fileURLToPath } from 'node:url';
import { createServer } from 'vite';

test('the isolated dev proxy preserves request provenance', async (t) => {
  const backend = createHttpServer((request, response) => {
    request.resume();
    response.setHeader('Content-Type', 'application/json');
    response.end(
      JSON.stringify({
        origin: request.headers.origin ?? null,
        fetchSite: request.headers['sec-fetch-site'],
      }),
    );
  });
  backend.listen(0, '127.0.0.1');
  await once(backend, 'listening');
  t.after(() => new Promise((resolve) => backend.close(resolve)));

  const previousTarget = process.env.CALIBURN_API_PROXY;
  process.env.CALIBURN_API_PROXY = `http://127.0.0.1:${backend.address().port}`;
  t.after(() => {
    if (previousTarget === undefined) delete process.env.CALIBURN_API_PROXY;
    else process.env.CALIBURN_API_PROXY = previousTarget;
  });
  // Load the actual application config; do not substitute a test-only proxy.
  const cacheDir = await mkdtemp(join(tmpdir(), 'caliburn-proxy-test-'));
  t.after(() => rm(cacheDir, { recursive: true, force: true }));
  const vite = await createServer({
    root: fileURLToPath(new URL('../', import.meta.url)),
    cacheDir,
    optimizeDeps: { noDiscovery: true, include: [] },
    server: { host: '127.0.0.1', port: 0, strictPort: true, hmr: false, watch: null },
  });
  t.after(() => vite.close());
  await vite.listen();
  const url = `http://127.0.0.1:${vite.httpServer.address().port}/api/probe`;

  for (const origin of ['http://127.0.0.1:9999', 'http://127.0.0.1:5174', null]) {
    await t.test(`Origin ${origin ?? '(absent)'} reaches the backend unchanged`, async () => {
      const response = await fetch(url, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Sec-Fetch-Site': 'same-site',
          ...(origin === null ? {} : { Origin: origin }),
        },
        body: '{}',
      });
      assert.equal(response.status, 200);
      assert.deepEqual(await response.json(), { origin, fetchSite: 'same-site' });
    });
  }
});
