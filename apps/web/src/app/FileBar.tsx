/** Top bar of one job file: identity, the way back, and the server-verified state of the current Turn. */
import { Link as RouterLink } from 'react-router';
import { Chip, IconButton, Link } from '@mui/material';
import { ArrowBackIcon } from '../shared/ui/icons';
import type { ConsultantTurn } from '../shared/api/generated/consultant-turn';
import type { JobFile } from '../shared/api/generated/job-file-list';
import { describeTurnBadge } from '../features/interview/turn-summary';
import type { TurnBadge } from '../features/interview/turn-summary';

const chipColor: Record<TurnBadge['tone'], 'info' | 'warning' | 'success' | 'error' | 'default'> = {
  info: 'info',
  warning: 'warning',
  success: 'success',
  error: 'error',
  neutral: 'default',
};

export function FileBar({ file, turn }: { file: JobFile; turn: ConsultantTurn | null }) {
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
      {badge && (
        <Chip size="small" variant="outlined" color={chipColor[badge.tone]} label={badge.label} />
      )}
    </header>
  );
}
