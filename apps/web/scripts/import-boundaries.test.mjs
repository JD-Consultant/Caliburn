import assert from 'node:assert/strict';
import { test } from 'node:test';
import { fileURLToPath } from 'node:url';
import { ESLint } from 'eslint';

const lint = new ESLint({ cwd: fileURLToPath(new URL('..', import.meta.url)) });

for (const [owner, dependency] of [
  ['features/memory/memory-api.ts', '../interview/interview-api'],
  ['features/memory/memory-api.ts', '../../app/query-client'],
  ['features/interview/interview-api.ts', '../memory/memory-api'],
  ['features/memory/memory-api.ts', '../../features/interview/interview-api'],
  ['features/interview/interview-api.ts', '../../features/memory/memory-api'],
]) {
  test(`${owner} refuses ${dependency}`, async () => {
    const [result] = await lint.lintText(`import '${dependency}';\n`, { filePath: `src/${owner}` });
    assert.deepEqual(
      result.messages.map(({ ruleId }) => ruleId),
      ['no-restricted-imports'],
    );
  });
}

for (const [owner, dependency] of [
  ['features/memory/memory-api.ts', '../../shared/api/http'],
  ['app/query-client.ts', '../features/memory/memory-api'],
  ['features/memory/memory-api.ts', '../../features/memory/PublishedMemoryViewer'],
  ['features/memory/memory-api.ts', './PublishedMemoryViewer'],
]) {
  test(`${owner} permits ${dependency}`, async () => {
    const [result] = await lint.lintText(`import '${dependency}';\n`, { filePath: `src/${owner}` });
    assert.deepEqual(result.messages, []);
  });
}
