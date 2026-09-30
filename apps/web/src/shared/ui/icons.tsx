/**
 * Small inline icon set (Material Icons path data, Apache-2.0) so no icon package is needed.
 * Every icon inherits the parent's font size and color; give the control an accessible name.
 */
import { SvgIcon } from '@mui/material';
import type { SvgIconProps } from '@mui/material';

function createIcon(displayName: string, path: string) {
  function Icon(props: SvgIconProps) {
    return (
      <SvgIcon fontSize="inherit" {...props}>
        <path d={path} />
      </SvgIcon>
    );
  }
  Icon.displayName = displayName;
  return Icon;
}

export const EditIcon = createIcon(
  'EditIcon',
  'M3 17.25V21h3.75L17.81 9.94l-3.75-3.75L3 17.25zM20.71 7.04a1 1 0 0 0 0-1.41l-2.34-2.34a1 1 0 0 0-1.41 0l-1.83 1.83 3.75 3.75 1.83-1.83z',
);
export const DeleteIcon = createIcon(
  'DeleteIcon',
  'M6 19a2 2 0 0 0 2 2h8a2 2 0 0 0 2-2V7H6v12zM19 4h-3.5l-1-1h-5l-1 1H5v2h14V4z',
);
export const ArrowUpIcon = createIcon(
  'ArrowUpIcon',
  'M4 12l1.41 1.41L11 7.83V20h2V7.83l5.58 5.59L20 12l-8-8-8 8z',
);
export const ArrowDownIcon = createIcon(
  'ArrowDownIcon',
  'M20 12l-1.41-1.41L13 16.17V4h-2v12.17l-5.58-5.59L4 12l8 8 8-8z',
);
export const AddIcon = createIcon('AddIcon', 'M19 13h-6v6h-2v-6H5v-2h6V5h2v6h6v2z');
export const CloseIcon = createIcon(
  'CloseIcon',
  'M19 6.41L17.59 5 12 10.59 6.41 5 5 6.41 10.59 12 5 17.59 6.41 19 12 13.41 17.59 19 19 17.59 13.41 12z',
);
export const ArrowBackIcon = createIcon(
  'ArrowBackIcon',
  'M20 11H7.83l5.59-5.59L12 4l-8 8 8 8 1.41-1.41L7.83 13H20v-2z',
);
export const DownloadIcon = createIcon('DownloadIcon', 'M19 9h-4V3H9v6H5l7 7 7-7zM5 18v2h14v-2H5z');
export const LinkIcon = createIcon(
  'LinkIcon',
  'M3.9 12a3.1 3.1 0 0 1 3.1-3.1h4V7H7a5 5 0 0 0 0 10h4v-1.9H7A3.1 3.1 0 0 1 3.9 12zM8 13h8v-2H8v2zm9-6h-4v1.9h4a3.1 3.1 0 0 1 0 6.2h-4V17h4a5 5 0 0 0 0-10z',
);
export const SendIcon = createIcon('SendIcon', 'M2.01 21L23 12 2.01 3 2 10l15 2-15 2z');
export const PauseIcon = createIcon('PauseIcon', 'M6 19h4V5H6v14zm8-14v14h4V5h-4z');
export const PlayIcon = createIcon('PlayIcon', 'M8 5v14l11-7z');
