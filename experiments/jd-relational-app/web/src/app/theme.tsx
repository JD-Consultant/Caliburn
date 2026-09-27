'use client';
import { createTheme, ThemeProvider, CssBaseline } from '@mui/material';
import { useMemo, type ReactNode } from 'react';
import { ColorModeProvider, useColorMode, type ColorMode } from './color-mode';

const fontFamily = '"Segoe UI Variable Text", "Segoe UI", "Microsoft JhengHei", sans-serif';

function buildTheme(mode: ColorMode) {
  const light = mode === 'light';
  return createTheme({
    palette: {
      mode,
      primary: { main: light ? '#059669' : '#34d399' },
      background: { default: light ? '#f2f5f3' : '#0f1513', paper: light ? '#ffffff' : '#161e1b' },
      divider: light ? '#dee6e2' : '#28322d',
      text: { primary: light ? '#161d1a' : '#e8efec', secondary: light ? '#54615c' : '#9db2aa' },
    },
    typography: {
      fontFamily,
      button: { textTransform: 'none', fontWeight: 600 },
      h5: { fontWeight: 700 },
      h6: { fontWeight: 700 },
      subtitle1: { fontWeight: 700 },
      subtitle2: { fontWeight: 700, letterSpacing: 0.2 },
    },
    shape: { borderRadius: 12 },
    components: {
      MuiTextField: { defaultProps: { variant: 'outlined', size: 'small', fullWidth: true } },
      MuiButton: { defaultProps: { disableElevation: true } },
      MuiAppBar: { styleOverrides: { root: { backgroundImage: 'none' } } },
      MuiPaper: { styleOverrides: { root: { backgroundImage: 'none' } } },
      // A stronger left accent bar keeps error/warning/info/success visually
      // unmistakable at a glance, on top of MUI's existing tint + icon —
      // the frontend must never blur the backend's error-severity taxonomy.
      MuiAlert: {
        styleOverrides: {
          root: { alignItems: 'flex-start' },
          colorError: ({ theme }) => ({ borderLeft: `4px solid ${theme.palette.error.main}` }),
          colorWarning: ({ theme }) => ({ borderLeft: `4px solid ${theme.palette.warning.main}` }),
          colorInfo: ({ theme }) => ({ borderLeft: `4px solid ${theme.palette.info.main}` }),
          colorSuccess: ({ theme }) => ({ borderLeft: `4px solid ${theme.palette.success.main}` }),
        },
      },
      MuiCssBaseline: {
        styleOverrides: {
          html: { colorScheme: mode },
          '::-webkit-scrollbar': { width: 10, height: 10 },
          '::-webkit-scrollbar-thumb': { backgroundColor: light ? '#c7d2cd' : '#33403a', borderRadius: 8 },
          '::-webkit-scrollbar-track': { backgroundColor: 'transparent' },
        },
      },
    },
  });
}

function ThemedApp({ children }: { children: ReactNode }) {
  const { mode } = useColorMode();
  const theme = useMemo(() => buildTheme(mode), [mode]);
  return <ThemeProvider theme={theme}><CssBaseline />{children}</ThemeProvider>;
}

export default function Theme({ children }: { children: ReactNode }) {
  return <ColorModeProvider><ThemedApp>{children}</ThemedApp></ColorModeProvider>;
}
