import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { BrowserRouter } from 'react-router';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { CssBaseline, StyledEngineProvider, ThemeProvider } from '@mui/material';
// Self-hosted variable fonts (SIL OFL): no request leaves the machine, and weights 500/600 exist on
// every OS. Browsers fetch only the unicode-range slices a page actually uses.
import '@fontsource-variable/inter/wght.css';
import '@fontsource-variable/noto-sans-tc/wght.css';
import { App } from './app/App';
import { theme } from './app/theme';
import './app/styles.css';

const root = document.getElementById('root');
if (!root) throw new Error('找不到應用程式掛載位置。');
const queryClient = new QueryClient({
  defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
});
createRoot(root).render(
  <StrictMode>
    {/* MUI styles go into a CSS layer, so the plain rules in styles.css always win over them. */}
    <StyledEngineProvider enableCssLayer>
      <ThemeProvider theme={theme}>
        <CssBaseline />
        <QueryClientProvider client={queryClient}>
          <BrowserRouter>
            <App />
          </BrowserRouter>
        </QueryClientProvider>
      </ThemeProvider>
    </StyledEngineProvider>
  </StrictMode>,
);
