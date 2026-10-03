/** The chevron that folds one block of the JD down to its heading; `name` says which block, e.g. 所需知識. */
import { IconAction } from '../../shared/ui/IconAction';
import { ExpandLessIcon, ExpandMoreIcon } from '../../shared/ui/icons';
import type { FoldState } from './use-fold';

export function FoldToggle({ name, fold }: { name: string; fold: FoldState }) {
  return (
    <IconAction
      label={`${fold.expanded ? '收合' : '展開'}${name}`}
      aria-expanded={fold.expanded}
      aria-controls={fold.bodyId}
      onClick={fold.toggle}
    >
      {fold.expanded ? <ExpandLessIcon /> : <ExpandMoreIcon />}
    </IconAction>
  );
}
