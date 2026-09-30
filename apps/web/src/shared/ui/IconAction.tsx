/** An icon-only control: the label is both its accessible name and its hover hint. */
import { IconButton } from '@mui/material';
import type { IconButtonProps } from '@mui/material';

type Props = Omit<IconButtonProps, 'aria-label' | 'title'> & { label: string };

export function IconAction({ label, children, ...props }: Props) {
  return (
    <IconButton size="small" aria-label={label} title={label} {...props}>
      {children}
    </IconButton>
  );
}
