"use client";

import type {
  ApprovedJobDocumentView,
  DocumentChangeSetView,
  DocumentPatchActionView,
} from "@caliburn/job-analysis-contract";

export type ReviewValue =
  | string
  | number
  | boolean
  | null
  | ReviewValue[]
  | { [key: string]: ReviewValue };

type ReviewObject = { [key: string]: ReviewValue };

type ReferenceOption = {
  id: string;
  label: string;
};

type ReviewReferences = {
  duties: ReferenceOption[];
  tasks: ReferenceOption[];
  indicators: ReferenceOption[];
};

const roleLabels: Record<string, string> = {
  primary: "主要負責",
  shared: "共同負責",
  assist: "協助執行",
};

const enablerKindLabels: Record<string, string> = {
  tool_system: "工具／系統",
  method: "方法",
  knowledge: "知識",
  skill: "技能",
  other: "其他",
};

const opksKindLabels: Record<string, string> = {
  output: "工作產出（O）",
  indicator: "績效指標（P）",
  knowledge: "所需知識（K）",
  skill: "所需技能（S）",
  attitude: "態度（既有內容）",
};

const objectFieldLabels: Record<string, string> = {
  statement: "內容",
  action: "動作",
  object: "對象",
  purpose_result: "目的／結果",
  context: "執行情境",
  frequency_text: "頻率",
  responsibility_role: "責任角色",
  duty_id: "所屬主要職責",
  enablers: "工具／方法／促成條件",
  text: "內容",
  task_ids: "關聯工作",
  indicator_ids: "關聯績效指標",
  display_order: "順序",
  kind: "類型",
};

export function toReviewValue(value: unknown): ReviewValue {
  if (
    value === null ||
    typeof value === "string" ||
    typeof value === "number" ||
    typeof value === "boolean"
  ) {
    return value;
  }
  if (Array.isArray(value)) return value.map(toReviewValue);
  if (typeof value === "object") {
    return Object.fromEntries(
      Object.entries(value).flatMap(([key, item]) =>
        item === undefined ? [] : [[key, toReviewValue(item)]],
      ),
    );
  }
  return null;
}

function isReviewObject(value: ReviewValue): value is ReviewObject {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}

function entityObjects(value: unknown): ReviewObject[] {
  const normalized = toReviewValue(value);
  if (Array.isArray(normalized)) return normalized.filter(isReviewObject);
  return isReviewObject(normalized) ? [normalized] : [];
}

function deduplicateOptions(options: ReferenceOption[]): ReferenceOption[] {
  const byId = new Map<string, ReferenceOption>();
  for (const option of options) byId.set(option.id, option);
  return [...byId.values()];
}

function proposedOptions(
  bundle: DocumentChangeSetView,
  collection: "duties" | "tasks" | "opks",
  idField: "duty_id" | "task_id" | "item_id",
  labelField: "statement" | "text",
  predicate: (item: ReviewObject) => boolean = () => true,
): ReferenceOption[] {
  return bundle.actions.flatMap((action) => {
    if (action.path !== `/${collection}`) return [];
    return entityObjects(action.employee_after ?? action.after).flatMap((item) => {
      const id = item[idField];
      const label = item[labelField];
      return typeof id === "string" && typeof label === "string" && predicate(item)
        ? [{ id, label }]
        : [];
    });
  });
}

function buildReferences(
  approvedDocument: ApprovedJobDocumentView,
  bundle: DocumentChangeSetView,
): ReviewReferences {
  return {
    duties: deduplicateOptions([
      ...approvedDocument.duties.map((item) => ({
        id: item.duty_id,
        label: item.statement,
      })),
      ...proposedOptions(bundle, "duties", "duty_id", "statement"),
    ]),
    tasks: deduplicateOptions([
      ...approvedDocument.tasks.map((item) => ({
        id: item.task_id,
        label: item.statement,
      })),
      ...proposedOptions(bundle, "tasks", "task_id", "statement"),
    ]),
    indicators: deduplicateOptions([
      ...approvedDocument.opks
        .filter((item) => item.kind === "indicator")
        .map((item) => ({ id: item.item_id, label: item.text })),
      ...proposedOptions(
        bundle,
        "opks",
        "item_id",
        "text",
        (item) => item.kind === "indicator",
      ),
    ]),
  };
}

function optionLabel(options: ReferenceOption[], id: string): string {
  return options.find((item) => item.id === id)?.label ?? "同組建議中的內容";
}

function rootCollection(path: string): "duties" | "tasks" | "opks" | null {
  const root = path.split("/").filter(Boolean)[0];
  return root === "duties" || root === "tasks" || root === "opks" ? root : null;
}

function lastPathField(path: string): string | null {
  const parts = path.split("/").filter(Boolean);
  return parts.length >= 3 ? parts.at(-1) ?? null : null;
}

function isEntityLevelPath(path: string): boolean {
  return path.split("/").filter(Boolean).length <= 2;
}

function fieldLabel(collection: string | null, field: string, suffix = ""): string {
  if (collection === "duties" && field === "statement") {
    return `主要職責內容${suffix}`;
  }
  if (collection === "tasks" && field === "statement") {
    return `工作任務內容${suffix}`;
  }
  if (collection === "opks" && field === "text") {
    return `O／P／K／S 內容${suffix}`;
  }
  return `${objectFieldLabels[field] ?? "內容"}${suffix}`;
}

function LabeledTextField({
  id,
  label,
  value,
  disabled,
  multiline = true,
  onChange,
}: {
  id: string;
  label: string;
  value: string;
  disabled: boolean;
  multiline?: boolean;
  onChange: (value: string) => void;
}) {
  return (
    <label className="block text-xs font-medium text-stone-600" htmlFor={id}>
      {label}
      {multiline ? (
        <textarea
          id={id}
          className="mt-1 min-h-20 w-full rounded-lg border border-stone-300 bg-white p-3 text-sm font-normal text-stone-900"
          value={value}
          disabled={disabled}
          onChange={(event) => onChange(event.target.value)}
        />
      ) : (
        <input
          id={id}
          className="mt-1 w-full rounded-lg border border-stone-300 bg-white px-3 py-2 text-sm font-normal text-stone-900"
          value={value}
          disabled={disabled}
          onChange={(event) => onChange(event.target.value)}
        />
      )}
    </label>
  );
}

function ReferenceSelect({
  id,
  label,
  value,
  options,
  disabled,
  allowEmpty = false,
  onChange,
}: {
  id: string;
  label: string;
  value: string | null;
  options: ReferenceOption[];
  disabled: boolean;
  allowEmpty?: boolean;
  onChange: (value: string | null) => void;
}) {
  return (
    <label className="block text-xs font-medium text-stone-600" htmlFor={id}>
      {label}
      <select
        id={id}
        className="mt-1 w-full rounded-lg border border-stone-300 bg-white px-3 py-2 text-sm font-normal text-stone-900"
        value={value ?? ""}
        disabled={disabled}
        onChange={(event) => onChange(event.target.value || null)}
      >
        {allowEmpty ? <option value="">尚未歸類</option> : null}
        {value && !options.some((item) => item.id === value) ? (
          <option value={value}>同組建議中的內容</option>
        ) : null}
        {options.map((option) => (
          <option key={option.id} value={option.id}>
            {option.label}
          </option>
        ))}
      </select>
    </label>
  );
}

function MultiReferenceSelect({
  id,
  label,
  value,
  options,
  disabled,
  onChange,
}: {
  id: string;
  label: string;
  value: string[];
  options: ReferenceOption[];
  disabled: boolean;
  onChange: (value: string[]) => void;
}) {
  const allOptions = deduplicateOptions([
    ...options,
    ...value
      .filter((idValue) => !options.some((item) => item.id === idValue))
      .map((idValue) => ({ id: idValue, label: "同組建議中的內容" })),
  ]);
  return (
    <div>
      <label className="block text-xs font-medium text-stone-600" htmlFor={id}>
        {label}
      </label>
      <select
        id={id}
        multiple
        className="mt-1 min-h-24 w-full rounded-lg border border-stone-300 bg-white px-3 py-2 text-sm font-normal text-stone-900"
        value={value}
        disabled={disabled}
        onChange={(event) =>
          onChange(
            [...event.currentTarget.selectedOptions].map((option) => option.value),
          )
        }
      >
        {allOptions.map((option) => (
          <option key={option.id} value={option.id}>
            {option.label}
          </option>
        ))}
      </select>
      <span className="mt-1 block text-[11px] font-normal text-stone-500">
        可按住 Ctrl（macOS 為 Command）選取多項。
      </span>
    </div>
  );
}

function EnablersEditor({
  idPrefix,
  value,
  disabled,
  onChange,
}: {
  idPrefix: string;
  value: ReviewValue[];
  disabled: boolean;
  onChange: (value: ReviewValue[]) => void;
}) {
  const items = value.filter(isReviewObject);
  if (!items.length) {
    return <p className="text-xs text-stone-500">目前沒有工具或方法建議。</p>;
  }
  return (
    <div className="space-y-2">
      <p className="text-xs font-medium text-stone-600">工具／方法／促成條件</p>
      {items.map((item, index) => {
        const name = typeof item.name === "string" ? item.name : "";
        const kind = typeof item.kind === "string" ? item.kind : "other";
        return (
          <div key={`${idPrefix}-${index}`} className="grid gap-2 sm:grid-cols-[10rem_1fr]">
            <label className="text-xs text-stone-500" htmlFor={`${idPrefix}-${index}-kind`}>
              類型
              <select
                id={`${idPrefix}-${index}-kind`}
                className="mt-1 w-full rounded-lg border border-stone-300 bg-white px-2 py-2 text-sm text-stone-900"
                value={kind}
                disabled={disabled}
                onChange={(event) => {
                  const next = [...value];
                  next[index] = { ...item, kind: event.target.value };
                  onChange(next);
                }}
              >
                {Object.entries(enablerKindLabels).map(([option, text]) => (
                  <option key={option} value={option}>{text}</option>
                ))}
              </select>
            </label>
            <LabeledTextField
              id={`${idPrefix}-${index}-name`}
              label="名稱"
              value={name}
              multiline={false}
              disabled={disabled}
              onChange={(nextName) => {
                const next = [...value];
                next[index] = { ...item, name: nextName };
                onChange(next);
              }}
            />
          </div>
        );
      })}
    </div>
  );
}

function EntityEditor({
  idPrefix,
  collection,
  value,
  suffix,
  references,
  disabled,
  onChange,
}: {
  idPrefix: string;
  collection: "duties" | "tasks" | "opks";
  value: ReviewObject;
  suffix: string;
  references: ReviewReferences;
  disabled: boolean;
  onChange: (value: ReviewObject) => void;
}) {
  const fields =
    collection === "duties"
      ? ["statement"]
      : collection === "tasks"
        ? [
            "statement",
            "action",
            "object",
            "purpose_result",
            "context",
            "frequency_text",
            "responsibility_role",
            "duty_id",
            "enablers",
          ]
        : ["text", "task_ids", "indicator_ids"];
  return (
    <div className="space-y-3 rounded-lg border border-stone-200 bg-stone-50/60 p-3">
      {collection === "opks" && typeof value.kind === "string" ? (
        <p className="text-xs font-semibold text-stone-600">
          {opksKindLabels[value.kind] ?? "O／P／K／S 內容"}
        </p>
      ) : null}
      {fields.flatMap((field) => {
        if (!(field in value)) return [];
        const current = value[field];
        const setField = (next: ReviewValue) => onChange({ ...value, [field]: next });
        if (field === "duty_id") {
          return [
            <ReferenceSelect
              key={field}
              id={`${idPrefix}-${field}`}
              label={fieldLabel(collection, field, suffix)}
              value={typeof current === "string" ? current : null}
              options={references.duties}
              allowEmpty
              disabled={disabled}
              onChange={setField}
            />,
          ];
        }
        if (field === "responsibility_role") {
          return [
            <label key={field} className="block text-xs font-medium text-stone-600" htmlFor={`${idPrefix}-${field}`}>
              {fieldLabel(collection, field, suffix)}
              <select
                id={`${idPrefix}-${field}`}
                className="mt-1 w-full rounded-lg border border-stone-300 bg-white px-3 py-2 text-sm font-normal text-stone-900"
                value={typeof current === "string" ? current : ""}
                disabled={disabled}
                onChange={(event) => setField(event.target.value || null)}
              >
                <option value="">尚未確認</option>
                {Object.entries(roleLabels).map(([option, text]) => (
                  <option key={option} value={option}>{text}</option>
                ))}
              </select>
            </label>,
          ];
        }
        if (field === "task_ids" || field === "indicator_ids") {
          const ids = Array.isArray(current)
            ? current.filter((item): item is string => typeof item === "string")
            : [];
          return [
            <MultiReferenceSelect
              key={field}
              id={`${idPrefix}-${field}`}
              label={fieldLabel(collection, field, suffix)}
              value={ids}
              options={field === "task_ids" ? references.tasks : references.indicators}
              disabled={disabled}
              onChange={setField}
            />,
          ];
        }
        if (field === "enablers") {
          return [
            <EnablersEditor
              key={field}
              idPrefix={`${idPrefix}-${field}`}
              value={Array.isArray(current) ? current : []}
              disabled={disabled}
              onChange={setField}
            />,
          ];
        }
        return [
          <LabeledTextField
            key={field}
            id={`${idPrefix}-${field}`}
            label={fieldLabel(collection, field, suffix)}
            value={typeof current === "string" ? current : ""}
            multiline={["statement", "purpose_result", "context", "text"].includes(field)}
            disabled={disabled}
            onChange={setField}
          />,
        ];
      })}
    </div>
  );
}

function ScalarEditor({
  action,
  idPrefix,
  label,
  value,
  references,
  disabled,
  onChange,
}: {
  action: DocumentPatchActionView;
  idPrefix: string;
  label: string;
  value: ReviewValue;
  references: ReviewReferences;
  disabled: boolean;
  onChange: (value: ReviewValue) => void;
}) {
  const field = lastPathField(action.path);
  if (field === "duty_id") {
    return (
      <ReferenceSelect
        id={idPrefix}
        label="所屬主要職責"
        value={typeof value === "string" ? value : null}
        options={references.duties}
        allowEmpty
        disabled={disabled}
        onChange={onChange}
      />
    );
  }
  if (field === "responsibility_role") {
    return (
      <label className="block text-xs font-medium text-stone-600" htmlFor={idPrefix}>
        責任角色
        <select
          id={idPrefix}
          className="mt-1 w-full rounded-lg border border-stone-300 bg-white px-3 py-2 text-sm font-normal text-stone-900"
          value={typeof value === "string" ? value : ""}
          disabled={disabled}
          onChange={(event) => onChange(event.target.value || null)}
        >
          <option value="">尚未確認</option>
          {Object.entries(roleLabels).map(([option, text]) => (
            <option key={option} value={option}>{text}</option>
          ))}
        </select>
      </label>
    );
  }
  if (field === "display_order" && typeof value === "number") {
    return (
      <label className="block text-xs font-medium text-stone-600" htmlFor={idPrefix}>
        排序位置（從 1 開始）
        <input
          id={idPrefix}
          type="number"
          min={1}
          className="mt-1 w-full rounded-lg border border-stone-300 bg-white px-3 py-2 text-sm font-normal text-stone-900"
          value={value + 1}
          disabled={disabled}
          onChange={(event) =>
            onChange(Math.max(0, Number(event.target.value || 1) - 1))
          }
        />
      </label>
    );
  }
  if (typeof value === "boolean") {
    return (
      <label className="block text-xs font-medium text-stone-600" htmlFor={idPrefix}>
        {label}
        <select
          id={idPrefix}
          className="mt-1 w-full rounded-lg border border-stone-300 bg-white px-3 py-2 text-sm font-normal text-stone-900"
          value={String(value)}
          disabled={disabled}
          onChange={(event) => onChange(event.target.value === "true")}
        >
          <option value="true">是</option>
          <option value="false">否</option>
        </select>
      </label>
    );
  }
  return (
    <LabeledTextField
      id={idPrefix}
      label={label}
      value={typeof value === "string" ? value : value === null ? "" : String(value)}
      disabled={disabled}
      onChange={onChange}
    />
  );
}

export function DocumentChangeEditor({
  action,
  value,
  approvedDocument,
  bundle,
  label,
  disabled,
  onChange,
}: {
  action: DocumentPatchActionView;
  value: ReviewValue;
  approvedDocument: ApprovedJobDocumentView;
  bundle: DocumentChangeSetView;
  label: string;
  disabled: boolean;
  onChange: (value: ReviewValue) => void;
}) {
  const references = buildReferences(approvedDocument, bundle);
  const collection = rootCollection(action.path);
  const field = lastPathField(action.path);
  const idPrefix = `review-${action.action_id}`;
  if (field === "enablers" && Array.isArray(value)) {
    return (
      <EnablersEditor
        idPrefix={idPrefix}
        value={value}
        disabled={disabled}
        onChange={onChange}
      />
    );
  }
  if (
    (field === "task_ids" || field === "indicator_ids") &&
    Array.isArray(value)
  ) {
    return (
      <MultiReferenceSelect
        id={idPrefix}
        label={field === "task_ids" ? "關聯工作" : "關聯績效指標"}
        value={value.filter((item): item is string => typeof item === "string")}
        options={field === "task_ids" ? references.tasks : references.indicators}
        disabled={disabled}
        onChange={onChange}
      />
    );
  }
  if (collection && isEntityLevelPath(action.path) && isReviewObject(value)) {
    return (
      <EntityEditor
        idPrefix={idPrefix}
        collection={collection}
        value={value}
        suffix=""
        references={references}
        disabled={disabled}
        onChange={onChange}
      />
    );
  }
  if (
    collection &&
    isEntityLevelPath(action.path) &&
    Array.isArray(value) &&
    value.every(isReviewObject)
  ) {
    return (
      <div className="space-y-3">
        {value.map((item, index) => (
          <EntityEditor
            key={`${idPrefix}-${index}`}
            idPrefix={`${idPrefix}-${index}`}
            collection={collection}
            value={item}
            suffix={` ${index + 1}`}
            references={references}
            disabled={disabled}
            onChange={(nextItem) => {
              const next = [...value];
              next[index] = nextItem;
              onChange(next);
            }}
          />
        ))}
      </div>
    );
  }
  if (value === null && action.operation === "withdraw") {
    return <p className="rounded-lg bg-stone-100 p-3 text-sm">AI 建議移除這項內容。</p>;
  }
  return (
    <ScalarEditor
      action={action}
      idPrefix={idPrefix}
      label={label}
      value={value}
      references={references}
      disabled={disabled}
      onChange={onChange}
    />
  );
}

function previewObject(value: ReviewObject, references: ReviewReferences): string {
  const visible = Object.entries(value).flatMap(([field, current]) => {
    if (["duty_id", "task_id", "item_id", "evidence_source_ids"].includes(field)) {
      if (field === "duty_id" && typeof current === "string") {
        return [`所屬主要職責：${optionLabel(references.duties, current)}`];
      }
      return [];
    }
    if (field === "task_ids" && Array.isArray(current)) {
      const labels = current
        .filter((item): item is string => typeof item === "string")
        .map((item) => optionLabel(references.tasks, item));
      return labels.length ? [`關聯工作：${labels.join("、")}`] : [];
    }
    if (field === "indicator_ids" && Array.isArray(current)) {
      const labels = current
        .filter((item): item is string => typeof item === "string")
        .map((item) => optionLabel(references.indicators, item));
      return labels.length ? [`關聯績效指標：${labels.join("、")}`] : [];
    }
    if (field === "enablers" && Array.isArray(current)) {
      const labels = current.flatMap((item) =>
        isReviewObject(item) && typeof item.name === "string" ? [item.name] : [],
      );
      return labels.length ? [`工具／方法：${labels.join("、")}`] : [];
    }
    if (field === "display_order" && typeof current === "number") {
      return [`順序：${current + 1}`];
    }
    if (field === "responsibility_role" && typeof current === "string") {
      return [`責任角色：${roleLabels[current] ?? current}`];
    }
    if (field === "kind" && typeof current === "string") {
      return [`類型：${opksKindLabels[current] ?? "O／P／K／S 內容"}`];
    }
    if (typeof current === "string" && current.trim()) {
      return [`${objectFieldLabels[field] ?? "內容"}：${current}`];
    }
    return [];
  });
  return visible.length ? visible.join("\n") : "（結構調整）";
}

export function DocumentChangePreview({
  action,
  value,
  approvedDocument,
  bundle,
}: {
  action: DocumentPatchActionView;
  value: unknown;
  approvedDocument: ApprovedJobDocumentView;
  bundle: DocumentChangeSetView;
}) {
  const references = buildReferences(approvedDocument, bundle);
  const normalized = toReviewValue(value);
  const field = lastPathField(action.path);
  let text: string;
  if (normalized === null) {
    text = "（目前沒有內容）";
  } else if (field === "duty_id" && typeof normalized === "string") {
    text = optionLabel(references.duties, normalized);
  } else if (field === "display_order" && typeof normalized === "number") {
    text = `第 ${normalized + 1} 順位`;
  } else if (field === "responsibility_role" && typeof normalized === "string") {
    text = roleLabels[normalized] ?? normalized;
  } else if (field === "enablers" && Array.isArray(normalized)) {
    const labels = normalized.flatMap((item) =>
      isReviewObject(item) && typeof item.name === "string"
        ? [
            `${
              typeof item.kind === "string"
                ? enablerKindLabels[item.kind] ?? "促成條件"
                : "促成條件"
            }：${item.name}`,
          ]
        : [],
    );
    text = labels.length ? labels.join("\n") : "（目前沒有工具或方法）";
  } else if (field === "task_ids" && Array.isArray(normalized)) {
    const labels = normalized
      .filter((item): item is string => typeof item === "string")
      .map((item) => optionLabel(references.tasks, item));
    text = labels.length ? labels.join("、") : "（目前沒有關聯工作）";
  } else if (field === "indicator_ids" && Array.isArray(normalized)) {
    const labels = normalized
      .filter((item): item is string => typeof item === "string")
      .map((item) => optionLabel(references.indicators, item));
    text = labels.length ? labels.join("、") : "（目前沒有關聯績效指標）";
  } else if (isReviewObject(normalized)) {
    text = previewObject(normalized, references);
  } else if (Array.isArray(normalized)) {
    text = normalized
      .map((item, index) =>
        isReviewObject(item)
          ? `${index + 1}. ${previewObject(item, references)}`
          : String(item),
      )
      .join("\n");
  } else {
    text = String(normalized);
  }
  return (
    <p className="mt-1 rounded-lg bg-stone-100 p-3 text-sm whitespace-pre-wrap">
      {text}
    </p>
  );
}
