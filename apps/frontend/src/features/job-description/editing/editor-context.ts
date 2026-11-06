import { createContext } from 'react';
import type { JobDescriptionResponse } from '../../../shared/api/generated/types.gen';
import type { TextDraft, TextDrafts } from './drafts';

export type JobDescriptionWrite = (
  current: JobDescriptionResponse,
) => Promise<JobDescriptionResponse>;

export type JobDescriptionEditorContextValue = {
  jobDescription: JobDescriptionResponse;
  busy: boolean;
  blocked: boolean;
  readOnly: boolean;
  editingKey: string | null;
  claimEdit: (key: string) => boolean;
  releaseEdit: (key: string) => void;
  reviewing: boolean;
  drafts: Readonly<TextDrafts>;
  execute: (write: JobDescriptionWrite) => Promise<boolean>;
  waitForWrites: () => Promise<boolean>;
  setDraft: (key: string, draft: TextDraft) => void;
  discardDraft: (key: string, confirmedValue?: string) => void;
};

export const JobDescriptionEditorContext =
  createContext<JobDescriptionEditorContextValue | null>(null);
