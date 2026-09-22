import { readFileSync, writeFileSync, mkdirSync, copyFileSync } from 'node:fs';
import { createHash } from 'node:crypto';
import { fixture } from '../jd-editor-profile-probe/fixture.mjs';

mkdirSync(new URL('./sources/', import.meta.url), { recursive: true });
const original = structuredClone(fixture), mapped = structuredClone(original), changes = [];
const visit = node => {
  if (node.type === 'li') for (const child of node.children) {
    if (child.type === 'p') { changes.push({ id: child.id, from: 'p', to: 'lic' }); child.type = 'lic'; }
  }
  node.children?.forEach(visit);
};
mapped.forEach(visit);
writeFileSync(new URL('./fixture-original-f01.json', import.meta.url), JSON.stringify(original, null, 2));
writeFileSync(new URL('./fixture.json', import.meta.url), JSON.stringify(mapped, null, 2));
const sources = ['../jd-editor-profile-probe/fixture.mjs', '../jd-editor-ui-probe/fixture.mjs', '../../docs/specs/2026-09-09-frontend-engineer-jd-sample.md'];
const provenance = sources.map((path, index) => {
  const source = new URL(path, import.meta.url), name = ['f01-fixture.mjs', 'ui-r2-fixture.mjs', 'r2-source.md'][index];
  const bytes = readFileSync(source);
  copyFileSync(source, new URL(`./sources/${name}`, import.meta.url));
  return { path, archivedAs: `sources/${name}`, sha256: createHash('sha256').update(bytes).digest('hex') };
});
writeFileSync(new URL('./fixture-mapping.json', import.meta.url), JSON.stringify({ note: 'Explicit fixed-fixture p→lic mapping under li only; no text/ID/source/marks removal. source_refs remain synthetic F01 evidence.', changes, provenance }, null, 2));
console.log(JSON.stringify({ mappedListParagraphs: changes.length, copiedSources: provenance.length }));
