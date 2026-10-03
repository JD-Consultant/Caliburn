/**
 * Small inline icon set so no icon package is needed: Lucide path data (ISC), drawn as 1.75px
 * rounded strokes on a 24px grid so every icon has the same weight (the former filled Material
 * glyphs mixed heavy and light shapes). Every icon inherits the parent's font size and color;
 * give the control an accessible name.
 */
import { SvgIcon } from '@mui/material';
import type { SvgIconProps } from '@mui/material';

function createIcon(displayName: string, paths: readonly string[]) {
  function Icon({ className, ...props }: SvgIconProps) {
    return (
      <SvgIcon
        fontSize="inherit"
        fill="none"
        stroke="currentColor"
        strokeWidth={1.75}
        strokeLinecap="round"
        strokeLinejoin="round"
        {...props}
        // The open-stroke rule lives on `cb-icon`: a caller's class adds to it and never replaces it.
        className={className ? `cb-icon ${className}` : 'cb-icon'}
      >
        {paths.map((d) => (
          <path key={d} d={d} />
        ))}
      </SvgIcon>
    );
  }
  Icon.displayName = displayName;
  return Icon;
}

export const EditIcon = createIcon('EditIcon', [
  'M21.174 6.812a1 1 0 0 0-3.986-3.987L3.842 16.174a2 2 0 0 0-.5.83l-1.321 4.352a.5.5 0 0 0 .623.622l4.353-1.32a2 2 0 0 0 .83-.497z',
  'm15 5 4 4',
]);
export const ArrowUpIcon = createIcon('ArrowUpIcon', ['m5 12 7-7 7 7', 'M12 19V5']);
export const ArrowDownIcon = createIcon('ArrowDownIcon', ['M12 5v14', 'm19 12-7 7-7-7']);
export const ExpandMoreIcon = createIcon('ExpandMoreIcon', ['m6 9 6 6 6-6']);
export const ExpandLessIcon = createIcon('ExpandLessIcon', ['m18 15-6-6-6 6']);
export const AddIcon = createIcon('AddIcon', ['M5 12h14', 'M12 5v14']);
export const CloseIcon = createIcon('CloseIcon', ['M18 6 6 18', 'm6 6 12 12']);
export const CheckIcon = createIcon('CheckIcon', ['M20 6 9 17l-5-5']);
export const MoveIcon = createIcon('MoveIcon', [
  'M2 9V5a2 2 0 0 1 2-2h3.9a2 2 0 0 1 1.69.9l.81 1.2a2 2 0 0 0 1.67.9H20a2 2 0 0 1 2 2v10a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2v-1',
  'M2 13h10',
  'm9 16 3-3-3-3',
]);
export const ArrowBackIcon = createIcon('ArrowBackIcon', ['m12 19-7-7 7-7', 'M19 12H5']);
export const DownloadIcon = createIcon('DownloadIcon', [
  'M12 15V3',
  'M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4',
  'm7 10 5 5 5-5',
]);
export const LinkIcon = createIcon('LinkIcon', [
  'M9 17H7A5 5 0 0 1 7 7h2',
  'M15 7h2a5 5 0 1 1 0 10h-2',
  'M8 12h8',
]);
export const SendIcon = createIcon('SendIcon', [
  'M3.714 3.048a.498.498 0 0 0-.683.627l2.843 7.627a2 2 0 0 1 0 1.396l-2.842 7.627a.498.498 0 0 0 .682.627l18-8.5a.5.5 0 0 0 0-.904z',
  'M6 12h16',
]);
export const PauseIcon = createIcon('PauseIcon', [
  'M15 3h3a1 1 0 0 1 1 1v16a1 1 0 0 1-1 1h-3a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1z',
  'M6 3h3a1 1 0 0 1 1 1v16a1 1 0 0 1-1 1H6a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1z',
]);
export const InfoIcon = createIcon('InfoIcon', [
  'M12 2a10 10 0 1 0 0 20 10 10 0 0 0 0-20z',
  'M12 16v-4',
  'M12 8h.01',
]);
export const CheckCircleIcon = createIcon('CheckCircleIcon', [
  'M12 2a10 10 0 1 0 0 20 10 10 0 0 0 0-20z',
  'm16 9-5.5 5.5L8 12',
]);
export const WarningIcon = createIcon('WarningIcon', [
  'm21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3',
  'M12 9v4',
  'M12 17h.01',
]);
export const ErrorIcon = createIcon('ErrorIcon', [
  'M12 2a10 10 0 1 0 0 20 10 10 0 0 0 0-20z',
  'M12 8v4',
  'M12 16h.01',
]);
export const PlayIcon = createIcon('PlayIcon', [
  'M5 5a2 2 0 0 1 3.008-1.728l11.997 6.998a2 2 0 0 1 .003 3.458l-12 7A2 2 0 0 1 5 19z',
]);
export const ChevronRightIcon = createIcon('ChevronRightIcon', ['m9 18 6-6-6-6']);
export const MessageIcon = createIcon('MessageIcon', [
  'M22 17a2 2 0 0 1-2 2H6.828a2 2 0 0 0-1.414.586l-2.202 2.202A.71.71 0 0 1 2 21.286V5a2 2 0 0 1 2-2h16a2 2 0 0 1 2 2z',
]);
export const FileTextIcon = createIcon('FileTextIcon', [
  'M6 22a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h8a2.4 2.4 0 0 1 1.704.706l3.588 3.588A2.4 2.4 0 0 1 20 8v12a2 2 0 0 1-2 2z',
  'M14 2v5a1 1 0 0 0 1 1h5',
  'M10 9H8',
  'M16 13H8',
  'M16 17H8',
]);
export const RefreshIcon = createIcon('RefreshIcon', [
  'M3 12a9 9 0 0 1 9-9 9.75 9.75 0 0 1 6.74 2.74L21 8',
  'M21 3v5h-5',
  'M21 12a9 9 0 0 1-9 9 9.75 9.75 0 0 1-6.74-2.74L3 16',
  'M8 16H3v5',
]);
