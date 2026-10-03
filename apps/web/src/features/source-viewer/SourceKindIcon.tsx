/** What kind of source a row or link leads to: a spoken interview or a written Memory entry. */
import { FileTextIcon, MessageIcon } from '../../shared/ui/icons';

export function SourceKindIcon({ kind }: { kind: string }) {
  const Icon = kind === 'interview' ? MessageIcon : FileTextIcon;
  return <Icon className="source-kind" aria-hidden="true" />;
}
