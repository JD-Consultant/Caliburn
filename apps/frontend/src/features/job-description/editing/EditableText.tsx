import { useEffect, useId, useRef, useState } from 'react';
import { TextField } from '@mui/material';
import type { JobDescriptionResponse } from '../../../shared/api/generated/types.gen';
import { IconAction } from '../../../shared/ui/IconAction';
import { CheckIcon, CloseIcon } from '../../../shared/ui/icons';
import { useJobDescriptionEditor } from './useJobDescriptionEditor';

export function EditableText({
  draftKey,
  label,
  value,
  multiline = false,
  required = false,
  hideLabel = false,
  placeholder = '尚未填寫',
  className = '',
  onSave,
}: {
  draftKey: string;
  label: string;
  value: string | null;
  multiline?: boolean;
  required?: boolean;
  hideLabel?: boolean;
  placeholder?: string;
  className?: string;
  onSave: (
    value: string,
    current: JobDescriptionResponse,
  ) => Promise<JobDescriptionResponse>;
}) {
  const editor = useJobDescriptionEditor();
  const draft = editor.drafts[draftKey];
  const open = editor.editingKey === draftKey;
  const canOpen = !editor.readOnly && (editor.editingKey === null || open);
  const composing = useRef(false);
  const pending = useRef(false);
  const [saving, setSaving] = useState(false);
  const trigger = useRef<HTMLButtonElement>(null);
  const input = useRef<HTMLInputElement | HTMLTextAreaElement>(null);
  const wasOpen = useRef(false);
  const id = useId();
  const text = draft?.value ?? value ?? '';
  const releaseEdit = editor.releaseEdit;
  useEffect(() => () => releaseEdit(draftKey), [draftKey, releaseEdit]);

  useEffect(() => {
    if (open) {
      input.current?.focus({ preventScroll: true });
      input.current?.setSelectionRange(
        input.current.value.length,
        input.current.value.length,
      );
      input.current?.closest('form')?.scrollIntoView?.({ block: 'nearest' });
    } else if (wasOpen.current) trigger.current?.focus({ preventScroll: true });
    wasOpen.current = open;
  }, [open]);

  function begin() {
    if (!canOpen || !editor.claimEdit(draftKey)) return;
    if (!draft)
      editor.setDraft(draftKey, { value: value ?? '', baseValue: value, label });
  }

  function cancel() {
    if (pending.current) return;
    editor.discardDraft(draftKey);
    editor.releaseEdit(draftKey);
  }

  async function save() {
    if (!draft || composing.current || editor.blocked || pending.current) return;
    if (draft.value === (value ?? '')) {
      cancel();
      return;
    }
    pending.current = true;
    setSaving(true);
    const success = await editor.execute((current) => onSave(draft.value, current));
    pending.current = false;
    setSaving(false);
    if (success) {
      editor.discardDraft(draftKey, draft.value);
      editor.releaseEdit(draftKey);
    }
  }

  return (
    <div className={`jd-editable ${className}`}>
      {!hideLabel && <span className="jd-field-label">{label}</span>}
      {open ? (
        <form
          className="inline-edit"
          onSubmit={(event) => {
            event.preventDefault();
            void save();
          }}
          onKeyDown={(event) => {
            if (event.nativeEvent.isComposing || composing.current) return;
            if (event.key === 'Escape') {
              event.preventDefault();
              cancel();
            }
            if (event.key === 'Enter' && (!multiline || event.ctrlKey || event.metaKey)) {
              event.preventDefault();
              event.currentTarget.requestSubmit();
            }
          }}
        >
          <TextField
            id={id}
            inputRef={input}
            size="small"
            fullWidth
            value={text}
            required={required}
            multiline={multiline}
            minRows={multiline ? 2 : undefined}
            placeholder={placeholder}
            disabled={saving || editor.readOnly}
            slotProps={{ htmlInput: { 'aria-label': label } }}
            onChange={(event) =>
              editor.setDraft(draftKey, {
                value: event.target.value,
                baseValue: draft?.baseValue ?? value,
                label,
              })
            }
            onCompositionStart={() => {
              composing.current = true;
            }}
            onCompositionEnd={() => {
              composing.current = false;
            }}
          />
          {draft && editor.reviewing && (
            <div className="jd-field-recovery">
              <p>目前內容：{value || '未填寫'}</p>
              <p>保留的輸入尚未保存，請先核對目前內容。</p>
            </div>
          )}
          <div className="inline-edit__actions">
            <IconAction
              type="submit"
              label={editor.reviewing ? '套用輸入' : '儲存'}
              hint={multiline ? '儲存（Ctrl／⌘＋Enter）' : '儲存（Enter）'}
              disabled={editor.blocked || saving}
            >
              <CheckIcon />
            </IconAction>
            <IconAction
              label={editor.reviewing ? '使用目前內容' : '取消'}
              hint="取消（Esc）"
              disabled={saving}
              onClick={cancel}
            >
              <CloseIcon />
            </IconAction>
          </div>
        </form>
      ) : (
        <div
          className="inline-text"
          data-disabled={canOpen ? undefined : ''}
          onClick={() => {
            if (!(window.getSelection()?.toString() ?? '')) begin();
          }}
        >
          <span className={text ? 'inline-text__value' : 'inline-text__placeholder'}>
            {text || placeholder}
          </span>
          {draft && <span className="jd-draft-hint">未保存</span>}
          <button
            ref={trigger}
            type="button"
            className="inline-text__edit"
            aria-label={`修改${label}`}
            aria-disabled={!canOpen}
            onClick={(event) => {
              event.stopPropagation();
              begin();
            }}
          />
        </div>
      )}
    </div>
  );
}
