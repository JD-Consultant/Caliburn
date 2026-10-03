import { readFileSync, writeFileSync, readdirSync, mkdirSync, copyFileSync } from 'node:fs';
import { join, relative } from 'node:path';
import { fileURLToPath } from 'node:url';
import { createHash } from 'node:crypto';

const root = fileURLToPath(new URL('.', import.meta.url));
const sha = path => createHash('sha256').update(readFileSync(path)).digest('hex');
const write = (name, data) => writeFileSync(join(root, name), JSON.stringify(data, null, 2));
const copy = (source, destination) => { mkdirSync(join(destination, '..'), { recursive: true }); copyFileSync(source, destination); };
const walk = directory => readdirSync(directory, { withFileTypes: true }).flatMap(e => e.isDirectory() ? walk(join(directory, e.name)) : [join(directory, e.name)]);
const lock = JSON.parse(readFileSync(join(root, 'package-lock.json'), 'utf8'));
const packages = [];
for (const [location, item] of Object.entries(lock.packages)) {
  if (!location) continue;
  const directory = join(root, location), meta = JSON.parse(readFileSync(join(directory, 'package.json'), 'utf8'));
  const archiveName = location.replaceAll('/', '__');
  copy(join(directory, 'package.json'), join(root, 'sources', 'packages', `${archiveName}.json`));
  const licenses = readdirSync(directory, { withFileTypes: true }).filter(e => e.isFile() && /^(licen[cs]e|copying|notice)/i.test(e.name)).map(e => {
    const source = join(directory, e.name), target = join(root, 'licenses', archiveName, e.name); copy(source, target);
    return { source: `${location}/${e.name}`, archivedAs: relative(root, target).replaceAll('\\', '/'), sha256: sha(source) };
  });
  packages.push({ location, name: meta.name, version: meta.version, declaredLicense: meta.license ?? null, resolved: item.resolved, integrity: item.integrity, licenses });
}
write('license-inventory.json', { checkedOn: '2026-09-10', scope: 'Actual isolated F02 install only', packageCount: packages.length, packages });
const sourceRules = {
  '@platejs/core': /(?:withSlate[^/]*\.js|index\.d\.ts)$/,
  '@platejs/basic-nodes': /\.(?:js|ts)$/,
  '@platejs/list-classic': /\.(?:js|ts)$/,
  '@platejs/table': /\.(?:js|ts)$/,
  '@platejs/slate': /(?:index\.js|index\.d\.ts)$/,
  '@platejs/utils': /(?:index\.js|index\.d\.ts)$/,
  '@platejs/diff': /\.(?:js|ts)$/,
  'slate': /index\.es\.js$/,
};
const sourceFiles = [];
for (const [name, pattern] of Object.entries(sourceRules)) {
  const base = join(root, 'node_modules', name, 'dist');
  for (const source of walk(base).filter(p => pattern.test(p.replaceAll('\\', '/')))) {
    const destination = join(root, 'sources', 'installed', name.replaceAll('/', '__'), relative(base, source));
    copy(source, destination); sourceFiles.push({ package: name, source: relative(root, source).replaceAll('\\', '/'), archivedAs: relative(root, destination).replaceAll('\\', '/'), sha256: sha(source) });
  }
}
write('sources/installed-source-manifest.json', { checkedOn: '2026-09-10', note: 'Exact actual npm dist source; no edits or vendor patches', files: sourceFiles });
const paths = walk(root).filter(p => !relative(root, p).split(/[\\/]/).includes('node_modules') && !p.endsWith('artifact-hashes.json'));
write('artifact-hashes.json', { algorithm: 'sha256', generatedAt: new Date().toISOString(), files: paths.map(p => ({ path: relative(root, p).replaceAll('\\', '/'), bytes: readFileSync(p).length, sha256: sha(p) })) });
console.log(JSON.stringify({ packageCount: packages.length, missingLicenseFiles: packages.filter(p => !p.licenses.length).map(p => `${p.name}@${p.version}`), installedSourceFiles: sourceFiles.length, artifactFiles: paths.length }));
