import { createRequire } from 'node:module';
import { pathToFileURL } from 'node:url';
import { isDeepStrictEqual } from 'node:util';

// P-only native computation boundary. One JSON request on stdin, one response
// on stdout. No DB, filesystem writes, persistence, custom diff/history/rebase.
// The sibling package is the existing pinned dependency installation.
// Request per PROTOCOL.md: { value, commands: [{ type, target_id, text }] }.
const requirePinned = createRequire(new URL('../jd-editor-native-probe/package.json', import.meta.url));
const record = value => value !== null && typeof value === 'object' && !Array.isArray(value);
const fixtureElementTypes = ['p', 'h1', 'h2', 'h3', 'blockquote', 'table', 'tr', 'th', 'td', 'ul', 'li', 'hr'];
function validNode(node) {
  if (!record(node)) return false;
  if (Object.hasOwn(node, 'text')) return typeof node.text === 'string' && !Object.hasOwn(node, 'children');
  return typeof node.type === 'string' && fixtureElementTypes.includes(node.type)
    && (!Object.hasOwn(node, 'id') || (typeof node.id === 'string' && node.id.length > 0))
    && Array.isArray(node.children) && node.children.length > 0 && node.children.every(validNode);
}
const failure = (code, commandIndex, message) => ({ ok: false, error: { code, command_index: commandIndex, message }, durable_effect: 'none' });
const flush = () => new Promise(resolve => setImmediate(resolve));

async function run(input) {
  if (!record(input) || !Array.isArray(input.value) || !input.value.every(validNode) || !Array.isArray(input.commands)) {
    return failure('invalid_input', null, 'Expected {value: supported Plate value, commands: array}.');
  }
  for (let index = 0; index < input.commands.length; index++) {
    const command = input.commands[index];
    if (!record(command) || typeof command.type !== 'string' || typeof command.target_id !== 'string' || command.target_id.length === 0 || typeof command.text !== 'string') {
      return failure('invalid_input', index, 'Expected command {type, target_id: nonempty string, text: string}.');
    }
    if (!['append_text', 'insert_paragraph_after'].includes(command.type)) {
      return failure('unsupported_command', index, 'Only append_text and insert_paragraph_after are supported by this fixed probe.');
    }
  }

  const { createSlateEditor, createSlatePlugin, PathApi } = await import(pathToFileURL(requirePinned.resolve('platejs')).href);
  const candidate = createSlateEditor({
    value: structuredClone(input.value),
    nodeId: { reuseId: true, initialValueIds: 'always' },
    plugins: fixtureElementTypes.filter(key => key !== 'p').map(key => createSlatePlugin({ key, node: { isElement: true } })),
  });
  const operations = [];
  const priorOnChange = candidate.onChange;
  candidate.onChange = options => {
    operations.push(...structuredClone(candidate.operations));
    priorOnChange(options);
  };
  let commandIndex = null;
  let commandFailure;
  try {
    candidate.tf.withNewBatch(() => candidate.tf.withoutNormalizing(() => {
      for (let index = 0; index < input.commands.length; index++) {
        commandIndex = index;
        const command = input.commands[index];
        const matches = [...candidate.api.nodes({ at: [], mode: 'all', match: node => node.id === command.target_id && Array.isArray(node.children) })];
        if (matches.length !== 1) {
          commandFailure = failure(matches.length ? 'target_ambiguous' : 'target_missing', index, matches.length ? 'Target ID is not unique in this candidate.' : 'Target ID does not exist in this candidate.');
          throw new Error('Discard candidate after target lookup failure.');
        }
        const [, path] = matches[0];
        if (command.type === 'append_text') {
          candidate.tf.insertText(command.text, { at: candidate.api.end(path) });
        } else {
          candidate.tf.insertNodes({ type: 'p', children: [{ text: command.text }] }, { at: PathApi.next(path) });
        }
      }
    }));
    await flush();
    return { ok: true, value: structuredClone(candidate.children), operations, changed: !isDeepStrictEqual(candidate.children, input.value) };
  } catch {
    // A failed candidate may contain partial native changes and damaged history.
    // Let its queued onChange finish, then discard it. Never return partial value.
    await flush();
    return commandFailure ?? failure('execution_failed', commandIndex, 'Native candidate execution did not complete; candidate discarded.');
  }
}

let response;
try {
  process.stdin.setEncoding('utf8');
  let source = '';
  for await (const chunk of process.stdin) source += chunk;
  let input;
  try { input = JSON.parse(source); }
  catch { response = failure('invalid_input', null, 'stdin must contain one complete JSON request.'); }
  if (!response) response = await run(input);
} catch {
  response = failure('execution_failed', null, 'Native probe boundary could not complete.');
}
process.stdout.write(JSON.stringify(response) + '\n');
