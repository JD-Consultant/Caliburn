import { ArrowRightLeft } from 'lucide-react';
import { useRef, useState } from 'react';
import type { TaskResponse } from '../../../shared/api/generated/types.gen';
import { moveTask } from '../content-api';
import { useJobDescriptionEditor } from '../editing/useJobDescriptionEditor';
import { focusTask } from './task-navigation';

export function TaskDestinationSelect({ task }: { task: TaskResponse }) {
  const { jobDescription: jd, blocked, editingKey, execute } = useJobDescriptionEditor();
  const pending = useRef(false);
  const [moving, setMoving] = useState(false);
  async function move(dutyId: string | null) {
    if (blocked || editingKey !== null || pending.current || dutyId === task.duty_id)
      return;
    pending.current = true;
    setMoving(true);
    try {
      const saved = await execute((current) =>
        moveTask(current.workspace_id, current.job_description_id, task.id, {
          expected_version: current.version,
          destination_duty_id: dutyId,
          before_id: null,
        }),
      );
      if (saved) requestAnimationFrame(() => focusTask(task.id));
    } finally {
      pending.current = false;
      setMoving(false);
    }
  }
  return (
    <label className="jd-destination-select" title="移至職責">
      <ArrowRightLeft size={14} aria-hidden="true" />
      <span className="sr-only">移至職責</span>
      <select
        value={task.duty_id ?? ''}
        disabled={blocked || editingKey !== null || moving}
        onChange={(event) => {
          void move(event.target.value || null);
        }}
      >
        <option value="">未分類任務</option>
        {jd.duties.map((duty) => (
          <option key={duty.id} value={duty.id}>
            {duty.name}
          </option>
        ))}
      </select>
    </label>
  );
}
