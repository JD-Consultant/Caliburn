// HTTP 契約只從正式後端匯出；型別與 validator 共用同一份 OpenAPI。
import { execFile } from 'node:child_process';
import {
  mkdir,
  mkdtemp,
  readFile,
  readdir,
  realpath,
  rm,
  writeFile,
} from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { parseArgs, promisify } from 'node:util';
import { createClient } from '@hey-api/openapi-ts';
import { Ajv2020 } from 'ajv/dist/2020.js';
import addFormats from 'ajv-formats';
import standaloneCode from 'ajv/dist/standalone/index.js';
import { format, resolveConfig } from 'prettier';
import { build } from 'vite';

const frontendRoot = fileURLToPath(new URL('..', import.meta.url));
const backendRoot = path.resolve(frontendRoot, '../backend');
const generatedRoot = path.join(frontendRoot, 'src/shared/api/generated');
const outputRoot = path.join(frontendRoot, 'output');
const execute = promisify(execFile);
const banner = '/* Generated from FastAPI OpenAPI; do not edit. */\n';
const requiredModels = [
  'AddCollaborationRequest',
  'AddConditionRequest',
  'AddDutyRequest',
  'AddKnowledgeRequest',
  'AddSkillRequest',
  'AddTaskRequest',
  'CreateWorkspaceRequest',
  'ErrorResponse',
  'HistoryPageResponse',
  'HistoryResponse',
  'JobDescriptionDifferenceResponse',
  'JobDescriptionErrorResponse',
  'JobDescriptionResponse',
  'RenameWorkspaceRequest',
  'RestoreJobDescriptionRequest',
  'UpdateCollaborationRequest',
  'UpdateConditionRequest',
  'UpdateDutyRequest',
  'UpdateJobDescriptionRequest',
  'UpdateKnowledgeRequest',
  'UpdateSkillRequest',
  'UpdateTaskRequest',
  'WorkspaceConflictResponse',
  'WorkspacePageResponse',
  'WorkspaceResponse',
];
function contractsFrom(document) {
  const models = Object.keys(document.components.schemas).sort();
  for (const name of requiredModels) {
    if (!models.includes(name))
      throw new Error(`Required HTTP schema is missing: ${name}`);
  }
  const arrays = new Map();
  for (const item of Object.values(document.paths)) {
    for (const operation of Object.values(item)) {
      for (const [status, response] of Object.entries(operation.responses ?? {})) {
        const schema = response.content?.['application/json']?.schema;
        if (!status.startsWith('2') || schema?.type !== 'array') continue;
        const model = schema.items?.$ref?.split('/').at(-1);
        if (!model || !models.includes(model))
          throw new Error('Expected component array items.');
        arrays.set(model, schema);
      }
    }
  }
  const names = [
    ...models.map((name) => `validate${name}`),
    ...[...arrays.keys()].map((name) => `validate${name}Array`),
    'validateExpectedVersionQuery',
  ];
  return { models, arrays, names };
}

async function exportOpenApi(temporary) {
  const python =
    process.env.PYTHON ||
    path.join(
      backendRoot,
      '.venv',
      process.platform === 'win32' ? 'Scripts/python.exe' : 'bin/python',
    );
  const destination = path.join(temporary, 'openapi.json');
  // 不經 shell，不讀部署設定；這個後端入口不啟 HTTP 或連資料庫。
  await execute(python, ['-m', 'caliburn.export_openapi', '--output', destination], {
    cwd: backendRoot,
    encoding: 'utf8',
    env: { ...process.env, PYTHONUTF8: '1' },
    windowsHide: true,
    timeout: 60_000,
    maxBuffer: 1024 * 1024,
  });
  const document = JSON.parse(await readFile(destination, 'utf8'));
  if (!document.openapi?.startsWith('3.1.') || !document.components?.schemas) {
    throw new Error('Expected OpenAPI 3.1 with component schemas from the backend.');
  }
  return document;
}

function compileValidators(document, contracts) {
  const validator = new Ajv2020({
    strict: true,
    // PATCH 的 anyOf.required 使用父層 properties；不改變 JSON Schema 接受集合。
    strictRequired: false,
    inlineRefs: false,
    code: { source: true },
  });
  addFormats(validator);
  const uuidSchema = document.paths['/workspaces/{workspace_id}'].get.parameters.find(
    (parameter) => parameter.in === 'path' && parameter.name === 'workspace_id',
  )?.schema;
  if (uuidSchema?.format !== 'uuid' || typeof uuidSchema.pattern !== 'string') {
    throw new Error(
      'Expected the canonical UUID pattern on the Workspace path parameter.',
    );
  }
  // ajv-formats 接受 URN；沿 HTTP 來源的 pattern，並排除 JS $ 允許的尾換行。
  validator.addFormat('uuid', new RegExp(`(?:${uuidSchema.pattern})(?![\\s\\S])`, 'u'));
  // 保留原本的 ref 位址；union 仍由 oneOf 與分支 const 驗證。
  validator.addKeyword({ keyword: 'components', schemaType: 'object', valid: true });
  validator.addKeyword({ keyword: 'discriminator', schemaType: 'object', valid: true });
  const base = 'https://caliburn.invalid/rebuild-http-openapi';
  validator.addSchema({ $id: base, components: document.components });
  for (const name of Object.keys(document.components.schemas).sort()) {
    if (!validator.getSchema(`${base}#/components/schemas/${name}`)) {
      throw new Error(`Cannot compile HTTP schema: ${name}`);
    }
  }
  const guards = {};
  for (const name of contracts.models) {
    if (!Object.hasOwn(document.components.schemas, name)) {
      throw new Error(`Required HTTP schema is missing: ${name}`);
    }
    guards[`validate${name}`] = `${base}#/components/schemas/${name}`;
  }
  for (const [model, schema] of contracts.arrays) {
    const id = `${base}/arrays/${model}`;
    validator.addSchema({ ...schema, components: document.components }, id);
    guards[`validate${model}Array`] = id;
  }
  const expectedVersion = document.paths[
    '/workspaces/{workspace_id}/job-descriptions/{job_description_id}/tasks/{task_id}'
  ].delete.parameters.find(
    (parameter) => parameter.in === 'query' && parameter.name === 'expected_version',
  )?.schema;
  if (expectedVersion?.type !== 'string' || typeof expectedVersion.pattern !== 'string') {
    throw new Error('Expected the canonical version schema on the Task DELETE query.');
  }
  // DELETE 沒有 request model，直接生成正式 query 的驗證器。
  validator.addSchema(expectedVersion, `${base}/expected-version`);
  guards.validateExpectedVersionQuery = `${base}/expected-version`;
  return standaloneCode(validator, guards);
}

async function bundleValidators(temporary, source, names) {
  await writeFile(path.join(temporary, 'validators.cjs'), source, 'utf8');
  const entry = path.join(temporary, 'validators-entry.mjs');
  const exports = names;
  await writeFile(
    entry,
    `export { ${exports.join(', ')} } from './validators.cjs';\n`,
    'utf8',
  );
  // Ajv standalone 仍可能 require runtime helpers；使用既有 Vite 產生瀏覽器 ESM。
  const result = await build({
    root: frontendRoot,
    configFile: false,
    logLevel: 'silent',
    build: {
      write: false,
      minify: true,
      lib: { entry, formats: ['es'] },
      // Rolldown 的來源註記相對這裡命名，避免隨 mkdtemp 隨機目錄改變產物。
      rolldownOptions: { cwd: temporary },
      commonjsOptions: { include: [/validators\.cjs$/, /node_modules/] },
    },
  });
  const bundles = Array.isArray(result) ? result : [result];
  const chunks = bundles
    .flatMap((bundle) => bundle.output)
    .filter((item) => item.type === 'chunk');
  const chunk = chunks[0];
  if (
    chunks.length !== 1 ||
    chunk.imports.length !== 0 ||
    chunk.dynamicImports.length !== 0 ||
    exports.some((name) => !chunk.exports.includes(name))
  ) {
    throw new Error(
      'HTTP validators must be one self-contained ESM module with all named exports.',
    );
  }
  return banner + chunk.code;
}

async function generateOutputs(document, temporary, contracts) {
  const typesRoot = path.join(temporary, 'types');
  await createClient({
    input: document,
    output: { path: typesRoot, tsConfigPath: path.join(frontendRoot, 'tsconfig.json') },
    plugins: ['@hey-api/typescript'],
    logs: { level: 'silent' },
  });
  const outputs = new Map();
  for (const name of (await readdir(typesRoot)).sort()) {
    if (!name.endsWith('.ts'))
      throw new Error(`Unexpected type generator output: ${name}`);
    outputs.set(name, await readFile(path.join(typesRoot, name), 'utf8'));
  }
  const turnEvent = document.components.schemas.TurnEvent;
  const eventNames = turnEvent.oneOf.map((branch) => {
    const name = branch.$ref.split('/').at(-1);
    const event = document.components.schemas[name].properties.event.const;
    if (typeof event !== 'string') throw new Error(`Missing SSE event name in ${name}`);
    return event;
  });
  outputs.set(
    'events.gen.ts',
    banner + `export const turnEventNames = ${JSON.stringify(eventNames)} as const;\n`,
  );
  outputs.set(
    'validators.js',
    await bundleValidators(
      temporary,
      compileValidators(document, contracts),
      contracts.names,
    ),
  );
  outputs.set(
    'validators.d.ts',
    banner +
      "import type { ValidateFunction } from 'ajv';\n" +
      `import type { ${[...contracts.models, 'JdDeleteTaskData'].join(', ')} } from './types.gen';\n\n` +
      contracts.models
        .map((name) => `export declare const validate${name}: ValidateFunction<${name}>;`)
        .join('\n') +
      [...contracts.arrays.keys()]
        .map(
          (name) =>
            `\nexport declare const validate${name}Array: ValidateFunction<${name}[]>;`,
        )
        .join('') +
      "\nexport declare const validateExpectedVersionQuery: ValidateFunction<JdDeleteTaskData['query']['expected_version']>;\n",
  );
  const style = (await resolveConfig(path.join(frontendRoot, 'package.json'))) ?? {};
  for (const [name, source] of outputs) {
    outputs.set(
      name,
      await format(source, { ...style, filepath: name, endOfLine: 'lf' }),
    );
  }
  return outputs;
}

async function readGeneratedFile(name) {
  try {
    return await readFile(path.join(generatedRoot, name), 'utf8');
  } catch (error) {
    if (error.code === 'ENOENT') return null;
    throw error;
  }
}

async function checkOutputs(outputs) {
  let existing;
  try {
    existing = await readdir(generatedRoot);
  } catch (error) {
    if (error.code !== 'ENOENT') throw error;
    existing = [];
  }
  const differences = existing.filter((name) => !outputs.has(name));
  for (const [name, expected] of outputs) {
    const current = await readGeneratedFile(name);
    // Git 在 Windows checkout 可用 CRLF；只忽略換行形式，不忽略內容差異。
    if (current?.replaceAll('\r\n', '\n') !== expected) differences.push(name);
  }
  if (differences.length) {
    throw new Error(
      `Generated HTTP contracts differ: ${differences.sort().join(', ')}. Run pnpm codegen.`,
    );
  }
}

async function removeTemporaryDirectory(temporary, resolvedOutputRoot) {
  const resolvedTemporary = await realpath(temporary);
  const relative = path.relative(resolvedOutputRoot, resolvedTemporary);
  if (!relative || relative.startsWith('..') || path.isAbsolute(relative)) {
    throw new Error(
      'Refusing to remove a contract temporary directory outside frontend/output.',
    );
  }
  await rm(resolvedTemporary, { recursive: true, force: true });
}

async function main() {
  const { values } = parseArgs({
    options: { check: { type: 'boolean', default: false } },
  });
  await mkdir(outputRoot, { recursive: true });
  const resolvedOutputRoot = await realpath(outputRoot);
  const temporary = await mkdtemp(path.join(resolvedOutputRoot, 'contracts-'));
  try {
    const document = await exportOpenApi(temporary);
    const contracts = contractsFrom(document);
    const outputs = await generateOutputs(document, temporary, contracts);
    if (values.check) {
      await checkOutputs(outputs);
    } else {
      await mkdir(generatedRoot, { recursive: true });
      for (const [name, source] of outputs) {
        await writeFile(path.join(generatedRoot, name), source, 'utf8');
      }
    }
    console.log(
      `HTTP contracts ${values.check ? 'verified' : 'generated'}: ${outputs.size} files; ` +
        `${Object.keys(document.components.schemas).length} schemas compiled; ${contracts.names.length} validators exported.`,
    );
  } finally {
    await removeTemporaryDirectory(temporary, resolvedOutputRoot);
  }
}

await main();
