/** Offline Markdown file/anchor checks; default targets must belong to the public Git inventory. */
import { readFile, stat } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { parseArgs } from 'node:util';
import { findPublishedFiles, parseDocument, selectDocuments } from './documentation.mjs';
export { selectDocuments } from './documentation.mjs';

function isInside(root, target) {
  const relative = path.relative(root, target);
  return !path.isAbsolute(relative) && relative !== '..' && !relative.startsWith(`..${path.sep}`);
}

export async function checkDocuments(root, files, { publishedFiles } = {}) {
  root = path.resolve(root);
  const published = publishedFiles === undefined ? undefined :
    new Set(publishedFiles.map(file => path.resolve(root, file)));
  const publicDirectories = new Set();
  for (const file of published ?? []) {
    for (let directory = path.dirname(file); isInside(root, directory); directory = path.dirname(directory)) {
      publicDirectories.add(directory);
      if (directory === root) break;
    }
  }
  const cache = new Map();
  const errors = [];
  let links = 0;
  async function document(file) {
    if (!cache.has(file)) cache.set(file, parseDocument(await readFile(file, 'utf8')));
    return cache.get(file);
  }
  for (const file of files) {
    const source = path.resolve(root, file);
    if (!isInside(root, source)) {
      errors.push({ file, line: 1, target: file, reason: 'outside repository' });
      continue;
    }
    let parsed;
    try { parsed = await document(source); }
    catch (error) {
      if (error.code !== 'ENOENT' && error.code !== 'ENOTDIR') throw error;
      errors.push({ file, line: 1, target: file, reason: 'missing source file' });
      continue;
    }
    for (const { target, line } of parsed.links) {
      if (/^(?:https?:|mailto:|tel:|data:|app:|codex:|\/\/)/i.test(target)) continue;
      links++;
      let reason;
      try {
        const hash = target.indexOf('#');
        const location = decodeURIComponent((hash < 0 ? target : target.slice(0, hash)).split('?')[0]);
        const anchor = hash < 0 ? '' : decodeURIComponent(target.slice(hash + 1));
        const resolved = location ? path.resolve(location.startsWith('/') ? root : path.dirname(source),
          location.startsWith('/') ? `.${location}` : location) : source;
        if (!isInside(root, resolved)) reason = 'outside repository';
        else {
          const info = await stat(resolved);
          if (published && !(info.isDirectory() ? publicDirectories.has(resolved) : published.has(resolved))) {
            reason = 'not a public file or directory';
          } else if (anchor && info.isFile() && path.extname(resolved).toLowerCase() === '.md' &&
              !(await document(resolved)).anchors.has(anchor)) reason = 'missing anchor';
        }
      } catch (error) {
        if (error.code === 'ENOENT' || error.code === 'ENOTDIR') reason = 'missing file';
        else if (error instanceof URIError) reason = 'invalid URL encoding';
        else throw error;
      }
      if (reason) errors.push({ file, line, target, reason });
    }
  }
  return { files: files.length, links, errors };
}

async function main() {
  const { values, positionals } = parseArgs({
    options: { json: { type: 'boolean' }, list: { type: 'boolean' } }, allowPositionals: true,
  });
  const root = fileURLToPath(new URL('../', import.meta.url));
  const publishedFiles = positionals.length ? undefined : await findPublishedFiles(root);
  const files = positionals.length ? positionals.map(file => path.relative(root, path.resolve(file)).split(path.sep).join('/')) : selectDocuments(publishedFiles);
  if (values.list) { console.log(files.join('\n')); return; }
  const result = await checkDocuments(root, files, { publishedFiles });
  if (values.json) console.log(JSON.stringify(result, null, 2));
  else {
    for (const error of result.errors) console.error(`${error.file}:${error.line}: ${error.reason}: ${error.target}`);
    console.log(`文件 ${result.files}；本地引用 ${result.links}；問題 ${result.errors.length}（不檢查外部網址）`);
  }
  process.exitCode = result.errors.length ? 1 : 0;
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) await main();
