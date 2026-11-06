import { createContext } from 'react';
import type {
  CitationResponse,
  JobDescriptionContentResponse,
} from '../../../shared/api/generated/types.gen';

export type SourceTarget = { kind: CitationResponse['target_kind']; id: string };
export type SourcesContextValue = {
  jobDescription: JobDescriptionContentResponse;
  open: boolean;
  show: (trigger: HTMLButtonElement, target?: SourceTarget) => void;
};
export const SourcesContext = createContext<SourcesContextValue | null>(null);
