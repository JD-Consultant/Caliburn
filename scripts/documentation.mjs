/** Shared scope and Markdown observations for offline documentation maintenance. */
import { execFileSync } from 'node:child_process';
import { stat } from 'node:fs/promises';
import path from 'node:path';
import { unified } from 'unified';
import remarkParse from 'remark-parse';
import remarkGfm from 'remark-gfm';
import GithubSlugger from 'github-slugger';

const parser = unified().use(remarkParse).use(remarkGfm);
const evidenceIndexes = new Set([
  'docs/experiments/README.md', 'docs/experiments/artifact-storage.md',
  'docs/experiments/product-validation/README.md', 'docs/experiments/engineering/README.md',
]);

export function selectDocuments(files) {
  return files.filter(file => file.startsWith('docs/') && file.endsWith('.md') &&
    !file.startsWith('docs/archive/') &&
    (!file.startsWith('docs/adr/') || file === 'docs/adr/README.md') &&
    !file.startsWith('docs/plans/evidence/') &&
    (!file.startsWith('docs/experiments/') || evidenceIndexes.has(file)));
}

export async function findDocuments(root) {
  const candidates = execFileSync('git', ['ls-files', '--cached', '--others', '--exclude-standard', '-z', '--', 'docs'],
    { cwd: root, encoding: 'utf8', maxBuffer: 16 * 1024 * 1024 }).split('\0').filter(Boolean);
  const files = selectDocuments([...new Set(candidates)]).sort();
  const existing = await Promise.all(files.map(async file => {
    try { return (await stat(path.resolve(root, file))).isFile(); }
    catch (error) { if (error.code === 'ENOENT' || error.code === 'ENOTDIR') return false; throw error; }
  }));
  return files.filter((_, index) => existing[index]);
}

function visit(node, action) {
  action(node);
  for (const child of node.children ?? []) visit(child, action);
}

function headingText(node) {
  if (node.type === 'html') return '';
  return node.value ?? node.alt ?? (node.children ?? []).map(headingText).join('');
}

export function parseDocument(body) {
  const tree = parser.parse(body);
  const anchors = new Set();
  const links = [];
  const images = [];
  const definitions = new Map();
  const slugger = new GithubSlugger();
  let inlineDiagram = false;
  visit(tree, node => {
    if (node.type === 'definition' && !definitions.has(node.identifier)) definitions.set(node.identifier, node.url);
  });
  visit(tree, node => {
    if (node.type === 'heading') anchors.add(slugger.slug(headingText(node)));
    if (['link', 'image', 'definition'].includes(node.type)) {
      links.push({ target: node.url, line: node.position.start.line });
    }
    if (node.type === 'image' || node.type === 'imageReference') {
      const target = node.type === 'image' ? node.url : definitions.get(node.identifier);
      if (target) images.push({ target, title: node.alt ?? '', line: node.position.start.line });
    }
    if (node.type === 'code' && node.lang === 'mermaid') inlineDiagram = true;
    // Raw HTML is observed, never executed; attributes follow the repo's quoted markup.
    if (node.type === 'html') {
      for (const match of node.value.matchAll(/\s(?:id|name)\s*=\s*["']([^"']+)["']/gi)) anchors.add(match[1]);
      for (const match of node.value.matchAll(/\s(?:href|src)\s*=\s*["']([^"']+)["']/gi)) {
        links.push({ target: match[1], line: node.position.start.line });
      }
      for (const match of node.value.matchAll(/<img\b[^>]*>/gi)) {
        const target = match[0].match(/\ssrc\s*=\s*["']([^"']+)["']/i)?.[1];
        const title = match[0].match(/\salt\s*=\s*["']([^"']*)["']/i)?.[1] ?? '';
        if (target) images.push({ target, title, line: node.position.start.line });
      }
    }
  });
  return { anchors, links, images, inlineDiagram };
}
