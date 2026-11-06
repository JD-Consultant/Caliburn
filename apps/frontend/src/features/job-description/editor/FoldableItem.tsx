import { useRef, type ReactNode } from 'react';
import { Box, Stack } from '@mui/material';
import { IconAction } from '../../../shared/ui/IconAction';
import { ExpandLessIcon, ExpandMoreIcon } from '../../../shared/ui/icons';
import { useFold } from './useFold';

/** 職責／任務標頭只有箭頭收合，名稱與來源各自處理自己的操作。 */
export function FoldableItem({
  id,
  kind,
  name,
  title,
  meta,
  children,
}: {
  id: string;
  kind: 'duty' | 'task';
  name: string;
  title: ReactNode;
  meta?: ReactNode;
  children: ReactNode;
}) {
  const element = useRef<HTMLElement>(null);
  const fold = useFold(element);
  const label = `${kind === 'duty' ? '職責' : '任務'} ${name}`;
  return (
    <Box
      component={kind === 'duty' ? 'section' : 'article'}
      ref={element}
      id={id}
      tabIndex={-1}
      aria-label={label}
      className={`jd-${kind} jd-edit-${kind}`}
    >
      <Stack
        direction="row"
        spacing={1}
        className="jd-fold-head jd-item-heading"
        sx={{ alignItems: 'center', flexWrap: 'wrap' }}
      >
        <IconAction
          label={`${fold.expanded ? '收合' : '展開'}${label}`}
          aria-expanded={fold.expanded}
          aria-controls={fold.bodyId}
          data-jd-fold-toggle
          onClick={fold.toggle}
        >
          {fold.expanded ? <ExpandLessIcon /> : <ExpandMoreIcon />}
        </IconAction>
        <div
          role="heading"
          aria-level={kind === 'duty' ? 3 : 4}
          aria-label={name}
          className="jd-item-title"
        >
          {title}
        </div>
        {meta}
      </Stack>
      <div
        id={fold.bodyId}
        hidden={!fold.expanded}
        className={kind === 'duty' ? 'jd-duty-edit-content' : 'jd-task-content'}
      >
        {children}
      </div>
    </Box>
  );
}
