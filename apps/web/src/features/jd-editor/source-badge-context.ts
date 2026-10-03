/**
 * Lets the page put a source badge next to JD items without jd-editor importing source-viewer.
 * Targets are built from item identity, mirroring the server's `Target`; labels are never used.
 */
import { createContext, useContext } from 'react';
import type { ReactNode } from 'react';
import type { Target } from '../../shared/api/generated/jd-sources-view';

export type RenderSourceBadge = (target: Target) => ReactNode;

export const SourceBadgeContext = createContext<RenderSourceBadge>(() => null);

export function useSourceBadge(): RenderSourceBadge {
  return useContext(SourceBadgeContext);
}

export function profileTarget(field: NonNullable<Target['field']>): Target {
  return { kind: 'profile_field', field, item_id: null, task_id: null };
}

export function itemTarget(
  kind: 'area' | 'task' | 'capability' | 'collaborator' | 'condition',
  itemId: string,
): Target {
  return { kind, field: null, item_id: itemId, task_id: null };
}

export function detailTarget(taskId: string, detailId: string): Target {
  return { kind: 'detail', field: null, item_id: detailId, task_id: taskId };
}
