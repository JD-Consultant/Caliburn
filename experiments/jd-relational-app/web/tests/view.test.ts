import assert from "node:assert/strict";
import { test } from "node:test";
import type { ReadPage, ReadRecord } from "../../src/jd_relational/generated/jd-read.ts";
import { containerKey, fieldKey, fieldLabels, kindLabels, projectView } from "../src/lib/view.ts";

const ids = {
  duty: "00000000-0000-4000-8000-000000000001",
  first: "00000000-0000-4000-8000-000000000002",
  second: "00000000-0000-4000-8000-000000000003",
  knowledge: "00000000-0000-4000-8000-000000000004",
};

test('container ancestors keep stable keys across revisions without decoding refs', () => {
  const original = projectView(page('one'));
  const next = projectView(page('two'));
  assert.deepEqual(original.containers.map(container => containerKey(original, container)),
    next.containers.map(container => containerKey(next, container)));
  assert.equal(containerKey(original, original.containers[1]), JSON.stringify(['duties_tasks', ids.duty, 'task']));
  assert.equal(containerKey(original, original.containers[0]), JSON.stringify(['duties_tasks', null, 'duty']));
});

function page(revision = "one"): ReadPage {
  const r = (key: string) => `${revision}:opaque:${key}`;
  const records: ReadRecord[] = [
    ...(["profile", "purpose", "duties_tasks", "knowledge", "skills", "conditions"] as const).map(
      (section_key) => ({ type: "section" as const, section_ref: r(section_key), section_key, title: section_key }),
    ),
    { type: "container", container_ref: r("duties"), section_ref: r("duties_tasks"), owner_ref: null, child_kind: "duty" },
    { type: "container", container_ref: r("tasks"), section_ref: r("duties_tasks"), owner_ref: r("duty"), child_kind: "task" },
    { type: "container", container_ref: r("knowledge-list"), section_ref: r("knowledge"), owner_ref: null, child_kind: "knowledge" },
    { type: "field", field_ref: r("title-field"), section_ref: r("profile"), item_ref: null, name: "job_title", value: null },
    { type: "field", field_ref: r("purpose-field"), section_ref: r("purpose"), item_ref: null, name: "purpose", value: "負責實際工作。" },
    { type: "item", item_ref: r("duty"), item_id: ids.duty, section_ref: r("duties_tasks"), container_ref: r("duties"), kind: "duty", position: 0 },
    { type: "item", item_ref: r("first"), item_id: ids.first, section_ref: r("duties_tasks"), container_ref: r("tasks"), kind: "task", position: 0 },
    { type: "item", item_ref: r("second"), item_id: ids.second, section_ref: r("duties_tasks"), container_ref: r("tasks"), kind: "task", position: 1 },
    { type: "item", item_ref: r("knowledge-item"), item_id: ids.knowledge, section_ref: r("knowledge"), container_ref: r("knowledge-list"), kind: "knowledge", position: 0 },
    { type: "field", field_ref: r("first-name"), section_ref: r("duties_tasks"), item_ref: r("first"), name: "name", value: "同名任務" },
    { type: "field", field_ref: r("first-description"), section_ref: r("duties_tasks"), item_ref: r("first"), name: "description", value: "修正🙂\n同字／同字" },
    { type: "field", field_ref: r("second-name"), section_ref: r("duties_tasks"), item_ref: r("second"), name: "name", value: "同名任務" },
    { type: "field", field_ref: r("second-description"), section_ref: r("duties_tasks"), item_ref: r("second"), name: "description", value: null },
    { type: "task_capability", section_ref: r("duties_tasks"), task_ref: r("first"), capability_ref: r("knowledge-item"), capability_kind: "knowledge", position: 0 },
    { type: "source", section_ref: r("profile"), target_ref: r("title-field"), related_capability_ref: null, source_ref: "same-opaque-source", basis_status: "current", readability: "not_checked" },
    { type: "source", section_ref: r("duties_tasks"), target_ref: r("first"), related_capability_ref: r("knowledge-item"), source_ref: "same-opaque-source", basis_status: "needs_recheck", readability: "unavailable" },
  ];
  return { format_version: 2, view: "current", access: "current", revision_ref: r("revision"), records,
    start_index: 0, total_records: records.length, has_more: false, next_cursor: null, oversized_unit: false };
}

function record<T extends ReadRecord["type"]>(value: ReadPage, type: T, index = 0): Extract<ReadRecord, { type: T }> {
  return value.records.filter((item) => item.type === type)[index] as Extract<ReadRecord, { type: T }>;
}

test("projects six sections and opaque associations without changing input or filling text", () => {
  const input = page();
  const before = structuredClone(input);
  const view = projectView(input);
  assert.equal(view.revisionRef, input.revision_ref);
  assert.equal(view.sections.length, 6);
  assert.equal(view.items.length, 4);
  assert.equal(view.containers.length, 3);
  assert.equal(view.relations.length, 1);
  assert.deepEqual(view.items.find((item) => item.item_id === ids.first)?.fields.map((field) => field.value), ["同名任務", "修正🙂\n同字／同字"]);
  assert.equal(view.items.find((item) => item.item_id === ids.second)?.fields[1].value, null);
  assert.deepEqual(view.items.find((item) => item.item_id === ids.duty)?.fields, []);
  assert.deepEqual(input, before);
});

test("field identity survives revision ref changes; profile fields have null itemId", () => {
  const first = projectView(page("one"));
  const next = projectView(page("two"));
  assert.deepEqual(first.fields.map((field) => field.key), next.fields.map((field) => field.key));
  assert.notEqual(first.fields[0].field_ref, next.fields[0].field_ref);
  assert.equal(first.fields[0].itemId, null);
  assert.equal(first.fields[0].key, JSON.stringify([null, "job_title"]));
  assert.equal(fieldKey(ids.first, "description"), JSON.stringify([ids.first, "description"]));
});

test("reordered records and identical text never choose the wrong item", () => {
  const input = page();
  input.records.reverse();
  const first = record(input, "item", 1);
  first.position = 0;
  const view = projectView(input);
  assert.equal(view.items.find((item) => item.item_id === ids.first)?.fields.find((field) => field.name === "description")?.value, "修正🙂\n同字／同字");
  assert.equal(view.items.find((item) => item.item_id === ids.second)?.fields.find((field) => field.name === "description")?.value, null);
  assert.deepEqual(view.items.map((item) => item.item_ref), input.records.filter((item) => item.type === "item").map((item) => item.item_ref));
});

for (const type of ["section", "container", "item", "field", "task_capability"] as const) {
  test(`rejects duplicate ${type} records`, () => {
    const input = page();
    input.records.push(structuredClone(record(input, type)));
    input.total_records = input.records.length;
    assert.throws(() => projectView(input), { message: "invalid_read_view" });
  });
}

test("rejects duplicate stable item, section and field identities behind different refs", () => {
  for (const change of [
    (input: ReadPage) => { record(input, "item", 1).item_id = record(input, "item").item_id; },
    (input: ReadPage) => { record(input, "section", 1).section_key = record(input, "section").section_key; },
    (input: ReadPage) => { record(input, "field", 3).name = record(input, "field", 2).name; },
    (input: ReadPage) => { record(input, "field").field_ref = record(input, "item").item_ref; },
  ]) {
    const input = page(); change(input);
    assert.throws(() => projectView(input), { message: "invalid_read_view" });
  }
});

test("rejects every dangling reference without exposing its contents", () => {
  const secret = "private-missing-reference";
  for (const change of [
    (input: ReadPage) => { record(input, "container").section_ref = secret; },
    (input: ReadPage) => { record(input, "container", 1).owner_ref = secret; },
    (input: ReadPage) => { record(input, "item").section_ref = secret; },
    (input: ReadPage) => { record(input, "item").container_ref = secret; },
    (input: ReadPage) => { record(input, "field").section_ref = secret; },
    (input: ReadPage) => { record(input, "field", 2).item_ref = secret; },
    (input: ReadPage) => { record(input, "task_capability").task_ref = secret; },
    (input: ReadPage) => { record(input, "task_capability").capability_ref = secret; },
    (input: ReadPage) => { record(input, "source").target_ref = secret; },
    (input: ReadPage) => { record(input, "source", 1).related_capability_ref = secret; },
  ]) {
    const input = page(); change(input);
    assert.throws(() => projectView(input), { message: "invalid_read_view" });
  }
});

test("rejects contradictory page associations rather than silently rendering wrong groups", () => {
  for (const change of [
    (input: ReadPage) => { record(input, "field", 2).section_ref = record(input, "section").section_ref; },
    (input: ReadPage) => { record(input, "item", 1).container_ref = record(input, "container").container_ref; },
    (input: ReadPage) => { record(input, "task_capability").capability_kind = "skill"; },
    (input: ReadPage) => { input.records = input.records.filter((item) => item.type !== "task_capability"); input.total_records = input.records.length; },
  ]) {
    const input = page(); change(input);
    assert.throws(() => projectView(input), { message: "invalid_read_view" });
  }
});

test("rejects incomplete page envelopes and history indexes; accepts complete historical content", () => {
  for (const patch of [ { has_more: true }, { next_cursor: "cursor" }, { start_index: 1 }, { total_records: null }, { total_records: 999 }, { format_version: 1 } ]) {
    assert.throws(() => projectView({ ...page(), ...patch }), { message: "invalid_read_view" });
  }
  const history = page(); history.access = "history"; history.view = "history";
  assert.equal(projectView(history).items.length, 4);
  const index = page(); index.records = [{ type: "revision", revision_ref: "history-ref", revision_number: 1, origin: "initial", created_at: "2026-09-13T00:00:00Z", change_ref: null, operation_ref: null }]; index.total_records = 1;
  assert.throws(() => projectView(index), { message: "invalid_read_view" });
});

test("all generated field and item kinds have Chinese labels", () => {
  assert.equal(fieldLabels.job_title, "職稱");
  assert.equal(fieldLabels.description, "說明");
  assert.equal(kindLabels.requirement, "要求");
  assert.equal(Object.keys(fieldLabels).length, 9);
  assert.equal(Object.keys(kindLabels).length, 12);
});
