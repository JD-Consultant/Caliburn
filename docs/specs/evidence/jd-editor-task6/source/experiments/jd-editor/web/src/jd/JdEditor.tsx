"use client";
import React, { useEffect, useState } from "react";
import equal from "fast-deep-equal";
import { Plate, PlateContent, type PlateElementProps } from "platejs/react";
import type { Operation } from "platejs";
import { TablePlugin } from "@platejs/table/react";
import { createJdReactEditor } from "@caliburn/jd-editor-native/react-profile";
import { copyJdElements } from "@caliburn/jd-editor-native/copy";
import type {
  JdDocumentValue,
  JdReadSuccess,
  JdChangeReadSuccess,
  JdText,
} from "@caliburn/jd-editor-contract";
import { DocumentView, JdNode, type DisplayNode } from "./JdNode";
import { JdLeaf } from "./JdLeaf";
export type LiveEditor = ReturnType<typeof createJdReactEditor>;
export function applySavedHead(
  editor: LiveEditor,
  baseline: JdReadSuccess,
  next: JdReadSuccess,
  change: JdChangeReadSuccess | null,
) {
  if (equal(editor.children, next.fragment))
    return true;
  if (!equal(editor.children, baseline.fragment))
    return false;
  if (
    !change?.native_operations ||
    change.before_revision_ref !== baseline.revision_ref ||
    change.after_revision_ref !== next.revision_ref
  )
    return false;
  editor.tf.withNewBatch(() =>
    editor.tf.withoutNormalizing(() => {
      for (const operation of change.native_operations ?? [])
        editor.tf.apply(operation as unknown as Operation);
    }),
  );
  editor.tf.setSplittingOnce(true);
  return equal(editor.children, next.fragment);
}
export function JdEditor({
  value,
  locked,
  saving = false,
  onEdit,
  onReady,
  onSelection,
  source,
}: {
  value: JdDocumentValue;
  locked: boolean;
  saving?: boolean;
  onEdit: (value: JdDocumentValue) => void;
  onReady: (editor: LiveEditor) => void;
  onSelection?: () => void;
  source?: (ref: string) => void;
}) {
  const [editor] = useState(() =>
    createJdReactEditor(
      value,
      Object.fromEntries(
        [
          "p",
          "h1",
          "h2",
          "h3",
          "blockquote",
          "hr",
          "ul",
          "ol",
          "li",
          "lic",
          "table",
          "tr",
          "td",
          "th",
          "jd_section",
          "jd_duty",
          "jd_task",
          "jd_outcomes",
          "jd_requirements",
          "jd_knowledge",
          "jd_skill",
        ].map((key) => [
          key,
          (props: PlateElementProps) => (
            <JdNode
              element={props.element as DisplayNode}
              attributes={props.attributes}
            >
              {props.children}
            </JdNode>
          ),
        ]),
      ),
    ),
  );
  const [current, setCurrent] = useState(value);
  const [error, setError] = useState("");
  const [selected, setSelected] = useState(false);
  useEffect(() => {
    onReady(editor);
  }, [editor, onReady]);
  function action(work: () => void) {
    if (locked) return;
    try {
      work();
      editor.tf.focus();
      setError("");
    } catch (error) {
      setError("修改尚未保存：" + String(error));
    }
  }
  return (
    <div
      className="editor-shell"
      data-react-version={React.version}
      onKeyDownCapture={(e) => {
        if (saving) e.preventDefault();
      }}
      onBeforeInputCapture={(e) => {
        if (saving) e.preventDefault();
      }}
      onPasteCapture={(e) => {
        if (saving) e.preventDefault();
      }}
      onCutCapture={(e) => {
        if (saving) e.preventDefault();
      }}
    >
      <div className="toolbar" aria-label="正文編輯工具">
        {(["bold", "italic", "underline", "strikethrough"] as const).map(
          (mark, i) => (
            <button
              type="button"
              disabled={locked}
              key={mark}
              onMouseDown={(e) => e.preventDefault()}
              onClick={() => action(() => editor.tf.toggleMark(mark))}
            >
              {["粗體", "斜體", "底線", "刪除線"][i]}
            </button>
          ),
        )}
        <button
          disabled={locked}
          onMouseDown={(e) => e.preventDefault()}
          onClick={() => action(() => editor.tf.undo())}
        >
          復原
        </button>
        <button
          disabled={locked}
          onMouseDown={(e) => e.preventDefault()}
          onClick={() => action(() => editor.tf.redo())}
        >
          重做
        </button>
        <button
          disabled={locked}
          onMouseDown={(e) => e.preventDefault()}
          onClick={() =>
            action(() => editor.getTransforms(TablePlugin).insert.tableRow())
          }
        >
          表格增列
        </button>
        <button
          disabled={locked}
          onMouseDown={(e) => e.preventDefault()}
          onClick={() =>
            action(() => editor.getTransforms(TablePlugin).remove.tableRow())
          }
        >
          表格刪列
        </button>
        <button
          disabled={locked}
          onMouseDown={(e) => e.preventDefault()}
          onClick={() =>
            action(() => {
              const entry = editor.api.block();
              if (!entry) return;
              const [node, path] = entry;
              copyJdElements(
                editor,
                [String(node.id)],
                [...path.slice(0, -1), path[path.length - 1] + 1],
              );
            })
          }
        >
          複製區塊
        </button>
      </div>
      {selected && (
        <p className="hint" role="note">
          已選取正文
        </p>
      )}
      {error && <p role="alert">{error}</p>}
      <DocumentView.Provider
        value={{
          value: current,
          source,
          link: locked
            ? undefined
            : (id, field, ids) =>
                action(() => {
                  const entry = [
                    ...editor.api.nodes({
                      at: [],
                      match: (n: { id?: unknown }) => n.id === id,
                    }),
                  ][0];
                  if (entry)
                    editor.tf.setNodes({ [field]: ids }, { at: entry[1] });
                }),
        }}
      >
        <Plate
          editor={editor}
          readOnly={locked && !saving}
          onSelectionChange={({ editor }) => {
            const range = editor.selection;
            const selected =
              !!range &&
              JSON.stringify(range.anchor) !== JSON.stringify(range.focus);
            setSelected(selected);
            if (selected) onSelection?.();
          }}
          onValueChange={({ value }) => {
            const next = value as JdDocumentValue;
            setCurrent(next);
            onEdit(next);
          }}
          renderElement={(props) => (
            <JdNode
              element={props.element as DisplayNode}
              attributes={props.attributes}
            >
              {props.children}
            </JdNode>
          )}
          renderLeaf={(props) => (
            <JdLeaf leaf={props.leaf as JdText} attributes={props.attributes}>
              {props.children}
            </JdLeaf>
          )}
        >
          <PlateContent
            aria-label="職務說明書正文"
            className="jd-editable"
            style={saving ? { pointerEvents: "none" } : undefined}
            spellCheck={false}
          />
        </Plate>
      </DocumentView.Provider>
    </div>
  );
}
