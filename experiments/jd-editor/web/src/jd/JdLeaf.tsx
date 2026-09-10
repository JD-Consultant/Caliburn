import React from "react";
import type { JdText } from "@caliburn/jd-editor-contract";
export function JdLeaf({
  leaf,
  children,
  attributes = {},
}: {
  leaf: JdText & { diffOperation?: { type: string } };
  children: React.ReactNode;
  attributes?: React.HTMLAttributes<HTMLSpanElement>;
}) {
  let body = children;
  if (leaf.bold) body = <strong>{body}</strong>;
  if (leaf.italic) body = <em>{body}</em>;
  if (leaf.underline) body = <u>{body}</u>;
  if (leaf.strikethrough) body = <s>{body}</s>;
  const marks = [
    leaf.bold && "粗體",
    leaf.italic && "斜體",
    leaf.underline && "底線",
    leaf.strikethrough && "刪除線",
  ].filter(Boolean);
  return (
    <span
      {...attributes}
      className={
        leaf.diffOperation ? "diff-" + leaf.diffOperation.type : undefined
      }
    >
      {body}
      {leaf.text === "" && marks.length > 0 && (
        <small contentEditable={false} className="empty-mark">
          空白文字格式：{marks.join("、")}
        </small>
      )}
    </span>
  );
}
