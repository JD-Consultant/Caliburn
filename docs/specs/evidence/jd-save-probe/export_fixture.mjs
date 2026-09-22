import { writeFile } from 'node:fs/promises';
import { before } from '../jd-editor-ui-probe/fixture.mjs';

// Export only: preserve the already verified complete r2 fixed fixture,
// including its deliberately synthetic element metadata. No source importer.
const bytes = JSON.stringify(before, null, 2) + '\n';
await writeFile(new URL('fixture.json', import.meta.url), bytes);
console.log(`Exported complete r2 fixed fixture (${Buffer.byteLength(bytes)} UTF-8 bytes).`);
