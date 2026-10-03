/** Global header for pages that have no top bar of their own (the workspace brings its own). */
import { Link as RouterLink } from 'react-router';
import { Chip, Link, Typography } from '@mui/material';

export function AppHeader() {
  return (
    <header className="app-header">
      <Link component={RouterLink} to="/" underline="none" className="brand">
        Caliburn
      </Link>
      <Typography variant="body2" color="text.secondary" className="app-tagline">
        職務訪談與職務說明書
      </Typography>
      <Chip label="新架構開發中" size="small" variant="outlined" />
    </header>
  );
}
