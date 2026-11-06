import { Link, Typography } from '@mui/material';
import { Link as RouterLink, Outlet } from 'react-router';

export function AppShell() {
  return (
    <>
      <a href="#main-content" className="skip-link">
        跳到主要內容
      </a>
      <header className="app-header">
        <Link component={RouterLink} to="/workspaces" underline="none" className="brand">
          Caliburn
        </Link>
        <Typography variant="body2" color="text.secondary" className="app-tagline">
          職務訪談與職務說明書
        </Typography>
      </header>
      <main id="main-content" tabIndex={-1}>
        <Outlet />
      </main>
    </>
  );
}
