import { Ajv2020 } from "ajv/dist/2020.js";
import schema from "@caliburn/jd-editor-contract/schema" with { type: "json" };
import type {
  JdDocumentValue,
  JdPlateTransformFailure,
} from "@caliburn/jd-editor-contract";
export class JdInputError extends Error {
  constructor(
    public code: string,
    message: string,
  ) {
    super(message);
  }
}
export function assertJson(
  value: unknown,
  ancestors = new Set<object>(),
): void {
  if (value === null || typeof value === "string" || typeof value === "boolean")
    return;
  if (typeof value === "number" && Number.isFinite(value)) return;
  if (typeof value !== "object" || ancestors.has(value))
    throw new JdInputError(
      "invalid_input",
      "Expected a finite ordinary JSON value.",
    );
  if (
    !Array.isArray(value) &&
    Object.getPrototypeOf(value) !== Object.prototype
  )
    throw new JdInputError(
      "invalid_input",
      "Only plain JSON objects are supported.",
    );
  ancestors.add(value);
  if (Array.isArray(value)) {
    for (let i = 0; i < value.length; i++) {
      if (!(i in value))
        throw new JdInputError(
          "invalid_input",
          "Sparse arrays are not supported.",
        );
      assertJson(value[i], ancestors);
    }
  } else for (const x of Object.values(value)) assertJson(x, ancestors);
  ancestors.delete(value);
}
const ajv = new Ajv2020({
  strict: false,
  allErrors: false,
  coerceTypes: false,
  useDefaults: false,
  removeAdditional: false,
});
ajv.addSchema(schema);
const validators = new Map<string, ReturnType<typeof ajv.compile>>();
export function assertContract(name: string, value: unknown): void {
  assertJson(value);
  let check = validators.get(name);
  if (!check) {
    check = ajv.compile({ $ref: `${schema.$id}#/$defs/${name}` });
    validators.set(name, check);
  }
  if (!check(value))
    throw new JdInputError(
      "invalid_input",
      `${name}: ${ajv.errorsText(check.errors).slice(0, 400)}`,
    );
}
export function assertJdValue(
  value: unknown,
): asserts value is JdDocumentValue {
  assertContract("JdDocumentValue", value);
  const ids = new Map<string, Record<string, unknown>>();
  const tasks: Record<string, unknown>[] = [];
  const walk = (nodes: unknown[]) => {
    for (const raw of nodes) {
      const n = raw as Record<string, unknown>;
      if (!("children" in n)) continue;
      const id = n.id as string;
      if (ids.has(id))
        throw new JdInputError("duplicate_id", `Duplicate element ID: ${id}`);
      ids.set(id, n);
      if (n.type === "jd_task") tasks.push(n);
      if (n.attributes) {
        const attrs = n.attributes as Record<string, string>;
        for (const [key, html] of [
          ["colSpan", "colspan"],
          ["rowSpan", "rowspan"],
        ])
          if (
            n[key] !== undefined &&
            attrs[html] !== undefined &&
            n[key] !== Number(attrs[html])
          )
            throw new JdInputError(
              "invalid_span",
              `Conflicting span on ${id}.`,
            );
      }
      walk(n.children as unknown[]);
    }
  };
  walk(value as unknown[]);
  for (const task of tasks)
    for (const [field, type] of [
      ["knowledge_ids", "jd_knowledge"],
      ["skill_ids", "jd_skill"],
    ])
      for (const id of (task[field] ?? []) as string[]) {
        const item = ids.get(id);
        if (!item)
          throw new JdInputError(
            "referenced_item",
            `Task ${task.id} references missing item ${id}.`,
          );
        if (item.type !== type)
          throw new JdInputError(
            "invalid_relation_kind",
            `Task ${task.id} references wrong item kind ${id}.`,
          );
      }
}
export function failure(
  error: unknown,
  index: number | null = null,
): JdPlateTransformFailure {
  return {
    ok: false,
    error: {
      code: error instanceof JdInputError ? error.code : "engine_failed",
      message:
        error instanceof JdInputError
          ? error.message
          : "Native editor operation failed.",
      command_index: index,
    },
  };
}
