"use client";
import React, { useState } from "react";
export function DocumentActions({
  disabled,
  onCreate,
}: {
  disabled: boolean;
  onCreate: (title: string) => Promise<void>;
}) {
  const [title, setTitle] = useState("未命名職務說明書");
  return (
    <form
      className="create-document"
      onSubmit={(e) => {
        e.preventDefault();
        void onCreate(title);
      }}
    >
      <label htmlFor="document-title">文件名稱</label>
      <input
        id="document-title"
        value={title}
        maxLength={200}
        onChange={(e) => setTitle(e.target.value)}
        disabled={disabled}
      />
      <button className="primary" disabled={disabled || !title.trim()}>
        建立文件
      </button>
    </form>
  );
}
