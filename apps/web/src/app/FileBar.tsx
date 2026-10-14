/** Top bar of one job file: identity, the way back, and the server-verified state of the current Turn. */
import { Link as RouterLink } from 'react-router';
import { Chip, IconButton, Link } from '@mui/material';
import { ArrowBackIcon } from '../shared/ui/icons';
import type { ConsultantTurn, JobFile } from '../shared/api/generated/http/types.gen';

import { describeTurnBadge } from '../features/interview/turn-summary';
import type { TurnBadge } from '../features/interview/turn-summary';
import { PublishedMemoryViewer } from '../features/memory/PublishedMemoryViewer';

const chipColor: Record<TurnBadge['tone'], 'info' | 'warning' | 'success' | 'error' | 'default'> = {
  info: 'info',
  warning: 'warning',
  success: 'success',
  error: 'error',
  neutral: 'default',
};

function formatUsageDuration(totalSeconds: number): string {
  const seconds = Math.max(0, Math.floor(totalSeconds));
  const hours = Math.floor(seconds / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  const remaining = seconds % 60;
  const pad = (value: number) => String(value).padStart(2, '0');
  return hours > 0
    ? `${hours}:${pad(minutes)}:${pad(remaining)}`
    : `${pad(minutes)}:${pad(remaining)}`;
}

export function FileBar({
  file,
  turn,
  activeUsageSeconds,
}: {
  file: JobFile;
  turn: ConsultantTurn | null;
  activeUsageSeconds: number;
}) {
  const badge = describeTurnBadge(turn);
  return (
    <header className="file-bar">
      <IconButton
        component={RouterLink}
        to="/"
        aria-label="回到職務檔案清單"
        title="回到職務檔案清單"
        size="small"
      >
        <ArrowBackIcon />
      </IconButton>
      <Link component={RouterLink} to="/" underline="none" className="brand" aria-label="Caliburn">
        Caliburn
      </Link>
      <div className="file-bar-title">
        <h1>{file.display_name}</h1>
        <span className="file-bar-meta">受訪員工：{file.employee_name}</span>
      </div>
      <span className="file-bar-usage-timer" aria-label="累計使用時間" title="累計使用時間">
        已使用 {formatUsageDuration(activeUsageSeconds)}
      </span>
      <PublishedMemoryViewer jobFileId={file.job_file_id} />
      {badge && (
        <Chip size="small" variant="outlined" color={chipColor[badge.tone]} label={badge.label} />
      )}
    </header>
  );
}
