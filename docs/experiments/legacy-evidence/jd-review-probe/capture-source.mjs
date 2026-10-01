import fs from 'node:fs';
import path from 'node:path';
import { createHash } from 'node:crypto';

const commit = 'cee7a4ec0328718d8cf147094466b597215f5406';
const sourceRoot = '../jd-oss/plate/packages/suggestion';
const selected = [
  'package.json', 'src/lib/BaseSuggestionPlugin.ts', 'src/lib/withSuggestion.ts',
  'src/lib/queries/findSuggestionProps.ts', 'src/lib/transforms/insertTextSuggestion.ts',
  'src/lib/transforms/deleteFragmentSuggestion.ts', 'src/lib/transforms/deleteSuggestion.ts',
  'src/lib/transforms/removeMarkSuggestion.ts', 'src/lib/transforms/removeMarkSuggestion.spec.tsx',
  'src/lib/transforms/acceptSuggestion.ts', 'src/lib/transforms/rejectSuggestion.ts',
  'src/lib/utils/getSuggestionKeys.ts', 'src/lib/utils/getSuggestionId.ts',
  'src/lib/transforms/setSuggestionNodes.ts', 'src/lib/transforms/getSuggestionProps.ts',
  'src/lib/transforms/insertFragmentSuggestion.ts', 'src/lib/types.ts',
  'src/react/SuggestionPlugin.tsx',
];
const digest = file => createHash('sha256').update(fs.readFileSync(file)).digest('hex');
const sourceManifest = [];
for (const relative of selected) {
  const from = path.join(sourceRoot, relative);
  const to = path.join('source', 'official-fixed', relative);
  fs.mkdirSync(path.dirname(to), { recursive: true }); fs.copyFileSync(from, to);
  sourceManifest.push({ file: to, originalSha256: digest(from), archivedSha256: digest(to), url: `https://github.com/udecode/plate/blob/${commit}/packages/suggestion/${relative}` });
}
const installedFiles = ['package.json', 'LICENSE', 'dist/index.js', 'dist/index.d.ts', 'dist/src-CMqLOrDd.js'];
for (const relative of installedFiles) {
  const from = path.join('node_modules/@platejs/suggestion', relative);
  const to = path.join('source', 'installed-suggestion', relative);
  fs.mkdirSync(path.dirname(to), { recursive: true }); fs.copyFileSync(from, to);
  sourceManifest.push({ file: to, originalSha256: digest(from), archivedSha256: digest(to), package: '@platejs/suggestion@53.2.3' });
}
fs.mkdirSync('source/licenses', { recursive: true });
fs.copyFileSync('node_modules/@platejs/diff/LICENSE', 'source/licenses/diff-LICENSE.txt');
fs.copyFileSync('node_modules/platejs/LICENSE', 'source/licenses/plate-LICENSE.txt');
const lock = JSON.parse(fs.readFileSync('package-lock.json', 'utf8'));
const packages = [];
for (const [location, entry] of Object.entries(lock.packages)) {
  if (!location || !fs.existsSync(path.join(location, 'package.json'))) continue;
  const pkg = JSON.parse(fs.readFileSync(path.join(location, 'package.json'), 'utf8'));
  packages.push({ name: pkg.name, version: pkg.version, license: pkg.license ?? null, resolved: entry.resolved, note: pkg.name === '@platejs/diff' ? 'Package LICENSE read separately: Apache-2.0 derived code; modifications dual Apache-2.0/MIT.' : undefined });
}
packages.sort((a, b) => a.name.localeCompare(b.name));
fs.writeFileSync('results/source-manifest.json', JSON.stringify({ accessed: '2026-09-09', sourceCommit: commit, note: 'Selected official source/tests and installed dist copied read-only; package tag/current-source comparison was recorded by parent separately.', files: sourceManifest }, null, 2) + '\n');
fs.writeFileSync('results/dependency-inventory.json', JSON.stringify({ accessed: '2026-09-09', installedCount: packages.length, packageLockSha256: digest('package-lock.json'), packages }, null, 2) + '\n');
console.log(JSON.stringify({ installedCount: packages.length, declarations: packages.reduce((sum, pkg) => { const key = pkg.license ?? 'separate LICENSE'; sum[key] = (sum[key] ?? 0) + 1; return sum; }, {}), sourceFiles: sourceManifest.length, everyCopyHashEqual: sourceManifest.every(item => item.originalSha256 === item.archivedSha256) }));
