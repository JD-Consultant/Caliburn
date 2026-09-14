import fs from 'node:fs/promises';
const lock = JSON.parse(await fs.readFile('package-lock.json', 'utf8'));
const inventory = [];
for (const [path, metadata] of Object.entries(lock.packages)) {
  if (!path) continue;
  let pkg;
  try { pkg = JSON.parse(await fs.readFile(`${path}/package.json`, 'utf8')); }
  catch (error) { if (error.code === 'ENOENT') continue; throw error; }
  inventory.push({ name: pkg.name, version: pkg.version, license: pkg.license ?? null, path, resolved: metadata.resolved, repository: pkg.repository ?? null, note: pkg.name === '@platejs/diff' ? 'Read package LICENSE: slate-diff Apache-2.0; Plate modifications dual Apache-2.0/MIT.' : undefined });
}
inventory.sort((a, b) => a.name.localeCompare(b.name));
await fs.writeFile('results/license-inventory.json', JSON.stringify({ accessed: '2026-09-09', count: inventory.length, packages: inventory }, null, 2) + '\n');
for (const [source, output] of [['@platejs/diff/LICENSE', 'diff-LICENSE.txt'], ['platejs/LICENSE', 'plate-LICENSE.txt'], ['esbuild/LICENSE.md', 'esbuild-LICENSE.txt']]) {
  await fs.copyFile(`node_modules/${source}`, `results/${output}`);
}
// Platform binary package declares MIT and ships no separate LICENSE file.
await fs.copyFile('node_modules/@esbuild/win32-x64/package.json', 'results/esbuild-win32-package.json');
console.log(JSON.stringify({ count: inventory.length, licenseDeclarations: inventory.reduce((acc, item) => { const key = item.license ?? 'package LICENSE separately reviewed'; acc[key] = (acc[key] ?? 0) + 1; return acc; }, {}), primary: inventory.filter(p => ['platejs', '@platejs/core', '@platejs/diff', 'react', 'react-dom', 'esbuild', '@esbuild/win32-x64'].includes(p.name)) }, null, 2));
