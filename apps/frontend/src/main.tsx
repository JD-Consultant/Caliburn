import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { BrowserRouter } from 'react-router';
import { QueryClientProvider } from '@tanstack/react-query';
import { CssBaseline, StyledEngineProvider, ThemeProvider } from '@mui/material';
import '@fontsource-variable/inter/wght.css';
import '@fontsource-variable/noto-sans-tc/wght.css';
import { App } from './app/App';
import { theme } from './app/theme';
import { createQueryClient } from './app/query-client';
import './app/styles.css';
import './app/legacy.css';
import './app/workspace-layout.css';

const root = document.getElementById('root');
if (!root) throw new Error('找不到應用程式入口。');
createRoot(root).render(
  <StrictMode>
    <StyledEngineProvider enableCssLayer>
      <ThemeProvider theme={theme}>
        <CssBaseline />
        <QueryClientProvider client={createQueryClient()}>
          <BrowserRouter>
            <App />
          </BrowserRouter>
        </QueryClientProvider>
      </ThemeProvider>
    </StyledEngineProvider>
  </StrictMode>,
);
