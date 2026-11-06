import { revealJdTarget } from './jd-navigation';

/** 任務搬移與反向用途定位共用；先展開祖先，再移動鍵盤焦點。 */
export function focusTask(taskId: string): void {
  if (!revealJdTarget(`jd-task-${taskId}`)) return;
  const target = document.getElementById(`jd-task-${taskId}`);
  target
    ?.querySelector<HTMLElement>(':scope > .jd-item-heading > [data-jd-fold-toggle]')
    ?.focus({ preventScroll: true });
}
