import { useEffect, useId, useRef, useState } from 'react';

export function CompetencyLevelPicker({
  label,
  value,
  onChange,
  disabled = false,
}: {
  label: string;
  value: number | null;
  onChange: (value: number | null) => void | Promise<boolean>;
  disabled?: boolean;
}) {
  const name = useId();
  const pending = useRef(false);
  const focusAfterSave = useRef<HTMLInputElement | null>(null);
  const [saving, setSaving] = useState(false);
  const [failed, setFailed] = useState(false);
  useEffect(() => {
    if (saving) return;
    const control = focusAfterSave.current;
    focusAfterSave.current = null;
    if (
      control?.isConnected &&
      !control.matches(':disabled') &&
      document.activeElement === document.body
    ) {
      control.focus();
    }
  }, [saving]);
  async function choose(level: number | null, control: HTMLInputElement) {
    if (pending.current || disabled) return;
    pending.current = true;
    focusAfterSave.current = control;
    setSaving(true);
    setFailed(false);
    try {
      await onChange(level);
    } catch {
      setFailed(true);
    } finally {
      pending.current = false;
      setSaving(false);
    }
  }
  return (
    <fieldset
      className="jd-level-picker"
      disabled={disabled || saving}
      aria-busy={saving}
    >
      <legend>{label}</legend>
      <div className="jd-level-options">
        {[null, 1, 2, 3, 4, 5, 6].map((level) => (
          <label
            key={level ?? 'unset'}
            title={level === null ? '未填' : `第 ${String(level)} 級`}
          >
            <input
              type="radio"
              name={name}
              value={level ?? ''}
              checked={value === level}
              aria-label={level === null ? '未填' : `第 ${String(level)} 級`}
              onChange={(event) => {
                void choose(level, event.currentTarget);
              }}
            />
            <span>{level ?? '—'}</span>
          </label>
        ))}
      </div>
      {failed && (
        <p role="alert" className="field-error">
          無法確認級別，請重新讀取後核對。
        </p>
      )}
    </fieldset>
  );
}
