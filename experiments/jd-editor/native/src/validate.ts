import { isDeepStrictEqual } from "node:util";
import type {
  JdDocumentValue,
  JdPlateValidateValueRequest,
  JdPlateValidateValueResult,
  JdPlateTransformSuccess,
} from "@caliburn/jd-editor-contract";
import { createJdEditor, capture, type JdEditor } from "./profile.js";
import { assertContract, assertJdValue, failure } from "./schema.js";
export { assertContract, assertJdValue } from "./schema.js";
export function result(
  editor: JdEditor,
  before: JdDocumentValue,
  operations: unknown[],
  affectedIds: ReadonlySet<string>,
): JdPlateTransformSuccess {
  assertJdValue(editor.children);
  const out = {
    ok: true as const,
    changed: !isDeepStrictEqual(before, editor.children),
    value: structuredClone(editor.children) as JdDocumentValue,
    native_operations: JSON.parse(JSON.stringify(operations)),
    affected_element_ids: isDeepStrictEqual(before, editor.children)
      ? []
      : [...affectedIds],
  };
  assertContract("JdPlateTransformResult", out);
  return out;
}
export function validateJdValue(
  request: JdPlateValidateValueRequest,
): JdPlateValidateValueResult {
  try {
    assertContract("JdPlateValidateValueRequest", request);
    const editor = createJdEditor(request.value);
    const c = capture(editor);
    editor.tf.normalize({ force: true });
    c.flush();
    return result(editor, request.value, c.operations, c.affectedIds);
  } catch (e) {
    return failure(e);
  }
}
