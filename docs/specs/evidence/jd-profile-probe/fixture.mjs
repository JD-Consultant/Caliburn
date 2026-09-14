import { before as original } from '../jd-editor-ui-probe/fixture.mjs';

export const clone = structuredClone;
export const source = clone(original);
// Only these four deliberately synthetic fields are absent from the proposed
// product profile. Preserve the previous fixture and all its counterexamples.
for (const key of ['score', 'approved', 'provenance', 'obsolete']) delete source[12][key];
const wrapper = (type, id, children, props = {}) => ({ type, id, ...props, children });
const task = (number, start) => wrapper('jd_task', `task-${number}`, clone(source.slice(start, start + 3)), {
  source_refs: [`fixture-source:task-${number}`],
});
const duty = (number, start, tasks) => wrapper('jd_duty', `duty-${number}`, [clone(source[start]), ...tasks]);
const section = (kind, children) => wrapper('jd_section', `section-${kind}`, children, { section_kind: kind });

// Exact, explicit r2 layout; not a Markdown or arbitrary-document importer.
export const fixture = [
  ...clone(source.slice(0, 2)),
  section('identity', clone(source.slice(2, 4))),
  section('purpose', clone(source.slice(4, 6))),
  section('work', [clone(source[6]),
    duty(1, 7, [task(1, 8), task(2, 11)]),
    duty(2, 14, [task(3, 15), task(4, 18)]),
    duty(3, 21, [task(5, 22), task(6, 25)]),
    duty(4, 28, [task(7, 29), task(8, 32)]),
  ]),
  section('knowledge', clone(source.slice(35, 37))),
  section('skills', clone(source.slice(37, 39))),
  section('conditions', clone(source.slice(39, 41))),
  ...clone(source.slice(41)),
];
export const types = ['p', 'h1', 'h2', 'h3', 'blockquote', 'table', 'tr', 'th', 'td', 'ul', 'li', 'hr', 'jd_section', 'jd_duty', 'jd_task'];
export const paragraph = (id, text) => ({ type: 'p', id, children: [{ text }] });
export const textOf = node => typeof node.text === 'string' ? node.text : node.children.map(textOf).join('');
export const allText = value => value.map(textOf).join('');
export const sourceLabels = Object.fromEntries(Array.from({ length: 8 }, (_, index) => [
  `fixture-source:task-${index + 1}`, `F01 虛構情境：任務 ${index + 1}`,
]));

// Test oracle only: the new wrappers/references must not lose any old content.
export function unwrappedOracle(value) {
  return value.flatMap(node => {
    if (!node.children) return [clone(node)];
    if (['jd_section', 'jd_duty', 'jd_task'].includes(node.type)) return unwrappedOracle(node.children);
    const result = clone(node);
    delete result.source_refs;
    result.children = unwrappedOracle(result.children);
    return [result];
  });
}
