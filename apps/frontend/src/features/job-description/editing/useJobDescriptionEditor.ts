import { useContext } from 'react';
import { JobDescriptionEditorContext } from './editor-context';

export function useJobDescriptionEditor() {
  const context = useContext(JobDescriptionEditorContext);
  if (!context) throw new Error('JD 編輯元件必須放在 JobDescriptionEditorProvider 內');
  return context;
}
