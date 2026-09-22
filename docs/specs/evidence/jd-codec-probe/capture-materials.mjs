import fs from 'node:fs';
import path from 'node:path';
import { createHash } from 'node:crypto';

const hash = file => createHash('sha256').update(fs.readFileSync(file)).digest('hex');
const records = [];
function copy(from, to) {
  fs.mkdirSync(path.dirname(to), { recursive: true });
  fs.copyFileSync(from, to);
  records.push({ original: from, copy: to, originalSha256: hash(from), copySha256: hash(to) });
}
for (const filename of ['package.json', 'LICENSE', 'README.md', 'dist/index.js', 'dist/index.d.ts', 'dist/transformer.js', 'dist/plainer.js', 'dist/is.js', 'dist/util.js']) {
  copy(`node_modules/superjson/${filename}`, `source/installed-superjson/${filename}`);
}
for (const filename of ['package.json', 'LICENSE', 'README.md', 'dist/index.js']) {
  copy(`node_modules/copy-anything/${filename}`, `source/installed-copy-anything/${filename}`);
}
for (const filename of ['package.json', 'package-lock.json']) copy(`../jd-editor-review-probe/${filename}`, `source/borrowed-review-probe/${filename}`);
for (const filename of ['package.json', 'LICENSE', 'dist/index.js', 'dist/index.d.ts', 'dist/src-CMqLOrDd.js']) {
  copy(`../jd-editor-review-probe/node_modules/@platejs/suggestion/${filename}`, `source/borrowed-suggestion/${filename}`);
}
for (const filename of ['package.json', 'LICENSE']) copy(`../jd-editor-review-probe/node_modules/platejs/${filename}`, `source/borrowed-platejs/${filename}`);
const lock = JSON.parse(fs.readFileSync('package-lock.json', 'utf8'));
const packages = Object.entries(lock.packages).filter(([location]) => location).map(([location, entry]) => {
  const pkg = JSON.parse(fs.readFileSync(`${location}/package.json`, 'utf8'));
  return { name: pkg.name, version: pkg.version, license: pkg.license, dependencies: pkg.dependencies ?? {}, engines: pkg.engines ?? {}, resolved: entry.resolved, integrity: entry.integrity, licenseSha256: hash(`${location}/LICENSE`) };
});
fs.writeFileSync('source/materials-manifest.json', JSON.stringify({ accessed: '2026-09-09', note: 'Installed artifacts and borrowed fixed Plate material copied read-only. TypeScript source and compiled JS are not claimed byte-identical.', files: records }, null, 2) + '\n');
fs.writeFileSync('source/dependency-inventory.json', JSON.stringify({ accessed: '2026-09-09', installedCount: packages.length, packageLockSha256: hash('package-lock.json'), packages }, null, 2) + '\n');
const r01Root = '../jd-editor-review-probe/results/2026-09-09T14-36-40-805Z';
const r01 = JSON.parse(fs.readFileSync(`${r01Root}/run-hashes.json`, 'utf8'));
const followRoot = '../jd-editor-review-probe/results/order-followup-2026-09-09T14-53-39-183Z';
const follow = JSON.parse(fs.readFileSync(`${followRoot}/run-hashes.json`, 'utf8'));
const preserved = [
  ['../jd-editor-review-probe/review-probe.mjs', r01.script],
  ['../jd-editor-review-probe/package-lock.json', r01.packageLock],
  [`${r01Root}/review-results.json`, r01.results],
  [`${r01Root}/review-traces.json`, r01.traces],
  ['../jd-editor-review-probe/review-order-followup.mjs', follow.script],
  [`${followRoot}/review-order-results.json`, follow.results],
  [`${followRoot}/review-order-traces.json`, follow.traces],
  [`${r01Root}/ai-human-ai-pending-value.json`, follow.sourceInput],
].map(([file, expected]) => ({ file, expectedSha256: expected, actualSha256: hash(file), unchanged: hash(file) === expected }));
fs.writeFileSync('results/original-probes-preserved.json', JSON.stringify({ accessed: '2026-09-09', files: preserved }, null, 2) + '\n');
console.log(JSON.stringify({ installedCount: packages.length, packages: packages.map(({ name, version, license }) => ({ name, version, license })), copiedFiles: records.length, everyCopyHashEqual: records.every(item => item.originalSha256 === item.copySha256), allOriginalProbeHashesUnchanged: preserved.every(item => item.unchanged) }, null, 2));
