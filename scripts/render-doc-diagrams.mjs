/** 由維護文件的圖片引用發現中央圖源；同一圖源只產生一組圖片。 */
import { createServer } from 'node:http';
import { createRequire } from 'node:module';
import { mkdir, readFile, readdir, rename, writeFile } from 'node:fs/promises';
import { createHash, randomUUID } from 'node:crypto';
import path from 'node:path';
import { parseArgs } from 'node:util';
import { findDocuments, parseDocument } from './documentation.mjs';

const { values } = parseArgs({ options: {
  'mermaid-dir': { type: 'string' },
  browser: { type: 'string' },
  output: { type: 'string', default: '.tmp/doc-diagrams' },
  reports: { type: 'boolean', default: false },
  select: { type: 'string', multiple: true },
  list: { type: 'boolean', default: false },
} });
const root = process.cwd();
const output = path.resolve(values.output);
if (!output.startsWith(root + path.sep)) throw new Error('輸出須位於工作區內。');
const diagramRoot = path.resolve('docs/diagrams');
const portable = file => path.relative(root, file).replaceAll('\\', '/');
const sha256 = content => createHash('sha256').update(content).digest('hex');
async function artifactHash(file) {
  try { return sha256(await readFile(file)); }
  catch (error) { if (error.code === 'ENOENT') return null; throw error; }
}
async function filesUnder(directory) {
  const files = [];
  for (const entry of (await readdir(directory, { withFileTypes: true })).sort((a, b) => a.name.localeCompare(b.name))) {
    const file = path.join(directory, entry.name);
    if (entry.isDirectory()) files.push(...await filesUnder(file));
    else if (entry.isFile()) files.push(file);
  }
  return files;
}
async function maintainedDocuments() {
  // An index inside the diagram directory must not make an orphaned source look used.
  return (await findDocuments(root)).filter(file => !file.startsWith('docs/diagrams/')).map(file => path.resolve(root, file));
}
async function writeArtifact(file, content) {
  const bytes = Buffer.isBuffer(content) ? content : Buffer.from(content, 'utf8');
  try {
    if ((await readFile(file)).equals(bytes)) return;
  } catch (error) {
    if (error.code !== 'ENOENT') throw error;
  }
  // 先寫完整新檔再替換，避免 Windows 開啟既有圖片做截斷寫入時失敗。
  const pendingFile = `${file}.${randomUUID()}.tmp`;
  await writeFile(pendingFile, bytes, { flag: 'wx' });
  await rename(pendingFile, file);
}
const bySource = new Map();
const inlineFiles = [];
for (const absoluteFile of await maintainedDocuments()) {
  const file = portable(absoluteFile);
  const body = await readFile(absoluteFile, 'utf8');
  const parsed = parseDocument(body);
  if (parsed.inlineDiagram) inlineFiles.push(file);
  for (const [index, reference] of parsed.images.entries()) {
    if (/^(?:[a-z][a-z\d+.-]*:|\/\/)/i.test(reference.target)) continue;
    const imagePath = decodeURIComponent(reference.target.split(/[?#]/)[0]);
    if (!/\.(?:png|svg)$/i.test(imagePath)) continue;
    const png = imagePath.startsWith('/') ? path.resolve(root, `.${imagePath}`) : path.resolve(path.dirname(absoluteFile), imagePath);
    if (!png.startsWith(diagramRoot + path.sep)) continue;
    const sourceFile = png.replace(/\.(?:png|svg)$/, '.mmd');
    const references = bySource.get(sourceFile) ?? [];
    references.push({ file, index: index + 1, title: reference.title });
    bySource.set(sourceFile, references);
  }
}
if (inlineFiles.length) throw new Error('圖源須移至 docs/diagrams，正文只引用圖片：\n' + inlineFiles.join('\n'));
const sources = (await filesUnder(diagramRoot)).filter(file => file.endsWith('.mmd'));
const unused = sources.filter(file => !bySource.has(file));
if (unused.length) throw new Error('中央圖源缺少正文圖片引用：\n' + unused.map(portable).join('\n'));
const allInputs = [];
const markers = new Map();
for (const [sourceFile, references] of bySource) {
  const source = await readFile(sourceFile, 'utf8');
  const relativeSource = portable(sourceFile);
  const expectedOwner = 'docs/' + path.relative(diagramRoot, path.dirname(sourceFile)).replaceAll('\\', '/') + '.md';
  const owner = references.find(reference => reference.file === expectedOwner) ?? references[0];
  const marker = source.match(/^%% diagram: (.+)$/m)?.[1].trim();
  if (marker && markers.has(marker)) throw new Error('圖形 marker 重複：' + marker + '（' + markers.get(marker) + '、' + relativeSource + '）');
  if (marker) markers.set(marker, relativeSource);
  // 既有核心圖保留原 ID，避免只因擴充發現範圍而重寫輸出。
  const core = /^docs\/(architecture|implementation)\/([^/]+)\.md$/.exec(owner.file);
  const id = core ? core[1] + '-' + core[2] + '-' + owner.index
    : 'doc-' + path.relative(diagramRoot, sourceFile).replace(/\.mmd$/, '').replace(/[^a-zA-Z0-9_-]/g, '-');
  allInputs.push({ file: owner.file, sourceFile: relativeSource, source, sourceSha256: sha256(source), index: owner.index, marker, id,
    title: source.match(/^%% title: (.+)$/m)?.[1].trim() ?? owner.title,
    legend: source.match(/^%% legend: (.+)$/m)?.[1].trim() ?? '',
    references, target: path.dirname(sourceFile), basename: path.basename(sourceFile, '.mmd') });
}
const selectedPaths = (values.select ?? []).map(value => path.resolve(value));
const matchesSelection = (input, selected) => [path.resolve(input.sourceFile), ...input.references.map(reference => path.resolve(reference.file))]
  .some(file => file === selected || file.startsWith(selected + path.sep));
for (const selected of selectedPaths) {
  if (!allInputs.some(input => matchesSelection(input, selected))) throw new Error('--select 未找到圖源或引用文件：' + selected);
}
const inputs = allInputs.filter(input => !selectedPaths.length || selectedPaths.some(selected => matchesSelection(input, selected)));
if (values.reports) console.warn('--reports 保留相容：報告圖已納入預設發現範圍；不另產生第二份圖片。');
if (values.list) {
  const inventory = await Promise.all(inputs.map(async ({ source, target, ...input }) => ({ ...input,
    existingSvgSha256: await artifactHash(path.join(target, `${input.basename}.svg`)),
    existingPngSha256: await artifactHash(path.join(target, `${input.basename}.png`)),
  })));
  console.log(JSON.stringify({ discovered: allInputs.length, selected: inputs.length,
    diagrams: inventory }, null, 2));
  process.exit(0);
}
if (!values['mermaid-dir']) throw new Error('請提供 --mermaid-dir（Mermaid dist 目錄）；--browser 可指定既有 Chromium。先用 --list 檢查圖源與引用。');
const mermaidDir = path.resolve(values['mermaid-dir']);
const require = createRequire(path.join(root, 'apps/web/package.json'));
const { chromium } = require('@playwright/test');
const version = JSON.parse(await readFile(path.join(mermaidDir, '../package.json'), 'utf8')).version;
if (version !== '12.1.0') throw new Error('文件渲染鎖定 Mermaid 12.1.0，目前版本：' + version);

await mkdir(output, { recursive: true });
const server = createServer(async (request, response) => {
  try {
    const name = decodeURIComponent(new URL(request.url, 'http://localhost').pathname.slice(1));
    if (!name) { response.setHeader('Content-Type', 'text/html; charset=utf-8'); response.end('<html lang="zh-Hant"><body></body></html>'); return; }
    const file = path.resolve(mermaidDir, name);
    if (!file.startsWith(mermaidDir + path.sep)) { response.writeHead(403).end(); return; }
    response.setHeader('Content-Type', 'text/javascript');
    response.end(await readFile(file));
  } catch { response.writeHead(404).end(); }
});
await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
let browser;
const results = [];
try {
  browser = await chromium.launch({ headless: true,
    executablePath: values.browser ? path.resolve(values.browser) : chromium.executablePath() });
  const page = await browser.newPage({ viewport: { width: 1600, height: 1100 }, deviceScaleFactor: 2 });
  await page.goto(`http://127.0.0.1:${server.address().port}/`);
  await page.evaluate(async () => {
    window.mermaid = (await import('/mermaid.esm.min.mjs')).default;
    window.mermaid.initialize({ startOnLoad: false, theme: 'neutral', securityLevel: 'strict',
      fontFamily: 'Microsoft JhengHei, Noto Sans CJK TC, sans-serif' });
  });
  for (const input of inputs) {
    const result = await page.evaluate(async ({ source, id, title, legend }) => {
      document.body.innerHTML = '';
      await window.mermaid.parse(source);
      const { svg } = await window.mermaid.render(id, source);
      document.body.innerHTML = svg;
      const diagram = document.querySelector('svg');
      const box = diagram.viewBox.baseVal;
      const width = Math.max(720, box.width + 32);
      const ns = 'http://www.w3.org/2000/svg';
      const frame = document.createElementNS(ns, 'svg');
      const addText = (text, y, size) => {
        const node = document.createElementNS(ns, 'text');
        node.setAttribute('x', '16'); node.setAttribute('y', String(y));
        node.setAttribute('font-family', 'Microsoft JhengHei, Noto Sans CJK TC, sans-serif');
        node.setAttribute('font-size', String(size)); node.setAttribute('fill', '#202124');
        node.textContent = text; frame.append(node); return node;
      };
      frame.setAttribute('xmlns', ns);
      frame.style.background = 'white';
      const label = addText(title, 28, 18);
      document.body.append(frame);
      let frameWidth = Math.max(width, label.getComputedTextLength() + 32);
      let headerHeight = 48;
      if (legend) {
        const lines = legend.match(/.{1,36}/gu) ?? [];
        for (const line of lines) {
          const lineNode = addText(line, headerHeight + 6, 13);
          frameWidth = Math.max(frameWidth, lineNode.getComputedTextLength() + 32);
          headerHeight += 21;
        }
        headerHeight += 12;
      }
      diagram.setAttribute('x', String((frameWidth - box.width) / 2));
      diagram.setAttribute('y', String(headerHeight));
      diagram.setAttribute('width', String(box.width));
      diagram.setAttribute('height', String(box.height));
      diagram.style.maxWidth = 'none';
      frame.append(diagram);
      const height = box.height + headerHeight + 16;
      frame.setAttribute('width', String(frameWidth)); frame.setAttribute('height', String(height));
      frame.setAttribute('viewBox', `0 0 ${frameWidth} ${height}`);
      const serialized = new XMLSerializer().serializeToString(frame);
      if (new DOMParser().parseFromString(serialized, 'image/svg+xml').querySelector('parsererror')) throw new Error('Invalid SVG XML');
      const img = new Image();
      img.src = 'data:image/svg+xml;base64,' + btoa(unescape(encodeURIComponent(serialized)));
      await img.decode();
      document.body.replaceChildren(img);
      return { svg: serialized, width: img.naturalWidth, height: img.naturalHeight };
    }, input);
    const basename = input.basename ?? input.id;
    await writeArtifact(path.join(input.target, `${basename}.svg`), result.svg);
    const png = await page.locator('img').screenshot({ type: 'png' });
    await writeArtifact(path.join(input.target, `${basename}.png`), png);
    results.push({ file: input.file, sourceFile: input.sourceFile, sourceSha256: input.sourceSha256,
      svgSha256: sha256(result.svg), pngSha256: sha256(png), references: input.references, index: input.index, marker: input.marker, id: input.id,
      width: result.width, height: result.height, png: path.relative(root, path.join(input.target, `${basename}.png`)).replaceAll('\\', '/') });
  }
  await writeFile(path.join(output, 'manifest.json'), JSON.stringify({ generatedAt: new Date().toISOString(), mermaid: version,
    rendererSha256: await artifactHash(path.join(root, 'scripts/render-doc-diagrams.mjs')),
    discovered: allInputs.length, selected: inputs.length, diagrams: results }, null, 2));
  console.log(JSON.stringify({ mermaid: version, rendered: results.length, output }));
} finally {
  await browser?.close();
  await new Promise(resolve => server.close(resolve));
}
