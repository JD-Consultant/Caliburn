import { readFileSync, writeFileSync } from 'node:fs';
import { inspect } from 'node:util';
import { editor, capture, flush, clone, profile } from './engine.mjs';

// New OS process each call. No DB, model, production state, custom codec or replay logic.
const [inputFile, outputFile, mode = 'normalize'] = process.argv.slice(2);
const input = JSON.parse(readFileSync(inputFile, 'utf8'));
const e = editor(mode === 'apply' ? input.value : input), batches = capture(e);
try {
  if (mode === 'apply') e.tf.withNewBatch(() => e.tf.withoutNormalizing(() => {
    for (const operation of input.operations) e.tf.apply(clone(operation));
  }));
  e.tf.normalize({ force: true });
  await flush();
  const output = { ok: true, pid: process.pid, node: process.version, mode, profile, value: clone(e.children), batches };
  writeFileSync(outputFile, JSON.stringify(output, null, 2));
  writeFileSync(`${outputFile}.inspect.txt`, inspect(output, { depth: null, maxArrayLength: null, maxStringLength: null, compact: false }));
} catch (error) {
  const output = { ok: false, pid: process.pid, mode, error: { message: error.message, stack: error.stack }, value: clone(e.children), batches };
  writeFileSync(outputFile, JSON.stringify(output, null, 2));
  writeFileSync(`${outputFile}.inspect.txt`, inspect(output, { depth: null, maxArrayLength: null, maxStringLength: null, compact: false }));
  process.exitCode = 1;
}
