import { IconAction } from '../../../shared/ui/IconAction';
import { ArrowDownIcon, ArrowUpIcon } from '../../../shared/ui/icons';
import { useEffect, useRef, useState } from 'react';

export type OrderControlsProps = {
  id: string;
  label: string;
  items: readonly { id: string }[];
  disabled: boolean;
  onMove: (beforeId: string | null) => Promise<boolean>;
};

export function OrderControls({
  id,
  label,
  items,
  disabled,
  onMove,
}: OrderControlsProps) {
  const [message, setMessage] = useState('');
  const [moving, setMoving] = useState(false);
  const pending = useRef(false);
  const focusAfterMove = useRef<HTMLButtonElement | null>(null);
  useEffect(() => {
    if (moving) return;
    const control = focusAfterMove.current;
    focusAfterMove.current = null;
    if (control?.isConnected && document.activeElement === document.body) {
      const target = control.matches(':disabled')
        ? control.parentElement?.querySelector<HTMLButtonElement>('button:not(:disabled)')
        : control;
      target?.focus();
    }
  }, [moving]);
  if (items.length < 2) return null;
  const index = items.findIndex((item) => item.id === id);
  const previous = items[index - 1];
  const following = items[index + 2];
  async function move(target: string | null, control: HTMLButtonElement) {
    if (pending.current || disabled) return;
    pending.current = true;
    focusAfterMove.current = control;
    setMoving(true);
    try {
      if (await onMove(target)) setMessage(`已調整「${label}」的位置。`);
    } catch {
      setMessage('無法調整位置，請檢查文件上方的說明。');
    } finally {
      pending.current = false;
      setMoving(false);
    }
  }
  return (
    <div className="jd-order-controls" role="group" aria-label={`排序：${label}`}>
      <IconAction
        label={`上移${label}`}
        disabled={disabled || moving || !previous}
        onClick={(event) => {
          if (previous) void move(previous.id, event.currentTarget);
        }}
      >
        <ArrowUpIcon />
      </IconAction>
      <IconAction
        label={`下移${label}`}
        disabled={disabled || moving || index < 0 || index === items.length - 1}
        onClick={(event) => {
          void move(following?.id ?? null, event.currentTarget);
        }}
      >
        <ArrowDownIcon />
      </IconAction>
      <span role="status" className="sr-only">
        {message}
      </span>
    </div>
  );
}
