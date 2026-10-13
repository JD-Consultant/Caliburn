// Pydantic/FastAPI OpenAPI → 官方 SDK／型別與 Ajv 獨立驗證器。
// 正式產物只由 Python 寫入／核對；本腳本僅使用暫存目錄。
import { mkdtemp, readFile, readdir, rm, writeFile } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { createClient } from '@hey-api/openapi-ts';
import { Ajv2020 } from 'ajv/dist/2020.js';
import addFormats from 'ajv-formats';
import standaloneCode from 'ajv/dist/standalone/index.js';
import { format } from 'prettier';
import { build } from 'vite';
import { CANONICAL_UUID_PATTERN } from '../src/shared/api/uuid.ts';

const webRoot = fileURLToPath(new URL('..', import.meta.url));
const banner = '/* Generated from FastAPI OpenAPI; do not edit. */\n';

export async function httpOutputs(document) {
  const temporary = await mkdtemp(path.join(webRoot, 'node_modules/.caliburn-http-'));
  try {
    const generated = path.join(temporary, 'http');
    await createClient({
      input: document,
      output: {
        path: generated,
        tsConfigPath: path.join(webRoot, 'tsconfig.json'),
        // 鎖版 client/core 範本不支援 exactOptionalPropertyTypes；SDK／型別仍嚴格檢查。
        // 官方 header hook 的複製範本沒有 file context。
        header: ({ defaultValue, file }) =>
          file ? defaultValue : ['// @ts-nocheck', ...defaultValue],
      },
      logs: { level: 'silent' },
      plugins: ['@hey-api/typescript', '@hey-api/client-fetch', '@hey-api/sdk'],
    });
    const validator = new Ajv2020({ code: { source: true }, inlineRefs: false, strict: true });
    addFormats(validator);
    validator.addFormat('uuid', new RegExp(CANONICAL_UUID_PATTERN.source, 'i'));
    // OpenAPI 註記容器不增加 JSON Schema 驗證語意。
    validator.addKeyword({ keyword: 'components', schemaType: 'object', valid: true });
    validator.addKeyword({ keyword: 'discriminator', schemaType: 'object', valid: true });
    const base = 'https://caliburn.invalid/http-openapi';
    validator.addSchema({ $id: base, components: document.components });
    const guards = {};
    const declarations = [];
    for (const name of Object.keys(document.components.schemas).sort()) {
      // 公開值型別使用 PascalCase；命名衝突的全限定名稱只供回應內部引用。
      if (!/^[A-Z][A-Za-z0-9]*$/.test(name)) continue;
      guards[`is${name}`] = `${base}#/components/schemas/${name}`;
      declarations.push(`import type { ${name} } from './types.gen';`);
      declarations.push(`export declare const is${name}: (value: unknown) => value is ${name};`);
    }
    const responses = [];
    for (const [route, methods] of Object.entries(document.paths)) {
      for (const [method, operation] of Object.entries(methods)) {
        if (!operation.operationId) continue;
        for (const [status, response] of Object.entries(operation.responses)) {
          if (!status.startsWith('2')) continue;
          const key = `${method.toUpperCase()} ${route}`;
          const schema = response.content?.['application/json']?.schema;
          if (!schema) {
            const mediaTypes = Object.keys(response.content ?? {});
            responses.push({
              key,
              status,
              policy: mediaTypes.length
                ? `{ kind: 'media', mediaTypes: ${JSON.stringify(mediaTypes)} }`
                : `{ kind: 'empty' }`,
            });
            continue;
          }
          const name = `response${responses.length}`;
          const reference = `${base}/responses/${name}`;
          // 解析文件內引用，不維護第二份 schema 來源。
          const anchored = JSON.parse(
            JSON.stringify(schema, (key, value) =>
              key === '$ref' && value.startsWith('#/') ? base + value : value,
            ),
          );
          validator.addSchema({ ...anchored, $id: reference });
          guards[name] = reference;
          responses.push({ key, status, policy: `{ kind: 'json', validate: ${name} }` });
        }
      }
    }
    await writeFile(path.join(temporary, 'validators.cjs'), standaloneCode(validator, guards));
    const entry = path.join(temporary, 'entry.mjs');
    const grouped = new Map();
    for (const { key, status, policy } of responses) {
      if (!grouped.has(key)) grouped.set(key, []);
      grouped.get(key).push(`${JSON.stringify(status)}: ${policy}`);
    }
    const map = [...grouped]
      .map(([key, values]) => `${JSON.stringify(key)}: { ${values.join(', ')} }`)
      .join(',\n');
    const components = Object.keys(guards).filter((name) => name.startsWith('is'));
    await writeFile(
      entry,
      `import { ${Object.keys(guards).join(', ')} } from './validators.cjs';\n` +
        `export { ${components.join(', ')} };\nexport const responsePolicies = { ${map} };\n`,
    );
    const [result] = await build({
      root: webRoot,
      configFile: false,
      logLevel: 'silent',
      build: { write: false, minify: true, lib: { entry, formats: ['es'] } },
    });
    const chunks = result.output.filter((output) => output.type === 'chunk');
    if (chunks.length !== 1 || chunks[0].imports.length || chunks[0].dynamicImports.length)
      throw new Error('Standalone validators must be one self-contained ESM module');
    const style = { singleQuote: true, printWidth: 100 };
    const outputs = {};
    for (const filename of await readdir(generated, { recursive: true })) {
      const source = path.join(generated, filename);
      if (!filename.endsWith('.ts')) continue;
      outputs[`http/${filename.replaceAll(path.sep, '/')}`] = await format(
        await readFile(source, 'utf8'),
        { ...style, parser: 'typescript' },
      );
    }
    outputs['http/validators.js'] =
      banner + (await format(chunks[0].code, { ...style, parser: 'babel' }));
    declarations.push(
      `type ResponsePolicy =
        | { readonly kind: 'json'; readonly validate: (value: unknown) => boolean }
        | { readonly kind: 'empty' }
        | { readonly kind: 'media'; readonly mediaTypes: readonly string[] };
      export declare const responsePolicies: Readonly<Record<string, Readonly<Record<number, ResponsePolicy>>>>;`,
    );
    outputs['http/validators.d.ts'] =
      banner + (await format(declarations.join('\n'), { ...style, parser: 'typescript' }));
    return outputs;
  } finally {
    await rm(temporary, { recursive: true, force: true });
  }
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  let input = '';
  for await (const chunk of process.stdin) input += chunk;
  process.stdout.write(JSON.stringify(await httpOutputs(JSON.parse(input))));
}
