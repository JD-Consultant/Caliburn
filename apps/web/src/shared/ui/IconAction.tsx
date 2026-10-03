/** An icon-only control: the label is its accessible name and, unless `hint` says more, its hover hint. */
import { IconButton } from '@mui/material';
import type { IconButtonProps } from '@mui/material';

type Props = Omit<IconButtonProps, 'aria-label' | 'title'> & {
  label: string;
  /** A longer hover hint, e.g. one that names the keyboard shortcut; the accessible name stays `label`. */
  hint?: string;
};

export function IconAction({ label, hint, children, ...props }: Props) {
  return (
    <IconButton size="small" aria-label={label} title={hint ?? label} {...props}>
      {children}
    </IconButton>
  );
}
