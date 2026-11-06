import { Alert, Button, IconButton, TextField, Typography } from '@mui/material';
import { AddIcon } from '../../../shared/ui/icons';
import { useEffect, useId, useRef, useState, type ReactNode } from 'react';
import { useJobDescriptionEditor } from '../editing/useJobDescriptionEditor';
import { isRecord, useCreationDraft } from './useCreationDraft';

export function CreatePanel({
  title,
  children,
  draftKey,
  triggerLabel,
}: {
  title: string;
  children: (close: () => void) => ReactNode;
  draftKey?: string;
  triggerLabel?: string;
}) {
  const [openedByUser, setOpenedByUser] = useState(false);
  const generatedKey = useId();
  const slotKey = draftKey ?? generatedKey;
  const contentRef = useRef<HTMLDivElement>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const opened = useRef(false);
  const { drafts, readOnly, editingKey, claimEdit, releaseEdit } =
    useJobDescriptionEditor();
  const hasDraft = draftKey !== undefined && drafts[draftKey] !== undefined;
  const expanded = editingKey === slotKey || (hasDraft && editingKey === null);
  useEffect(() => () => releaseEdit(slotKey), [releaseEdit, slotKey]);
  useEffect(() => {
    if (hasDraft && editingKey === null && !readOnly) claimEdit(slotKey);
  }, [hasDraft, editingKey, readOnly, claimEdit, slotKey]);
  useEffect(() => {
    if (openedByUser && expanded && !opened.current) {
      contentRef.current?.querySelector<HTMLElement>('input, textarea, select')?.focus();
    } else if (!expanded && opened.current) {
      triggerRef.current?.focus();
    }
    opened.current = expanded;
  }, [expanded, openedByUser]);
  const triggerProps = {
    ref: triggerRef,
    'aria-label': title,
    title,
    disabled: readOnly || (editingKey !== null && editingKey !== slotKey),
    onClick: () => {
      if (claimEdit(slotKey)) setOpenedByUser(true);
    },
  };
  return (
    <div className={`jd-create-panel${expanded ? ' is-expanded' : ''}`}>
      {!expanded ? (
        triggerLabel ? (
          <Button {...triggerProps} size="small" className="jd-add-trigger">
            {triggerLabel}
          </Button>
        ) : (
          <IconButton {...triggerProps} size="small" className="jd-add-trigger">
            <AddIcon />
          </IconButton>
        )
      ) : (
        <div className="jd-create-content" ref={contentRef}>
          <Typography component="h4" variant="subtitle2">
            {title}
          </Typography>
          {children(() => {
            setOpenedByUser(false);
            releaseEdit(slotKey);
          })}
        </div>
      )}
    </div>
  );
}

/** 新增表單只在明確成功後關閉；失敗保留全部輸入。 */
export function EditorForm({
  children,
  onSubmit,
  onDone,
  submitLabel,
  disabled = false,
  cancelLabel = '放棄新增',
}: {
  children: ReactNode;
  onSubmit: () => Promise<boolean>;
  onDone: () => void;
  submitLabel: string;
  disabled?: boolean;
  cancelLabel?: string;
}) {
  const pending = useRef(false);
  const { readOnly } = useJobDescriptionEditor();
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  async function submit() {
    if (pending.current || disabled || readOnly) return;
    pending.current = true;
    setSubmitting(true);
    setError(null);
    try {
      if (await onSubmit()) onDone();
      else setError('尚未確認完成，輸入已保留。請查看文件上方的說明。');
    } catch {
      setError('操作未能完成，已保留輸入。請檢查文件上方的說明後再處理。');
    } finally {
      pending.current = false;
      setSubmitting(false);
    }
  }
  return (
    <form
      className="jd-editor-form"
      onSubmit={(event) => {
        event.preventDefault();
        void submit();
      }}
      onKeyDown={(event) => {
        if (event.nativeEvent.isComposing || event.keyCode === 229) return;
        if (event.key === 'Escape' && !pending.current) {
          event.preventDefault();
          event.stopPropagation();
          onDone();
        }
        if (event.key === 'Enter' && (event.ctrlKey || event.metaKey)) {
          event.preventDefault();
          event.currentTarget.requestSubmit();
        }
      }}
    >
      <fieldset disabled={submitting || readOnly}>{children}</fieldset>
      {error && <Alert severity="error">{error}</Alert>}
      <div className="jd-form-actions">
        <Button
          type="submit"
          variant="contained"
          size="small"
          disabled={disabled || submitting || readOnly}
        >
          {submitLabel}
        </Button>
        <Button type="button" size="small" disabled={submitting} onClick={onDone}>
          {cancelLabel}
        </Button>
      </div>
    </form>
  );
}

export function FormField({
  label,
  value,
  onChange,
  multiline = false,
  required = false,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  multiline?: boolean;
  required?: boolean;
}) {
  const id = useId();
  return (
    <TextField
      id={id}
      label={label}
      value={value}
      required={required}
      multiline={multiline}
      minRows={multiline ? 3 : undefined}
      size="small"
      fullWidth
      slotProps={{ htmlInput: { 'aria-label': label } }}
      onChange={(event) => onChange(event.target.value)}
    />
  );
}

export function NamedCreateForm({
  nameLabel,
  descriptionLabel,
  submitLabel,
  onCreate,
  onDone,
  disabled,
  draftKey,
}: {
  nameLabel: string;
  descriptionLabel: string;
  submitLabel: string;
  onCreate: (name: string, description: string | null) => Promise<boolean>;
  onDone: () => void;
  disabled: boolean;
  draftKey: string;
}) {
  const draft = useCreationDraft(
    draftKey,
    submitLabel,
    { name: '', description: '' },
    (value): value is { name: string; description: string } =>
      isRecord(value) &&
      typeof value.name === 'string' &&
      typeof value.description === 'string',
  );
  const { name, description } = draft.value;
  return (
    <EditorForm
      onSubmit={() => onCreate(name, description === '' ? null : description)}
      onDone={() => {
        draft.discard();
        onDone();
      }}
      submitLabel={submitLabel}
      disabled={disabled || name === ''}
    >
      <FormField
        label={nameLabel}
        value={name}
        onChange={(value) => draft.setValue({ ...draft.value, name: value })}
        required
      />
      <FormField
        label={descriptionLabel}
        value={description}
        onChange={(value) => draft.setValue({ ...draft.value, description: value })}
        multiline
      />
    </EditorForm>
  );
}

export function TextCreateForm({
  label,
  onCreate,
  onDone,
  disabled,
  draftKey,
}: {
  label: string;
  onCreate: (text: string) => Promise<boolean>;
  onDone: () => void;
  disabled: boolean;
  draftKey: string;
}) {
  const draft = useCreationDraft(
    draftKey,
    `新增${label}`,
    { text: '' },
    (value): value is { text: string } =>
      isRecord(value) && typeof value.text === 'string',
  );
  const { text } = draft.value;
  return (
    <EditorForm
      onSubmit={() => onCreate(text)}
      onDone={() => {
        draft.discard();
        onDone();
      }}
      submitLabel={`建立${label}`}
      disabled={disabled || text === ''}
    >
      <FormField
        label={label}
        value={text}
        onChange={(value) => draft.setValue({ text: value })}
        multiline
        required
      />
    </EditorForm>
  );
}
